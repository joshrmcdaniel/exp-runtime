import copy
import struct
import unittest

from exp_runtime.decode.bytecode import OPERAND_OPCODES, decode_program
from exp_runtime.vm import KiwiVM, StopKind, VMError


def program(*instructions, words=(), gap=0):
    code = bytearray()
    for item in instructions:
        op, arg = item if isinstance(item, tuple) else (item, None)
        code.append(op)
        if op in OPERAND_OPCODES:
            code.extend(struct.pack('>H', arg & 0xFFFF))
    header = b'kiwi\x02\x00\x00' + struct.pack('>4H', len(words), gap, 0, len(instructions))
    return decode_program(header + struct.pack(f'>{len(words)}H', *words) + code)


class VMTests(unittest.TestCase):
    def test_choice_result_changes_the_executed_branch(self):
        vm = KiwiVM(program(
            (0x1A, 99), (0x1F, 0x4E01), 0x21, (0x1A, 1), 0x0A,
            (0x2B, 4), (0x1A, 111), (0x1F, 0x0D01), 0x33,
            (0x1A, 222), (0x1F, 0x0D01), 0x33,
        ))
        event = vm.run()
        self.assertEqual((event.yield_id, event.args), (78, (99,)))
        self.assertIs(vm.run(), event)
        self.assertEqual(vm.pc, 2)
        self.assertEqual(vm.stack, (99,))  # pending frame is retained
        other = copy.deepcopy(vm)
        for machine, result, text in ((vm, 1, 111), (other, 0, 222)):
            machine.resume(result)
            self.assertEqual(machine.stack, ())  # result is a register, not a push
            self.assertEqual(machine.run().args, (text,))
            machine.resume(0)
            self.assertEqual(machine.run().kind, StopKind.HALT)
            self.assertEqual(machine.stack, ())

    def test_call_frame_locals_and_return_skip_jump_instruction(self):
        vm = KiwiVM(program(
            (0x1A, 40), 0x42, (0x29, 7), 0x15, 0x07, (0x1F, 0x0D01), 0x33,
            0x48, 0x4A, (0x41, -3), (0x1A, 2), 0x50, 0x03, 0x22, 0x43,
        ))
        self.assertEqual(vm.stack_base, 0x7BF5)
        self.assertEqual(vm.run().args, (42,))
        self.assertEqual(vm.fp, 0)
        vm.resume(0)
        # Native stack storage survives a pop; an address can still read it.
        self.assertEqual(vm.read_word(vm.stack_base), 42)
        self.assertEqual(vm.run().kind, StopKind.HALT)

    def test_signed_arithmetic_comparisons_and_c_division(self):
        for op, left, right, expected in (
            (0x50, 32767, 1, -32768), (0x51, -32768, 1, 32767),
            (0x52, 30000, 3, 24464), (0x53, -7, 3, -2),
            (0x54, -7, 3, -1), (0x53, 7, -3, -2), (0x54, 7, -3, 1),
            (0x0A, -1, -1, 1), (0x0B, -1, 1, 1), (0x0C, -1, 1, 0),
            (0x0D, 1, -1, 1), (0x0E, -1, 1, 1), (0x0F, -1, -1, 1),
            (0x11, 0, -2, 1), (0x12, 2, 0, 0),
        ):
            with self.subTest(op=op, left=left, right=right):
                vm = KiwiVM(program((0x1A, left), (0x1A, right), op, (0x1F, 0x0101)))
                self.assertEqual(vm.run().args, (expected,))

    def test_registers_packed_immediates_and_unsplit_yield(self):
        vm = KiwiVM(program((0x01, 7), 0x07, (0x1B, 0x807F),
                            (0x20, 3), (0x1E, 13), 0x33))
        self.assertEqual(vm.run().args, (7, 127, -128))
        vm.resume(-1)
        self.assertEqual(vm.result, -1)

    def test_mutable_data_and_backward_branch(self):
        vm = KiwiVM(program((0x40, 0), (0x1F, 0x0101), (0x01, 0), 0x26,
                            (0x40, 0), (0x2A, -5), 0x33, words=(3,)))
        for value in (3, 2, 1):
            self.assertEqual(vm.run().args, (value,))
            vm.resume(0)
        self.assertEqual(vm.run().kind, StopKind.HALT)
        self.assertEqual(vm.read_word(0), 0)

    def test_store_initializes_gap_and_preserves_assigned_value(self):
        vm = KiwiVM(program((0x1A, 0), (0x1A, -5), 0x3E,
                            (0x1F, 0x0101), 0x33, gap=1))
        self.assertEqual(vm.run().args, (-5,))
        self.assertEqual(vm.read_word(0), -5)

    def test_stack_allocation_and_compact_frame_address(self):
        vm = KiwiVM(program((0x19, -1), 0x5F, (0x1A, 9), 0x3E, 0x15,
                            (0x41, 0), (0x1F, 0x0101), 0x33))
        self.assertEqual(vm.run().args, (9,))
        self.assertEqual(vm.stack, (9, 9))

    def test_peek_branch_and_compact_switch(self):
        vm = KiwiVM(program((0x1A, 5), (0x2C, 2), 0x33, 0x05,
                            (0x5C, 0x0205), 0x33, (0x1F, 0x0101)))
        self.assertEqual(vm.run().args, (5,))

    def test_pause_and_budget_are_resumable(self):
        vm = KiwiVM(program(0x32, 0x33))
        pause = vm.run()
        self.assertEqual(pause.kind, StopKind.PAUSE)
        self.assertIs(vm.run(), pause)
        vm.continue_after_pause()
        self.assertEqual(vm.run().kind, StopKind.HALT)
        loop = KiwiVM(program((0x28, 0)))
        self.assertEqual(loop.run(20).kind, StopKind.BUDGET)
        self.assertEqual(loop.steps_executed, 20)
        self.assertEqual(loop.run(3).kind, StopKind.BUDGET)
        self.assertEqual(loop.steps_executed, 23)

    def test_errors_do_not_invent_memory_or_results(self):
        for p in (
            program(0x21), program(0x15), program((0x40, 0), gap=1),
            program((0x1F, 0x0102)), program(0xFF),
            program((0x1A, 1), (0x1A, 0), 0x53), program((0x29, 200)),
        ):
            with self.subTest(program=p), self.assertRaises(VMError):
                KiwiVM(p).run()
        with self.assertRaises(VMError):
            KiwiVM(program(0x33)).resume(0)


if __name__ == '__main__':
    unittest.main()
