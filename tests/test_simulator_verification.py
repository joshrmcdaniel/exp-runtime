"""Simulator orchestration checks use authored reports and a virtual clock."""
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from tools import test_ios


class Clock:
    def __init__(self, on_sleep=lambda _: None):
        self.elapsed = 0
        self.on_sleep = on_sleep

    def monotonic(self):
        return self.elapsed

    def sleep(self, seconds):
        self.elapsed += seconds
        self.on_sleep(self.elapsed)


class SimulatorVerificationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.documents = self.root / 'container/Documents'
        self.documents.mkdir(parents=True)
        self.report = self.documents / 'ios-presentation-verification.json'
        self.diagnostics = self.root / 'diagnostics'
        self.diagnostics.mkdir()
        self.process = Mock()
        self.process.poll.return_value = None
        self.passed = dict(status='passed', platform='ios', checks=['authored verification'])
        self.calls = []
        for stream in ('sys.stdout', 'sys.stderr'):
            redirect = patch(stream, new_callable=io.StringIO)
            redirect.start()
            self.addCleanup(redirect.stop)

    def wait(self, clock, **kwargs):
        with patch.object(test_ios, 'time', clock):
            return test_ios.wait_for_report(self.process, self.report, self.diagnostics / 'launch.log', **kwargs)

    def test_slow_startup_can_complete_while_console_stays_attached(self):
        def write_report(elapsed):
            if elapsed >= 65:
                self.report.write_text(json.dumps(self.passed))
        clock = Clock(write_report)
        self.assertEqual(self.wait(clock), self.passed)
        self.assertGreater(clock.elapsed, 60)
        self.assertIsNone(self.process.poll())

    def test_partial_report_is_retried_but_failed_or_wrong_platform_is_fatal(self):
        self.report.write_text('{')
        clock = Clock(lambda _: self.report.write_text(json.dumps(self.passed)))
        self.assertEqual(self.wait(clock), self.passed)
        for report in (dict(status='failed', platform='ios', error='authored failure'),
                       dict(status='passed', platform='darwin'), ['invalid report']):
            self.report.write_text(json.dumps(report))
            with self.subTest(report=report), self.assertRaisesRegex(RuntimeError, 'verification failed'):
                self.wait(Clock())

    def test_hung_startup_has_a_deadline_and_early_exit_is_not_success(self):
        clock = Clock()
        with self.assertRaisesRegex(TimeoutError, 'within 3 seconds'):
            self.wait(clock, timeout=3)
        self.assertLess(clock.elapsed, 3.3)
        for code in (0, 1):
            self.process.poll.return_value = code
            with self.subTest(code=code), self.assertRaisesRegex(RuntimeError, f'exited with status {code}'):
                self.wait(Clock())
        with self.assertRaisesRegex(ValueError, 'positive'):
            self.wait(Clock(), timeout=0)

    def simctl(self, *args, **kwargs):
        self.calls.append(args)
        if args[0] == 'list':
            return json.dumps(dict(runtimes=[dict(isAvailable=True, version='26.0', name='iOS authored',
                identifier='com.apple.CoreSimulator.SimRuntime.iOS-authored',
                supportedDeviceTypes=[dict(name='iPhone authored', identifier='authored-phone')])]))
        if args[0] == 'create':
            return 'authored-device'
        if args[0] == 'get_app_container':
            return str(self.documents.parent)
        if args[0] == 'io':
            self.assertFalse(self.process.terminate.called, 'App stopped before screenshot')
        return ''

    def test_success_keeps_app_alive_for_capture_then_stops_console_and_device(self):
        with patch.object(test_ios, 'ROOT', self.root), patch.object(test_ios, 'simctl', self.simctl), \
                patch.object(test_ios.subprocess, 'Popen', return_value=self.process), \
                patch.object(test_ios, 'wait_for_report', return_value=self.passed):
            result = test_ios.verify(self.root / 'authored.app')
        self.assertEqual(result, self.passed)
        saved = json.loads((self.root / 'build/ios/verification-simulator.json').read_text())
        self.assertEqual(saved['checks'], self.passed['checks'])
        self.assertEqual(saved['simulator'], 'iOS authored')
        self.process.terminate.assert_called_once()
        self.assertEqual([c[0] for c in self.calls[-3:]], ['terminate', 'shutdown', 'delete'])

    def test_failure_preserves_diagnostics_and_original_error_despite_cleanup_timeouts(self):
        saved = self.root / 'build/ios/verification-simulator.json'
        saved.parent.mkdir(parents=True)
        saved.write_text(json.dumps(self.passed))
        original = TimeoutError('authored app startup timeout')

        def calls(*args, **kwargs):
            result = self.simctl(*args, **kwargs)
            if args[0] in ('terminate', 'shutdown'):
                raise subprocess.TimeoutExpired(args, kwargs['timeout'])
            return result

        def diagnostics(device, documents, path, error):
            self.assertIs(error, original)
            self.assertFalse(self.process.terminate.called)
            (path / 'failure.txt').write_text(str(error))

        self.process.wait.side_effect = [subprocess.TimeoutExpired('console', 5), 0]
        with patch.object(test_ios, 'ROOT', self.root), patch.object(test_ios, 'simctl', calls), \
                patch.object(test_ios.subprocess, 'Popen', return_value=self.process), \
                patch.object(test_ios, 'wait_for_report', side_effect=original), \
                patch.object(test_ios, 'collect_failure', side_effect=diagnostics):
            with self.assertRaises(TimeoutError) as raised:
                test_ios.verify(self.root / 'authored.app')
        self.assertIs(raised.exception, original)
        self.assertFalse(saved.exists(), 'An earlier success must not survive a failed run')
        self.assertEqual((saved.parent / 'simulator-diagnostics/authored-device/failure.txt').read_text(), str(original))
        self.process.kill.assert_called_once()
        self.assertEqual(self.calls[-1], ('delete', 'authored-device'))

    def test_failure_collection_keeps_reports_when_a_diagnostic_command_hangs(self):
        self.report.write_text(json.dumps(dict(status='failed', error='authored error')))
        with patch.object(test_ios.subprocess, 'run', side_effect=[
                subprocess.TimeoutExpired('list', 20), Mock(returncode=0), Mock(returncode=0)]) as run:
            test_ios.collect_failure('authored-device', self.documents, self.diagnostics, TimeoutError('startup'))
        self.assertEqual((self.diagnostics / self.report.name).read_bytes(), self.report.read_bytes())
        self.assertIn('startup', (self.diagnostics / 'failure.txt').read_text())
        self.assertIn('Diagnostic command failed', (self.diagnostics / 'devices.log').read_text())
        self.assertEqual(run.call_count, 3)


if __name__ == '__main__':
    unittest.main()
