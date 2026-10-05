"""Verify the embedded runtime in a temporary, isolated iOS simulator."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def simctl(*args, timeout=60, check=True):
    return subprocess.run(['xcrun', 'simctl', *map(str, args)], text=True, capture_output=True,
                          timeout=timeout, check=check).stdout.strip()


def verify(bundle, content=()):
    runtimes = json.loads(simctl('list', 'runtimes', '--json'))['runtimes']
    candidates = [r for r in runtimes if r.get('isAvailable') and r['identifier'].startswith('com.apple.CoreSimulator.SimRuntime.iOS-')]
    if not candidates:
        raise ValueError('Install an iOS simulator runtime through Xcode before verification')
    runtime = max(candidates, key=lambda r: tuple(map(int, r['version'].split('.'))))
    device_type = next(t['identifier'] for t in runtime['supportedDeviceTypes'] if t['name'].startswith('iPhone'))
    device = simctl('create', 'EXP Runtime Verification', device_type, runtime['identifier'])
    try:
        simctl('boot', device)
        simctl('bootstatus', device, '-b', timeout=180)
        simctl('install', device, bundle)
        container = Path(simctl('get_app_container', device, 'org.expruntime.player', 'data'))
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
        simctl('launch', device, 'org.expruntime.player', '--self-test')
        report = documents / 'ios-presentation-verification.json'
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            if report.is_file():
                try:
                    result = json.loads(report.read_text())
                except json.JSONDecodeError:
                    pass
                else:
                    if result.get('status') != 'passed' or result.get('platform') != 'ios':
                        raise RuntimeError(f'iOS runtime verification failed: {result}')
                    output = ROOT / 'build/ios/verification-simulator.json'
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_text(json.dumps(dict(simulator=runtime['name'], **result), indent=2) + '\n')
                    image = documents / 'ios-chooser.png'
                    if image.is_file():
                        shutil.copy2(image, output.with_suffix('.png'))
                    if content:
                        private = ROOT / 'build/ios/content-verification'
                        private.mkdir(exist_ok=True)
                        for screenshot in documents.glob('ios-content-*.png'):
                            shutil.copy2(screenshot, private / screenshot.name)
                    simctl('io', device, 'screenshot', output.with_name('verification-window.png'))
                    print(output.read_text())
                    return result
            time.sleep(.2)
        raise TimeoutError('The app did not write its presentation verification report within 180 seconds')
    finally:
        simctl('terminate', device, 'org.expruntime.player', check=False)
        simctl('shutdown', device, check=False)
        simctl('delete', device, check=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, default=ROOT / 'dist/ios/iphonesimulator/EXP Runtime.app')
    parser.add_argument('--content', nargs=2, action='append', metavar=('GAME', 'ARCHIVE'), default=[],
                        help='Optionally test a locally supplied game archive in the temporary simulator only')
    args = parser.parse_args()
    verify(args.bundle.resolve(), args.content)
