"""Service 70's verified Android constants, with authored VM callers."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from exp_runtime.engine import EngineAction, EngineState
from exp_runtime.runtime import Session
from exp_runtime.vm import KiwiVM, StopKind, VMError
from test_runtime import Resources, answer_screen, host_call, text_words
from test_vm import program


def query_program(selector, *, dynamic=False, extra=()):
    args = (selector, *extra)
    call = ([(0x1a, a) for a in args] + [(0x20, len(args)), (0x1e, 70)]
            if dynamic else host_call(70, *args))
    return program((0x1a, 77), *call, 0x21, (0x1f, 0xfe02), 0x33)


class BuildQueryTests(unittest.TestCase):
    def test_constants_defaults_and_both_call_encodings_preserve_host_state(self):
        cases = ((2, 2), (3, 6), (6, 0x7ff5), (9, 1), (10, 0),
                 (0, 0), (1, 0), (4, 0), (5, 0), (7, 0), (8, 0),
                 (12, 0), (32767, 0), (-1, 0), (-32768, 0))
        for dynamic in (False, True):
            for extra in ((), (432, -4)):
                for selector, expected in cases:
                    with self.subTest(dynamic=dynamic, extra=extra, selector=selector):
                        vm = KiwiVM(query_program(selector, dynamic=dynamic, extra=extra))
                        vm.write_word(vm.stack_base + 1023, 12345)
                        engine = EngineState(numbers={401: 7}, last_input='Separate input')
                        engine.dynamic_strings[0] = 'Existing slot text'
                        engine.result_cells[0] = 31
                        before = copy.deepcopy(engine)
                        request = vm.run()
                        pc, steps = vm.pc, vm.steps_executed
                        action = engine.dispatch(vm)
                        self.assertTrue(action.completed)
                        self.assertEqual(action.details, dict(result=expected, selector=selector))
                        self.assertIs(action.request, request)
                        self.assertEqual((vm.pc, vm.steps_executed), (pc, steps))
                        self.assertEqual(engine, before)
                        self.assertEqual(vm.run().args, (77, expected))
                        self.assertEqual(vm.read_word(vm.stack_base + 1023), 12345)

    def test_selector_six_returns_a_live_string_handle_without_populating_it(self):
        engine = EngineState(last_input='This is not slot zero')
        vm = KiwiVM(query_program(6))
        vm.run()
        engine.dispatch(vm)
        handle = vm.result
        self.assertEqual(handle, 0x7ff5)
        self.assertEqual(engine.read_text(vm, handle), '')
        engine.dynamic_strings[0] = 'Changed after the query'
        self.assertEqual(engine.read_text(vm, handle), 'Changed after the query')
        self.assertEqual(engine.last_input, 'This is not slot zero')

    def test_application_identity_selector_stays_pending_and_missing_selector_fails(self):
        r = Resources(query_program(11, extra=(456,)))
        s = Session(r)
        before = copy.deepcopy(s.engine)
        action = s.advance()
        self.assertEqual(action.name, 'unhandled_yield')
        self.assertEqual(action.details['selector'], 11)
        held = s.vm.snapshot()
        self.assertIs(s.advance(), action)
        with self.assertRaises(VMError):
            s.answer()
        self.assertEqual(s.vm.snapshot(), held)
        self.assertEqual(s.engine, before)
        restored = Session.from_snapshot(r, json.loads(json.dumps(s.snapshot())))
        self.assertEqual(restored.snapshot(), s.snapshot())
        vm = KiwiVM(program(*host_call(70)))
        request = vm.run()
        with self.assertRaisesRegex(VMError, 'at least 1'):
            s.engine.dispatch(vm)
        self.assertIs(vm.pending, request)
        # The verified default for selector values is not a default for services.
        unknown = Session(Resources(program(*host_call(254, 10))))
        self.assertEqual(unknown.advance().name, 'unhandled_yield')

    def test_old_stop_completes_only_its_frame_without_replaying_previous_randomness(self):
        r = Resources(program(*host_call(27, 100), *host_call(54, 123, 45),
                              *host_call(70, 10), 0x21, (0x1f, 0xfe01)))
        s = Session(r)
        while (request := s.vm.run()).yield_id != 70:
            self.assertTrue(s.engine.dispatch(s.vm).completed)
        s.pending = EngineAction('unhandled_yield', request, False)
        saved = json.loads(json.dumps(s.snapshot()))
        untouched = copy.deepcopy(saved)
        restored = Session.from_snapshot(r, saved)
        self.assertEqual(saved, untouched)
        self.assertEqual(restored.pending.request.args, (0,))
        self.assertEqual(restored.engine, s.engine)
        self.assertEqual(restored.vm.steps_executed, s.vm.steps_executed + 2)
        self.assertEqual(Session.from_snapshot(r, restored.snapshot()).snapshot(), restored.snapshot())

    def test_saved_query_retains_the_previous_portrait_for_the_next_dialogue(self):
        words, refs = text_words('First reply.', 'Next reply.')
        r = Resources(program(*host_call(13, refs[0], 0), *host_call(70, 10),
                              *host_call(13, refs[1], 0), 0x33, words=words))

        def start():
            s = Session(r)
            s.engine.character_names[0] = 'Alex'
            s.engine.character_art_variants[0] = [100] * 5
            s.advance()
            return s

        old = start()
        dispatch = old.engine.dispatch

        def unsupported(vm, **kwargs):
            if vm.pending.yield_id == 70:
                return EngineAction('unhandled_yield', vm.pending, False)
            return dispatch(vm, **kwargs)

        with patch.object(old.engine, 'dispatch', side_effect=unsupported):
            answer_screen(old)
        restored = Session.from_snapshot(r, old.snapshot())
        fresh = start()
        fresh.engine.random = copy.deepcopy(old.engine.random)
        answer_screen(fresh)
        self.assertEqual(restored.snapshot(), fresh.snapshot())
        self.assertFalse(restored.engine.dialogue_animation.changed)

    @unittest.skipUnless(Path('.shs-library/library.json').is_file(), 'player content is absent')
    def test_original_football_call_returns_zero_and_executes_its_conditional_branch(self):
        from exp_runtime.content import ContentLibrary
        with ContentLibrary(Path('.shs-library')) as library:
            r = library.open_episode('Football Star')
            vm = KiwiVM(r.program(25001))
            vm.pc = 221  # Isolated original PUSH and reported call; no game-state fabrication.
            request = vm.run()
            self.assertEqual((request.pc, request.yield_id, request.args), (222, 70, (10,)))
            engine = EngineState()
            self.assertTrue(engine.dispatch(vm).completed)
            self.assertEqual((vm.result, vm.sp, vm.pc), (0, 0, 223))
            # PUSH R, PUSH 2, compare equal, and the original branch-on-zero.
            self.assertEqual(vm.run(4).kind, StopKind.BUDGET)
            self.assertEqual(vm.pc, 234)


if __name__ == '__main__':
    unittest.main()
