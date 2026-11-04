"""Persistent, comparable benchmarks for the fixed qualified CGAL broker recipe."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import time
import uuid

from broker import Broker, sha
from telemetry import host_fingerprint


BENCHMARK_ID = 'cgal.mesh.validate.fixed-tetra.v1'
TIERS = {'single': 1, 'small-batch': 3, 'medium-batch': 5}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def environment_fingerprint(entry):
    return digest({key: entry[key] for key in ('runtimeManifestSha256', 'adapterSha256',
        'workerContractSha256', 'workerBinarySha256', 'pythonSha256', 'packageRecordsSha256',
        'productContractSha256', 'suiteRevisionSha256')})


def compare(baseline, candidate):
    reasons = []
    for field, label in [('benchmarkId', 'benchmark ID'), ('hostFingerprintSha256', 'host'),
                         ('environmentFingerprintSha256', 'environment fingerprint'),
                         ('certificationRecordId', 'qualification record'),
                         ('inputSha256', 'fixed fixture'), ('suiteRevisionSha256', 'suite revision'),
                         ('benchmarkSourceSha256', 'benchmark suite source'),
                         ('brokerSourceSha256', 'broker source'), ('telemetrySourceSha256', 'telemetry collector'),
                         ('policy', 'cold/warm policy')]:
        if baseline.get(field) != candidate.get(field):
            reasons.append(label + ' differs')
    if set(baseline.get('tiers', {})) != set(candidate.get('tiers', {})):
        reasons.append('input tiers differ')
    for name in set(baseline.get('tiers', {})) & set(candidate.get('tiers', {})):
        if baseline['tiers'][name].get('batchSize') != candidate['tiers'][name].get('batchSize'):
            reasons.append(name + ' batch size differs')
    if reasons:
        return {'verdict': 'inconclusive', 'warning': 'Benchmark environments or policies differ; performance change is not comparable.',
                'reasons': reasons, 'baselineRunId': baseline.get('benchmarkRunId')}
    metrics = {}
    for name in TIERS:
        first = baseline['tiers'][name]['medianWorkerDurationMs']
        second = candidate['tiers'][name]['medianWorkerDurationMs']
        metrics[name] = {'baselineMedianMs': first, 'candidateMedianMs': second,
                         'ratio': round(second / first, 6) if first > 0 else None}
    return {'verdict': 'comparable', 'reasons': [], 'baselineRunId': baseline['benchmarkRunId'], 'metrics': metrics}


def run_job(broker, input_path):
    request = {'schemaVersion': 1, 'runtimeId': 'cgal-win-conda',
               'capabilityId': 'mesh.interop.vtk-math3d',
               'input': {'path': str(input_path), 'sha256': sha(input_path)}}
    snapshot = broker.submit(request)
    deadline = time.monotonic() + 150
    while snapshot['state'] == 'running' and time.monotonic() < deadline:
        time.sleep(0.025)
        snapshot = broker.snapshot(broker.jobs[snapshot['jobId']])
    if snapshot['state'] != 'succeeded' or snapshot.get('cleanup', {}).get('state') != 'passed':
        raise RuntimeError(f"Benchmark job {snapshot['jobId']} ended {snapshot['state']}: {snapshot['diagnostics']}")
    telemetry_path = Path(snapshot['directory']) / 'telemetry.json'
    if sha(telemetry_path) != snapshot['telemetrySha256']:
        raise RuntimeError('Benchmark telemetry hash changed.')
    return {'jobId': snapshot['jobId'], 'workerDurationMs': snapshot['workerDurationMs'],
            'wallDurationMs': snapshot['durationMs'], 'telemetrySha256': snapshot['telemetrySha256'],
            'cleanup': snapshot['cleanup']['state']}


def run_benchmark(config_path, repetitions):
    if not 2 <= repetitions <= 20:
        raise ValueError('Benchmark repetitions must be between 2 and 20.')
    broker = Broker(config_path)
    if len(broker.capabilities) != 1:
        raise ValueError('The fixed CGAL capability is not certified.')
    entry = broker.capabilities[0]
    input_path = broker.paths['datasetRoot'] / 'math3d' / 'basic' / '01_tetrahedron.obj'
    if sha(input_path) != entry['referenceInputSha256']:
        raise ValueError('Benchmark fixture differs from the current qualification.')
    policy = {'tierDimension': 'sequential jobs per batch; geometry remains the fixed tetrahedron',
              'cold': 'first worker job after a new Broker instance per tier; OS caches uncontrolled',
              'warmupBatches': 1, 'measuredBatches': repetitions,
              'measure': 'workerDurationMs, including adapter and worker startup'}
    report = {'schemaVersion': 1, 'benchmarkId': BENCHMARK_ID, 'benchmarkRunId': uuid.uuid4().hex,
              'createdAtUtc': datetime.now(timezone.utc).isoformat(),
              'runtimeId': 'cgal-win-conda', 'capabilityId': 'mesh.interop.vtk-math3d',
              'certificationRecordId': entry['recordId'], 'sourceRunFingerprintSha256': entry['runFingerprintSha256'],
              'suiteRevisionSha256': entry['suiteRevisionSha256'], 'inputSha256': sha(input_path),
              'hostFingerprintSha256': host_fingerprint(),
              'environmentFingerprintSha256': environment_fingerprint(entry),
              'benchmarkSourceSha256': sha(Path(__file__)),
              'brokerSourceSha256': sha(Path(__file__).with_name('broker.py')),
              'telemetrySourceSha256': sha(Path(__file__).with_name('telemetry.py')),
              'policy': policy, 'tiers': {}}
    for name, batch_size in TIERS.items():
        broker = Broker(config_path)
        cold = run_job(broker, input_path)
        warmup = [run_job(broker, input_path) for _ in range(batch_size)]
        samples = []
        for _ in range(repetitions):
            started = time.monotonic()
            jobs = [run_job(broker, input_path) for _ in range(batch_size)]
            elapsed = round((time.monotonic() - started) * 1000)
            samples.append({'jobIds': [item['jobId'] for item in jobs],
                            'workerDurationMs': [item['workerDurationMs'] for item in jobs],
                            'batchWallDurationMs': elapsed,
                            'throughputJobsPerSecond': round(batch_size * 1000 / elapsed, 6) if elapsed else None})
        durations = [duration for sample in samples for duration in sample['workerDurationMs']]
        report['tiers'][name] = {'batchSize': batch_size, 'coldJob': cold,
            'warmupJobIds': [item['jobId'] for item in warmup], 'samples': samples,
            'medianWorkerDurationMs': statistics.median(durations),
            'medianBatchThroughputJobsPerSecond': statistics.median(
                sample['throughputJobsPerSecond'] for sample in samples)}
    root = broker.jobs_root.parent / 'benchmarks' / BENCHMARK_ID
    root.mkdir(parents=True, exist_ok=True)
    baseline_path = root / 'baseline.json'
    if baseline_path.exists():
        pointer = json.loads(baseline_path.read_text(encoding='utf-8'))
        saved = root / (pointer['benchmarkRunId'] + '.json')
        if sha(saved) != pointer['sha256']:
            raise ValueError('Pinned benchmark baseline hash changed.')
        report['comparison'] = compare(json.loads(saved.read_text(encoding='utf-8')), report)
    else:
        report['comparison'] = {'verdict': 'baseline', 'reasons': [], 'baselineRunId': report['benchmarkRunId']}
    report['recordId'] = digest(report)
    path = root / (report['benchmarkRunId'] + '.json')
    with path.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, separators=(',', ':'))
    if not baseline_path.exists():
        with baseline_path.open('x', encoding='utf-8') as stream:
            json.dump({'schemaVersion': 1, 'benchmarkRunId': report['benchmarkRunId'],
                       'sha256': sha(path)}, stream, separators=(',', ':'))
    return path, report


def history(config_path):
    broker = Broker(config_path)
    root = broker.jobs_root.parent / 'benchmarks' / BENCHMARK_ID
    results = []
    for path in sorted(root.glob('[0-9a-f]*.json')) if root.exists() else []:
        report = json.loads(path.read_text(encoding='utf-8'))
        if report.get('benchmarkId') == BENCHMARK_ID:
            results.append({'benchmarkRunId': report['benchmarkRunId'], 'createdAtUtc': report['createdAtUtc'],
                            'comparison': report['comparison'],
                            'medianWorkerDurationMs': {name: tier['medianWorkerDurationMs']
                                                       for name, tier in report['tiers'].items()}})
    return results


def pin_baseline(config_path, run_id):
    if not re.fullmatch('[0-9a-f]{32}', run_id):
        raise ValueError('A 32-character benchmark run ID is required.')
    broker = Broker(config_path)
    root = broker.jobs_root.parent / 'benchmarks' / BENCHMARK_ID
    path = root / (run_id + '.json')
    report = json.loads(path.read_text(encoding='utf-8'))
    if report.get('benchmarkId') != BENCHMARK_ID or report.get('benchmarkRunId') != run_id:
        raise ValueError('Selected benchmark record is invalid.')
    identity = {key: value for key, value in report.items() if key != 'recordId'}
    if report.get('recordId') != digest(identity):
        raise ValueError('Selected benchmark record identity changed.')
    pointer = {'schemaVersion': 1, 'benchmarkRunId': run_id, 'sha256': sha(path)}
    baseline_path = root / 'baseline.json'
    if baseline_path.exists():
        archive = root / 'baseline-history'
        archive.mkdir(exist_ok=True)
        with (archive / (uuid.uuid4().hex + '.json')).open('x', encoding='utf-8') as stream:
            stream.write(baseline_path.read_text(encoding='utf-8'))
    temporary = root / 'baseline.json.tmp'
    temporary.write_text(json.dumps(pointer, separators=(',', ':')), encoding='utf-8')
    os.replace(temporary, baseline_path)
    return pointer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('run', 'history', 'compare', 'pin'))
    parser.add_argument('--config', required=True)
    parser.add_argument('--repetitions', type=int, default=3)
    parser.add_argument('--baseline')
    parser.add_argument('--candidate')
    parser.add_argument('--run-id')
    args = parser.parse_args()
    if args.command == 'run':
        path, report = run_benchmark(args.config, args.repetitions)
        print(json.dumps({'record': str(path), 'benchmarkRunId': report['benchmarkRunId'],
                          'comparison': report['comparison'],
                          'medianWorkerDurationMs': {name: tier['medianWorkerDurationMs']
                                                     for name, tier in report['tiers'].items()}}, indent=2))
    elif args.command == 'history':
        print(json.dumps(history(args.config), indent=2))
    elif args.command == 'pin':
        if not args.run_id:
            raise ValueError('--run-id is required for pin.')
        print(json.dumps(pin_baseline(args.config, args.run_id), indent=2))
    else:
        if not args.baseline or not args.candidate:
            raise ValueError('--baseline and --candidate are required for compare.')
        print(json.dumps(compare(json.loads(Path(args.baseline).read_text()),
                                 json.loads(Path(args.candidate).read_text())), indent=2))


if __name__ == '__main__':
    main()
