"""Trace each local EXP to the first pending action; emit a compact audit."""
import json
from pathlib import Path
import sys

from exp_runtime.trace import trace_archive


def main():
    results = []
    for root in sys.argv[1:] or ['Episodes', 'extract/assets/Assets']:
        path = Path(root)
        archives = sorted(path.rglob('*.exp')) if path.is_dir() else [path]
        for archive in archives:
            try:
                trace = trace_archive(archive)
                last = trace['events'][-1] if trace['events'] else {}
                results.append(dict(
                    archive=str(archive), sha256=trace['sha256'], status=trace['status'],
                    scene=trace['scene'], pc=trace['pc'], steps=trace['steps'],
                    actions=len(trace['events']), error=trace['error'],
                    last_yield=last.get('request', {}).get('yield_id'),
                ))
            except Exception as exc:
                results.append(dict(archive=str(archive), status='error', error=str(exc)))
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
