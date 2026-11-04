"""Standalone, localhost Scientific Runtime Broker for certified CGAL mesh handoffs."""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import threading
import time
import uuid
from urllib.parse import urlsplit


CONTRACT = dict(id='math3d.mesh-product-handoff', version=1, workerResultSchemaVersion=1,
                meshDocumentSchemaVersion=1, inputFormat='obj', viewer='MeshDocumentViewport')
CONSUMER_FILES = {'renderer/src/mesh/surfaceMesh.ts', 'renderer/src/mesh/meshDocumentAdapter.ts',
                  'renderer/src/mesh/meshResourceStore.ts', 'renderer/src/workspace/MeshDocumentViewport.tsx',
                  'renderer/src/components/SurfaceViewer.tsx', 'packages/core/src/meshDocument.ts'}
MAX_INPUT = 32 * 1024 * 1024


def sha(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(65536), b''):
            digest.update(block)
    return digest.hexdigest()


def package_hash(prefix):
    records = sorted((prefix / 'conda-meta').glob('*.json'), key=lambda path: path.name)
    if not records:
        raise ValueError('Conda package inventory is unavailable.')
    text = ''.join(f'{item.name}\0{sha(item)}\n' for item in records)
    return hashlib.sha256(text.encode()).hexdigest()


def require_hash(path, expected, label):
    if not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected):
        raise ValueError(f'{label} identity is missing.')
    if not path.is_file() or sha(path) != expected:
        raise ValueError(f'{label} hash mismatch.')


class Broker:
    def __init__(self, config_path):
        config = json.loads(Path(config_path).read_text(encoding='utf-8'))
        if config.get('schemaVersion') != 1:
            raise ValueError('Unsupported broker configuration.')
        self.paths = {name: Path(config[name]).resolve(strict=True) for name in
                      ('manifest', 'runtimeManifest', 'adapter', 'workerContract', 'python', 'worker', 'prefix', 'datasetRoot')}
        self.math3d_root = Path(config['math3dRoot']).resolve(strict=True) if config.get('math3dRoot') else None
        self.jobs_root = Path(config['jobsRoot']).resolve()
        self.jobs_root.mkdir(parents=True, exist_ok=True)
        self.jobs = {}
        self.lock = threading.RLock()
        self.verify()
        for saved in self.jobs_root.glob('*/broker-result.json'):
            try:
                job = json.loads(saved.read_text(encoding='utf-8'))
                if re.fullmatch('[0-9a-f]{32}', job.get('jobId', '')) and job.get('state') != 'running':
                    job['process'] = None
                    job['cancel'] = threading.Event()
                    self.jobs[job['jobId']] = job
            except (OSError, ValueError, KeyError):
                pass

    def verify(self):
        manifest_path = self.paths['manifest']
        require_hash(manifest_path, Path(str(manifest_path) + '.sha256').read_text().strip(), 'Certified manifest')
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if manifest.get('schemaVersion') != 1 or manifest.get('kind') != 'scientific.certified-capabilities':
            raise ValueError('Unsupported certified manifest.')
        capabilities = manifest.get('certifiedCapabilities')
        if not isinstance(capabilities, list):
            raise ValueError('Certified capabilities are missing.')
        for entry in capabilities:
            if (entry.get('runtimeId'), entry.get('capabilityId'), entry.get('level')) != (
                    'cgal-win-conda', 'mesh.interop.vtk-math3d', 'L9'):
                raise ValueError('Unqualified or unsupported provider in certified manifest.')
            if entry.get('productContract') != CONTRACT:
                raise ValueError('MATH3D product contract changed.')
            contract_hash = hashlib.sha256(json.dumps(CONTRACT, separators=(',', ':')).encode()).hexdigest()
            if entry.get('productContractSha256') != contract_hash:
                raise ValueError('MATH3D product contract hash mismatch.')
            for name, field in [('runtimeManifest', 'runtimeManifestSha256'), ('adapter', 'adapterSha256'),
                                ('workerContract', 'workerContractSha256'), ('python', 'pythonSha256'),
                                ('worker', 'workerBinarySha256')]:
                require_hash(self.paths[name], entry.get(field), name)
            if package_hash(self.paths['prefix']) != entry.get('packageRecordsSha256'):
                raise ValueError('Conda package inventory hash mismatch.')
            if any(not re.fullmatch('[0-9a-f]{64}', entry.get(key, '')) for key in
                   ('recordId', 'runFingerprintSha256', 'suiteRevisionSha256', 'qualificationSha256',
                    'referenceInputSha256', 'referenceArtifactSha256', 'sourceL8RecordId',
                    'consumerSourceSha256')):
                raise ValueError('Qualification identity is incomplete.')
            support = entry.get('supportingRecords')
            if not isinstance(support, list) or len(support) != 10:
                raise ValueError('The L0-L9 qualification chain is incomplete.')
            for level, record in enumerate(support):
                if (record.get('level') != f'L{level}' or not re.fullmatch('[0-9a-f]{64}', record.get('recordId', ''))
                        or not re.fullmatch('[0-9a-f]{32}', record.get('runId', ''))):
                    raise ValueError('The L0-L9 qualification chain is invalid.')
            if support[-1]['recordId'] != entry['recordId'] or support[-1]['runId'] != entry['sourceRunId']:
                raise ValueError('L9 qualification identity differs from its support chain.')
            if support[8]['recordId'] != entry['sourceL8RecordId'] or support[8]['runId'] != entry['sourceL8RunId']:
                raise ValueError('L8 qualification identity differs from its support chain.')
            if not isinstance(entry.get('consumerSources'), dict) or set(entry['consumerSources']) != CONSUMER_FILES:
                raise ValueError('MATH3D consumer source identity is missing.')
        self.capabilities = capabilities
        return capabilities

    def discover(self):
        self.verify()
        return {'schemaVersion': 1, 'providers': [{'runtimeId': 'cgal-win-conda', 'backend': 'windows-native',
                'capabilities': [{'capabilityId': entry['capabilityId'], 'level': entry['level'],
                                  'recordId': entry['recordId'], 'contractVersion': CONTRACT['version']}]
                } for entry in self.capabilities]}

    def snapshot(self, job):
        with self.lock:
            return {key: value for key, value in job.items() if key not in ('process', 'cancel')}

    def submit(self, body):
        self.verify()
        if body.get('schemaVersion') != 1 or body.get('runtimeId') != 'cgal-win-conda' or body.get('capabilityId') != 'mesh.interop.vtk-math3d':
            raise ValueError('Unsupported broker job contract.')
        if not self.capabilities:
            raise ValueError('No current certified capability is available.')
        timeout = body.get('timeoutSeconds', 120)
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 1 <= timeout <= 120:
            raise ValueError('Invalid timeout.')
        input_info = body.get('input')
        if not isinstance(input_info, dict) or not isinstance(input_info.get('path'), str):
            raise ValueError('Input artifact is required.')
        source = Path(input_info['path']).resolve(strict=True)
        if source.suffix.lower() != '.obj' or not source.is_relative_to(self.paths['datasetRoot']) or source.stat().st_size > MAX_INPUT:
            raise ValueError('Input must be a bounded registered OBJ dataset.')
        require_hash(source, input_info.get('sha256'), 'Input artifact')
        if input_info['sha256'] != self.capabilities[0]['referenceInputSha256']:
            raise ValueError('Input is outside the fixed L9 qualification fixture.')
        job_id = uuid.uuid4().hex
        directory = self.jobs_root / job_id
        dataset = directory / 'dataset'
        dataset.mkdir(parents=True)
        copied = dataset / 'input.obj'
        shutil.copyfile(source, copied)
        require_hash(copied, input_info['sha256'], 'Copied input artifact')
        request = {'schemaVersion': 1, 'runId': job_id, 'runtimeId': 'cgal-win-conda',
                   'recipeId': 'cgal.validate', 'operation': 'cgal.validate', 'parameters': {},
                   'workingDirectory': str(directory), 'datasetRoot': str(dataset),
                   'timeoutSeconds': timeout, 'inputArtifacts': [{'path': str(copied), 'sha256': input_info['sha256']}],
                   'outputArtifacts': [{'path': 'l5-positive.obj', 'mediaType': 'model/obj'}],
                   'provenance': {'brokerContractVersion': 1, 'certificationRecordId': self.capabilities[0]['recordId']}}
        (directory / 'request.json').write_text(json.dumps(request, separators=(',', ':')), encoding='utf-8')
        job = {'jobId': job_id, 'runtimeId': 'cgal-win-conda', 'capabilityId': 'mesh.interop.vtk-math3d',
               'state': 'running', 'stage': 'queued', 'progress': 0, 'contractVersion': 1,
               'certificationRecordId': self.capabilities[0]['recordId'], 'artifacts': [], 'diagnostics': [],
               'directory': str(directory), 'cancel': threading.Event(), 'process': None}
        with self.lock:
            self.jobs[job_id] = job
        threading.Thread(target=self._run, args=(job, timeout), daemon=True).start()
        return self.snapshot(job)

    @staticmethod
    def _stop_process(process):
        if process is None or process.poll() is not None:
            return
        if os.name == 'nt':
            subprocess.run(['taskkill', '/T', '/F', '/PID', str(process.pid)], capture_output=True)
        else:
            os.killpg(process.pid, signal.SIGKILL)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()

    def cancel(self, job_id):
        with self.lock:
            job = self.jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            if job['state'] == 'running':
                job['cancel'].set()
                self._stop_process(job['process'])
            return self.snapshot(job)

    def _run(self, job, timeout):
        directory = Path(job['directory'])
        started = time.monotonic()
        process = None
        try:
            self.verify()
            with self.lock:
                job.update(stage='worker', progress=20)
            env = os.environ.copy()
            prefix = self.paths['prefix']
            env['PATH'] = os.pathsep.join([str(prefix), str(prefix / 'Library' / 'bin'), str(prefix / 'Scripts'), env.get('PATH', '')])
            env['PYTHONNOUSERSITE'] = '1'
            env['PYTHONIOENCODING'] = 'utf-8'
            command = [str(self.paths['python']), str(self.paths['adapter']), '--request', str(directory / 'request.json'),
                       '--worker', str(self.paths['worker'])]
            log_path = directory / 'full.log'
            with log_path.open('w', encoding='utf-8') as log:
                process = subprocess.Popen(command, cwd=directory, env=env, stdout=log, stderr=subprocess.STDOUT,
                                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), start_new_session=os.name != 'nt')
                with self.lock:
                    job['process'] = process
                while process.poll() is None:
                    if job['cancel'].is_set() or time.monotonic() - started > timeout + 5:
                        self._stop_process(process)
                        break
                    with self.lock:
                        job['progress'] = min(85, max(job['progress'], int((time.monotonic() - started) / timeout * 80) + 20))
                    time.sleep(0.1)
                process.wait(timeout=5)
            if job['cancel'].is_set():
                with self.lock: job.update(state='cancelled', stage='completed', diagnostics=['Job cancelled.'])
                return
            if time.monotonic() - started >= timeout:
                with self.lock: job.update(state='timed-out', stage='completed', diagnostics=['Job time limit exceeded.'])
                return
            result_path = directory / 'results.json'
            if result_path.is_file() and result_path.stat().st_size > 1048576:
                raise ValueError('Worker result exceeds 1 MiB.')
            result = json.loads(result_path.read_text(encoding='utf-8')) if result_path.is_file() else None
            artifact = directory / 'l5-positive.obj'
            if artifact.is_file() and artifact.stat().st_size > MAX_INPUT:
                raise ValueError('Worker artifact exceeds 32 MiB.')
            if process.returncode != 0 or result is None or result.get('state') != 'succeeded':
                state = 'partial' if artifact.exists() else 'failed'
                with self.lock: job.update(state=state, stage='completed', diagnostics=[
                    item.get('message', '') for item in (result or {}).get('diagnostics', [])] or ['Worker failed.'])
                return
            artifact_hash = sha(artifact)
            if (result.get('runId') != job['jobId'] or 'mesh.validate' not in result.get('validatedCapabilities', [])
                    or not any(item.get('path') == 'l5-positive.obj' and item.get('sha256') == artifact_hash
                               for item in result.get('artifacts', []))):
                with self.lock: job.update(state='partial', stage='completed', diagnostics=['Worker artifact verification failed.'])
                return
            self.verify()
            entry = next((item for item in self.capabilities if item['recordId'] == job['certificationRecordId']), None)
            if entry is None or artifact_hash != entry['referenceArtifactSha256']:
                with self.lock: job.update(state='partial', stage='completed', diagnostics=['Current qualification or reference artifact differs.'])
                return
            handoff = {'schemaVersion': 1, 'contract': CONTRACT, 'runtimeId': 'cgal-win-conda',
                       'capabilityId': 'mesh.interop.vtk-math3d', 'sourceL8RunId': entry['sourceL8RunId'],
                       'sourceL8RecordId': entry['sourceL8RecordId'],
                       'workerRequest': {'path': str(directory / 'request.json'), 'sha256': sha(directory / 'request.json')},
                       'workerResult': {'path': str(result_path), 'sha256': sha(result_path)},
                       'artifact': {'path': str(artifact), 'sha256': artifact_hash}}
            handoff_path = directory / 'handoff.json'
            handoff_path.write_text(json.dumps(handoff, separators=(',', ':')), encoding='utf-8')
            artifacts = [{'path': name, 'sha256': sha(directory / name), 'bytes': (directory / name).stat().st_size}
                         for name in ('l5-positive.obj', 'handoff.json')]
            with self.lock: job.update(state='succeeded', stage='completed', progress=100, artifacts=artifacts)
        except Exception as error:
            with self.lock: job.update(state='failed', stage='completed', diagnostics=[str(error)[:1000]])
        finally:
            with self.lock:
                job['process'] = None
                job['durationMs'] = round((time.monotonic() - started) * 1000)
                (directory / 'broker-result.json').write_text(json.dumps(self.snapshot(job), separators=(',', ':')), encoding='utf-8')

    def artifact(self, job_id, name):
        with self.lock:
            job = self.jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            if job['state'] != 'succeeded':
                raise ValueError('Job has no verified artifacts.')
            entry = next((item for item in job['artifacts'] if item['path'] == name), None)
            if entry is None:
                raise ValueError('Artifact is not registered.')
            path = Path(job['directory']) / name
            if path.stat().st_size != entry['bytes'] or path.stat().st_size > MAX_INPUT:
                raise ValueError('Output artifact size changed.')
            require_hash(path, entry['sha256'], 'Output artifact')
            return path.read_bytes()

    def promote(self, job_id):
        with self.lock:
            job = self.jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            reasons = []
            entry = None
            try:
                self.verify()
                entry = next((item for item in self.capabilities if item['recordId'] == job['certificationRecordId']), None)
                if entry is None:
                    reasons.append('The supporting L0-L9 qualification is no longer current in the certified manifest.')
            except (ValueError, OSError) as error:
                reasons.append('Certified manifest or runtime identity changed: ' + str(error))
            if job['state'] != 'succeeded':
                reasons.append(f"Source job is {job['state']}; a successful verified run is required.")
            if entry is not None and job['state'] == 'succeeded':
                if self.math3d_root is None:
                    reasons.append('MATH3D consumer checkout is not configured for promotion.')
                else:
                    for name, expected in entry['consumerSources'].items():
                        try:
                            require_hash(self.math3d_root / name, expected, 'MATH3D consumer ' + name)
                        except (ValueError, OSError) as error:
                            reasons.append(str(error))
                    source_hash = hashlib.sha256(json.dumps(entry['consumerSources'], separators=(',', ':')).encode()).hexdigest()
                    if source_hash != entry['consumerSourceSha256']:
                        reasons.append('MATH3D consumer source fingerprint changed.')
                try:
                    handoff = json.loads(self.artifact(job_id, 'handoff.json'))
                    output = self.artifact(job_id, 'l5-positive.obj')
                    worker_request = json.loads((Path(job['directory']) / 'request.json').read_text(encoding='utf-8'))
                    worker_result = json.loads((Path(job['directory']) / 'results.json').read_text(encoding='utf-8'))
                    if (handoff.get('contract') != CONTRACT or handoff.get('runtimeId') != job['runtimeId']
                            or handoff.get('capabilityId') != job['capabilityId']
                            or handoff.get('sourceL8RunId') != entry['sourceL8RunId']
                            or handoff.get('sourceL8RecordId') != entry['sourceL8RecordId']
                            or worker_request.get('runId') != job_id or worker_result.get('runId') != job_id
                            or worker_result.get('state') != 'succeeded'
                            or 'mesh.validate' not in worker_result.get('validatedCapabilities', [])
                            or handoff.get('artifact', {}).get('sha256') != hashlib.sha256(output).hexdigest()
                            or handoff.get('workerResult', {}).get('sha256') != sha(Path(job['directory']) / 'results.json')
                            or handoff.get('workerRequest', {}).get('sha256') != sha(Path(job['directory']) / 'request.json')):
                        reasons.append('The broker handoff contract or worker artifact identity changed.')
                except (ValueError, OSError, KeyError, json.JSONDecodeError) as error:
                    reasons.append('Verified broker handoff is unavailable: ' + str(error))
            decision = 'allowed' if not reasons else 'blocked'
            promotion_id = uuid.uuid4().hex
            record = {'schemaVersion': 1, 'kind': 'scientific.math3d-promotion', 'promotionId': promotion_id,
                      'decision': decision, 'reasons': reasons, 'sourceJobId': job_id,
                      'sourceJobState': job['state'], 'capabilityId': job['capabilityId'],
                      'runtimeId': job['runtimeId'], 'certificationRecordId': job['certificationRecordId'],
                      'manifestSha256': sha(self.paths['manifest']) if self.paths['manifest'].is_file() else None,
                      'contractVersion': CONTRACT['version'],
                      'handoffSha256': sha(Path(job['directory']) / 'handoff.json') if decision == 'allowed' else None,
                      'artifactSha256': entry['referenceArtifactSha256'] if decision == 'allowed' else None}
            directory = Path(job['directory']) / 'promotions'
            directory.mkdir(exist_ok=True)
            path = directory / (promotion_id + '.json')
            with path.open('x', encoding='utf-8') as stream:
                json.dump(record, stream, separators=(',', ':'))
            return {**record, 'path': str(path), 'sha256': sha(path)}


def handler_for(broker):
    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, data):
            raw = json.dumps(data, separators=(',', ':')).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            parts = urlsplit(self.path).path.strip('/').split('/')
            try:
                if parts == ['v1', 'providers']:
                    return self.reply(200, broker.discover())
                if len(parts) == 3 and parts[:2] == ['v1', 'jobs']:
                    with broker.lock:
                        job = broker.jobs.get(parts[2])
                        if job is None: raise KeyError(parts[2])
                        return self.reply(200, broker.snapshot(job))
                if len(parts) == 5 and parts[:2] == ['v1', 'jobs'] and parts[3] == 'artifacts':
                    raw = broker.artifact(parts[2], parts[4])
                    self.send_response(200)
                    self.send_header('Content-Type', 'model/obj' if parts[4].endswith('.obj') else 'application/json')
                    self.send_header('Content-Length', str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                    return
                self.reply(404, {'error': 'Unknown route.'})
            except KeyError:
                self.reply(404, {'error': 'Job not found.'})
            except (ValueError, OSError) as error:
                self.reply(409, {'error': str(error)})

        def do_POST(self):
            parts = urlsplit(self.path).path.strip('/').split('/')
            try:
                if parts == ['v1', 'jobs']:
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 0 < size <= 65536: raise ValueError('Request exceeds 64 KiB.')
                    return self.reply(202, broker.submit(json.loads(self.rfile.read(size))))
                if len(parts) == 4 and parts[:2] == ['v1', 'jobs'] and parts[3] == 'cancel':
                    return self.reply(200, broker.cancel(parts[2]))
                if len(parts) == 4 and parts[:2] == ['v1', 'jobs'] and parts[3] == 'promote':
                    return self.reply(200, broker.promote(parts[2]))
                self.reply(404, {'error': 'Unknown route.'})
            except KeyError:
                self.reply(404, {'error': 'Job not found.'})
            except (ValueError, OSError, json.JSONDecodeError) as error:
                self.reply(400, {'error': str(error)})

        def log_message(self, format, *args):
            pass
    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('verify', 'serve'))
    parser.add_argument('--config', required=True)
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    broker = Broker(args.config)
    if args.command == 'verify':
        print(json.dumps(broker.discover(), indent=2))
        return
    with ThreadingHTTPServer(('127.0.0.1', args.port), handler_for(broker)) as server:
        print(f'Scientific broker listening on http://127.0.0.1:{server.server_port}', flush=True)
        server.serve_forever()


if __name__ == '__main__':
    main()
