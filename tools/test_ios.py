"""Verify the embedded runtime in a temporary, isolated iOS simulator."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
APP_ID = 'org.expruntime.player'


def simctl(*args, timeout=60, check=True):
    print(f'simctl {args[0]}', flush=True)
    try:
        return subprocess.run(['xcrun', 'simctl', *map(str, args)], text=True, capture_output=True,
                              timeout=timeout, check=check).stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        for output in (error.stdout, error.stderr):
            if output:
                print(output.decode(errors='replace') if isinstance(output, bytes) else output,
                      file=sys.stderr, flush=True)
        raise


def wait_for_report(process, report, log, *, timeout=300):
    """Watch the app's report while simctl remains attached to its console."""
    if timeout <= 0:
        raise ValueError('Verification timeout must be positive')
    print(f'Launching self-test; allowing {timeout}s for startup and verification', flush=True)
    deadline = time.monotonic() + timeout
    progress = time.monotonic() + 30
    while time.monotonic() < deadline:
        if report.is_file():
            try:
                result = json.loads(report.read_text())
            except json.JSONDecodeError:
                pass
            else:
                if not isinstance(result, dict) or result.get('status') != 'passed' or result.get('platform') != 'ios':
                    raise RuntimeError(f'iOS runtime verification failed: {result}')
                return result
        code = process.poll()
        if code is not None:
            raise RuntimeError(f'simctl launch exited with status {code} before the app completed verification; see {log}')
        if time.monotonic() >= progress:
            print('Waiting for the iOS presentation verification report...', flush=True)
            progress = time.monotonic() + 30
        time.sleep(.2)
    raise TimeoutError(f'The app did not complete startup and presentation verification within {timeout} seconds; see {log}')


def collect_failure(device, documents, diagnostics, error):
    """Keep evidence before deleting the disposable simulator."""
    (diagnostics / 'failure.txt').write_text(str(error) + '\n')
    if documents:
        for name in ('ios-verification.json', 'ios-presentation-verification.json'):
            source = documents / name
            if source.is_file():
                shutil.copy2(source, diagnostics / name)
    commands = (
        ('devices.log', ('list', 'devices', '--json')),
        ('system.log', ('spawn', device, 'log', 'show', '--style', 'compact', '--last', '5m',
                        '--predicate', 'process == "EXP Runtime" OR process == "SpringBoard" OR process == "runningboardd"')),
        ('screenshot.log', ('io', device, 'screenshot', diagnostics / 'failure.png')),
    )
    for name, args in commands:
        with (diagnostics / name).open('w') as output:
            try:
                subprocess.run(['xcrun', 'simctl', *map(str, args)], stdout=output,
                               stderr=subprocess.STDOUT, timeout=20, check=False)
            except (OSError, subprocess.SubprocessError) as failure:
                output.write(f'\nDiagnostic command failed: {failure}\n')
    print(f'Simulator failure diagnostics: {diagnostics}', file=sys.stderr, flush=True)


def verify(bundle, content=(), *, timeout=300):
    if timeout <= 0:
        raise ValueError('Verification timeout must be positive')
    output = ROOT / 'build/ios/verification-simulator.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.unlink(missing_ok=True)
    runtimes = json.loads(simctl('list', 'runtimes', '--json'))['runtimes']
    candidates = [r for r in runtimes if r.get('isAvailable') and r['identifier'].startswith('com.apple.CoreSimulator.SimRuntime.iOS-')]
    if not candidates:
        raise ValueError('Install an iOS simulator runtime through Xcode before verification')
    runtime = max(candidates, key=lambda r: tuple(map(int, r['version'].split('.'))))
    device_type = next(t['identifier'] for t in runtime['supportedDeviceTypes'] if t['name'].startswith('iPhone'))
    device = simctl('create', 'EXP Runtime Verification', device_type, runtime['identifier'])
    diagnostics = output.parent / 'simulator-diagnostics' / device
    documents = None
    process = None
    try:
        diagnostics.mkdir(parents=True, exist_ok=True)
        simctl('boot', device)
        simctl('bootstatus', device, '-b', timeout=300)
        simctl('install', device, bundle)
        container = Path(simctl('get_app_container', device, APP_ID, 'data'))
        documents = container / 'Documents'
        documents.mkdir(exist_ok=True)
        inputs = []
        for index, (game, path) in enumerate(content):
            destination = documents / 'Verification/inputs' / str(index) / Path(path).name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
            inputs.append(dict(game=game, path=str(destination)))
        if inputs:
            (documents / 'ios-playback-input.json').write_text(json.dumps(inputs))
        log = diagnostics / 'launch.log'
        with log.open('w') as console:
            process = subprocess.Popen(['xcrun', 'simctl', 'launch', '--console', device, APP_ID, '--self-test'],
                                       stdout=console, stderr=subprocess.STDOUT)
            result = wait_for_report(process, documents / 'ios-presentation-verification.json', log, timeout=timeout)
        image = documents / 'ios-chooser.png'
        if image.is_file():
            shutil.copy2(image, output.with_suffix('.png'))
        if content:
            private = ROOT / 'build/ios/content-verification'
            private.mkdir(exist_ok=True)
            for screenshot in documents.glob('ios-content-*.png'):
                shutil.copy2(screenshot, private / screenshot.name)
        simctl('io', device, 'screenshot', output.with_name('verification-window.png'))
        output.write_text(json.dumps(dict(simulator=runtime['name'], **result), indent=2) + '\n')
        print(output.read_text())
        return result
    except Exception as error:
        try:
            collect_failure(device, documents, diagnostics, error)
        except Exception as failure:
            print(f'Could not collect simulator diagnostics: {failure}', file=sys.stderr, flush=True)
        raise
    finally:
        # --console stays attached until the app exits. Stop only this
        # launch process after collecting screenshots/reports/diagnostics.
        if process is not None:
            try:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
            except (OSError, subprocess.SubprocessError) as error:
                print(f'Could not stop simulator console: {error}', file=sys.stderr, flush=True)
        for args in (('terminate', device, APP_ID), ('shutdown', device), ('delete', device)):
            try:
                simctl(*args, timeout=20, check=False)
            except (OSError, subprocess.SubprocessError) as error:
                print(f'Simulator cleanup {args[0]} failed: {error}', file=sys.stderr, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, default=ROOT / 'dist/ios/iphonesimulator/EXP Runtime.app')
    parser.add_argument('--content', nargs=2, action='append', metavar=('GAME', 'ARCHIVE'), default=[],
                        help='Optionally test a locally supplied game archive in the temporary simulator only')
    parser.add_argument('--timeout', type=int, default=300, help='Maximum seconds for app startup and verification')
    args = parser.parse_args()
    verify(args.bundle.resolve(), args.content, timeout=args.timeout)
