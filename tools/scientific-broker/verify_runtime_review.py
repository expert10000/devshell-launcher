"""Verify the local UI review archive against its source-controlled baseline."""

import argparse
import hashlib
import json
import re
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / 'docs/evidence/scientific-runtime-review-baseline.v1.json'
MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
MAX_IMAGE_BYTES = 2 * 1024 * 1024


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify(archive_path, baseline_path=BASELINE):
    baseline = json.loads(Path(baseline_path).read_text(encoding='utf-8'))
    if baseline.get('schemaVersion') != 1 or baseline.get('kind') != 'devshell.scientific-runtime-review-baseline':
        raise ValueError('Unsupported runtime review baseline.')
    archive_path = Path(archive_path).resolve(strict=True)
    if archive_path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError('Runtime review archive exceeds the size limit.')
    if digest(archive_path.read_bytes()) != baseline['archiveSha256']:
        raise ValueError('Runtime review archive hash changed.')
    expected_manifest = (ROOT / baseline['manifestPath']).resolve(strict=True)
    if not expected_manifest.is_relative_to(ROOT) or digest(expected_manifest.read_bytes()) != baseline['manifestSha256']:
        raise ValueError('Source-controlled review manifest changed.')
    with zipfile.ZipFile(archive_path) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if len(names) != len(set(names)):
            raise ValueError('Runtime review archive has duplicate entries.')
        for entry in entries:
            name = PurePosixPath(entry.filename)
            if name.is_absolute() or '..' in name.parts or '\\' in entry.filename or entry.is_dir():
                raise ValueError('Runtime review archive contains an unsafe path.')
            if entry.file_size > MAX_IMAGE_BYTES and entry.filename.endswith('.jpg'):
                raise ValueError('Runtime review image exceeds the size limit.')
        if 'manifest.json' not in names or digest(archive.read('manifest.json')) != baseline['manifestSha256']:
            raise ValueError('Archive review manifest changed.')
        if not {'README.md', 'index.html', 'captions.md'} <= set(names):
            raise ValueError('Review navigation or captions are missing.')
        manifest = json.loads(archive.read('manifest.json'))
        records = manifest.get('screenshots', [])
        count = len(baseline['expectedProviders']) * baseline['screenshotsPerProvider']
        if (manifest.get('schemaVersion') != 1 or manifest.get('sourceCommit') != baseline['sourceCommit']
                or manifest.get('screenshotCount') != count or len(records) != count):
            raise ValueError('Runtime review source or screenshot count changed.')
        if Counter(item['provider'] for item in records) != {
                provider: baseline['screenshotsPerProvider'] for provider in baseline['expectedProviders']}:
            raise ValueError('Runtime review provider coverage changed.')
        paths = [item['file'] for item in records]
        if len(paths) != len(set(paths)) or len({item['sha256'] for item in records}) != count:
            raise ValueError('Runtime review image identity repeated.')
        if set(names) != set(paths) | {'manifest.json', 'README.md', 'index.html', 'captions.md'}:
            raise ValueError('Runtime review archive has missing or unexpected files.')
        for item in records:
            if (not re.fullmatch(r'screenshots/[0-9]{3}_[a-z0-9_-]+\.jpg', item['file'])
                    or not re.fullmatch(r'[a-f0-9]{64}', item['sha256'])
                    or digest(archive.read(item['file'])) != item['sha256']):
                raise ValueError(f"Runtime review image changed: {item['file']}")
    return {'verdict': 'verified-recorded-ui-only', 'sourceCommit': baseline['sourceCommit'],
            'screenshots': count, 'archiveSha256': baseline['archiveSha256']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.archive), indent=2))
