"""DS-SCI-029: real CGAL concurrency, isolation, capacity and memory evidence."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import statistics
import tempfile
import threading
import time
import uuid

from broker import Broker, sha
from qualify_cleanup import DiagnosticBroker, fixture, wait_state
from telemetry import host_fingerprint, psutil


def configured(config_path, **options):
    config = json.loads(Path(config_path).read_text(encoding='utf-8'))
    config.update(options)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', encoding='utf-8', delete=False) as stream:
        json.dump(config, stream)
        path = Path(stream.name)
    return path


def launch_batch(broker, count):
    gate = threading.Barrier(count)
    request = fixture(broker)
    release = broker.jobs_root.parent / 'diagnostics' / ('release-' + uuid.uuid4().hex + '.gate')
    release.parent.mkdir(exist_ok=True)
    broker.batch_release_gate = release
    submitted = []

    def submit_one(_):
        gate.wait(timeout=20)
        return broker.submit(request)

    started = time.monotonic()
    try:
        with ThreadPoolExecutor(max_workers=count) as pool:
            submitted = list(pool.map(submit_one, range(count)))
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if all('workerPid' in broker.snapshot(broker.jobs[item['jobId']]) for item in submitted):
                break
            time.sleep(0.005)
        else:
            raise TimeoutError('Not all scientific workers reached the release barrier.')
        release.write_text('go', encoding='utf-8')
        jobs = [wait_state(broker, item['jobId'], timeout=120) for item in submitted]
        elapsed = time.monotonic() - started
    finally:
        if not release.exists():
            release.write_text('go', encoding='utf-8')
        broker.batch_release_gate = None
        for item in submitted:
            if broker.jobs[item['jobId']]['state'] == 'running':
                broker.cancel(item['jobId'])
                wait_state(broker, item['jobId'])
        release.unlink(missing_ok=True)
    if any(job['state'] != 'succeeded' or job.get('cleanup', {}).get('state') != 'passed' for job in jobs):
        raise AssertionError('A concurrent CGAL job failed: ' + str([(job['jobId'], job['state'], job['diagnostics']) for job in jobs]))
    ids = [job['jobId'] for job in jobs]
    directories = [job['directory'] for job in jobs]
    if len(set(ids)) != count or len(set(directories)) != count:
        raise AssertionError('Concurrent jobs did not receive isolated identities and directories.')
    reference_hash = broker.capabilities[0]['referenceArtifactSha256']
    events = []
    timings = []
    for job in jobs:
        directory = Path(job['directory'])
        request_data = json.loads((directory / 'request.json').read_text(encoding='utf-8'))
        result = json.loads((directory / 'results.json').read_text(encoding='utf-8'))
        handoff = json.loads(broker.artifact(job['jobId'], 'handoff.json'))
        snapshot = broker.source(job['jobId'])
        timing_path = directory / 'adapter-timing.json'
        timing = json.loads(timing_path.read_text(encoding='utf-8'))
        if timing['exitCode'] != 0 or timing['finishedMonotonicNs'] <= timing['startedMonotonicNs']:
            raise AssertionError('Concurrent adapter timing evidence is invalid.')
        events.extend([(timing['startedMonotonicNs'], 1), (timing['finishedMonotonicNs'], -1)])
        timings.append({'jobId': job['jobId'], 'adapterPid': timing['adapterPid'],
                        'startedMonotonicNs': timing['startedMonotonicNs'],
                        'finishedMonotonicNs': timing['finishedMonotonicNs'], 'timingSha256': sha(timing_path)})
        if (request_data['runId'] != job['jobId'] or result['runId'] != job['jobId'] or
                request_data['provenance']['sourceSnapshotSha256'] != job['sourceSnapshotSha256'] or
                snapshot['schemaVersion'] != 1 or handoff['workerRequest']['sha256'] != sha(directory / 'request.json') or
                handoff['workerResult']['sha256'] != sha(directory / 'results.json') or
                handoff['artifact']['sha256'] != reference_hash or
                sha(directory / 'l5-positive.obj') != reference_hash):
            raise AssertionError('Concurrent artifact or source identity crossed a job boundary.')
    active = peak = 0
    for _, delta in sorted(events, key=lambda event: (event[0], -event[1])):
        active += delta
        peak = max(peak, active)
    if peak != count:
        raise AssertionError(f'Only {peak} of {count} CGAL adapters overlapped.')
    return {'concurrency': count, 'jobIds': ids, 'outputSha256': reference_hash,
            'peakAdapterOverlap': peak, 'adapterTimings': timings,
            'sourceSnapshotSha256': [job['sourceSnapshotSha256'] for job in jobs],
            'throughputJobsPerSecond': round(count / elapsed, 4),
            'tailLatencyMs': max(job['durationMs'] for job in jobs),
            'medianLatencyMs': statistics.median(job['durationMs'] for job in jobs)}


def check_capacity(config_path):
    path = configured(config_path, maxConcurrentJobs=1)
    previous = os.environ.get('SCIENTIFIC_BROKER_DIAGNOSTIC_MODE')
    os.environ['SCIENTIFIC_BROKER_DIAGNOSTIC_MODE'] = 'hold'
    broker = None
    job = None
    try:
        broker = DiagnosticBroker(path)
        job = broker.submit(fixture(broker))
        deadline = time.monotonic() + 10
        while 'workerPid' not in broker.snapshot(broker.jobs[job['jobId']]) and time.monotonic() < deadline:
            time.sleep(0.01)
        try:
            broker.submit(fixture(broker))
        except ValueError as error:
            if 'Worker capacity reached' not in str(error):
                raise
            reason = str(error)
        else:
            raise AssertionError('Worker capacity limit accepted a second active job.')
        broker.cancel(job['jobId'])
        finished = wait_state(broker, job['jobId'])
        if finished['state'] != 'cancelled' or finished['cleanup']['state'] != 'passed':
            raise AssertionError('Capacity test worker did not cleanly cancel.')
        return {'limit': 1, 'rejectedReason': reason, 'heldJobId': job['jobId'], 'terminalState': finished['state']}
    finally:
        if broker and job and broker.jobs[job['jobId']]['state'] == 'running':
            broker.cancel(job['jobId'])
            wait_state(broker, job['jobId'])
        path.unlink(missing_ok=True)
        if previous is None:
            os.environ.pop('SCIENTIFIC_BROKER_DIAGNOSTIC_MODE', None)
        else:
            os.environ['SCIENTIFIC_BROKER_DIAGNOSTIC_MODE'] = previous


def check_memory(config_path):
    path = configured(config_path, memoryLimitMiB=1)
    try:
        broker = Broker(path)
        submitted = broker.submit(fixture(broker))
        job = wait_state(broker, submitted['jobId'], timeout=30)
        if job['state'] != 'resource-exhausted' or not any('memory budget exceeded' in item for item in job['diagnostics']):
            raise AssertionError(f"Memory pressure was not reported clearly: {job['state']} {job['diagnostics']}")
        if job['artifacts'] or job['cleanup']['state'] != 'passed':
            raise AssertionError('Memory-limited job retained artifacts or active workers.')
        if broker.promote(job['jobId'])['decision'] != 'blocked':
            raise AssertionError('Resource failure was promoted.')
        return {'limitMiB': 1, 'jobId': job['jobId'], 'terminalState': job['state'],
                'reason': job['diagnostics'][0], 'cleanup': job['cleanup']['state']}
    finally:
        path.unlink(missing_ok=True)


def run_suite(config_path):
    if psutil is None:
        raise RuntimeError('psutil is required for process and memory verification.')
    path = configured(config_path, maxConcurrentJobs=8)
    try:
        broker = Broker(path)
        entry = broker.capabilities[0]
        available_gib = psutil.virtual_memory().available / 1024 ** 3
        counts = [1, 2, 4, 8] if available_gib >= 8 else [1, 2, 4] if available_gib >= 4 else [1, 2]
        batches = [launch_batch(broker, count) for count in counts for _ in range(2)]
        capacity = check_capacity(config_path)
        memory = check_memory(config_path)
        report = {'schemaVersion': 1, 'suiteId': 'scientific-broker-concurrency-v1',
                  'suiteRunId': uuid.uuid4().hex, 'createdAtUtc': datetime.now(timezone.utc).isoformat(),
                  'state': 'passed', 'runtimeId': 'cgal-win-conda',
                  'capabilityId': 'mesh.interop.vtk-math3d', 'certificationRecordId': entry['recordId'],
                  'hostFingerprintSha256': host_fingerprint(), 'availableMemoryGiBAtStart': round(available_gib, 2),
                  'testedConcurrency': counts, 'batchRuns': batches, 'capacity': capacity, 'memoryPressure': memory,
                  'suiteSourceSha256': sha(Path(__file__)), 'brokerSourceSha256': sha(Path(__file__).with_name('broker.py')),
                  'telemetrySourceSha256': sha(Path(__file__).with_name('telemetry.py')),
                  'launcherSourceSha256': sha(Path(__file__).with_name('start_worker.py')),
                  'sourceSnapshotSourceSha256': sha(Path(__file__).with_name('source_snapshot.py')),
                  'diagnosticWorkerQualified': False}
        root = broker.jobs_root.parent / 'diagnostics'
        root.mkdir(exist_ok=True)
        output = root / (report['suiteRunId'] + '.json')
        with output.open('x', encoding='utf-8') as stream:
            json.dump(report, stream, separators=(',', ':'))
        return output, report
    finally:
        path.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    path, report = run_suite(args.config)
    print(json.dumps({'record': str(path), 'state': report['state'],
                      'suiteRunId': report['suiteRunId'], 'testedConcurrency': report['testedConcurrency'],
                      'jobCount': sum(len(batch['jobIds']) for batch in report['batchRuns']),
                      'capacity': report['capacity'], 'memoryPressure': report['memoryPressure']}, indent=2))


if __name__ == '__main__':
    main()
