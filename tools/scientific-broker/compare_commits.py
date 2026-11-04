"""DS-SCI-031: isolated, identical scientific build/test/mesh matrix for two commits."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import uuid

from source_snapshot import git, repository_snapshot
from telemetry import host_fingerprint


TETRA = (b'v 1 1 1\nv -1 -1 1\nv -1 1 -1\nv 1 -1 -1\n'
         b'f 1 3 2\nf 1 2 4\nf 1 4 3\nf 2 3 4\n')
SUITE_ID = 'scientific-commit-matrix-v1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def resolve_commit(repo, value):
    commit = git(repo, 'rev-parse', '--verify', value + '^{commit}').decode().strip()
    if len(commit) not in (40, 64):
        raise ValueError('Git did not resolve a full commit identity.')
    return commit


def run_command(command, cwd, log_path, timeout=180):
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, timeout=timeout)
        output = result.stdout + b'\n--- stderr ---\n' + result.stderr
        state = 'passed' if result.returncode == 0 else 'failed'
        exit_code = result.returncode
    except subprocess.TimeoutExpired as error:
        output = (error.stdout or b'') + b'\n--- timeout stderr ---\n' + (error.stderr or b'')
        state = 'timed-out'
        exit_code = None
    log_path.write_bytes(output)
    return {'state': state, 'exitCode': exit_code, 'log': str(log_path), 'logSha256': sha(log_path),
            'diagnosticTail': output.decode('utf-8', 'replace')[-1500:] if state != 'passed' else None}


def evaluate(worktree, destination, python, dotnet):
    destination.mkdir(parents=True)
    source = repository_snapshot(worktree)
    if source['dirty']:
        raise ValueError('The isolated worktree is dirty before execution.')
    parser = worktree / 'tools' / 'scientific-artifact-roundtrip.py'
    test = worktree / 'tests' / 'test_scientific_artifact_roundtrip.py'
    project = worktree / 'tools' / 'scientific-broker' / 'ScientificBroker.csproj'
    for path in (parser, test, project):
        if not path.is_file():
            raise ValueError(f'The selected commit lacks required suite source: {path.relative_to(worktree)}')
    case = {'source': source, 'suiteRevision': {'parserSha256': sha(parser), 'testSha256': sha(test),
            'projectSha256': sha(project)}}
    case['build'] = run_command([dotnet, 'build', str(project), '--nologo', '-v', 'quiet'],
                                worktree, destination / 'build.log')
    case['tests'] = run_command([python, '-m', 'unittest', 'discover', '-s', 'tests',
                                  '-p', 'test_scientific_artifact_roundtrip.py', '-v'],
                                 worktree, destination / 'tests.log')
    test_output = (destination / 'tests.log').read_text(encoding='utf-8', errors='replace')
    count = re.search(r'Ran ([1-9][0-9]*) tests? in ', test_output)
    case['tests']['testCount'] = int(count.group(1)) if count else 0
    if case['tests']['state'] == 'passed' and not count:
        case['tests'].update(state='failed', diagnosticTail='The selected scientific suite ran zero tests.')
    fixture = destination / 'fixed-tetrahedron.obj'
    fixture.write_bytes(TETRA)
    result_path = destination / 'mesh-result.json'
    case['mesh'] = run_command([python, str(parser), '--input', str(fixture), '--result', str(result_path)],
                               worktree, destination / 'mesh.log')
    case['inputSha256'] = sha(fixture)
    if case['mesh']['state'] == 'passed':
        case['meshResult'] = json.loads(result_path.read_text(encoding='utf-8'))
        case['meshResultSha256'] = sha(result_path)
        mesh = case['meshResult']
        if (mesh.get('format') != 'obj' or mesh.get('points') != 4 or mesh.get('triangles') != 4 or
                mesh.get('bounds') != [-1.0, 1.0] * 3 or mesh.get('boundaryEdges') != 0 or
                mesh.get('nonManifoldEdges') != 0 or mesh.get('closed') is not True or
                abs(mesh.get('absoluteVolume', 0) - 8 / 3) > 1e-9 or
                abs(mesh.get('signedVolume', 0) - 8 / 3) > 1e-9 or
                abs(mesh.get('surfaceArea', 0) - 8 * math.sqrt(3)) > 1e-9):
            case['mesh'].update(state='failed', diagnosticTail='The fixed tetrahedron geometry contract failed.')
    return case


def compare(repo, baseline, candidate, output_root):
    repo = Path(git(repo, 'rev-parse', '--show-toplevel').decode().strip()).resolve()
    baseline_commit = resolve_commit(repo, baseline)
    candidate_commit = resolve_commit(repo, candidate)
    if baseline_commit == candidate_commit:
        raise ValueError('Baseline and candidate must be different commits.')
    python = str(Path(sys.executable).resolve())
    dotnet = shutil.which('dotnet')
    if not dotnet:
        raise ValueError('dotnet SDK is required for the two-source build matrix.')
    dotnet = str(Path(dotnet).resolve())
    run_id = uuid.uuid4().hex
    output = Path(output_root).resolve() / run_id
    output.mkdir(parents=True)
    report = {'schemaVersion': 1, 'suiteId': SUITE_ID, 'comparisonId': run_id,
              'createdAtUtc': datetime.now(timezone.utc).isoformat(),
              'hostFingerprintSha256': host_fingerprint(),
              'environment': {'pythonExecutable': python, 'pythonVersion': platform.python_version(),
                              'dotnetExecutable': dotnet, 'dotnetVersion': subprocess.check_output([dotnet, '--version'], text=True).strip(),
                              'platform': platform.platform()},
              'fixtureSha256': hashlib.sha256(TETRA).hexdigest(),
              'changedPaths': git(repo, 'diff', '--name-status', baseline_commit, candidate_commit).decode('utf-8', 'replace').splitlines(),
              'cases': {}}
    environment_sha = hashlib.sha256(json.dumps({'host': report['hostFingerprintSha256'],
        'tools': report['environment']}, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    with tempfile.TemporaryDirectory(prefix='scientific-commit-matrix-') as temp:
        temp_root = Path(temp).resolve()
        for label, commit in [('baseline', baseline_commit), ('candidate', candidate_commit)]:
            worktree = temp_root / label
            if not worktree.resolve().is_relative_to(temp_root):
                raise ValueError('Worktree escaped its temporary root.')
            git(repo, 'worktree', 'add', '--detach', str(worktree), commit)
            try:
                report['cases'][label] = evaluate(worktree, output / label, python, dotnet)
                report['cases'][label]['environmentFingerprintSha256'] = environment_sha
                if report['cases'][label]['source']['commit'] != commit:
                    raise ValueError('Worktree HEAD differs from selected commit.')
            finally:
                git(repo, 'worktree', 'remove', '--force', str(worktree))
    first, second = report['cases']['baseline'], report['cases']['candidate']
    stages = ('build', 'tests', 'mesh')
    both_pass = all(first[key]['state'] == second[key]['state'] == 'passed' for key in stages)
    geometry_keys = ('format', 'points', 'triangles', 'bounds', 'boundaryEdges',
                     'nonManifoldEdges', 'closed', 'absoluteVolume', 'signedVolume', 'surfaceArea')
    geometry_diff = {key: {'baseline': first['meshResult'].get(key), 'candidate': second['meshResult'].get(key)}
                     for key in geometry_keys if 'meshResult' in first and 'meshResult' in second and
                     first['meshResult'].get(key) != second['meshResult'].get(key)}
    report['evidenceDiff'] = {'buildStates': [first['build']['state'], second['build']['state']],
                              'testStates': [first['tests']['state'], second['tests']['state']],
                              'meshStates': [first['mesh']['state'], second['mesh']['state']],
                              'geometry': geometry_diff,
                              'suiteRevisionChanged': first['suiteRevision'] != second['suiteRevision']}
    report['verdict'] = 'inconclusive' if not both_pass else 'different' if geometry_diff else 'equivalent'
    report['qualificationImpact'] = 'none; this source matrix does not certify a broker runtime or worker binary'
    report_path = output / 'comparison.json'
    with report_path.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, separators=(',', ':'))
    return report_path, report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True)
    parser.add_argument('--baseline', required=True)
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--output-root', required=True)
    args = parser.parse_args()
    path, report = compare(args.repo, args.baseline, args.candidate, args.output_root)
    print(json.dumps({'record': str(path), 'comparisonId': report['comparisonId'],
                      'verdict': report['verdict'], 'baselineCommit': report['cases']['baseline']['source']['commit'],
                      'candidateCommit': report['cases']['candidate']['source']['commit'],
                      'evidenceDiff': report['evidenceDiff']}, indent=2))


if __name__ == '__main__':
    main()
