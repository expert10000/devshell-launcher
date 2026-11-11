"""Evidence-gated operation cost advice; manual backend selection remains authoritative."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import uuid

from benchmark import BENCHMARK_ID, TIERS, compare, digest, environment_fingerprint
from broker import Broker, sha
from telemetry import host_fingerprint
from comparable_inspect import verify as verify_shared_inspect


def benchmark_records(broker, entry, tier):
    root = broker.jobs_root.parent / 'benchmarks' / BENCHMARK_ID
    valid, excluded = [], []
    for path in sorted(root.glob('[0-9a-f]' * 32 + '.json')) if root.exists() else []:
        try:
            record = json.loads(path.read_text(encoding='utf-8'))
            identity = {key: value for key, value in record.items() if key != 'recordId'}
            if (record.get('recordId') != digest(identity) or record.get('benchmarkRunId') != path.stem
                    or record.get('benchmarkId') != BENCHMARK_ID):
                raise ValueError('record identity changed')
            expected = {
                'runtimeId': entry['runtimeId'], 'capabilityId': entry['capabilityId'],
                'certificationRecordId': entry['recordId'], 'suiteRevisionSha256': entry['suiteRevisionSha256'],
                'inputSha256': entry['referenceInputSha256'],
                'environmentFingerprintSha256': environment_fingerprint(entry),
                'hostFingerprintSha256': host_fingerprint(),
                'benchmarkSourceSha256': sha(Path(__file__).with_name('benchmark.py')),
                'brokerSourceSha256': sha(Path(__file__).with_name('broker.py')),
                'telemetrySourceSha256': sha(Path(__file__).with_name('telemetry.py')),
            }
            if any(record.get(key) != value for key, value in expected.items()):
                raise ValueError('host, environment, certification, fixture or suite differs')
            measurements = record['tiers'][tier]
            if (not measurements.get('samples') or not isinstance(measurements.get('medianWorkerDurationMs'), (int, float))
                    or measurements['medianWorkerDurationMs'] <= 0):
                raise ValueError('measured tier is incomplete')
            valid.append((path, record))
        except (OSError, ValueError, KeyError, TypeError) as error:
            excluded.append({'record': path.name, 'reason': str(error)[:180]})
    groups = []
    for path, record in valid:
        peers = [(other_path, other) for other_path, other in valid if other_path != path
                 and compare(record, other)['verdict'] == 'comparable']
        if peers:
            groups.append((path, record, peers))
    if not groups:
        return None, excluded + [{'reason': 'At least two current, comparable benchmark runs are required.'}]
    path, record, peers = sorted(groups, key=lambda item: item[1]['createdAtUtc'])[-1]
    return {'benchmarkRunId': record['benchmarkRunId'], 'benchmarkRecordSha256': sha(path),
            'peerRunIds': [other['benchmarkRunId'] for _, other in peers],
            'tier': tier, 'batchSize': record['tiers'][tier]['batchSize'],
            'policySha256': digest(record['policy']), 'inputSha256': record['inputSha256'],
            'medianWorkerDurationMs': record['tiers'][tier]['medianWorkerDurationMs'],
            'medianThroughputJobsPerSecond': record['tiers'][tier]['medianBatchThroughputJobsPerSecond'],
            'hostFingerprintSha256': record['hostFingerprintSha256'],
            'environmentFingerprintSha256': record['environmentFingerprintSha256']}, excluded


def rank(candidates):
    if len(candidates) < 2:
        return None
    for key in ('policySha256', 'inputSha256', 'hostFingerprintSha256', 'tier', 'batchSize'):
        if len({item['cost'][key] for item in candidates}) != 1:
            return None
    return min(candidates, key=lambda item: item['cost']['medianWorkerDurationMs'])['runtimeId']


def advise(config, capability_id, tier, manual_provider, output_root):
    if capability_id == 'mesh.inspect':
        raise ValueError('Shared mesh.inspect ranking requires a current comparable-inspection record.')
    if tier not in TIERS:
        raise ValueError('Unknown benchmark tier.')
    broker = Broker(config)
    entries = [item for item in broker.capabilities if item['capabilityId'] == capability_id]
    if manual_provider and manual_provider not in {item['runtimeId'] for item in entries}:
        raise ValueError('Manual provider is not currently certified for this capability.')
    candidates, excluded = [], []
    for entry in entries:
        cost, skipped = benchmark_records(broker, entry, tier)
        excluded.extend({'runtimeId': entry['runtimeId'], **item} for item in skipped)
        if cost:
            candidates.append({'runtimeId': entry['runtimeId'], 'capabilityId': capability_id,
                               'certificationRecordId': entry['recordId'], 'cost': cost})
    # Comparing within one provider validates its cost evidence, but cannot rank backends.
    recommendation = rank(candidates)
    record = {'schemaVersion': 1, 'kind': 'scientific.backend-advice',
              'createdAtUtc': datetime.now(timezone.utc).isoformat(), 'capabilityId': capability_id,
              'tier': tier, 'manualProvider': manual_provider, 'selectedProvider': manual_provider,
              'recommendation': recommendation,
              'state': 'ranked' if recommendation else 'insufficient-comparison',
              'reason': None if recommendation else 'Fewer than two certified providers have matching operation, fixture and benchmark policies.',
              'candidates': candidates, 'excluded': excluded,
              'manifestSha256': sha(broker.paths['manifest']), 'advisorSourceSha256': sha(Path(__file__))}
    root = Path(output_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    path = root / (uuid.uuid4().hex + '.json')
    with path.open('x', encoding='utf-8') as stream:
        json.dump(record, stream, separators=(',', ':'))
    Path(str(path) + '.sha256').write_text(sha(path), encoding='utf-8')
    return path, record


def advise_shared(scope_record, tier, manual_provider, output_root):
    scope = verify_shared_inspect(scope_record)
    if tier not in scope['tiers']:
        raise ValueError('Requested size tier is outside the qualified shared scope.')
    providers = {'cgal': 'cgal-win-conda', 'vtk': 'vtk-win-conda'}
    if manual_provider and manual_provider not in providers.values():
        raise ValueError('Manual provider is outside the shared scope.')
    measurements = scope['tiers'][tier]['measurements']
    ranked = sorted((measurements[name]['statistics']['medianMs'], providers[name]) for name in providers)
    record = {'schemaVersion': 1, 'kind': 'scientific.shared-inspect-advice',
              'createdAtUtc': datetime.now(timezone.utc).isoformat(), 'operation': 'mesh.inspect',
              'tier': tier, 'scopeRecord': str(Path(scope_record).resolve()),
              'scopeRecordSha256': sha(scope_record), 'contractSha256': scope['contractSha256'],
              'manualProvider': manual_provider, 'selectedProvider': manual_provider,
              'recommendation': ranked[0][1],
              'mediansMs': {providers[name]: measurements[name]['statistics']['medianMs'] for name in providers},
              'state': 'ranked-within-qualified-shared-scope'}
    root = Path(output_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    path = root / (uuid.uuid4().hex + '.json')
    path.write_text(json.dumps(record, separators=(',', ':')), encoding='utf-8')
    Path(str(path) + '.sha256').write_text(sha(path), encoding='utf-8')
    return path, record


def verify_shared_advice(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text().strip():
        raise ValueError('Shared advice seal changed.')
    record = json.loads(path.read_text(encoding='utf-8'))
    scope = verify_shared_inspect(record['scopeRecord'])
    if (record['scopeRecordSha256'] != sha(record['scopeRecord'])
            or record['contractSha256'] != scope['contractSha256']
            or record['tier'] not in scope['tiers']):
        raise ValueError('Shared advice scope drifted.')
    providers = {'cgal': 'cgal-win-conda', 'vtk': 'vtk-win-conda'}
    medians = {providers[name]: scope['tiers'][record['tier']]['measurements'][name]['statistics']['medianMs']
               for name in providers}
    expected = min(medians, key=medians.get)
    if (record['mediansMs'] != medians or record['recommendation'] != expected
            or record['state'] != 'ranked-within-qualified-shared-scope'
            or record['selectedProvider'] != record['manualProvider']):
        raise ValueError('Shared advice recommendation changed.')
    return record


def verify(path, config=None):
    path = Path(path).resolve(strict=True)
    if not re.fullmatch('[0-9a-f]{32}\.json', path.name) or sha(path) != Path(str(path) + '.sha256').read_text().strip():
        raise ValueError('Advisor record hash mismatch.')
    record = json.loads(path.read_text(encoding='utf-8'))
    if record.get('schemaVersion') != 1 or record.get('kind') != 'scientific.backend-advice':
        raise ValueError('Advisor record schema changed.')
    if config:
        broker = Broker(config)
        if (record['manifestSha256'] != sha(broker.paths['manifest'])
                or record['advisorSourceSha256'] != sha(Path(__file__))):
            raise ValueError('Advisor certification or suite source changed.')
        entries = {item['runtimeId']: item for item in broker.capabilities
                   if item['capabilityId'] == record['capabilityId']}
        if record['selectedProvider'] != record['manualProvider'] or (
                record['manualProvider'] and record['manualProvider'] not in entries):
            raise ValueError('Manual backend selection is no longer certified.')
        for candidate in record['candidates']:
            entry = entries.get(candidate['runtimeId'])
            if not entry or candidate['certificationRecordId'] != entry['recordId']:
                raise ValueError('Advice candidate is no longer certified.')
            cost = candidate['cost']
            root = broker.jobs_root.parent / 'benchmarks' / BENCHMARK_ID
            if not re.fullmatch('[0-9a-f]{32}', cost['benchmarkRunId']):
                raise ValueError('Advice benchmark ID is invalid.')
            benchmark_path = root / (cost['benchmarkRunId'] + '.json')
            if sha(benchmark_path) != cost['benchmarkRecordSha256']:
                raise ValueError('Advice benchmark hash changed.')
            benchmark = json.loads(benchmark_path.read_text(encoding='utf-8'))
            identity = {key: value for key, value in benchmark.items() if key != 'recordId'}
            if (benchmark.get('recordId') != digest(identity)
                    or benchmark['certificationRecordId'] != entry['recordId']
                    or benchmark['suiteRevisionSha256'] != entry['suiteRevisionSha256']
                    or benchmark['hostFingerprintSha256'] != host_fingerprint()
                    or benchmark['environmentFingerprintSha256'] != environment_fingerprint(entry)
                    or benchmark['inputSha256'] != entry['referenceInputSha256']
                    or benchmark['benchmarkSourceSha256'] != sha(Path(__file__).with_name('benchmark.py'))
                    or benchmark['brokerSourceSha256'] != sha(Path(__file__).with_name('broker.py'))
                    or benchmark['telemetrySourceSha256'] != sha(Path(__file__).with_name('telemetry.py'))
                    or benchmark['tiers'][record['tier']]['medianWorkerDurationMs'] != cost['medianWorkerDurationMs']
                    or digest(benchmark['policy']) != cost['policySha256']
                    or benchmark['inputSha256'] != cost['inputSha256']):
                raise ValueError('Advice benchmark is no longer applicable.')
            if not cost['peerRunIds']:
                raise ValueError('Advice has no comparable benchmark peer.')
            for peer_id in cost['peerRunIds']:
                if not re.fullmatch('[0-9a-f]{32}', peer_id):
                    raise ValueError('Advice benchmark peer ID is invalid.')
                peer = json.loads((root / (peer_id + '.json')).read_text(encoding='utf-8'))
                peer_identity = {key: value for key, value in peer.items() if key != 'recordId'}
                if peer.get('recordId') != digest(peer_identity) or compare(benchmark, peer)['verdict'] != 'comparable':
                    raise ValueError('Advice benchmark peer is not comparable.')
        expected = rank(record['candidates'])
        if record['recommendation'] != expected or record['state'] != ('ranked' if expected else 'insufficient-comparison'):
            raise ValueError('Advice recommendation changed.')
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['advise', 'verify', 'advise-shared', 'verify-shared'])
    parser.add_argument('--config')
    parser.add_argument('--capability-id', default='mesh.interop.vtk-math3d')
    parser.add_argument('--tier', default='single')
    parser.add_argument('--manual-provider')
    parser.add_argument('--output-root')
    parser.add_argument('--record')
    parser.add_argument('--shared-record')
    args = parser.parse_args()
    if args.command == 'advise-shared':
        if not args.shared_record or not args.output_root:
            parser.error('advise-shared requires --shared-record and --output-root')
        path, report = advise_shared(args.shared_record, args.tier, args.manual_provider, args.output_root)
        print(json.dumps({'record': str(path), 'recommendation': report['recommendation'],
                          'selectedProvider': report['selectedProvider'], 'tier': report['tier']}))
    elif args.command == 'verify-shared':
        report = verify_shared_advice(args.record)
        print(json.dumps({'state': report['state'], 'recommendation': report['recommendation']}))
    elif args.command == 'verify':
        report = verify(args.record, args.config)
        print(json.dumps({'state': report['state'], 'selectedProvider': report['selectedProvider']}))
    else:
        if not args.config or not args.output_root:
            parser.error('advise requires --config and --output-root')
        path, report = advise(args.config, args.capability_id, args.tier, args.manual_provider, args.output_root)
        print(json.dumps({'record': str(path), 'state': report['state'], 'recommendation': report['recommendation'],
                          'selectedProvider': report['selectedProvider'], 'reason': report['reason']}))


if __name__ == '__main__':
    main()
