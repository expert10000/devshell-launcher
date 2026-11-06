"""Reviewed, hash-pinned failure fixtures for the fixed certified CGAL broker path."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
from broker import Broker, sha

HEX32 = re.compile(r'[0-9a-f]{32}\Z')
REVIEWER = re.compile(r'[A-Za-z0-9_.@-]{3,80}\Z')
FAILURES = {'failed', 'partial', 'timed-out', 'resource-exhausted'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, separators=(',', ':'))
    Path(str(path) + '.sha256').write_text(sha(path), encoding='utf-8')
    return path


def read(path, kind):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('Regression record hash mismatch.')
    value = json.loads(path.read_text(encoding='utf-8'))
    if value.get('schemaVersion') != 1 or value.get('kind') != kind:
        raise ValueError('Regression record contract mismatch.')
    return value


def source_failure(broker, job_id):
    if not HEX32.fullmatch(job_id) or job_id not in broker.jobs:
        raise ValueError('Source broker job is unavailable.')
    job = broker.snapshot(broker.jobs[job_id])
    entry = broker.capabilities[0]
    if (job.get('state') not in FAILURES or job.get('runtimeId') != 'cgal-win-conda'
            or job.get('capabilityId') != 'mesh.interop.vtk-math3d'
            or job.get('certificationRecordId') != entry['recordId'] or job.get('artifacts')):
        raise ValueError('Source is not a failed run of the current certified capability.')
    broker.source(job_id)
    request = json.loads((Path(job['directory']) / 'request.json').read_text(encoding='utf-8'))
    inputs = request.get('inputArtifacts', [])
    if (request.get('runId') != job_id or len(inputs) != 1
            or inputs[0].get('sha256') != entry['referenceInputSha256']
            or request.get('timeoutSeconds') is None):
        raise ValueError('Source input or request identity differs from fixed public fixture.')
    return job, request


def draft(config_path, job_id, output_root):
    broker = Broker(config_path)
    job, request = source_failure(broker, job_id)
    proposal = {'schemaVersion': 1, 'kind': 'scientific.regression-draft',
                'draftId': uuid.uuid4().hex, 'createdAtUtc': datetime.now(timezone.utc).isoformat(),
                'sourceJobId': job_id, 'runtimeId': job['runtimeId'], 'capabilityId': job['capabilityId'],
                'expectedState': job['state'], 'inputFixtureId': 'math3d.basic.01_tetrahedron',
                'inputSha256': broker.capabilities[0]['referenceInputSha256'],
                'certificationRecordId': job['certificationRecordId'],
                'sourceSnapshotSha256': job['sourceSnapshotSha256'],
                'manifestSha256': sha(broker.paths['manifest']),
                'contractVersion': job['contractVersion'], 'timeoutSeconds': request['timeoutSeconds'],
                'memoryLimitMiB': broker.memory_limit_mib,
                'privacy': {'inputScope': 'fixed-registered-fixture', 'rawInputIncluded': False,
                            'logsIncluded': False, 'pathsIncluded': False},
                'reviewStatus': 'pending'}
    return save(Path(output_root) / 'drafts' / (proposal['draftId'] + '.json'), proposal)


def replay_once(broker, expected):
    source = broker.paths['datasetRoot'] / 'math3d' / 'basic' / '01_tetrahedron.obj'
    if sha(source) != expected['inputSha256']:
        raise ValueError('Registered public input fixture changed.')
    job = broker.submit({'schemaVersion': 1, 'runtimeId': 'cgal-win-conda',
                         'capabilityId': 'mesh.interop.vtk-math3d',
                         'input': {'path': str(source), 'sha256': expected['inputSha256']},
                         'timeoutSeconds': expected['timeoutSeconds']})
    deadline = time.monotonic() + expected['timeoutSeconds'] + 15
    while job['state'] == 'running' and time.monotonic() < deadline:
        time.sleep(0.05)
        job = broker.snapshot(broker.jobs[job['jobId']])
    if job['state'] == 'running':
        broker.cancel(job['jobId'])
        raise TimeoutError('Regression replay did not reach a terminal state.')
    broker.source(job['jobId'])
    return {'jobId': job['jobId'], 'state': job['state'], 'artifactCount': len(job['artifacts']),
            'certificationRecordId': job['certificationRecordId'],
            'sourceSnapshotSha256': job['sourceSnapshotSha256']}


def promote(config_path, draft_path, reviewer, approve_public_fixture, output_root):
    if not approve_public_fixture or not REVIEWER.fullmatch(reviewer):
        raise ValueError('A named review and explicit public-fixture approval are required.')
    proposal = read(draft_path, 'scientific.regression-draft')
    if proposal.get('reviewStatus') != 'pending' or proposal.get('privacy', {}).get('rawInputIncluded'):
        raise ValueError('Draft is not eligible for reviewed promotion.')
    broker = Broker(config_path)
    source, _ = source_failure(broker, proposal['sourceJobId'])
    if (source['state'] != proposal['expectedState']
            or broker.memory_limit_mib != proposal['memoryLimitMiB']
            or broker.capabilities[0]['referenceInputSha256'] != proposal['inputSha256']
            or sha(broker.paths['manifest']) != proposal['manifestSha256']):
        raise ValueError('Source failure, resource policy or qualification changed.')
    replays = [replay_once(broker, proposal) for _ in range(2)]
    passed = all(item['state'] == proposal['expectedState'] and item['artifactCount'] == 0
                 and item['certificationRecordId'] == proposal['certificationRecordId'] for item in replays)
    review = {'schemaVersion': 1, 'kind': 'scientific.regression-review',
              'draftId': proposal['draftId'], 'draftSha256': sha(draft_path),
              'reviewedBy': reviewer, 'reviewedAtUtc': datetime.now(timezone.utc).isoformat(),
              'publicFixtureApproved': True, 'deterministicReplay': passed,
              'replays': replays, 'sourceJobId': proposal['sourceJobId']}
    review_path = save(Path(output_root) / 'reviews' / (uuid.uuid4().hex + '.json'), review)
    if not passed:
        return review_path, None
    fixture = {'schemaVersion': 1, 'kind': 'scientific.regression-fixture',
               'fixtureId': uuid.uuid4().hex, 'draftId': proposal['draftId'],
               'draftSha256': sha(draft_path), 'reviewSha256': sha(review_path),
               'reviewRecord': review_path.name, 'sourceJobId': proposal['sourceJobId'],
               'runtimeId': 'cgal-win-conda', 'capabilityId': 'mesh.interop.vtk-math3d',
               'expectedState': proposal['expectedState'], 'inputFixtureId': proposal['inputFixtureId'],
               'inputSha256': proposal['inputSha256'], 'certificationRecordId': proposal['certificationRecordId'],
               'manifestSha256': proposal['manifestSha256'], 'contractVersion': proposal['contractVersion'],
               'timeoutSeconds': proposal['timeoutSeconds'], 'memoryLimitMiB': proposal['memoryLimitMiB'],
               'privacy': proposal['privacy'], 'supportingReplayJobIds': [item['jobId'] for item in replays]}
    fixture['recordId'] = digest(fixture)
    fixture_path = save(Path(output_root) / 'fixtures' / (fixture['fixtureId'] + '.json'), fixture)
    return review_path, fixture_path


def verify_fixture(config_path, fixture_path, replay=False):
    fixture = read(fixture_path, 'scientific.regression-fixture')
    identity = dict(fixture)
    record_id = identity.pop('recordId', None)
    if record_id != digest(identity):
        raise ValueError('Regression fixture identity changed.')
    root = Path(fixture_path).resolve().parent.parent
    review_path = root / 'reviews' / fixture['reviewRecord']
    review = read(review_path, 'scientific.regression-review')
    draft_path = root / 'drafts' / (fixture['draftId'] + '.json')
    if (sha(review_path) != fixture['reviewSha256'] or sha(draft_path) != fixture['draftSha256']
            or review.get('draftSha256') != fixture['draftSha256']
            or not review.get('publicFixtureApproved') or not review.get('deterministicReplay')
            or not REVIEWER.fullmatch(review.get('reviewedBy', ''))
            or [item['jobId'] for item in review['replays']] != fixture['supportingReplayJobIds']):
        raise ValueError('Regression review or draft evidence changed.')
    broker = Broker(config_path)
    source, _ = source_failure(broker, fixture['sourceJobId'])
    if (source['state'] != fixture['expectedState'] or broker.memory_limit_mib != fixture['memoryLimitMiB']
            or sha(broker.paths['manifest']) != fixture['manifestSha256']):
        raise ValueError('Regression source or current policy changed.')
    for item in review['replays']:
        job, _ = source_failure(broker, item['jobId'])
        if (job['state'] != fixture['expectedState'] or job['artifacts']
                or job['sourceSnapshotSha256'] != item['sourceSnapshotSha256']):
            raise ValueError('Saved regression replay evidence changed.')
        broker.source(item['jobId'])
    result = replay_once(broker, fixture) if replay else None
    if result and (result['state'] != fixture['expectedState'] or result['artifactCount'] != 0):
        raise ValueError('Regression fixture did not replay deterministically.')
    return fixture, result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['draft', 'promote', 'verify', 'replay'])
    parser.add_argument('--config', required=True)
    parser.add_argument('--job-id')
    parser.add_argument('--draft')
    parser.add_argument('--reviewed-by')
    parser.add_argument('--approve-public-fixture', action='store_true')
    parser.add_argument('--fixture')
    parser.add_argument('--output-root')
    args = parser.parse_args()
    if args.command == 'draft':
        path = draft(args.config, args.job_id, args.output_root)
        print(json.dumps({'draft': str(path), 'reviewStatus': 'pending'}))
    elif args.command == 'promote':
        review, fixture = promote(args.config, args.draft, args.reviewed_by or '', args.approve_public_fixture, args.output_root)
        print(json.dumps({'review': str(review), 'fixture': str(fixture) if fixture else None,
                          'verdict': 'promoted' if fixture else 'blocked-nondeterministic'}))
        if fixture is None:
            raise SystemExit(1)
    else:
        fixture, result = verify_fixture(args.config, args.fixture, replay=args.command == 'replay')
        print(json.dumps({'fixtureId': fixture['fixtureId'], 'verdict': 'passed', 'replay': result}))


if __name__ == '__main__':
    main()
