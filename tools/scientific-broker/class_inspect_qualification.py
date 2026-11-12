"""Current desktop and live broker evidence for bounded shared inspection classes."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import shutil
import time
import uuid

from broker import Broker, sha
from comparable_inspect import verify_release, host_fingerprint, summary
from inspect_classes import classify, equivalent, policy


def wait(broker, request):
    job_id = broker.submit(request)['jobId']
    deadline = time.monotonic() + 150
    while broker.jobs[job_id]['state'] == 'running' and time.monotonic() < deadline:
        time.sleep(.1)
    job = broker.snapshot(broker.jobs[job_id])
    if job['state'] != 'succeeded':
        raise ValueError('Bounded inspection broker job failed: ' + str(job['diagnostics']))
    promotion = broker.promote(job_id)
    if promotion['decision'] != 'allowed':
        raise ValueError('Bounded inspection promotion was blocked: ' + str(promotion['reasons']))
    folder = Path(job['directory'])
    obj = folder / ('inspected.obj' if broker.inspect else 'read.obj')
    if not equivalent(folder / 'dataset/input.obj', obj):
        raise ValueError('Bounded inspection changed input geometry.')
    result = json.loads((folder / 'results.json').read_text(encoding='utf-8'))
    telemetry = broker.telemetry(job_id)
    warm = (result.get('engineDetails', {}).get('durationMs') if broker.inspect
            else result.get('durationMs'))
    if (not isinstance(warm, (int, float)) or warm < 0 or warm > job['workerDurationMs']
            or telemetry.get('ram', {}).get('state') != 'recorded'
            or not isinstance(telemetry['ram'].get('value'), int)):
        raise ValueError('Cold/warm timing or attributed RAM telemetry is unavailable.')
    files = {name: {'path': str(folder / name), 'sha256': sha(folder / name)}
             for name in ('request.json', 'results.json', 'broker-result.json', 'telemetry.json', obj.name)}
    files['promotion.json'] = {'path': promotion['path'], 'sha256': promotion['sha256']}
    if broker.vtk_read:
        files['read.vtp'] = {'path': str(folder / 'read.vtp'), 'sha256': sha(folder / 'read.vtp')}
    return {'jobId': job_id, 'coldInvocationMs': job['workerDurationMs'],
            'warmExecutionMs': warm,
            'startupOverheadMs': job['workerDurationMs'] - warm,
            'peakRssBytes': telemetry['ram']['value'], 'files': files}


def request(broker, class_id, path):
    return {'schemaVersion': 1, 'runtimeId': broker.runtime_id,
            'capabilityId': broker.capability_id, 'classId': class_id,
            'input': {'path': str(path), 'sha256': sha(path)}, 'timeoutSeconds': 120}


def run(release_path, output_root, samples=5):
    if not 5 <= samples <= 20:
        raise ValueError('Bounded class qualification requires 5–20 measured samples.')
    release_path = Path(release_path).resolve(strict=True)
    release = verify_release(release_path)
    if release['kind'] != 'scientific.six-capability-release':
        raise ValueError('Bounded classes require a six-capability release.')
    repo = Path(release['repo'])
    classes, policy_hash = policy(repo)
    configs = {'cgal': Path(release['profiles']['inspect']['config']),
               'vtk': Path(release['profiles']['vtk_read']['config'])}
    brokers = {name: Broker(path) for name, path in configs.items()}
    if not brokers['cgal'].inspect or not brokers['vtk'].vtk_read:
        raise ValueError('Both current dedicated inspection profiles are required.')
    folder = Path(output_root).resolve() / uuid.uuid4().hex
    folder.mkdir(parents=True)
    accepted, rejected = {}, []
    for entry in classes['classes']:
        source = repo / entry['holdoutFixture']
        proof = classify(source, repo)
        if proof['classId'] != entry['id'] or proof['inputSha256'] != entry['holdoutSha256']:
            raise ValueError('Holdout is outside its declared class.')
        staged = {}
        for name, broker in brokers.items():
            target = broker.paths['datasetRoot'] / ('inspect-class-' + entry['id'] + '-' + name + '.obj')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            staged[name] = target
        runs = {name: [] for name in brokers}
        order_rng = random.Random(int(policy_hash[:16], 16) ^ int.from_bytes(entry['id'].encode(), 'big'))
        order = []
        for index in range(samples):
            pair = ['cgal', 'vtk']
            order_rng.shuffle(pair)
            order.append(pair)
            for name in pair:
                runs[name].append(wait(brokers[name], request(brokers[name], entry['id'], staged[name])))
        left = Path(runs['cgal'][0]['files']['inspected.obj']['path'])
        right = Path(runs['vtk'][0]['files']['read.obj']['path'])
        if not equivalent(left, right):
            raise ValueError('Holdout providers disagree: ' + entry['id'])
        accepted[entry['id']] = {'holdoutSha256': entry['holdoutSha256'],
                                 'tier': entry['tier'], 'sampleOrder': order, 'runs': runs,
                                 'statistics': {name: {
                                     'coldInvocation': summary([item['coldInvocationMs'] for item in items]),
                                     'warmExecution': summary([item['warmExecutionMs'] for item in items]),
                                     'startupOverhead': summary([item['startupOverheadMs'] for item in items]),
                                     'peakRssBytes': max(item['peakRssBytes'] for item in items)}
                                     for name, items in runs.items()}}
    for adverse in classes['rejectedFixtures']:
        source = repo / adverse['path']
        for name, broker in brokers.items():
            target = broker.paths['datasetRoot'] / ('inspect-class-reject-' + adverse['reason'] + '-' + name + '.obj')
            shutil.copyfile(source, target)
            try:
                broker.submit(request(broker, classes['classes'][0]['id'], target))
            except ValueError as error:
                rejected.append({'fixture': adverse['path'], 'sha256': adverse['sha256'],
                                 'provider': name, 'reason': str(error)[:240]})
            else:
                raise ValueError('Adverse class input was accepted: ' + adverse['path'])
    record = {'schemaVersion': 3, 'kind': 'scientific.bounded-inspect-class-qualification',
              'createdAtUtc': datetime.now(timezone.utc).isoformat(),
              'sourceCommit': release['sourceCommit'], 'releaseRecord': str(release_path),
              'releaseRecordSha256': sha(release_path), 'policySha256': policy_hash,
              'hostFingerprintSha256': host_fingerprint(),
              'desktopRecordIds': {name: release['profiles'][name]['recordId']
                                   for name in ('inspect', 'vtk_read')},
              'configPaths': {name: str(path) for name, path in configs.items()},
              'configSha256': {name: sha(path) for name, path in configs.items()},
              'samples': samples, 'classes': accepted, 'rejections': rejected}
    path = folder / 'classes.json'
    path.write_text(json.dumps(record, separators=(',', ':')), encoding='utf-8')
    Path(str(path) + '.sha256').write_text(sha(path), encoding='utf-8')
    verify(path)
    return path, record


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('Bounded class record seal changed.')
    record = json.loads(path.read_text(encoding='utf-8'))
    if record.get('schemaVersion') != 3 or record.get('kind') != 'scientific.bounded-inspect-class-qualification':
        raise ValueError('Bounded class record contract changed.')
    release = verify_release(record['releaseRecord'])
    repo = Path(release['repo'])
    classes, policy_hash = policy(repo)
    if (record['sourceCommit'] != release['sourceCommit']
            or record['releaseRecordSha256'] != sha(record['releaseRecord'])
            or record['policySha256'] != policy_hash
            or record['hostFingerprintSha256'] != host_fingerprint()
            or record['desktopRecordIds'] != {name: release['profiles'][name]['recordId']
                                               for name in ('inspect', 'vtk_read')}
            or set(record['classes']) != {item['id'] for item in classes['classes']}
            or not 5 <= record['samples'] <= 20):
        raise ValueError('Bounded class source, host or desktop support drifted.')
    if set(record['configPaths']) != {'cgal', 'vtk'}:
        raise ValueError('Bounded class provider set changed.')
    brokers = {}
    for name, config in record['configPaths'].items():
        if sha(config) != record['configSha256'][name]:
            raise ValueError('Bounded class broker config changed.')
        brokers[name] = Broker(config)
    for entry in classes['classes']:
        saved = record['classes'][entry['id']]
        source = repo / entry['holdoutFixture']
        if (saved['holdoutSha256'] != entry['holdoutSha256'] or saved['tier'] != entry['tier']
                or classify(source, repo)['classId'] != entry['id']):
            raise ValueError('Bounded class holdout changed.')
        rng = random.Random(int(policy_hash[:16], 16) ^ int.from_bytes(entry['id'].encode(), 'big'))
        expected_order = []
        for _ in range(record['samples']):
            pair = ['cgal', 'vtk']
            rng.shuffle(pair)
            expected_order.append(pair)
        if saved['sampleOrder'] != expected_order:
            raise ValueError('Bounded class paired sample order changed.')
        for name in ('cgal', 'vtk'):
            runs = saved['runs'][name]
            if len(runs) != record['samples']:
                raise ValueError('Bounded class broker samples are incomplete.')
            for run in runs:
                for artifact in run['files'].values():
                    if sha(artifact['path']) != artifact['sha256']:
                        raise ValueError('Bounded class broker artifact changed.')
                request_value = json.loads(Path(run['files']['request.json']['path']).read_text(encoding='utf-8'))
                result_value = json.loads(Path(run['files']['results.json']['path']).read_text(encoding='utf-8'))
                broker_value = json.loads(Path(run['files']['broker-result.json']['path']).read_text(encoding='utf-8'))
                telemetry = json.loads(Path(run['files']['telemetry.json']['path']).read_text(encoding='utf-8'))
                promotion = json.loads(Path(run['files']['promotion.json']['path']).read_text(encoding='utf-8'))
                obj = run['files']['inspected.obj' if name == 'cgal' else 'read.obj']['path']
                if (request_value['provenance'].get('inspectionClassId') != entry['id']
                        or request_value['provenance'].get('inspectionClassPolicySha256') != policy_hash
                        or request_value['inputArtifacts'][0]['sha256'] != entry['holdoutSha256']
                        or result_value.get('state') != 'succeeded'
                        or result_value.get('runId') != run['jobId']
                        or broker_value.get('workerDurationMs') != run['coldInvocationMs']
                        or broker_value.get('telemetrySha256') != run['files']['telemetry.json']['sha256']
                        or (result_value.get('engineDetails', {}).get('durationMs') if name == 'cgal'
                            else result_value.get('durationMs')) != run['warmExecutionMs']
                        or run['startupOverheadMs'] != run['coldInvocationMs'] - run['warmExecutionMs']
                        or telemetry.get('ram', {}).get('state') != 'recorded'
                        or telemetry['ram'].get('value') != run['peakRssBytes']
                        or promotion.get('decision') != 'allowed'
                        or promotion.get('sourceJobId') != run['jobId']
                        or not equivalent(source, obj)):
                    raise ValueError('Bounded class broker promotion or geometry changed.')
                fresh = brokers[name].promote(run['jobId'])
                if fresh['decision'] != 'allowed':
                    raise ValueError('Bounded class broker promotion no longer passes.')
            expected = {'coldInvocation': summary([item['coldInvocationMs'] for item in runs]),
                        'warmExecution': summary([item['warmExecutionMs'] for item in runs]),
                        'startupOverhead': summary([item['startupOverheadMs'] for item in runs]),
                        'peakRssBytes': max(item['peakRssBytes'] for item in runs)}
            if saved['statistics'][name] != expected:
                raise ValueError('Bounded class statistics changed.')
        if not equivalent(saved['runs']['cgal'][0]['files']['inspected.obj']['path'],
                          saved['runs']['vtk'][0]['files']['read.obj']['path']):
            raise ValueError('Bounded class provider geometry diverged.')
    expected_rejections = {(item['path'], name, item['sha256'])
                           for item in classes['rejectedFixtures'] for name in ('cgal', 'vtk')}
    observed = {(item['fixture'], item['provider'], item['sha256']) for item in record['rejections']}
    if observed != expected_rejections or len(record['rejections']) != len(expected_rejections):
        raise ValueError('Bounded class rejection evidence is incomplete.')
    for item in record['rejections']:
        try:
            classify(repo / item['fixture'], repo)
        except ValueError as error:
            if item['reason'] != str(error)[:240]:
                raise ValueError('Bounded class rejection reason changed.') from error
        else:
            raise ValueError('Adverse inspection input became accepted.')
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('run', 'verify'))
    parser.add_argument('--release')
    parser.add_argument('--output-root')
    parser.add_argument('--samples', type=int, default=5)
    parser.add_argument('--record')
    options = parser.parse_args()
    if options.command == 'run':
        if not options.release or not options.output_root:
            parser.error('run requires --release and --output-root')
        path, value = run(options.release, options.output_root, options.samples)
    else:
        if not options.record:
            parser.error('verify requires --record')
        path, value = options.record, verify(options.record)
    print(json.dumps({'record': str(path), 'classes': list(value['classes']), 'verdict': 'qualified'}))
