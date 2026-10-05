import struct
import unittest

from exp_runtime.decode.bytecode import decode_program, KiwiFormatError


def script(code, count, previous=b'', words=(0x4142, 0), extra=(0x1234,)):
    return (b'kiwi\x02' + bytes((bool(previous),)) + previous + b'\x00'
            + struct.pack('>4H', len(words), 3, len(extra), count)
            + struct.pack(f'>{len(words) + len(extra)}H', *(words + extra)) + code)


class BytecodeTests(unittest.TestCase):
    def test_preserves_control_flow_and_data(self):
        data = script(b'\x1a\x00\x07\x2a\xff\xff\x1f\x0d\x03\x33', 4)
        program = decode_program(data)
        self.assertEqual(program.to_bytes(), data)
        self.assertEqual(program.main_words, (0x4142, 0))
        self.assertEqual(program.gap_count, 3)
        self.assertEqual(program.extra_words, (0x1234,))
        self.assertEqual(program.instructions[1].branch_target(), 0)
        self.assertEqual(program.instructions[2].yield_id, 13)
        self.assertEqual([i.byte_offset for i in program.instructions], [21, 24, 27, 30])

    def test_previous_segment_and_absolute_target(self):
        data = script(b'\x29\x00\x02', 1, struct.pack('>HH', 10, 20))
        program = decode_program(data)
        self.assertEqual(program.previous_data_count, 10)
        self.assertEqual(program.instructions[0].pc, 20)
        self.assertEqual(program.instructions[0].branch_target(), 2)
        self.assertEqual(program.to_bytes(), data)

    def test_unknown_opcode_is_preserved(self):
        data = script(b'\xff', 1)
        self.assertEqual(decode_program(data).to_bytes(), data)

    def test_truncation_is_rejected_at_every_boundary(self):
        data = script(b'\x1a\x12\x34', 1)
        for end in range(len(data)):
            with self.subTest(end=end), self.assertRaises(KiwiFormatError):
                decode_program(data[:end])

    def test_trailing_data_and_unsupported_version(self):
        data = script(b'\x33', 1)
        for invalid in (data + b'\x00', data[:4] + b'\x03' + data[5:]):
            with self.assertRaises(KiwiFormatError):
                decode_program(invalid)


if __name__ == '__main__':
    unittest.main()
