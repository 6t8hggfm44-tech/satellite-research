#!/usr/bin/env python3
"""Hash a reviewed evidence directory without following symlinks or hashing itself."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.directory.resolve()
    if not root.is_dir():
        parser.error('directory must exist')
    if args.output.is_symlink():
        parser.error('output must not be a symlink')
    output = args.output.resolve()
    entries = []
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            parser.error(f'symlink must be reviewed and removed from evidence scope: {path.relative_to(root)}')
        if not path.is_file() or path.resolve() == output:
            continue
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block)
        entries.append({'path': path.relative_to(root).as_posix(), 'bytes': path.stat().st_size,
                        'sha256': digest.hexdigest()})
    manifest = {'schemaVersion': 1, 'createdAtUTC': datetime.now(timezone.utc).isoformat(),
                'algorithm': 'sha256', 'fileCount': len(entries),
                'totalBytes': sum(e['bytes'] for e in entries), 'files': entries,
                'note': 'Hashes establish preserved-byte identity, not measurement authenticity or permission to publish.'}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'fileCount': manifest['fileCount'], 'totalBytes': manifest['totalBytes']}))


if __name__ == '__main__':
    main()
