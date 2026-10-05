import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

from exp_runtime.content import ContentError
from exp_runtime.trace import trace_archive
from test_content import archive, metadata
from test_vm import program


class TraceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / 'authored.exp'
        initial = program((0x1A, 25002), (0x1A, 0), (0x1F, 0x0A02), 0x33)
        pending = program((0x1A, 37), (0x1F, 0xFA01), 0x33)
        self.data = archive({1: metadata(), 25001: initial.to_bytes(),
                             25002: pending.to_bytes()},
                            compressed=(1, 25002), aliases={9: 1})
        self.path.write_bytes(self.data)

    def test_compressed_scene_load_retains_unknown_service_arguments(self):
        result = trace_archive(self.path)
        self.assertEqual(result['sha256'], hashlib.sha256(self.data).hexdigest())
        self.assertEqual((result['status'], result['scene'], result['pc'], result['sp']),
                         ('unhandled_yield', 25002, 2, 1))
        self.assertEqual(result['events'][-2]['name'], 'load_script')
        self.assertEqual(result['events'][-1]['request']['args'], (37,))
        self.assertFalse(result['events'][-1]['completed'])

    def test_strict_reader_rejects_unknown_archive_flags(self):
        data = bytearray(self.data)
        first_offset, = struct.unpack_from('>I', data, 11)
        struct.pack_into('>I', data, first_offset + 8, 2)
        self.path.write_bytes(data)
        with self.assertRaisesRegex(ContentError, 'Unsupported EXP flags'):
            trace_archive(self.path)

    def test_installed_module_traces_from_an_unrelated_directory(self):
        result = subprocess.run([sys.executable, '-m', 'exp_runtime', 'trace', str(self.path)],
                                cwd=self.root, text=True, capture_output=True, check=True)
        trace = json.loads(result.stdout)
        self.assertEqual(trace['scene'], 25002)
        self.assertEqual(trace['events'][-1]['request']['args'], [37])
        self.assertEqual(result.stderr, '')

    def test_invalid_cli_input_returns_a_concise_error(self):
        self.path.write_bytes(b'authored malformed archive')
        result = subprocess.run([sys.executable, '-m', 'exp_runtime', 'trace', str(self.path)],
                                cwd=self.root, text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('Not a CSPUD EXP archive', result.stderr)
        self.assertNotIn('Traceback', result.stderr)


if __name__ == '__main__':
    unittest.main()
