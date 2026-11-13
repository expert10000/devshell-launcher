"""Publish a verified six-capability ZIP under a content-addressed GitHub release asset."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from portable_six_evidence import verify as verify_bundle


def command(args, cwd, check=True):
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    if check and result.returncode:
        raise ValueError('Publication command failed: ' + ' '.join(args[:3]) + ': ' + result.stderr[-600:])
    return result


def publish(record_path, repo):
    repo = Path(repo).resolve(strict=True)
    record = json.loads(Path(record_path).resolve(strict=True).read_text(encoding='utf-8'))
    if record.get('kind') != 'scientific.six-inspect-publication':
        raise ValueError('Expected a six-capability inspection publication.')
    head = command(['git', 'rev-parse', 'HEAD'], repo).stdout.strip()
    remote = command(['git', 'ls-remote', 'origin', 'refs/heads/main'], repo).stdout.split()[0]
    if record['sourceCommit'] != head or head != remote:
        raise ValueError('Publication source must match pushed remote main.')
    bundle = Path(record['bundle']).resolve(strict=True)
    trust = repo / 'schemas/scientific-evidence-trust.v1.json'
    verdict = verify_bundle(bundle, trust)
    if verdict['signature'] != 'trusted' or verdict['manifestSha256'] != record['manifestSha256']:
        raise ValueError('Portable evidence signature or manifest differs from publication.')
    digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
    tag = 'scientific-six-' + head[:12]
    asset = 'six-capability-' + digest + '.zip'
    existing = command(['gh', 'release', 'view', tag, '--json', 'assets,url,targetCommitish'], repo, check=False)
    if existing.returncode:
        command(['gh', 'release', 'create', tag, '--target', head, '--title',
                 'Scientific six-capability evidence ' + head[:12],
                 '--notes', 'Signed portable inspection evidence. Verify with portable_six_evidence.py and the repository trust store.'], repo)
        existing = command(['gh', 'release', 'view', tag, '--json', 'assets,url,targetCommitish'], repo)
    release = json.loads(existing.stdout)
    if release['targetCommitish'] != head:
        raise ValueError('Release tag points at another source commit.')
    assets = {item['name'] for item in release['assets']}
    if any(name.startswith('six-capability-') and name != asset for name in assets):
        raise ValueError('Release already contains a different evidence bundle.')
    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder) / asset
        if asset not in assets:
            shutil.copyfile(bundle, target)
            command(['gh', 'release', 'upload', tag, str(target)], repo)
            target.unlink()
        command(['gh', 'release', 'download', tag, '--pattern', asset, '--dir', folder], repo)
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError('Downloaded release asset bytes differ from local bundle.')
        downloaded = verify_bundle(target, trust)
        if downloaded['manifestSha256'] != verdict['manifestSha256'] or downloaded['signature'] != 'trusted':
            raise ValueError('Downloaded release asset failed offline verification.')
    return {'release': release['url'], 'asset': asset, 'bundleSha256': digest,
            'manifestSha256': verdict['manifestSha256'], 'sourceCommit': head}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--publication', required=True)
    parser.add_argument('--repo', default='.')
    options = parser.parse_args()
    print(json.dumps(publish(options.publication, options.repo), indent=2))
