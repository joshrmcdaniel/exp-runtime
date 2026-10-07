"""Release metadata, opt-out, launch lifecycle and both host handoffs."""
import base64
from concurrent.futures import Future
from io import BytesIO
import json
import importlib.util
import os
from pathlib import Path
import tempfile
from threading import Event
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from exp_runtime.app_info import PROJECT_URL
from exp_runtime.settings import AppSettings
from exp_runtime.updates import (MAX_RESPONSE, RELEASE_API, UPDATE_MESSAGE, UpdateCheck,
                                  fetch_release, newer_release)


def release(tag='v0.5.0', **fields):
    return json.dumps(dict(tag_name=tag, draft=False, prerelease=False, **fields))


class UpdateTests(unittest.TestCase):
    def test_versions_are_numeric_and_only_new_stable_releases_are_offered(self):
        for current, latest, expected in (('0.4.1', 'v0.4.2', True), ('0.9.0', 'v0.10.0', True),
                ('0.10.0', 'v0.9.0', False), ('0.5.0', 'v0.5.0', False), ('1.0.0', 'v0.99.0', False),
                ('0.5.0rc1', 'v0.5.0', True), ('0.5.0.dev2', 'v0.5.0', True),
                ('0.5.0+local', 'v0.5.0', False), ('0.5.0.post1', 'v0.5.0', False),
                ('0.4.1', '0.5.0', True), ('development', 'v0.5.0', False),
                ('0.4.1', 'nightly', False), ('0.4.1', 'v0.5.0rc1', False)):
            with self.subTest(current=current, latest=latest):
                self.assertEqual(newer_release(release(latest), current) is not None, expected)
        for field in ('draft', 'prerelease'):
            data = json.loads(release())
            data[field] = True
            self.assertIsNone(newer_release(json.dumps(data), '0.4.1'))
            data[field] = 0
            self.assertIsNone(newer_release(json.dumps(data), '0.4.1'))

    def test_untrusted_metadata_cannot_change_the_download_destination(self):
        update = newer_release(release(html_url='file:///tmp/evil', body='Untrusted message'), '0.4.1')
        self.assertEqual(update.url, PROJECT_URL + '/releases/tag/v0.5.0')
        for payload in (None, 'null', '[]', '{}', '<html>offline</html>', b'\xff', ' ' * (MAX_RESPONSE + 1),
                        release('../../elsewhere'), release('v01.2.3'), release('v1.2.3/elsewhere')):
            self.assertIsNone(newer_release(payload, '0.4.1'))

    def test_check_runs_once_and_cancellation_ignores_late_results(self):
        future = Future()
        fetcher = Mock(return_value=future)
        check = UpdateCheck(fetcher, current='0.4.1')
        check.start(); check.start()
        fetcher.assert_called_once_with()
        self.assertIsNone(check.poll())
        future.set_result(release())
        self.assertEqual(check.poll().version, '0.5.0')
        check.dismiss(); check.start()
        self.assertIsNone(check.poll())
        fetcher.assert_called_once_with()
        late = Future(); late.set_running_or_notify_cancel()
        check = UpdateCheck(lambda: late, current='0.4.1')
        check.start(); check.cancel()
        late.set_result(release())
        self.assertIsNone(check.poll())
        skipped = Mock()
        UpdateCheck(skipped, current='development').start()
        skipped.assert_not_called()

    def test_transport_is_bounded_and_network_errors_stay_silent(self):
        response = Mock(status=200)
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = release().encode()
        with patch('exp_runtime.updates._ssl_context', return_value='verified context'), \
                patch('exp_runtime.updates.urlopen', return_value=response) as request:
            self.assertEqual(fetch_release().result(timeout=2), release().encode())
            self.assertEqual(request.call_args.args[0].full_url, RELEASE_API)
            self.assertEqual(request.call_args.args[0].get_method(), 'GET')
            self.assertEqual(request.call_args.kwargs['context'], 'verified context')
            self.assertEqual(request.call_args.kwargs['timeout'], 8)
            response.read.assert_called_once_with(MAX_RESPONSE + 1)
            response.read.return_value = b'x' * (MAX_RESPONSE + 1)
            self.assertIsNone(fetch_release().result(timeout=2))
        for error in (URLError('offline'), TimeoutError(), HTTPError(RELEASE_API, 403, 'rate limited', {}, None),
                      HTTPError(RELEASE_API, 404, 'no releases', {}, None)):
            with patch('exp_runtime.updates._ssl_context', return_value=None), \
                    patch('exp_runtime.updates.urlopen', side_effect=error):
                self.assertIsNone(fetch_release().result(timeout=2))

    def test_cancelling_a_blocked_transport_does_not_wait_for_network(self):
        entered, finish, stopped = Event(), Event(), Event()
        def offline(*args, **kwargs):
            entered.set()
            finish.wait(5)
            stopped.set()
            raise URLError('offline')
        with patch('exp_runtime.updates._ssl_context', return_value=None), \
                patch('exp_runtime.updates.urlopen', side_effect=offline):
            future = fetch_release()
            try:
                self.assertTrue(entered.wait(2))
                self.assertTrue(future.cancel())
                self.assertFalse(stopped.is_set())
            finally:
                finish.set()
                self.assertTrue(stopped.wait(2))

    def test_preferences_default_on_persist_globally_and_do_not_reenable_when_damaged(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'preferences/settings.json'
            settings = AppSettings(path)
            self.assertTrue(settings.check_for_updates)
            self.assertFalse(path.exists())
            settings.set_update_check(False)
            self.assertFalse(AppSettings(path).check_for_updates)
            before = path.read_bytes()
            with patch.object(Path, 'replace', side_effect=OSError('read-only disk')):
                with self.assertRaises(OSError):
                    settings.set_update_check(True)
            self.assertFalse(settings.check_for_updates)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual([p.name for p in path.parent.iterdir()], ['settings.json'])
            path.write_text('{"version":1,"check_for_updates":"yes"}')
            with self.assertLogs(level='WARNING'):
                self.assertFalse(AppSettings(path).check_for_updates)


@unittest.skipUnless(importlib.util.find_spec('pygame'), 'desktop extra is not installed')
class ApplicationUpdateTests(unittest.TestCase):
    def setUp(self):
        os.environ['SDL_VIDEODRIVER'] = os.environ['SDL_AUDIODRIVER'] = 'dummy'
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        version = patch('exp_runtime.updates.runtime_version', return_value='0.4.1')
        version.start(); self.addCleanup(version.stop)
        self.future = Future()
        self.fetcher = Mock(return_value=self.future)

    def app(self):
        from exp_runtime.application import Application
        app = Application(audio=False, library_root=self.root / 'libraries',
                          settings_path=self.root / 'settings.json', update_fetcher=self.fetcher)
        self.addCleanup(app.close)
        return app

    def test_launch_is_nonblocking_and_no_dismisses_once_without_opening_a_browser(self):
        app = self.app()
        self.assertFalse(app.busy)
        app.tick(50); app.render()
        self.assertIsNone(app.update_prompt)
        opener = app.url_opener = Mock()
        self.future.set_result(release())
        app.tick(0)
        with patch.object(app.renderer, 'label', wraps=app.renderer.label) as label:
            app.render()
            self.assertIn(UPDATE_MESSAGE, [call.args[0] for call in label.call_args_list])
        self.assertEqual([c for _, c in app.buttons], [('update_no',), ('update_yes',)])
        app.command(('choose_game', 'shs'))
        self.assertEqual(app.screen, 'games')  # Covered controls are inert.
        app.command(('update_no',))
        app.choose_game('shs'); app.tick(4000)
        app.show_game_chooser(); app.tick(4000)
        self.assertIsNone(app.update_prompt)
        opener.assert_not_called()
        self.fetcher.assert_called_once_with()

    def test_yes_opens_only_the_release_page_and_does_not_repeat_on_focus_return(self):
        app = self.app()
        opener = app.url_opener = Mock()
        self.future.set_result(release())
        app.tick(0); app.render()
        opener.assert_not_called()
        app.command(('update_yes',))
        opener.assert_called_once_with(PROJECT_URL + '/releases/tag/v0.5.0')
        app.active = False; app.tick(20)
        app.active = True; app.tick(20)
        self.assertIsNone(app.update_prompt)
        self.assertEqual(app.screen, 'games')

    def test_native_confirmation_uses_two_separate_button_regions_not_the_footer_art(self):
        from exp_runtime.ui_assets import Layout, LayoutBank, LayoutNode
        renderer = self.app().renderer
        # Authored footer: two art nodes followed by two hit regions. Native
        # node IDs are one-based; selecting the separator would stretch a
        # button across the whole footer and hide the other label.
        nodes = tuple(LayoutNode(bounds, (0, 0, 0, 0), kind, payload)
                      for bounds, kind, payload in (
                          ((0, 0, 302, 43), 1, (3, 0)),
                          ((0, 0, 302, 1), 1, (3, 1)),
                          ((15, 7, 93, 36), 6, ()),
                          ((209, 7, 287, 36), 6, ())))
        renderer.library = object()
        renderer.bank = LayoutBank(0, 0, 0, (), (Layout(1, 1, ()),) * 39 + (Layout(302, 43, nodes),))
        renderer.strings = {25: 'Yes', 26: 'No'}
        with patch.object(renderer, 'layout'), patch.object(renderer, 'label') as label:
            renderer.confirmation(UPDATE_MESSAGE)
        no, yes = renderer.buttons
        self.assertEqual(no[1], ('update_no',))
        self.assertEqual(yes[1], ('update_yes',))
        self.assertEqual(tuple(no[0]), (24, 288, 78, 29))
        self.assertEqual(tuple(yes[0]), (218, 288, 78, 29))
        self.assertFalse(no[0].colliderect(yes[0]))
        self.assertEqual([call.args[0] for call in label.call_args_list][-2:], ['No', 'Yes'])

    def test_opt_out_survives_game_switch_and_restart_and_disabling_ignores_inflight_result(self):
        app = self.app()
        self.future.set_running_or_notify_cancel()
        app.command(('options',)); app.tick(200); app.render()
        self.assertIn(('toggle_updates',), [command for _, command in app.buttons])
        app.command(('toggle_updates',))
        self.future.set_result(release())
        app.command(('back',)); app.tick(200)
        self.assertIsNone(app.update_prompt)
        for game in ('shs', 'cod'):
            app.choose_game(game)
            self.assertFalse(app.settings.check_for_updates)
        app.close()
        self.fetcher.reset_mock()
        restarted = self.app()
        restarted.tick(0)
        self.fetcher.assert_not_called()
        self.assertFalse(restarted.settings.check_for_updates)

    def test_reenable_starts_only_one_check_if_launch_was_disabled(self):
        AppSettings(self.root / 'settings.json').set_update_check(False)
        app = self.app()
        self.fetcher.assert_not_called()
        app.command(('toggle_updates',))
        self.fetcher.assert_called_once_with()
        app.command(('toggle_updates',)); app.command(('toggle_updates',))
        self.fetcher.assert_called_once_with()

    def test_alerts_imports_and_active_story_defer_the_prompt(self):
        app = self.app()
        app.message = 'An import warning'
        self.future.set_result(release())
        app.tick(0)
        self.assertIsNone(app.update_prompt)
        app.message = ''
        job = Future(); app.job = job
        app.tick(0)
        self.assertIsNone(app.update_prompt)
        app.job = None
        app.screen = 'game'
        app.game = SimpleNamespace(tick=Mock(), session=SimpleNamespace(episode_exited=False))
        app.tick(50)
        app.game.tick.assert_called_once_with(50)
        self.assertIsNone(app.update_prompt)
        app.game = None; app.screen = 'games'; app.tick(0)
        self.assertIsNotNone(app.update_prompt)

    def test_modal_cancels_old_gestures_and_enter_defaults_to_no(self):
        import pygame
        app = self.app()
        app.render()
        old = app.buttons[0][0].center
        position = tuple(round(n * app.viewport.width / 320) for n in old)
        app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=position))
        self.assertIsNotNone(app.pressed)
        self.future.set_result(release()); app.tick(0); app.render()
        self.assertIsNone(app.pressed)
        yes = next(r for r, command in app.buttons if command == ('update_yes',)).center
        position = tuple(round(n * app.viewport.width / 320) for n in yes)
        app.url_opener = Mock()
        app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=position))
        app.url_opener.assert_not_called()
        app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        self.assertIsNone(app.update_prompt)
        app.url_opener.assert_not_called()


class NativeUpdateTests(unittest.TestCase):
    def test_ios_fetch_is_one_shot_and_results_use_shared_modal_and_browser_handoff(self):
        from exp_runtime import graphics
        from exp_runtime.app_icon import icon_surface
        from exp_runtime.platforms.drawing import Backend
        from exp_runtime.platforms.ios import Host
        from PIL import Image, ImageDraw, ImageFont
        def font(request):
            face = ImageFont.load_default(size=request['size'])
            width, height = max(1, round(face.getlength(request['text']))), request['size'] + 5
            result = dict(width=width, height=height)
            if not request.get('measure'):
                image = Image.new('RGBA', (width, height))
                ImageDraw.Draw(image).text((0, 0), request['text'], font=face, fill=tuple(request['color']))
                stream = BytesIO(); image.save(stream, format='PNG')
                result['png'] = base64.b64encode(stream.getvalue()).decode('ascii')
            return result
        with tempfile.TemporaryDirectory() as temporary, \
                patch('exp_runtime.updates.runtime_version', return_value='0.4.1'):
            root = Path(temporary)
            icon = root / 'authored-icon.png'; Image.new('RGBA', (2, 2), 'green').save(icon)
            backend = Backend(font, icon)
            previous = graphics.install(backend)
            self.addCleanup(graphics.install, previous)
            icon_surface.cache_clear()
            self.addCleanup(icon_surface.cache_clear)
            host = Host(root, backend=backend, library_root=root / 'libraries')
            self.addCleanup(host.app.close)
            first = host.request({'operation': 'frame'})
            self.assertEqual(first['update_request']['url'], RELEASE_API)
            self.assertIsNone(host.request({'operation': 'frame'})['update_request'])
            shown = host.request(dict(operation='update_result', payload=release()))
            self.assertIsNotNone(host.app.update_prompt)
            generation = shown['generation']
            rect = next(rect for rect, cmd in host.app.buttons if cmd == ('update_yes',))
            point = [int(v * 1.5) for v in rect.center]
            stale = [dict(kind=kind, point=point, generation=generation - 1) for kind in ('down', 'up')]
            self.assertIsNone(host.request(dict(operation='frame', events=stale))['open_url'])
            events = [dict(kind=kind, point=point, generation=generation) for kind in ('down', 'up')]
            accepted = host.request(dict(operation='frame', events=events))
            self.assertEqual(accepted['open_url'], PROJECT_URL + '/releases/tag/v0.5.0')
            self.assertIsNone(host.request({'operation': 'frame'})['open_url'])
            self.assertIsNone(host.app.update_prompt)
