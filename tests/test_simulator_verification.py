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
        self.streams = {}
        for stream in ('sys.stdout', 'sys.stderr'):
            redirect = patch(stream, new_callable=io.StringIO)
            self.streams[stream] = redirect.start()
            self.addCleanup(redirect.stop)

    def test_cold_boot_reports_progress_before_completion_with_its_own_budget(self):
        log = self.diagnostics / 'boot.log'
        clock = Clock()

        def boot_progress(elapsed):
            if not log.read_text():
                with log.open('a') as output:
                    output.write('Waiting on Data Migration\n')
            if elapsed > 1:
                self.assertIn('Waiting on Data Migration', self.streams['sys.stdout'].getvalue())

        clock.on_sleep = boot_progress
        self.process.poll.side_effect = lambda: 0 if clock.elapsed >= 310 else None
        with patch.object(test_ios, 'time', clock), \
                patch.object(test_ios.subprocess, 'Popen', return_value=self.process):
            test_ios.wait_for_boot('authored-device', log, timeout=600)
        self.assertGreaterEqual(clock.elapsed, 310)
        console = self.streams['sys.stdout'].getvalue()
        self.assertEqual(console.count('Waiting on Data Migration'), 1)
        self.assertIn('30s elapsed, limit 600s', console)
        self.assertIn('Simulator boot completed', console)
        self.process.terminate.assert_not_called()

    def test_boot_timeout_stops_its_monitor_and_preserves_failure_output(self):
        log = self.diagnostics / 'boot.log'
        clock = Clock()
        self.process.wait.side_effect = [subprocess.TimeoutExpired('bootstatus', 5), 0]
        with patch.object(test_ios, 'time', clock), \
                patch.object(test_ios.subprocess, 'Popen', return_value=self.process):
            with self.assertRaisesRegex(TimeoutError, 'Simulator boot did not finish within 3 seconds'):
                test_ios.wait_for_boot('authored-device', log, timeout=3)
        self.assertLess(clock.elapsed, 3.3)
        self.process.terminate.assert_called_once()
        self.process.kill.assert_called_once()

        def failed_boot(*args, **kwargs):
            kwargs['stdout'].write('Authored boot failure\n')
            kwargs['stdout'].flush()
            self.process.poll.return_value = 1
            return self.process

        with patch.object(test_ios.subprocess, 'Popen', side_effect=failed_boot):
            with self.assertRaisesRegex(RuntimeError, 'bootstatus exited with status 1'):
                test_ios.wait_for_boot('authored-device', log)
        self.assertEqual(log.read_text(), 'Authored boot failure\n')
        self.assertIn('Authored boot failure', self.streams['sys.stdout'].getvalue())
        with self.assertRaisesRegex(ValueError, 'positive'):
            test_ios.wait_for_boot('authored-device', log, timeout=0)

    def wait(self, clock, **kwargs):
        with patch.object(test_ios, 'time', clock):
            return test_ios.wait_for_report(self.process, self.report, self.diagnostics / 'launch.log', **kwargs)

    def test_slow_install_streams_output_and_completes_after_the_old_sixty_second_limit(self):
        log = self.diagnostics / 'install.log'
        bundle = self.root / 'EXP Runtime.app'
        clock = Clock()

        def install_progress(elapsed):
            if not log.read_text():
                with log.open('a') as output:
                    output.write('Authored installation progress\n')
            if elapsed > 1:
                self.assertIn('Authored installation progress', self.streams['sys.stdout'].getvalue())

        clock.on_sleep = install_progress
        self.process.poll.side_effect = lambda: 0 if clock.elapsed >= 65 else None
        with patch.object(test_ios, 'time', clock), \
                patch.object(test_ios.subprocess, 'Popen', return_value=self.process) as start:
            test_ios.install_app('authored-device', bundle, log)
        self.assertGreaterEqual(clock.elapsed, 65)
        self.assertEqual(start.call_args.args[0], ['xcrun', 'simctl', 'install', 'authored-device', str(bundle)])
        self.assertEqual(start.call_args.kwargs['stderr'], subprocess.STDOUT)
        console = self.streams['sys.stdout'].getvalue()
        self.assertEqual(console.count('Authored installation progress'), 1)
        self.assertIn('Waiting for app installation (30s elapsed, limit 300s)', console)
        self.assertIn('App installation completed', console)
        self.process.terminate.assert_not_called()

    def test_install_failure_or_timeout_keeps_logs_and_never_launches_the_app(self):
        for code in (1, None):
            with self.subTest(exit_code=code):
                saved = self.root / 'build/ios/verification-simulator.json'
                saved.parent.mkdir(parents=True, exist_ok=True)
                saved.write_text(json.dumps(self.passed))
                process = Mock()
                process.poll.return_value = code
                process.wait.side_effect = [subprocess.TimeoutExpired('install', 5), 0]
                clock = Clock()

                def start(args, **kwargs):
                    self.assertEqual(args[2], 'install')
                    kwargs['stdout'].write('Authored installer diagnostic\n')
                    kwargs['stdout'].flush()
                    return process

                self.calls.clear()
                with patch.object(test_ios, 'ROOT', self.root), patch.object(test_ios, 'simctl', self.simctl), \
                        patch.object(test_ios, 'time', clock), patch.object(test_ios, 'wait_for_boot'), \
                        patch.object(test_ios.subprocess, 'Popen', side_effect=start) as popen, \
                        patch.object(test_ios.subprocess, 'run', return_value=Mock(returncode=0)), \
                        patch.object(test_ios, 'wait_for_report') as report:
                    message = 'installation did not finish within 3 seconds' if code is None else 'install exited with status 1'
                    with self.assertRaisesRegex(TimeoutError if code is None else RuntimeError, message):
                        test_ios.verify(self.root / 'authored.app', install_timeout=3)
                popen.assert_called_once()
                report.assert_not_called()
                self.assertNotIn('get_app_container', [c[0] for c in self.calls])
                self.assertFalse(saved.exists())
                diagnostics = saved.parent / 'simulator-diagnostics/authored-device'
                self.assertIn(message, (diagnostics / 'failure.txt').read_text())
                self.assertEqual((diagnostics / 'install.log').read_text(), 'Authored installer diagnostic\n')
                self.assertEqual([c[0] for c in self.calls[-3:]], ['terminate', 'shutdown', 'delete'])
                if code is None:
                    self.assertLess(clock.elapsed, 3.3)
                    process.terminate.assert_called_once()
                    process.kill.assert_called_once()
                else:
                    process.terminate.assert_not_called()

    def test_nonpositive_install_budget_is_rejected_before_creating_a_simulator(self):
        with patch.object(test_ios, 'simctl') as simctl, patch.object(test_ios.subprocess, 'Popen') as start:
            for timeout in (0, -1):
                with self.assertRaisesRegex(ValueError, 'positive'):
                    test_ios.install_app('authored-device', self.root / 'authored.app',
                                         self.diagnostics / 'install.log', timeout=timeout)
                with self.assertRaisesRegex(ValueError, 'positive'):
                    test_ios.verify(self.root / 'authored.app', install_timeout=timeout)
            simctl.assert_not_called()
            start.assert_not_called()

    def test_boot_install_and_startup_each_get_their_full_time_budget(self):
        clock = Clock()
        installer = Mock()
        installer.poll.side_effect = lambda: 0 if clock.elapsed >= 375 else None
        launched = []

        def boot(*args, **kwargs):
            clock.elapsed = 310

        def start(args, **kwargs):
            if args[2] == 'install':
                return installer
            self.assertEqual(args[2], 'launch')
            self.assertGreaterEqual(clock.elapsed, 375)
            launched.append(clock.elapsed)
            return self.process

        def complete(elapsed):
            if launched and elapsed - launched[0] >= 65:
                self.report.write_text(json.dumps(self.passed))

        clock.on_sleep = complete
        with patch.object(test_ios, 'ROOT', self.root), patch.object(test_ios, 'simctl', self.simctl), \
                patch.object(test_ios, 'time', clock), patch.object(test_ios, 'wait_for_boot', side_effect=boot), \
                patch.object(test_ios.subprocess, 'Popen', side_effect=start):
            result = test_ios.verify(self.root / 'authored.app', boot_timeout=600, install_timeout=90, timeout=90)
        self.assertEqual(result, self.passed)
        self.assertGreaterEqual(clock.elapsed, 440)
        installer.terminate.assert_not_called()
        self.process.terminate.assert_called_once()

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
                patch.object(test_ios, 'wait_for_boot') as boot, \
                patch.object(test_ios, 'install_app') as install, \
                patch.object(test_ios.subprocess, 'Popen', return_value=self.process), \
                patch.object(test_ios, 'wait_for_report', return_value=self.passed) as report:
            result = test_ios.verify(self.root / 'authored.app', boot_timeout=600, install_timeout=180, timeout=120)
        self.assertEqual(result, self.passed)
        saved = json.loads((self.root / 'build/ios/verification-simulator.json').read_text())
        self.assertEqual(saved['checks'], self.passed['checks'])
        self.assertEqual(saved['simulator'], 'iOS authored')
        diagnostics = self.root / 'build/ios/simulator-diagnostics'
        boot.assert_called_once_with('authored-device', diagnostics / 'authored-device/boot.log', timeout=600)
        install.assert_called_once_with('authored-device', self.root / 'authored.app',
                                        diagnostics / 'authored-device/install.log', timeout=180)
        report.assert_called_once_with(self.process, self.report,
                                       diagnostics / 'authored-device/launch.log', timeout=120)
        device = json.loads((diagnostics / 'authored-device/device.json').read_text())
        self.assertEqual(device['runtime'], json.loads((diagnostics / 'runtimes.json').read_text())[0])
        self.assertEqual(device['device_type']['identifier'], 'authored-phone')
        self.process.terminate.assert_called_once()
        self.assertEqual([c[0] for c in self.calls[-3:]], ['terminate', 'shutdown', 'delete'])

    def test_missing_runtime_stops_before_creating_a_device(self):
        runtimes = [dict(isAvailable=False, version='26.0', name='iOS unavailable',
                         identifier='com.apple.CoreSimulator.SimRuntime.iOS-unavailable')]
        with patch.object(test_ios, 'ROOT', self.root), \
                patch.object(test_ios, 'simctl', return_value=json.dumps(dict(runtimes=runtimes))) as simctl:
            with self.assertRaisesRegex(ValueError, 'Install an iOS simulator runtime'):
                test_ios.verify(self.root / 'authored.app')
        simctl.assert_called_once_with('list', 'runtimes', '--json')
        inventory = self.root / 'build/ios/simulator-diagnostics/runtimes.json'
        self.assertEqual(json.loads(inventory.read_text()), runtimes)

    def test_boot_failure_prevents_app_installation_but_still_collects_and_cleans_up(self):
        original = TimeoutError('authored boot timeout')
        with patch.object(test_ios, 'ROOT', self.root), patch.object(test_ios, 'simctl', self.simctl), \
                patch.object(test_ios, 'wait_for_boot', side_effect=original), \
                patch.object(test_ios, 'install_app') as install, \
                patch.object(test_ios, 'collect_failure') as diagnostics, \
                patch.object(test_ios.subprocess, 'Popen') as launch:
            with self.assertRaises(TimeoutError) as raised:
                test_ios.verify(self.root / 'authored.app')
        self.assertIs(raised.exception, original)
        self.assertNotIn('install', [c[0] for c in self.calls])
        install.assert_not_called()
        launch.assert_not_called()
        diagnostics.assert_called_once_with('authored-device', None,
            self.root / 'build/ios/simulator-diagnostics/authored-device', original)
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
                patch.object(test_ios, 'wait_for_boot'), \
                patch.object(test_ios, 'install_app'), \
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
        predicate = run.call_args_list[1].args[0][-1]
        for process in ('installd', 'installcoordinationd', 'lsd'):
            self.assertIn(f'process == "{process}"', predicate)


if __name__ == '__main__':
    unittest.main()
