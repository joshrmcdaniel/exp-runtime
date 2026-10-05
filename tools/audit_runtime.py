"""Validate a game library, or import an APK/IPA and EXPs temporarily, and audit starts."""
import argparse
from collections import Counter
import json
from pathlib import Path
import tempfile

from exp_runtime.content import ContentLibrary, import_game
from exp_runtime.runtime import Session


def audit(directory):
    starts, failures = Counter(), []
    script_count = 0
    with ContentLibrary(directory) as library:
        for record in library.episodes:
            try:
                resources = library.open_episode(record['id'])
                script_count += len(resources.programs)
                session = Session(resources)
                action = session.advance()
                starts[(action.name, action.request.yield_id)] += 1
            except Exception as error:
                failures.append(dict(episode=record['id'], name=record['name'],
                                     error=f'{type(error).__name__}: {error}'))
        source = library.manifest[library.kind]
        return dict(game=library.game_id, profile=library.profile,
                    **{library.kind + '_sha256': source['sha256']},
                    **({'native_sha256': source['native_sha256']} if library.kind == 'apk' else {}),
                    episodes=len(library.episodes), scripts=script_count,
                    initial_stops=[dict(action=name, service=service, count=count)
                                   for (name, service), count in sorted(starts.items())],
                    failures=failures)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--library', type=Path)
    source.add_argument('--apk', type=Path)
    source.add_argument('--ipa', type=Path)
    parser.add_argument('--episodes', type=Path, nargs='+', default=[])
    args = parser.parse_args()
    if args.library and args.episodes:
        parser.error('--episodes is only used with --apk or --ipa')
    if args.library:
        result = audit(args.library)
    else:
        with tempfile.TemporaryDirectory(prefix='exp-runtime-audit-') as temporary:
            directory = Path(temporary) / 'library'
            import_game(args.apk or args.ipa, args.episodes, directory)
            result = audit(directory)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return bool(result['failures'])


if __name__ == '__main__':
    raise SystemExit(main())
