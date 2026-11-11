"""Sealed L5/L6 qualification for the versioned orientation scope."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

from scientific_cgal_corpus import sha as file_sha
from scientific_cgal_orientation_scope import (ADAPTER, CASES, CONTRACT, MANIFEST, WORKER_SOURCE,
                                                manifest, run as live_scope, verify as verify_scope)

SOURCE = Path(__file__).resolve()


def sha(path):
    return file_sha(Path(path))


def base(kind):
    manifest()
    return {'schemaVersion': 1, 'kind': kind, 'verdict': 'passed',
            'createdAtUtc': datetime.now(timezone.utc).isoformat(),
            'capabilityId': 'mesh.orient', 'suiteId': 'cgal-orientation-v2',
            'manifestSha256': sha(MANIFEST), 'adapterSha256': sha(ADAPTER),
            'contractSha256': sha(CONTRACT), 'workerSourceSha256': sha(WORKER_SOURCE),
            'scopeSourceSha256': sha(Path(__file__).with_name('scientific_cgal_orientation_scope.py')),
            'qualificationSourceSha256': sha(SOURCE)}


def save(folder, name, report):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    with path.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, separators=(',', ':'), allow_nan=False)
    Path(str(path) + '.sha256').write_text(sha(path), encoding='utf-8')
    return path


def load(path, kind):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('Orientation qualification report seal changed.')
    report = json.loads(path.read_text(encoding='utf-8'))
    expected = base(kind)
    if any(report.get(key) != value for key, value in expected.items() if key != 'createdAtUtc'):
        raise ValueError('Orientation qualification source or identity changed.')
    return path, report


def run_l5(worker, prefix, output_root):
    folder = Path(output_root).resolve() / uuid.uuid4().hex
    folder.mkdir(parents=True)
    scope_path, scope = live_scope(worker, prefix, folder)
    report = {**base('scientific.cgal-orientation-L5'), 'scopePath': str(scope_path),
              'scopeSha256': sha(scope_path), 'workerPath': scope['workerPath'],
              'workerSha256': scope['workerSha256'], 'cases': scope['cases']}
    path = save(folder, 'l5.json', report)
    verify_l5(path)
    return path


def verify_l5(path):
    path, report = load(path, 'scientific.cgal-orientation-L5')
    scope_path = Path(report['scopePath']).resolve(strict=True)
    scope = verify_scope(scope_path)
    if (scope_path.parent.parent != path.parent or sha(scope_path) != report['scopeSha256']
            or report['workerSha256'] != scope['workerSha256']
            or report['workerPath'] != scope['workerPath'] or report['cases'] != scope['cases']
            or [item['caseId'] for item in report['cases']] != list(CASES)):
        raise ValueError('Orientation L5 case evidence changed.')
    return report


def run_l6(l5, output_root):
    baseline = verify_l5(l5)
    folder = Path(output_root).resolve() / uuid.uuid4().hex
    folder.mkdir(parents=True)
    replay_path, replay = live_scope(baseline['workerPath'],
                                    json.loads(Path(baseline['scopePath']).read_text())['prefix'], folder)
    compare_cases(baseline['cases'], replay['cases'])
    report = {**base('scientific.cgal-orientation-L6'), 'l5Path': str(Path(l5).resolve()),
              'l5Sha256': sha(Path(l5)), 'replayPath': str(replay_path), 'replaySha256': sha(replay_path),
              'comparison': 'state-and-output-sha256'}
    path = save(folder, 'l6.json', report)
    verify_l6(path)
    return path


def compare_cases(prior, replay):
    if (len(prior) != len(CASES) or len(replay) != len(CASES)
            or [(item['caseId'], item['state'], item['outputSha256']) for item in prior]
            != [(item['caseId'], item['state'], item['outputSha256']) for item in replay]):
        raise ValueError('Orientation L6 replay differs from its baseline.')


def verify_l6(path):
    path, report = load(path, 'scientific.cgal-orientation-L6')
    if (report['comparison'] != 'state-and-output-sha256'
            or sha(Path(report['l5Path'])) != report['l5Sha256']
            or sha(Path(report['replayPath'])) != report['replaySha256']
            or Path(report['replayPath']).resolve().parent.parent != path.parent):
        raise ValueError('Orientation L6 baseline or replay link changed.')
    baseline = verify_l5(report['l5Path'])
    replay = verify_scope(report['replayPath'])
    compare_cases(baseline['cases'], replay['cases'])
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('l5', 'l6', 'verify'))
    parser.add_argument('--worker')
    parser.add_argument('--prefix')
    parser.add_argument('--source')
    parser.add_argument('--output-root')
    args = parser.parse_args()
    if args.command == 'l5':
        target = run_l5(args.worker, args.prefix, args.output_root)
    elif args.command == 'l6':
        target = run_l6(args.source, args.output_root)
    else:
        target = Path(args.source).resolve()
        (verify_l5 if target.name == 'l5.json' else verify_l6)(target)
    print(json.dumps({'report': str(target), 'sha256': sha(target)}))
