"""Music routing uses native cues without aliasing the resource namespaces."""
import importlib.util
from io import BytesIO
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
import wave

from shs_runtime.audio import MusicCue, music_cue
from shs_runtime.content import ContentError
from shs_runtime.runtime import Session
from test_runtime import Resources, host_call
from test_vm import program


class MusicCueTests(unittest.TestCase):
    def test_shared_track_cues_and_unmapped_resources(self):
        self.assertEqual(music_cue(8213), MusicCue(8212, 4000))
        self.assertEqual(music_cue(8214), MusicCue(8212, 39200))
        for resource_id in (16, 8002, 8201, 8203, 8222, 8232, 26002, 28202):
            with self.subTest(resource_id=resource_id):
                self.assertEqual(music_cue(resource_id), MusicCue(resource_id, 0))


@unittest.skipUnless(importlib.util.find_spec('pygame'), 'desktop extra is not installed')
class MusicPlaybackTests(unittest.TestCase):
    def make_ui(self, service=80, music=8202):
        from shs_runtime.desktop import Desktop
        os.environ['SDL_VIDEODRIVER'] = os.environ['SDL_AUDIODRIVER'] = 'dummy'
        import pygame
        self.addCleanup(pygame.quit)
        r = Resources(program(*host_call(service, *([music] if service == 79 else [music, 0])), 0x33))
        r.read_asset = Mock(return_value=b'authored music bytes')
        ui = Desktop(Session(r), audio=False)
        ui.audio = True
        return ui, r

    def test_both_music_services_load_and_seek_without_changing_vm_or_save_ids(self):
        # Expected destinations and offsets recovered from the Java player,
        # including redirects beyond the five IDs in the original report.
        cues = [(8202, 8201, 2.8), (8204, 8203, .72), (8206, 8205, 28.28),
                (8208, 8207, 3.27), (8211, 8210, 6.), (8213, 8212, 4.),
                (8214, 8212, 39.2), (8216, 8215, 1.32), (8218, 8217, 1.92),
                (8220, 8219, 10.6), (8225, 8224, 29.2), (8221, 8221, 0.),
                (26002, 26002, 0.)]
        for service in (79, 80):
            for requested, source, seconds in cues:
                if service == 79 and requested >= 26000:
                    continue  # Service 79 treats episode resources as SFX.
                with self.subTest(service=service, requested=requested):
                    ui, r = self.make_ui(service, requested)
                    saved = ui.session.snapshot()
                    with patch('pygame.mixer.music') as music:
                        ui._sync_audio()
                        music.stop.assert_called_once_with()
                        music.load.assert_called_once()
                        self.assertEqual(music.load.call_args.args[0].getvalue(), b'authored music bytes')
                        music.play.assert_called_once_with(start=seconds)
                        r.read_asset.assert_called_once_with(source)
                        self.assertEqual(ui.session.snapshot(), saved)
                        self.assertEqual(ui.session.engine.music_id, requested)
                        ui._sync_audio()  # Rendering another frame must not restart it.
                        music.play.assert_called_once()

    def test_two_cues_in_one_track_restart_and_muting_preserves_the_request(self):
        ui, r = self.make_ui(music=8213)
        with patch('pygame.mixer.music') as music:
            ui._sync_audio()
            ui.session.engine.music_id = 8214
            ui._sync_audio()
            self.assertEqual([call.kwargs['start'] for call in music.play.call_args_list], [4., 39.2])
            self.assertEqual([call.args for call in r.read_asset.call_args_list], [(8212,), (8212,)])
            saved = ui.session.snapshot()
            ui.music_enabled = False
            ui._sync_audio()
            self.assertEqual(music.play.call_count, 2)
            self.assertEqual(music.stop.call_count, 3)
            ui.music_enabled = True
            ui._sync_audio()
            self.assertEqual(music.play.call_args.kwargs, {'start': 39.2})
            self.assertEqual(ui.session.snapshot(), saved)

    def test_pause_menu_resumes_the_same_stream_without_reloading_or_replaying_vm(self):
        import pygame
        for controls in ('buttons', 'escape'):
            with self.subTest(controls=controls):
                ui, resources = self.make_ui()
                saved = ui.session.snapshot()
                with patch('pygame.mixer.music') as music:
                    ui._sync_audio()
                    if controls == 'buttons':
                        ui.command(('menu',))
                    else:
                        ui.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
                    ui._sync_audio()
                    ui.tick(5000)
                    music.pause.assert_called_once_with()
                    music.unpause.assert_not_called()
                    if controls == 'buttons':
                        ui.command(('resume',))
                    else:
                        ui.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
                    ui._sync_audio()
                    ui._sync_audio()
                    music.unpause.assert_called_once_with()
                    music.load.assert_called_once()
                    music.play.assert_called_once_with(start=2.8)
                    resources.read_asset.assert_called_once_with(8201)
                    self.assertEqual(ui.session.snapshot(), saved)

    def test_focus_and_menu_holds_must_both_clear_before_music_resumes(self):
        import pygame
        ui, _ = self.make_ui()
        with patch('pygame.mixer.music') as music:
            ui._sync_audio()
            ui.command(('menu',))
            ui.handle_event(pygame.event.Event(pygame.WINDOWFOCUSLOST))
            ui.handle_event(pygame.event.Event(pygame.WINDOWFOCUSGAINED))
            ui._sync_audio()
            music.pause.assert_called_once_with()
            music.unpause.assert_not_called()
            ui.handle_event(pygame.event.Event(pygame.WINDOWFOCUSLOST))
            ui.command(('resume',))
            ui._sync_audio()
            music.unpause.assert_not_called()
            ui.handle_event(pygame.event.Event(pygame.WINDOWFOCUSGAINED))
            ui._sync_audio()
            music.unpause.assert_called_once_with()
            music.play.assert_called_once()

    def test_muting_stopping_and_switching_cues_while_paused_do_not_resume_stale_music(self):
        for change in ('mute', 'stop', 'cue'):
            with self.subTest(change=change):
                ui, _ = self.make_ui(music=8213)
                with patch('pygame.mixer.music') as music:
                    ui._sync_audio()
                    ui.command(('menu',))
                    ui._sync_audio()
                    if change == 'mute':
                        ui.music_enabled = False
                    else:
                        ui.session.engine.music_id = -1 if change == 'stop' else 8214
                    ui._sync_audio()
                    ui.command(('resume',))
                    ui._sync_audio()
                    if change == 'cue':
                        self.assertEqual([call.kwargs['start'] for call in music.play.call_args_list],
                                         [4., 39.2])
                        self.assertEqual(music.pause.call_count, 2)
                        music.unpause.assert_called_once_with()
                    else:
                        music.play.assert_called_once_with(start=4.)
                        music.unpause.assert_not_called()

    def test_live_main_menu_resume_keeps_the_stream_and_restart_loads_a_new_one(self):
        from shs_runtime.application import Application
        ui, resources = self.make_ui()
        resources.record['id'] = 'authored-episode'
        # Exercise application lifecycle without original menu art or writes.
        app = Application.__new__(Application)
        app.game, app.selected, app.audio, app.active = ui, resources.record['id'], True, True
        app.window = ui.window
        app.state = Mock(music=True, sound=True)
        app.state.title.return_value = resources.record['titles'][0]
        app.show, app.refresh_saves = Mock(), Mock()
        saved = ui.session.snapshot()
        with patch('pygame.mixer.music') as music, patch('pygame.mixer.stop'):
            ui._sync_audio()
            app.return_to_menu()
            music.pause.assert_called_once_with()
            app.start()
            ui._sync_audio()
            self.assertIs(app.game, ui)
            music.unpause.assert_called_once_with()
            music.load.assert_called_once()
            music.play.assert_called_once_with(start=2.8)
            self.assertEqual(ui.session.snapshot(), saved)
            app.return_to_menu()
            app.state.session.return_value = Session(resources)
            app.start(resume=False)
            app.game._sync_audio()
            self.assertIsNot(app.game, ui)
            self.assertEqual(music.load.call_count, 2)
            self.assertEqual(music.play.call_count, 2)

    def test_real_mixer_freezes_and_resumes_authored_music_position(self):
        import pygame
        ui, resources = self.make_ui(music=8201)
        sample = BytesIO()
        with wave.open(sample, 'wb') as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(8000)
            stream.writeframes(b'\0\0' * 16000)
        resources.read_asset.return_value = sample.getvalue()
        pygame.mixer.init(frequency=8000, size=-16, channels=1, buffer=128)
        ui._sync_audio()
        self.assertTrue(pygame.mixer.music.get_busy())
        pygame.time.wait(50)
        ui.command(('menu',))
        ui._sync_audio()
        self.assertFalse(pygame.mixer.music.get_busy())
        position = pygame.mixer.music.get_pos()
        pygame.time.wait(80)
        self.assertEqual(pygame.mixer.music.get_pos(), position)
        ui.command(('resume',))
        ui._sync_audio()
        self.assertTrue(pygame.mixer.music.get_busy())
        pygame.time.wait(50)
        self.assertGreater(pygame.mixer.music.get_pos(), position)
        resources.read_asset.assert_called_once_with(8201)
        pygame.mixer.music.stop()  # A finished/stopped stream must not be restarted by Resume.
        ui.command(('menu',))
        ui.command(('resume',))
        ui._sync_audio()
        self.assertFalse(pygame.mixer.music.get_busy())

    def test_unknown_missing_music_warns_and_sound_effect_ids_stay_exact(self):
        ui, r = self.make_ui(music=8222)
        r.read_asset.side_effect = ContentError('APK resource 8222 is missing')
        with patch('pygame.mixer.music') as music, self.assertLogs(level='WARNING') as logs:
            ui._sync_audio()
            ui._sync_audio()
            ui.command(('menu',))
            ui.command(('resume',))
            music.play.assert_not_called()
            music.unpause.assert_not_called()
            r.read_asset.assert_called_once_with(8222)
        self.assertEqual(len(logs.output), 1)
        self.assertIn('Music 8222 cannot be played', logs.output[0])
        r.read_asset.reset_mock(); r.read_asset.side_effect = None
        # The episode SFX bank must never acquire music-cue redirects.
        ui.session.engine.sound_id = 28202
        ui.session.engine.sound_ids = [28202]
        ui.session.engine.sound_serial += 1
        with patch('pygame.mixer.Sound') as sound:
            ui._sync_audio()
            r.read_asset.assert_called_once_with(28202)
            sound.return_value.play.assert_called_once_with()

    @unittest.skipUnless(Path('.shs-library/library.json').is_file(), 'user library is not present')
    def test_original_apk_contains_and_plays_every_redirected_track(self):
        import pygame
        from shs_runtime.content import ContentLibrary
        ui, _ = self.make_ui()
        pygame.mixer.init()
        with ContentLibrary(Path('.shs-library')) as lib:
            ui.session.resources = lib.open_episode('Football Star')
            for requested in (8202, 8204, 8206, 8208, 8211, 8213, 8214, 8216, 8218, 8220, 8225):
                with self.subTest(requested=requested), self.assertNoLogs(level='WARNING'):
                    cue = music_cue(requested)
                    # The APK has no standalone alias file. Keep generic
                    # resource reads exact even after implementing playback.
                    with self.assertRaises(ContentError):
                        lib.read_asset(requested)
                    self.assertIn(cue.asset_id, lib.base_members)
                    ui.session.engine.music_id = requested
                    ui._sync_audio()
                    self.assertTrue(pygame.mixer.music.get_busy())
            pygame.mixer.music.stop()
