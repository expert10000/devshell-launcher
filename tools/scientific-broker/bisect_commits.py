"""Isolated scientific Git bisect with explicit good/bad/skip evidence."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import uuid

from compare_commits import evaluate, resolve_commit
from source_snapshot import git
from telemetry import host_fingerprint


def classify(case):
    if case['build']['state'] != 'passed':
        return 'skip', 'Broker build failed or timed out.'
    if case['tests']['state'] != 'passed':
        log = Path(case['tests']['log']).read_text(encoding='utf-8', errors='replace')
        failures = re.search(r'FAILED \(failures=([1-9][0-9]*)(?:, errors=0)?\)', log)
        if failures and 'ERROR:' not in log and case['tests'].get('testCount', 0) > 0:
            return 'bad', 'Scientific assertion failed in the fixed reload suite.'
        return 'skip', 'Test setup, import, execution or timeout failed.'
    if case['mesh']['state'] != 'passed':
        if case['mesh'].get('diagnosticTail') == 'The fixed tetrahedron geometry contract failed.':
            return 'bad', 'Fixed mesh geometry, orientation or scale changed.'
        return 'skip', 'Mesh inspection failed without a valid scientific verdict.'
    return 'good', 'Build, scientific tests and fixed mesh contract passed.'


def search(commits, check):
    """Return an exact first-bad commit only when no skipped commit remains in its boundary."""
    if len(commits) < 2:
        raise ValueError('Bisect requires distinct endpoint commits.')
    labels = {}

    def label(index):
        if index not in labels:
            labels[index] = check(commits[index])
        return labels[index]

    first, last = label(0), label(len(commits) - 1)
    if first != 'good' or last != 'bad':
        return {'verdict': 'invalid-endpoints', 'firstBad': None, 'boundary': [commits[0], commits[-1]], 'labels': labels}
    low, high = 0, len(commits) - 1
    while high - low > 1:
        candidates = [index for index in range(low + 1, high) if index not in labels]
        if not candidates:
            break
        mid = (low + high) // 2
        index = min(candidates, key=lambda item: (abs(item - mid), item))
        result = label(index)
        if result == 'good':
            low = index
        elif result == 'bad':
            high = index
        elif result != 'skip':
            raise ValueError('Bisect evaluator must return good, bad or skip.')
    exact = high == low + 1
    return {'verdict': 'first-bad' if exact else 'inconclusive',
            'firstBad': commits[high] if exact else None,
            'boundary': [commits[low], commits[high]], 'labels': labels}


def linear_commits(repo, good, bad):
    full_good = resolve_commit(repo, good)
    full_bad = resolve_commit(repo, bad)
    if full_good == full_bad:
        raise ValueError('Good and bad endpoints must differ.')
    chain = git(repo, 'rev-list', '--first-parent', full_bad).decode().splitlines()
    if full_good not in chain:
        raise ValueError('Good endpoint is not on the bad endpoint first-parent chain.')
    return list(reversed(chain[:chain.index(full_good) + 1]))


def run_bisect(repo, good, bad, output_root):
    repo = Path(git(repo, 'rev-parse', '--show-toplevel').decode().strip()).resolve()
    commits = linear_commits(repo, good, bad)
    dotnet = shutil.which('dotnet')
    if not dotnet:
        raise ValueError('dotnet SDK is required for scientific bisect.')
    python = str(Path(sys.executable).resolve())
    dotnet = str(Path(dotnet).resolve())
    run_id = uuid.uuid4().hex
    output = Path(output_root).resolve() / run_id
    output.mkdir(parents=True)
    environment = {'hostFingerprintSha256': host_fingerprint(), 'python': python,
                   'pythonVersion': platform.python_version(), 'dotnet': dotnet,
                   'dotnetVersion': subprocess.check_output([dotnet, '--version'], text=True).strip(),
                   'platform': platform.platform()}
    evidence = {}

    def check(commit):
        destination = output / commit
        destination.mkdir()
        with tempfile.TemporaryDirectory(prefix='scientific-bisect-') as temporary:
            root = Path(temporary).resolve()
            worktree = root / 'source'
            if not worktree.resolve().is_relative_to(root):
                raise ValueError('Temporary worktree escaped its root.')
            git(repo, 'worktree', 'add', '--detach', str(worktree), commit)
            try:
                try:
                    case = evaluate(worktree, destination / 'matrix', python, dotnet)
                    verdict, reason = classify(case)
                except (OSError, ValueError, subprocess.TimeoutExpired) as error:
                    case, verdict, reason = None, 'skip', f'Build or test infrastructure unavailable: {str(error)[:300]}'
            finally:
                git(repo, 'worktree', 'remove', '--force', str(worktree))
        record = {'commit': commit, 'tree': git(repo, 'rev-parse', commit + '^{tree}').decode().strip(),
                  'classification': verdict, 'reason': reason,
                  'environmentFingerprintSha256': hashlib.sha256(json.dumps(environment, sort_keys=True).encode()).hexdigest(),
                  'case': case}
        path = destination / 'classification.json'
        with path.open('x', encoding='utf-8') as stream:
            json.dump(record, stream, separators=(',', ':'))
        evidence[commit] = {'classification': verdict, 'reason': reason, 'record': str(path),
                            'recordSha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        return verdict

    decision = search(commits, check)
    report = {'schemaVersion': 1, 'suiteId': 'scientific-git-bisect-v1', 'bisectId': run_id,
              'createdAtUtc': datetime.now(timezone.utc).isoformat(), 'scope': 'linear first-parent history',
              'goodEndpoint': commits[0], 'badEndpoint': commits[-1], 'commitCount': len(commits),
              'environment': environment, 'verdict': decision['verdict'],
              'firstBadCommit': decision['firstBad'], 'boundary': decision['boundary'],
              'examined': evidence, 'replay': f'python tools/scientific-broker/bisect_commits.py --repo "{repo}" --good {commits[0]} --bad {commits[-1]} --output-root "{Path(output_root).resolve()}"'}
    path = output / 'bisect.json'
    with path.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, separators=(',', ':'))
    return path, report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True)
    parser.add_argument('--good', required=True)
    parser.add_argument('--bad', required=True)
    parser.add_argument('--output-root', required=True)
    args = parser.parse_args()
    path, report = run_bisect(args.repo, args.good, args.bad, args.output_root)
    print(json.dumps({'record': str(path), 'verdict': report['verdict'],
                      'firstBadCommit': report['firstBadCommit'], 'boundary': report['boundary'],
                      'examined': {commit: item['classification'] for commit, item in report['examined'].items()}}, indent=2))


if __name__ == '__main__':
    main()
