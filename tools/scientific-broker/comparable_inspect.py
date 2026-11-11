"""Qualify a narrow shared mesh.inspect scope against current desktop and broker evidence."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import time
import uuid

from broker import Broker, sha
from differential import compare_descriptors, load_saved_mesh
from five_capability_release import verify as verify_release

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / 'schemas/scientific-mesh-inspect.v1.json'


def host_fingerprint():
    """Stable across qualified Python runtimes with different optional telemetry packages."""
    identity = {'node': platform.node(), 'system': platform.system(),
                'release': platform.release(), 'machine': platform.machine(),
                'processor': platform.processor(), 'logicalCpus': os.cpu_count()}
    return hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def policy(repo):
    path = Path(repo) / 'schemas/scientific-mesh-inspect.v1.json'
    value = json.loads(path.read_text(encoding='utf-8'))
    if (value.get('schemaVersion') != 1 or value.get('operation') != 'mesh.inspect'
            or [item.get('id') for item in value.get('tiers', [])] != ['tetra-4', 'octa-6', 'cube-8']
            or value.get('minimumSamples', 0) < 5 or not 0 < value.get('tolerance', 0) <= 1e-6):
        raise ValueError('Shared mesh.inspect contract changed.')
    for tier in value['tiers']:
        for side in ('cgal', 'vtk'):
            fixture = (Path(repo) / tier[side + 'Fixture']).resolve(strict=True)
            if not fixture.is_relative_to(Path(repo).resolve()) or sha(fixture) != tier[side + 'Sha256']:
                raise ValueError('Shared inspection fixture changed: ' + tier['id'])
    return value, sha(path)


def wait_job(broker, request):
    job_id = broker.submit(request)['jobId']
    deadline = time.monotonic() + 150
    while broker.jobs[job_id]['state'] == 'running' and time.monotonic() < deadline:
        time.sleep(.1)
    job = broker.snapshot(broker.jobs[job_id])
    if job['state'] != 'succeeded':
        raise ValueError('Broker gate rejected ' + request['caseId'] + ': ' + str(job['diagnostics']))
    promotion = broker.promote(job_id)
    if promotion['decision'] != 'allowed':
        raise ValueError('Broker promotion gate rejected ' + request['caseId'])
    result = Path(job['directory']) / 'results.json'
    return {'jobId': job_id, 'resultPath': str(result), 'resultSha256': sha(result),
            'promotionPath': promotion['path'], 'promotionSha256': promotion['sha256']}


def inspect_sample(broker, case_id, fixture, digest, provider):
    request = {'schemaVersion': 1, 'runtimeId': broker.runtime_id,
               'capabilityId': broker.capability_id, 'caseId': case_id,
               'input': {'path': str(fixture), 'sha256': digest}, 'timeoutSeconds': 120}
    if provider == 'cgal':
        request['operation'] = 'mesh.inspect'
    job_id = broker.submit(request)['jobId']
    deadline = time.monotonic() + 150
    while broker.jobs[job_id]['state'] == 'running' and time.monotonic() < deadline:
        time.sleep(.1)
    job = broker.snapshot(broker.jobs[job_id])
    if job['state'] != 'succeeded':
        raise ValueError('Shared inspect broker job failed: ' + str(job['diagnostics']))
    directory = Path(job['directory'])
    result_path = directory / 'results.json'
    broker_result = directory / 'broker-result.json'
    artifact = directory / ('inspected.obj' if provider == 'cgal' else 'read.vtp')
    request_path = directory / 'request.json'
    result = json.loads(result_path.read_text(encoding='utf-8'))
    if (result.get('operation') != 'mesh.inspect' or result.get('state') != 'succeeded'
            or result.get('runId') != job_id or result['inputArtifacts'][0]['sha256'] != digest
            or not isinstance(job.get('workerDurationMs'), (int, float))):
        raise ValueError('Typed shared inspect result changed.')
    return {'jobId': job_id, 'requestPath': str(request_path), 'requestSha256': sha(request_path),
            'resultPath': str(result_path), 'resultSha256': sha(result_path),
            'brokerResultPath': str(broker_result), 'brokerResultSha256': sha(broker_result),
            'artifactPath': str(artifact), 'artifactSha256': sha(artifact),
            'runId': result['runId'], 'durationMs': job['workerDurationMs'],
            'descriptor': load_saved_mesh(result_path, artifact.name)}


def summary(values):
    ordered = sorted(values)
    return {'samples': len(values), 'medianMs': statistics.median(values),
            'p10Ms': ordered[max(0, round((len(values) - 1) * .1))],
            'p90Ms': ordered[min(len(values) - 1, round((len(values) - 1) * .9))],
            'madMs': statistics.median(abs(value - statistics.median(values)) for value in values)}


def run(release_path, output_root, repetitions=7):
    release_path = Path(release_path).resolve(strict=True)
    release = verify_release(release_path)
    if not 5 <= repetitions <= 20:
        raise ValueError('Comparable inspection requires 5–20 measured samples.')
    repo = Path(release['repo'])
    contract, contract_sha = policy(repo)
    configs = {name: Path(release['profiles'][name]['config']) for name in ('remesh', 'vtk_read')}
    brokers = {name: Broker(path) for name, path in configs.items()}
    if not brokers['remesh'].remesh or not brokers['vtk_read'].vtk_read:
        raise ValueError('Current CGAL remesh and VTK read broker profiles are required.')
    root = Path(output_root).resolve() / uuid.uuid4().hex
    root.mkdir(parents=True)
    tiers = {}
    for tier in contract['tiers']:
        fixtures = {name: repo / tier[name + 'Fixture'] for name in ('cgal', 'vtk')}
        broker_jobs = {}
        staged = {}
        for name, broker in (('cgal', brokers['remesh']), ('vtk', brokers['vtk_read'])):
            case_id = tier['cgalCase' if name == 'cgal' else 'vtkCase']
            destination = broker.paths['datasetRoot'] / ('inspect-' + tier['id'] + '-' + name + '.obj')
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(fixtures[name], destination)
            staged[name] = destination
            broker_jobs[name] = wait_job(broker, {'schemaVersion': 1, 'runtimeId': broker.runtime_id,
                'capabilityId': broker.capability_id, 'caseId': case_id,
                'input': {'path': str(destination), 'sha256': sha(destination)}, 'timeoutSeconds': 120})
        active = {'cgal': brokers['remesh'], 'vtk': brokers['vtk_read']}
        warmups = {name: inspect_sample(active[name], tier[name + 'Case'], staged[name],
                                        tier[name + 'Sha256'], name) for name in active}
        observations = {name: [] for name in active}
        for _ in range(repetitions):
            for name in active:
                observations[name].append(inspect_sample(active[name], tier[name + 'Case'], staged[name],
                                                         tier[name + 'Sha256'], name))
        left, right = (observations[name][0]['descriptor'] for name in ('cgal', 'vtk'))
        geometry = compare_descriptors(left, right, contract['tolerance'])
        if geometry['verdict'] != 'equivalent':
            raise ValueError('Shared inspection geometry differs: ' + tier['id'])
        for name in active:
            first = observations[name][0]
            result = json.loads(Path(first['resultPath']).read_text(encoding='utf-8'))
            before = result['before']
            if (before.get('points') != tier['points'] or before.get('triangles') != tier['triangles']
                    or before.get('boundaryEdges') != 0 or before.get('nonManifoldEdges', 0) != 0):
                raise ValueError('Shared inspection topology differs: ' + tier['id'])
        tiers[tier['id']] = {'brokerJobs': broker_jobs, 'geometry': geometry,
            'warmups': {name: {key: value for key, value in run.items() if key != 'descriptor'}
                        for name, run in warmups.items()},
            'measurements': {name: {'runs': [{key: value for key, value in run.items() if key != 'descriptor'}
                                             for run in observations[name]],
                                    'statistics': summary([run['durationMs'] for run in observations[name]])}
                             for name in active}}
    record = {'schemaVersion': 1, 'kind': 'scientific.comparable-mesh-inspect',
              'state': 'qualified-shared-scope', 'operation': 'mesh.inspect',
              'createdAtUtc': datetime.now(timezone.utc).isoformat(),
              'sourceCommit': release['sourceCommit'], 'releaseRecord': str(release_path),
              'releaseRecordSha256': sha(release_path), 'contractSha256': contract_sha,
              'configPaths': {name: str(path) for name, path in configs.items()},
              'configSha256': {name: sha(path) for name, path in configs.items()},
              'host': {'fingerprintSha256': host_fingerprint(), 'node': platform.node(),
                       'system': platform.system()}, 'repetitions': repetitions, 'tiers': tiers}
    path = root / 'shared-inspect.json'
    path.write_text(json.dumps(record, separators=(',', ':')), encoding='utf-8')
    Path(str(path) + '.sha256').write_text(sha(path), encoding='utf-8')
    verify(path)
    return path, record


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text().strip():
        raise ValueError('Shared inspection record seal changed.')
    record = json.loads(path.read_text(encoding='utf-8'))
    if (record.get('schemaVersion') != 1 or record.get('kind') != 'scientific.comparable-mesh-inspect'
            or record.get('state') != 'qualified-shared-scope' or record.get('operation') != 'mesh.inspect'):
        raise ValueError('Shared inspection qualification changed.')
    release = verify_release(record['releaseRecord'])
    contract, contract_sha = policy(release['repo'])
    if (record['sourceCommit'] != release['sourceCommit'] or record['releaseRecordSha256'] != sha(record['releaseRecord'])
            or record['contractSha256'] != contract_sha or record['host']['fingerprintSha256'] != host_fingerprint()
            or set(record['tiers']) != {item['id'] for item in contract['tiers']}):
        raise ValueError('Shared inspection source, host or contract drifted.')
    for name, config in record['configPaths'].items():
        if sha(config) != record['configSha256'][name]:
            raise ValueError('Shared inspection broker config drifted.')
        Broker(config)
    for tier in contract['tiers']:
        saved = record['tiers'][tier['id']]
        for name in ('cgal', 'vtk'):
            job = saved['brokerJobs'][name]
            if sha(job['resultPath']) != job['resultSha256'] or sha(job['promotionPath']) != job['promotionSha256']:
                raise ValueError('Shared inspection broker gate changed.')
            measurements = saved['measurements'][name]
            runs = measurements['runs']
            if len(runs) != record['repetitions'] or len(runs) < contract['minimumSamples']:
                raise ValueError('Shared inspection sample count changed.')
            for run in [saved['warmups'][name], *runs]:
                if (sha(run['requestPath']) != run['requestSha256']
                        or sha(run['resultPath']) != run['resultSha256']
                        or sha(run['brokerResultPath']) != run['brokerResultSha256']
                        or sha(run['artifactPath']) != run['artifactSha256']):
                    raise ValueError('Shared inspection broker evidence changed.')
                request = json.loads(Path(run['requestPath']).read_text(encoding='utf-8'))
                result = json.loads(Path(run['resultPath']).read_text(encoding='utf-8'))
                broker_result = json.loads(Path(run['brokerResultPath']).read_text(encoding='utf-8'))
                if (request.get('operation') != 'mesh.inspect' or result.get('operation') != 'mesh.inspect'
                        or result.get('state') != 'succeeded' or result.get('runId') != run['jobId']
                        or broker_result.get('state') != 'succeeded'
                        or broker_result.get('jobId') != run['jobId']
                        or broker_result.get('workerDurationMs') != run['durationMs']
                        or result.get('inputArtifacts', [{}])[0].get('sha256') != tier[name + 'Sha256']):
                    raise ValueError('Shared operation evidence changed.')
            if summary([run['durationMs'] for run in runs]) != measurements['statistics']:
                raise ValueError('Shared inspection statistics changed.')
        left = load_saved_mesh(saved['measurements']['cgal']['runs'][0]['resultPath'], 'inspected.obj')
        right = load_saved_mesh(saved['measurements']['vtk']['runs'][0]['resultPath'], 'read.vtp')
        geometry = compare_descriptors(left, right, contract['tolerance'])
        if geometry != saved['geometry'] or geometry['verdict'] != 'equivalent':
            raise ValueError('Shared inspection geometry changed.')
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('run', 'verify'))
    parser.add_argument('--release')
    parser.add_argument('--output-root')
    parser.add_argument('--repetitions', type=int, default=7)
    parser.add_argument('--record')
    args = parser.parse_args()
    if args.command == 'run':
        if not args.release or not args.output_root:
            parser.error('run requires --release and --output-root')
        path, record = run(args.release, args.output_root, args.repetitions)
    else:
        if not args.record:
            parser.error('verify requires --record')
        path, record = args.record, verify(args.record)
    print(json.dumps({'record': str(path), 'state': record['state'], 'tiers': list(record['tiers'])}))


if __name__ == '__main__':
    main()
