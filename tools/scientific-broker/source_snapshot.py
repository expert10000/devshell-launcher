"""Read-only Git source identities for scientific run evidence."""
import hashlib
import json
import os
from pathlib import Path
import subprocess


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git(root, *args):
    result = subprocess.run(['git', '-C', str(root), *args], capture_output=True, timeout=30)
    if result.returncode:
        raise ValueError(result.stderr.decode('utf-8', 'replace').strip() or f'git {args[0]} failed')
    return result.stdout


def repository_snapshot(path):
    """Capture HEAD, worktree identity, and content hashes without changing Git state."""
    path = Path(path).resolve(strict=True)
    root = Path(git(path, 'rev-parse', '--show-toplevel').decode().strip()).resolve()
    commit = git(root, 'rev-parse', 'HEAD').decode().strip()
    tree = git(root, 'rev-parse', 'HEAD^{tree}').decode().strip()
    git_dir = Path(git(root, 'rev-parse', '--absolute-git-dir').decode().strip()).resolve()
    branch_result = subprocess.run(['git', '-C', str(root), 'symbolic-ref', '--quiet', '--short', 'HEAD'],
                                   capture_output=True, timeout=30)
    branch = branch_result.stdout.decode().strip() if branch_result.returncode == 0 else None
    patch = git(root, 'diff', '--binary', 'HEAD', '--')
    untracked = []
    for raw in git(root, 'ls-files', '--others', '--exclude-standard', '-z').split(b'\0'):
        if not raw:
            continue
        relative = raw.decode('utf-8', 'surrogateescape')
        source = root / relative
        if source.is_symlink():
            untracked.append({'path': relative.replace('\\', '/'), 'kind': 'symlink',
                              'sha256': digest(os.readlink(source).encode('utf-8', 'surrogateescape'))})
        elif source.is_file():
            checksum = hashlib.sha256()
            with source.open('rb') as stream:
                for block in iter(lambda: stream.read(65536), b''):
                    checksum.update(block)
            untracked.append({'path': relative.replace('\\', '/'), 'kind': 'file', 'sha256': checksum.hexdigest()})
    dirty = bool(patch or untracked)
    dirty_identity = {'trackedPatchSha256': digest(patch) if patch else None, 'untracked': untracked}
    snapshot = {'schemaVersion': 1, 'repository': str(root), 'gitDirectory': str(git_dir),
                'worktree': str(root), 'branch': branch, 'commit': commit, 'tree': tree,
                'dirty': dirty, **dirty_identity,
                'dirtyDigestSha256': digest(json.dumps(dirty_identity, sort_keys=True, separators=(',', ':')).encode())
                if dirty else None}
    snapshot['snapshotId'] = digest(json.dumps(snapshot, sort_keys=True, separators=(',', ':')).encode())
    return snapshot


def capture_sources(roots):
    repositories = {}
    for name, path in roots.items():
        if path is None:
            continue
        try:
            repositories[name] = {'state': 'captured', **repository_snapshot(path)}
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            repositories[name] = {'state': 'unavailable', 'requestedPath': str(path), 'reason': str(error)[:300]}
    return {'schemaVersion': 1, 'repositories': repositories}
