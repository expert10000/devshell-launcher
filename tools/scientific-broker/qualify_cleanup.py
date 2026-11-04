"""Real and diagnostic worker cancellation, timeout and orphan cleanup suite."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
import uuid

from broker import Broker, sha
from telemetry import psutil


class DiagnosticBroker(Broker):
    def __init__(self, config_path):
        self.diagnostic = False
        super().__init__(config_path)
        self.paths['adapter'] = Path(__file__).with_name('diagnostic_worker.py')
        self.diagnostic = True

    def verify(self):
        if self.diagnostic:
            return self.capabilities
        return super().verify()


def fixture(broker):
    source = broker.paths['datasetRoot'] / 'math3d' / 'basic' / '01_tetrahedron.obj'
    return {'schemaVersion': 1, 'runtimeId': 'cgal-win-conda',
            'capabilityId': 'mesh.interop.vtk-math3d',
            'input': {'path': str(source), 'sha256': sha(source)}}


def wait_state(broker, job_id, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        item = broker.snapshot(broker.jobs[job_id])
        if item['state'] != 'running':
            return item
        time.sleep(0.01)
    raise TimeoutError(f'Broker job {job_id} did not finish.')


def child_is_active(pid):
    try:
        process = psutil.Process(pid)
        return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False


def check_terminal(broker, item, expected, child_pid=None, expect_orphan=False):
    if item['state'] != expected or item['artifacts'] or item['cleanup']['state'] != 'passed':
        raise AssertionError(f"Unexpected {expected} outcome: {item['state']} / {item['cleanup']}")
    if Path(item['directory'], 'l5-positive.obj').exists() or Path(item['directory'], 'handoff.json').exists():
        raise AssertionError('A stopped job retained a partial mesh or handoff artifact.')
    if child_pid is not None and child_is_active(child_pid):
        raise AssertionError(f'Child process {child_pid} remains active.')
    if item['cleanup']['activePids'] or (expect_orphan and child_pid not in item['cleanup']['orphanPids']):
        raise AssertionError('Orphan detection or final process cleanup failed.')
    try:
        broker.artifact(item['jobId'], 'l5-positive.obj')
    except ValueError:
        pass
    else:
        raise AssertionError('Stopped job exposed an output artifact.')
    promotion = broker.promote(item['jobId'])
    if promotion['decision'] != 'blocked' or not any(expected in reason for reason in promotion['reasons']):
        raise AssertionError('Stopped job was not blocked from MATH3D promotion.')
    return {'jobId': item['jobId'], 'state': item['state'], 'workerPid': item.get('workerPid'),
            'childPid': child_pid, 'cleanup': item['cleanup'], 'telemetrySha256': item['telemetrySha256'],
            'promotionDecision': promotion['decision'], 'removedPartialArtifacts': item['cleanup']['removedPartialArtifacts']}


def run_diagnostic(config_path, mode, cancel=False):
    broker = DiagnosticBroker(config_path)
    previous = os.environ.get('SCIENTIFIC_BROKER_DIAGNOSTIC_MODE')
    os.environ['SCIENTIFIC_BROKER_DIAGNOSTIC_MODE'] = mode
    try:
        request = fixture(broker)
        request['timeoutSeconds'] = 1 if not cancel and mode == 'hold' else 120
        job = broker.submit(request)
        directory = Path(job['directory'])
        child_file = directory / 'diagnostic-child.json'
        deadline = time.monotonic() + 5
        while not child_file.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        if not child_file.exists():
            raise AssertionError('Diagnostic child did not start.')
        child_pid = json.loads(child_file.read_text())['pid']
        if cancel:
            broker.cancel(job['jobId'])
        item = wait_state(broker, job['jobId'])
        expected = 'cancelled' if cancel else 'timed-out' if mode == 'hold' else 'partial'
        return check_terminal(broker, item, expected, child_pid, expect_orphan=mode == 'orphan')
    finally:
        if 'job' in locals() and broker.jobs[job['jobId']]['state'] == 'running':
            broker.cancel(job['jobId'])
        if 'child_pid' in locals() and child_is_active(child_pid):
            try:
                psutil.Process(child_pid).kill()
            except psutil.NoSuchProcess:
                pass
        if previous is None:
            os.environ.pop('SCIENTIFIC_BROKER_DIAGNOSTIC_MODE', None)
        else:
            os.environ['SCIENTIFIC_BROKER_DIAGNOSTIC_MODE'] = previous


def run_real_cancel(config_path):
    broker = Broker(config_path)
    for _ in range(8):
        job = broker.submit(fixture(broker))
        deadline = time.monotonic() + 2
        while 'workerPid' not in broker.snapshot(broker.jobs[job['jobId']]) and time.monotonic() < deadline:
            time.sleep(0.002)
        broker.cancel(job['jobId'])
        item = wait_state(broker, job['jobId'])
        if item['state'] == 'cancelled':
            return check_terminal(broker, item, 'cancelled')
    raise AssertionError('Could not cancel an active real CGAL adapter in eight attempts.')


def run_suite(config_path):
    if psutil is None:
        raise RuntimeError('psutil is required to verify worker descendants and orphan cleanup.')
    broker = Broker(config_path)
    entry = broker.capabilities[0]
    cases = {'realCancellation': run_real_cancel(config_path),
             'forcedCancellation': run_diagnostic(config_path, 'hold', cancel=True),
             'forcedTimeout': run_diagnostic(config_path, 'hold'),
             'orphanCleanup': run_diagnostic(config_path, 'orphan')}
    report = {'schemaVersion': 1, 'suiteId': 'scientific-broker-cleanup-v1',
              'suiteRunId': uuid.uuid4().hex, 'state': 'passed',
              'certificationRecordId': entry['recordId'],
              'runFingerprintSha256': entry['runFingerprintSha256'],
              'brokerSourceSha256': sha(Path(__file__).with_name('broker.py')),
              'telemetrySourceSha256': sha(Path(__file__).with_name('telemetry.py')),
              'diagnosticWorkerSha256': sha(Path(__file__).with_name('diagnostic_worker.py')),
              'diagnosticWorkerQualified': False, 'cases': cases}
    report['recordId'] = hashlib.sha256(json.dumps(report, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    path = broker.jobs_root.parent / 'diagnostics' / (report['suiteRunId'] + '.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, separators=(',', ':'))
    return path, report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    path, report = run_suite(args.config)
    print(json.dumps({'state': report['state'], 'suiteRunId': report['suiteRunId'],
                      'record': str(path), 'cases': {name: case['state'] for name, case in report['cases'].items()}}, indent=2))


if __name__ == '__main__':
    main()
