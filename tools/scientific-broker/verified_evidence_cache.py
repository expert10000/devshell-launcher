"""Process-local reuse of completed semantic checks, guarded by every input byte."""
import hashlib
from copy import deepcopy
from pathlib import Path
import subprocess


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def witness(roots):
    result = hashlib.sha256()
    for root in roots:
        if Path(root).is_symlink():
            raise ValueError('Evidence witness cannot follow a symlink.')
        root = Path(root).resolve(strict=True)
        entries = [] if root.is_file() else list(root.rglob('*'))
        if any(path.is_symlink() for path in entries):
            raise ValueError('Evidence witness cannot follow a symlink.')
        files = [root] if root.is_file() else sorted(path for path in entries if path.is_file())
        for path in files:
            if path.is_symlink():
                raise ValueError('Evidence witness cannot follow a symlink.')
            name = '.' if path == root else path.relative_to(root).as_posix()
            result.update(str(root).encode('utf-8'))
            result.update(name.encode('utf-8'))
            result.update(bytes.fromhex(sha(path)))
    return result.hexdigest()


def sealed_files(root):
    """Freeze the files in a verified record tree before unrelated jobs are added."""
    if Path(root).is_symlink():
        raise ValueError('Evidence witness cannot follow a symlink.')
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Verified evidence root must be a real directory.')
    entries = sorted(root.rglob('*'))
    if any(path.is_symlink() for path in entries):
        raise ValueError('Evidence witness cannot follow a symlink.')
    return tuple(path for path in entries if path.is_file())


class VerifiedEvidenceCache:
    def __init__(self):
        self._entries = {}
        self._source = None

    def bind_source(self, repo, expected_commit):
        self._source = (Path(repo).resolve(strict=True), expected_commit,
                        self._source_witness(repo))

    @staticmethod
    def _source_witness(repo):
        repo = str(repo)
        head = subprocess.run(['git', '-C', repo, 'rev-parse', 'HEAD'], capture_output=True,
                              check=True).stdout.strip()
        diff = subprocess.run(['git', '-C', repo, 'diff', '--binary', 'HEAD'], capture_output=True,
                              check=True).stdout
        untracked = subprocess.run(['git', '-C', repo, 'ls-files', '-z', '--others', '--exclude-standard'],
                                   capture_output=True, check=True).stdout
        untracked_digest = hashlib.sha256()
        for name in sorted(item for item in untracked.split(b'\0') if item):
            untracked_digest.update(name)
            untracked_digest.update(bytes.fromhex(sha(Path(repo) / name.decode('utf-8'))))
        return (head.decode('ascii'), hashlib.sha256(diff).hexdigest(),
                untracked_digest.hexdigest())

    def check_source(self, repo, expected_commit):
        if (not self._source or self._source[:2] != (Path(repo).resolve(strict=True), expected_commit)
                or self._source[2] != self._source_witness(repo)
                or self._source[2][0] != expected_commit):
            raise ValueError('Publication source drifted after verification.')

    def add(self, name, path, value, roots=None):
        path = Path(path).resolve(strict=True)
        roots = tuple(Path(item).absolute() for item in (roots or (path.parent,)))
        self._entries[name] = (path, sha(path), roots, witness(roots), deepcopy(value))

    def get(self, name, path):
        if name not in self._entries:
            raise ValueError(name + ' has no verified evidence in this publication run.')
        saved_path, digest, roots, tree, value = self._entries[name]
        if Path(path).resolve(strict=True) != saved_path or sha(saved_path) != digest or witness(roots) != tree:
            raise ValueError(name + ' verified evidence changed after qualification.')
        return deepcopy(value)
