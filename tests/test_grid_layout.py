import copy
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest

from exp_runtime.shs.grid_layout import heading_lines, prompt_position, tutorial_box
from exp_runtime.runtime import SaveError, Session
from test_word_grid import play_phase, resources, tutorial_resources


class GridLayoutTests(unittest.TestCase):
    def test_tutorial_panels_follow_position_and_measured_paragraph_height(self):
        top = tutorial_box(128, 0)
        center = tutorial_box(128, 1)
        bottom = tutorial_box(128, 2)
        self.assertEqual((top.x, top.top, top.body_y, top.bottom), (7, 11, 33, 196))
        self.assertEqual((center.top, center.bottom), (147, 332))
        self.assertEqual((bottom.top, bottom.bottom), (283, 468))
        longer = tutorial_box(192, 0)
        self.assertEqual(longer.top, top.top)
        self.assertEqual(longer.bottom - top.bottom, 64)
        zooming = tutorial_box(128, 1, .5)
        self.assertEqual(zooming.x, 83.5)
        self.assertAlmostEqual((zooming.top + zooming.bottom + 1) / 2, 240)

    def test_native_heading_and_bottom_word_positions(self):
        g = SimpleNamespace(phase=1, phase_ms=0, problem=SimpleNamespace(heading='One\nTwo\nThree'))
        self.assertEqual(heading_lines(g), (('One', 110, 60, 1.), ('Two', 104, 80, 1.), ('Three', 95, 100, 1.)))
        self.assertEqual(prompt_position(1, 0, 100, 2), (47, 377, .65))
        self.assertEqual(prompt_position(1, 1, 100, 2), (70, 402, .65))
        g.phase, g.phase_ms = 2, 1600
        moving = heading_lines(g)
        self.assertGreater(moving[0][1], 110)
        g.phase_ms = 0
        self.assertEqual(heading_lines(g)[0][1], 110)
        g.phase = 6
        self.assertEqual(heading_lines(g), ())

    def test_decorative_clocks_banner_and_transition_survive_save_without_random_draws(self):
        r = tutorial_resources(); s = Session(r); s.advance()
        held, random = s.vm.snapshot(), s.engine.random.state
        for _ in range(5): s.tick(250)
        g = s.engine.word_grid
        self.assertEqual((g.visual_ms, g.banner.kind, g.banner.age_ms), (1250, 'ready', 250))
        saved = json.loads(json.dumps(s.snapshot()))
        restored = Session.from_snapshot(r, saved)
        for _ in range(20):
            s.tick(16); restored.tick(16)
            self.assertEqual(s.snapshot(), restored.snapshot())
        self.assertEqual(s.vm.snapshot(), held)
        self.assertEqual(s.engine.random.state, random)
        play_phase(s)
        s.answer()
        # Successful tutorial pages suppress ordinary success text.
        self.assertIsNone(g.banner)
        for _ in range(5): s.tick(250)
        self.assertEqual(g.phase, 4)
        self.assertEqual(g.transition.problem.tutorial_text, 'Touch to continue.')
        self.assertEqual(g.problem.tutorial_text, 'Trace the word.')
        saved = json.loads(json.dumps(s.snapshot()))
        restored = Session.from_snapshot(r, saved)
        self.assertEqual(restored.snapshot(), s.snapshot())
        for _ in range(40):
            s.tick(50); restored.tick(50)
            self.assertEqual(s.snapshot(), restored.snapshot())
        bad = copy.deepcopy(saved)
        bad['engine']['word_grid']['transition']['board'] = []
        with self.assertRaises(SaveError): Session.from_snapshot(r, bad)

    def test_version_six_grid_migration_keeps_board_vm_score_and_random_state(self):
        r = resources(tutorial=True); s = Session(r); s.advance(); play_phase(s)
        s.grid_pointer('down', 0); s.grid_pointer('move', 4)
        old = json.loads(json.dumps(s.snapshot())); old['version'] = 6
        for key in ('visual_ms', 'board_entry_ms', 'banner', 'transition'):
            del old['engine']['word_grid'][key]
        before = copy.deepcopy(old)
        restored = Session.from_snapshot(r, old)
        self.assertEqual(old, before)
        self.assertEqual(restored.vm.snapshot(), s.vm.snapshot())
        self.assertEqual(restored.engine.random, s.engine.random)
        g = restored.engine.word_grid
        self.assertEqual((g.board, g.selection, g.starts, g.score),
                         (s.engine.word_grid.board, [0, 4], [0, 3], 0))
        self.assertEqual((g.visual_ms, g.banner, g.transition), (0, None, None))
        self.assertEqual(g.board_entry_ms, 2000)

    def test_tile_entry_continues_through_target_banner_without_restarting(self):
        s = Session(resources()); s.advance()
        for _ in range(10): s.tick(250)
        g = s.engine.word_grid
        self.assertEqual((g.phase, g.board_entry_ms), (6, 0))
        for _ in range(7): s.tick(250)
        self.assertEqual((g.phase, g.board_entry_ms), (2, 1750))
        self.assertEqual(g.banner.kind, 'target')
        saved = s.snapshot()
        self.assertEqual(Session.from_snapshot(s.resources, saved).snapshot(), saved)
        s.tick(250)
        self.assertEqual(g.board_entry_ms, 2000)

    @unittest.skipUnless(importlib.util.find_spec('pygame') and Path('.shs-library/library.json').exists(),
                         'desktop extra and user library required')
    def test_original_assets_render_instruction_motion_pause_save_and_resized_grid_input(self):
        os.environ['SDL_VIDEODRIVER'] = 'dummy'
        os.environ['SDL_AUDIODRIVER'] = 'dummy'
        import pygame
        from exp_runtime.content import ContentLibrary
        from exp_runtime.desktop import Desktop
        self.addCleanup(pygame.quit)
        with ContentLibrary(Path('.shs-library')) as lib:
            r = lib.open_episode('The_New_Girl.exp')
            r.programs[25001] = tutorial_resources().program(25001)
            ui = Desktop(Session(r), audio=False)
            s = ui.session
            # Initial tutorial reveal begins after the native 3200ms delay.
            for _ in range(13): ui.tick(250)
            frames = set()
            held = s.vm.snapshot()
            for _ in range(20):
                ui.render(); self.assertIsNone(ui.error)
                frames.add(pygame.image.tobytes(ui.grid_renderer.canvas, 'RGB'))
                ui.tick(16)
            self.assertGreater(len(frames), 15)
            self.assertEqual(s.vm.snapshot(), held)
            saved = s.snapshot()
            ui.render(); pixels = pygame.image.tobytes(ui.grid_renderer.canvas, 'RGB')
            self.assertEqual(s.snapshot(), saved)
            ui.session = Session.from_snapshot(r, saved)
            ui.render()
            self.assertEqual(pygame.image.tobytes(ui.grid_renderer.canvas, 'RGB'), pixels)
            ui.command(('menu',)); ui.tick(1000)
            self.assertEqual(ui.session.snapshot(), saved)
            ui.command(('resume',))
            ui.handle_event(pygame.event.Event(pygame.WINDOWFOCUSLOST)); ui.tick(1000)
            self.assertEqual(ui.session.snapshot(), saved)
            ui.handle_event(pygame.event.Event(pygame.WINDOWFOCUSGAINED))
            s = ui.session
            play_phase(s); s.answer(); play_phase(s)
            ui.window = pygame.display.set_mode((800, 600), pygame.RESIZABLE)
            ui.render(); self.assertIsNone(ui.error)
            for kind, index in ((pygame.MOUSEBUTTONDOWN, 0), (pygame.MOUSEMOTION, 1), (pygame.MOUSEMOTION, 2)):
                x, y = ui.grid_renderer.cells[index][1].center
                pos = (ui.viewport.x + x * ui.viewport.width / 320,
                       ui.viewport.y + y * ui.viewport.height / 480)
                ui.handle_event(pygame.event.Event(kind, button=1, pos=pos))
            self.assertEqual(s.engine.word_grid.score, 100)
            self.assertEqual(s.vm.snapshot(), held)
