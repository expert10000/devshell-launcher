"""Candidate typed journey on the standard localhost broker job and artifact routes.

The profile accepts one pinned saved desktop Boolean result. Successful transport is
evidence, never a certified capability or release promotion.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import threading
import time
import uuid

from source_snapshot import capture_sources, repository_snapshot
from verify_typed_product import verify as verify_product


HEX = re.compile(r'^[0-9a-f]{64}$')
RUN = re.compile(r'^[0-9a-f]{32}$')
CAPABILITY = 'scientific.typed-journey-candidate'
ARTIFACTS = {
    'volume.msh': 'gmsh/volume.msh', 'boundary.obj': 'boundary/boundary.obj',
    'analysis.vtp': 'vtk/analysis.vtp', 'preview.png': 'vtk/preview.png',
    'measurement.json': 'scipy/measurement.json', 'converted.obj': 'converted.obj',
    'typed-provenance.json': 'typed-provenance.json',
    'vtk-mesh-document.json': 'product/vtk-mesh-document.json',
    'vtk-mesh-resource.bin': 'product/vtk-mesh-resource.bin',
    'read.m3dm': 'product/read.m3dm', 'product.json': 'product/product.json',
    'cold-reopen.json': 'cold-reopen.json', 'verification.json': 'verification.json',
}


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(65536), b''):
            digest.update(block)
    return digest.hexdigest()


def read(path, limit=1024 * 1024):
    path = Path(path).resolve(strict=True)
    if not path.is_file() or path.stat().st_size > limit:
        raise ValueError('Typed journey evidence is missing or oversized.')
    return json.loads(path.read_text(encoding='utf-8'))


class TypedJourneyBroker:
    def __init__(self, config):
        if config.get('schemaVersion') != 1 or config.get('profileKind') != 'typed-journey':
            raise ValueError('Unsupported typed journey broker profile.')
        if set(config) != {'schemaVersion', 'profileKind', 'runtimeId', 'capabilityId',
                          'sourceRoot', 'math3dRoot', 'datasetRoot', 'jobsRoot', 'gmshPython',
                          'vtkPython', 'node', 'caseProfile'}:
            raise ValueError('Typed journey broker configuration has unknown or missing fields.')
        if config['runtimeId'] != 'cgal-win-conda' or config['capabilityId'] != CAPABILITY:
            raise ValueError('Typed journey broker provider differs.')
        self.runtime_id = config['runtimeId']
        self.capability_id = CAPABILITY
        self.source_root = Path(config['sourceRoot']).resolve(strict=True)
        self.math3d_root = Path(config['math3dRoot']).resolve(strict=True)
        self.dataset_root = Path(config['datasetRoot']).resolve(strict=True)
        self.jobs_root = Path(config['jobsRoot']).resolve()
        self.jobs_root.mkdir(parents=True, exist_ok=True)
        self.gmsh_python = Path(config['gmshPython']).resolve(strict=True)
        self.vtk_python = Path(config['vtkPython']).resolve(strict=True)
        self.node = Path(config['node']).resolve(strict=True)
        self.case = config['caseProfile']
        if (not isinstance(self.case, dict) or set(self.case) != {'caseId', 'sourceRunId', 'resultPath', 'resultSha256',
                                                                'validationASha256', 'validationBSha256'}
                or not isinstance(self.case['caseId'], str) or not re.fullmatch('[a-z0-9-]{1,64}', self.case['caseId'])
                or not RUN.fullmatch(self.case['sourceRunId'])
                or any(not HEX.fullmatch(self.case[key]) for key in ('resultSha256', 'validationASha256', 'validationBSha256'))):
            raise ValueError('Typed journey case profile is invalid.')
        self.jobs = {}
        self.lock = threading.RLock()
        self.verify()
        for saved in self.jobs_root.glob('*/broker-result.json'):
            try:
                job = read(saved)
                if RUN.fullmatch(job.get('jobId', '')) and job.get('state') != 'running':
                    job['cancel'] = threading.Event()
                    job['process'] = None
                    self.jobs[job['jobId']] = job
            except (OSError, ValueError, KeyError):
                pass

    def verify(self):
        devshell = repository_snapshot(self.source_root)
        consumer = repository_snapshot(self.math3d_root)
        if devshell['dirty'] or consumer['dirty']:
            raise ValueError('Broker source and pulled MATH3D must be clean Git commits.')
        if not (self.math3d_root / 'renderer/node_modules/vite/package.json').is_file():
            raise ValueError('Pulled MATH3D renderer dependencies are missing.')
        source = Path(self.case['resultPath']).resolve(strict=True)
        if (not source.is_relative_to(self.dataset_root) or source.name != 'results.json'
                or not RUN.fullmatch(source.parent.name) or sha(source) != self.case['resultSha256']):
            raise ValueError('Allowlisted Boolean result path or hash changed.')
        result = read(source)
        operands = result.get('inputArtifacts', [])
        if (result.get('runId') != self.case['sourceRunId'] or result.get('recipeId') != 'cgal.boolean'
                or result.get('state') != 'succeeded' or result.get('boolean', {}).get('empty') is not False
                or len(operands) != 2 or operands[0].get('sha256') == operands[1].get('sha256')):
            raise ValueError('Allowlisted Boolean does not have two distinct validated inputs.')
        for role, operand in zip(('a', 'b'), operands):
            validation_path = source.parent / f'validation-{role}/results.json'
            if sha(validation_path) != self.case[f'validation{role.upper()}Sha256']:
                raise ValueError('Pinned Boolean topology validation changed.')
            validation = read(validation_path)
            if (validation.get('state') != 'succeeded' or validation.get('after', {}).get('closed') is not True
                    or validation.get('inputArtifacts', [{}])[0].get('sha256') != operand.get('sha256')):
                raise ValueError('Allowlisted Boolean topology validation differs.')
        snapshot_hash = result.get('sourceSnapshotSha256')
        snapshot_path = source.parent / 'source-snapshot.json'
        saved_source = read(snapshot_path, 2 * 1024 * 1024)['repositories']['devshell']
        if (not HEX.fullmatch(snapshot_hash or '') or sha(snapshot_path) != snapshot_hash
                or saved_source.get('state') != 'captured' or saved_source.get('dirty') is not False
                or saved_source.get('commit') != devshell['commit']):
            raise ValueError('Allowlisted Boolean source snapshot is stale.')
        export = result['boolean'].get('outputArtifact', '')
        if not isinstance(export, str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,99}\.m3dm', export):
            raise ValueError('Boolean M3DM export identity is invalid.')
        surface = source.parent / (export[:-5] + '.obj')
        artifact = next((item for item in result.get('artifacts', []) if item.get('path') == surface.name), None)
        if (artifact is None or surface.stat().st_size != artifact.get('bytes') or sha(surface) != artifact.get('sha256')):
            raise ValueError('Allowlisted Boolean OBJ artifact changed.')
        return source, result, surface, devshell, consumer

    def discover(self):
        self.verify()
        return {'schemaVersion': 1, 'providers': [{'runtimeId': self.runtime_id,
            'backend': 'windows-native', 'capabilities': [{'capabilityId': CAPABILITY,
            'level': 'candidate', 'caseId': self.case['caseId'], 'promotion': 'blocked-until-release'}]}]}

    def snapshot(self, job):
        return {key: value for key, value in job.items() if key not in ('cancel', 'process')}

    def submit(self, body):
        if (not isinstance(body, dict)
                or set(body) != {'schemaVersion', 'runtimeId', 'capabilityId', 'caseId', 'input', 'timeoutSeconds'}
                or body.get('schemaVersion') != 1 or body.get('runtimeId') != self.runtime_id
                or body.get('capabilityId') != CAPABILITY or body.get('caseId') != self.case['caseId']
                or not isinstance(body.get('input'), dict) or set(body['input']) != {'path', 'sha256'}
                or body['input']['path'] != self.case['resultPath']
                or body['input']['sha256'] != self.case['resultSha256']
                or isinstance(body.get('timeoutSeconds'), bool)
                or not isinstance(body.get('timeoutSeconds'), int) or not 1 <= body['timeoutSeconds'] <= 600):
            raise ValueError('Only the allowlisted typed Boolean case and hash may be submitted.')
        source, result, surface, devshell, consumer = self.verify()
        with self.lock:
            if any(job['state'] == 'running' for job in self.jobs.values()):
                raise ValueError('Typed journey broker is already running a job.')
            job_id = uuid.uuid4().hex
            directory = self.jobs_root / job_id
            directory.mkdir()
            snapshot = capture_sources({'devshell': self.source_root, 'math3d': self.math3d_root})
            snapshot_path = directory / 'source-snapshot.json'
            snapshot_path.write_text(json.dumps(snapshot, separators=(',', ':')), encoding='utf-8')
            (directory / 'request.json').write_text(json.dumps(body, separators=(',', ':')), encoding='utf-8')
            job = {'jobId': job_id, 'runtimeId': self.runtime_id, 'capabilityId': CAPABILITY,
                   'caseId': self.case['caseId'], 'state': 'running', 'stage': 'queued', 'progress': 0,
                   'contractVersion': 1, 'artifacts': [], 'diagnostics': [], 'directory': str(directory),
                   'sourceSnapshotSha256': sha(snapshot_path), 'sourceCommit': devshell['commit'],
                   'consumerCommit': consumer['commit'], 'sourceRunId': result['runId'],
                   'cancel': threading.Event(), 'process': None}
            self.jobs[job_id] = job
        threading.Thread(target=self._run, args=(job, body['timeoutSeconds'], source, result, surface), daemon=True).start()
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

    def _execute(self, job, args, deadline):
        if job['cancel'].is_set():
            raise InterruptedError('Job cancelled.')
        if time.monotonic() > deadline:
            raise TimeoutError('Typed journey timed out.')
        with (Path(job['directory']) / 'full.log').open('ab') as log:
            log.write(('> ' + ' '.join(map(str, args)) + '\n').encode())
            flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            process = subprocess.Popen(list(map(str, args)), cwd=self.source_root, stdout=log, stderr=log,
                                       creationflags=flags, start_new_session=os.name != 'nt')
            with self.lock:
                job['process'] = process
            try:
                while process.poll() is None:
                    if job['cancel'].is_set() or time.monotonic() > deadline:
                        self._stop_process(process)
                        raise InterruptedError('Job cancelled.') if job['cancel'].is_set() else TimeoutError('Typed journey timed out.')
                    time.sleep(0.1)
                if job['cancel'].is_set():
                    raise InterruptedError('Job cancelled.')
                if process.returncode:
                    raise ValueError(f'Typed stage exited {process.returncode}; inspect full.log.')
            finally:
                with self.lock:
                    job['process'] = None

    def _stage(self, job, folder, operation, input_id, parent_run, input_path, artifact_root,
               python, script, output_name, deadline, mesh_size=None, measurement=False):
        directory = Path(job['directory']) / folder
        directory.mkdir()
        stage_id = uuid.uuid4().hex
        source_result = read(Path(self.case['resultPath']))
        request = {'schemaVersion': 1, 'operation': operation, 'runId': stage_id,
                   'sourceRunId': parent_run, 'sourceCommit': job['sourceCommit'],
                   'sourceSnapshotSha256': source_result['sourceSnapshotSha256'],
                   'inputId': input_id, 'workingDirectory': str(directory),
                   'artifactRoot': str(artifact_root), 'lengthUnit': 'mm', 'frame': 'world',
                   'inputArtifact': {'path': str(input_path), 'sha256': sha(input_path),
                                     'bytes': input_path.stat().st_size}}
        if mesh_size is not None:
            request['meshSize'] = mesh_size
        (directory / 'request.json').write_text(json.dumps(request, separators=(',', ':')), encoding='utf-8')
        job['stage'] = folder
        self._execute(job, [python, self.source_root / 'tools' / script, '--request', directory / 'request.json'], deadline)
        result = read(directory / ('measurement.json' if measurement else 'results.json'))
        output = directory / output_name
        if (result.get('state') != 'succeeded' or result.get('runId') != stage_id
                or result.get('sourceCommit') != job['sourceCommit']
                or result.get('inputHashes', {}).get(input_id) != request['inputArtifact']['sha256']
                or not output.is_file()
                or not measurement and result.get('output', {}).get('sha256') != sha(output)):
            raise ValueError(f'{operation} typed identity or output changed.')
        return stage_id, result, output

    def _run(self, job, timeout, source, boolean, surface):
        directory = Path(job['directory'])
        deadline = time.monotonic() + timeout
        try:
            snapshot_sha = boolean['sourceSnapshotSha256']
            gmsh_id, gmsh, msh = self._stage(job, 'gmsh', 'gmsh.mesh', 'boolean-surface', boolean['runId'],
                surface, source.parent, self.gmsh_python, 'scientific-gmsh-boolean-volume.py', 'volume.msh', deadline, 0.5)
            boundary_id, boundary, obj = self._stage(job, 'boundary', 'gmsh.extract-boundary', 'gmsh-mesh', gmsh_id,
                msh, directory, self.gmsh_python, 'scientific-gmsh-boundary-extract.py', 'boundary.obj', deadline)
            _, vtk, vtp = self._stage(job, 'vtk', 'mesh.inspect', 'gmsh-boundary', boundary_id,
                obj, directory, self.vtk_python, 'scientific-vtk-boundary-inspect.py', 'analysis.vtp', deadline)
            if sha(directory / 'vtk/preview.png') != vtk['preview']['sha256']:
                raise ValueError('VTK preview changed.')
            _, scipy, measurement = self._stage(job, 'scipy', 'scipy.measure', 'vtk-analysis', boundary_id,
                vtp, directory, self.gmsh_python, 'scientific-scipy-surface-measure.py', 'measurement.json',
                deadline, measurement=True)
            converted = directory / 'converted.obj'
            job['stage'] = 'convert'
            self._execute(job, [self.vtk_python, self.source_root / 'tools/scientific-workbench-math3d-convert.py',
                '--source', vtp, '--expected-sha', sha(vtp), '--output', converted], deadline)
            conversion = read(directory / 'conversion.json')
            if conversion['objSha256'] != sha(converted):
                raise ValueError('Converted OBJ changed.')
            provenance = {'schemaVersion': 1, 'kind': 'scientific.typed-journey',
                'sourceCommit': job['sourceCommit'], 'sourceSnapshotSha256': snapshot_sha,
                'math3dCommit': job['consumerCommit'], 'convertedObjSha256': sha(converted),
                'vtkArtifactSha256': sha(vtp), 'measurementSha256': sha(measurement),
                'booleanSourceASha256': boolean['inputArtifacts'][0]['sha256'],
                'booleanSourceBSha256': boolean['inputArtifacts'][1]['sha256'],
                'booleanSurfaceSha256': sha(surface), 'gmshMeshSha256': sha(msh),
                'gmshBoundarySha256': sha(obj), 'lengthUnit': 'mm', 'frame': 'world',
                'geometryGeneration': 4, 'measurementGeneration': 5, 'consumerGeneration': 6,
                'measurement': scipy['measurement']}
            provenance_path = directory / 'typed-provenance.json'
            provenance_path.write_text(json.dumps(provenance, separators=(',', ':')), encoding='utf-8')
            product_dir = directory / 'product'
            job['stage'] = 'math3d-save'
            self._execute(job, [self.node, self.source_root / 'tools/math3d-vtk-read-product.mjs',
                '--checkout', self.math3d_root, '--source', converted, '--expected-sha', sha(converted),
                '--provenance', provenance_path, '--provenance-sha', sha(provenance_path),
                '--measurement', measurement, '--measurement-sha', sha(measurement), '--output', product_dir], deadline)
            cold = directory / 'cold-reopen.json'
            job['stage'] = 'cold-reopen'
            self._execute(job, [self.node, self.source_root / 'tools/math3d-typed-cold-reopen.mjs',
                '--checkout', self.math3d_root, '--product', product_dir, '--provenance', provenance_path,
                '--output', cold], deadline)
            job['stage'] = 'independent-verification'
            verified = verify_product(product_dir, provenance_path, measurement, vtp, converted, cold, self.math3d_root)
            if verified['verdict'] != 'verified-typed-product-relations':
                raise ValueError('Independent product verifier rejected the job.')
            (directory / 'verification.json').write_text(json.dumps(verified, separators=(',', ':')), encoding='utf-8')
            self.verify()
            artifact_records = []
            for alias, relative in ARTIFACTS.items():
                path = directory / relative
                if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 64 * 1024 * 1024:
                    raise ValueError('Typed artifact is missing or oversized: ' + alias)
                artifact_records.append({'name': alias, 'path': relative, 'bytes': path.stat().st_size, 'sha256': sha(path)})
            with self.lock:
                if job['cancel'].is_set():
                    raise InterruptedError('Job cancelled.')
                job.update(state='succeeded', stage='completed', progress=100, artifacts=artifact_records,
                           verification=verified, provenanceSha256=sha(provenance_path))
        except InterruptedError as error:
            with self.lock:
                job.update(state='cancelled', stage='stopped', progress=0, artifacts=[], diagnostics=[str(error)])
        except TimeoutError as error:
            with self.lock:
                job.update(state='timed-out', stage='timed-out', progress=0, artifacts=[], diagnostics=[str(error)])
        except Exception as error:
            with self.lock:
                job.update(state='failed', stage='failed', progress=0, artifacts=[], diagnostics=[str(error)[:500]])
        finally:
            (directory / 'broker-result.json').write_text(json.dumps(self.snapshot(job), separators=(',', ':')), encoding='utf-8')

    def artifact(self, job_id, alias):
        with self.lock:
            job = self.jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            if job['state'] != 'succeeded':
                raise ValueError('Only successful jobs transport artifacts.')
            record = next((item for item in job['artifacts'] if item['name'] == alias), None)
            if record is None or alias not in ARTIFACTS or record['path'] != ARTIFACTS[alias]:
                raise ValueError('Artifact is not registered for typed transport.')
            path = Path(job['directory']) / record['path']
            if path.is_symlink() or path.stat().st_size != record['bytes'] or sha(path) != record['sha256']:
                raise ValueError('Registered typed artifact changed.')
            return path.read_bytes()

    def source(self, job_id):
        job = self.jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        path = Path(job['directory']) / 'source-snapshot.json'
        if sha(path) != job['sourceSnapshotSha256']:
            raise ValueError('Broker source snapshot changed.')
        return read(path, 2 * 1024 * 1024)

    def telemetry(self, job_id):
        if job_id not in self.jobs:
            raise KeyError(job_id)
        return {'schemaVersion': 1, 'jobId': job_id, 'state': 'unavailable',
                'reason': 'Candidate typed journey does not issue resource qualification.'}

    def promote(self, job_id):
        with self.lock:
            job = self.jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            reasons = []
            if job['state'] != 'succeeded':
                reasons.append('Job did not succeed.')
            else:
                try:
                    self.verify()
                    for artifact in job['artifacts']:
                        self.artifact(job_id, artifact['name'])
                except (OSError, ValueError, KeyError) as error:
                    reasons.append(str(error))
            reasons.append('A current qualified release and signed journey bundle are required for promotion.')
            record = {'schemaVersion': 1, 'jobId': job_id, 'decision': 'blocked',
                      'reasons': reasons, 'candidate': True}
            path = Path(job['directory']) / 'promotion.json'
            path.write_text(json.dumps(record, separators=(',', ':')), encoding='utf-8')
            return {**record, 'path': str(path), 'sha256': sha(path)}
