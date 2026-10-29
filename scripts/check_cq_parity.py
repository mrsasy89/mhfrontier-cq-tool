"""Check pinned CQ source parity and the narrow, reviewed integration exceptions."""
import argparse
import hashlib
import json
from pathlib import Path


def check(project):
    project = Path(project)
    manifest = json.loads((project / 'docs/cq-baseline.json').read_text(encoding='utf-8'))
    source = project / 'desktop' if (project / 'desktop/src').is_dir() else project
    problems = []
    unchanged = exceptions = 0
    for row in manifest['files']:
        path = source / row['path']
        if not path.is_file():
            problems.append('Missing CQ baseline file: ' + row['path']); continue
        current = hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
        expected = row.get('expected_sha256', row['baseline_sha256'])
        if current != expected:
            problems.append('Unreviewed CQ source drift: ' + row['path'])
        if 'exception' in row:
            exceptions += 1
        else:
            unchanged += 1
    return {'revision': manifest['revision'], 'unchanged_files': unchanged,
            'documented_exceptions': exceptions, 'problems': problems}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    result = check(parser.parse_args().root)
    print(json.dumps(result, indent=2))
    raise SystemExit(bool(result['problems']))
