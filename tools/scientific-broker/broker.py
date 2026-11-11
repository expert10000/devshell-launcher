"""Standalone, localhost Scientific Runtime Broker for fixed certified mesh handoffs."""
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
import sys
import threading
import time
import uuid
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from telemetry import ResourceSampler, active_processes, stop_observed
from source_snapshot import capture_sources


CONTRACT = dict(id='math3d.mesh-product-handoff', version=1, workerResultSchemaVersion=1,
                meshDocumentSchemaVersion=1, inputFormat='obj', viewer='MeshDocumentViewport')
VOLUME_CONTRACT = dict(id='math3d.tetrahedral-product-handoff', version=1,
                       documentFormat='math3d.tetrahedral-mesh-document',
                       resourceEncoding='math3d.tetmesh-buffers.v1', viewer='TetrahedralMeshViewport')
REPAIR_CONTRACT_PATH = (Path(__file__).resolve().parents[2] /
    'scientific/fixtures/cgal-repair-qualification/product-contract.v1.json')
REPAIR_CONTRACT_TEXT = REPAIR_CONTRACT_PATH.read_text(encoding='utf-8')
REPAIR_CONTRACT = json.loads(REPAIR_CONTRACT_TEXT)


def compact_json_text(value):
    """Remove insignificant whitespace while retaining JSON numeric lexemes."""
    result = []
    quoted = escaped = False
    for char in value:
        if quoted:
            result.append(char)
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
            result.append(char)
        elif not char.isspace():
            result.append(char)
    return ''.join(result)


REPAIR_CONTRACT_SHA256 = hashlib.sha256(compact_json_text(REPAIR_CONTRACT_TEXT).encode()).hexdigest()
REMESH_CONTRACT = dict(id='math3d.guarded-remesh-handoff', version=1,
                       inputFormat='obj', outputFormat='obj', policyVersion=2,
                       viewer='MeshDocumentViewport')
ORIENTATION_CONTRACT = dict(id='math3d.orientation-handoff', version=1,
                            inputFormat='obj', outputFormat='obj', scopeVersion=2,
                            viewer='MeshDocumentViewport')
VTK_READ_CONTRACT = dict(id='math3d.vtk-mesh-read-handoff', version=1,
                         inputFormat='obj-ply-vtp', outputFormat='vtp-and-obj', scopeVersion=2,
                         viewer='MeshDocumentViewport')
VTK_READ_CASES = ('tetra', 'cube', 'octa', 'affine', 'open', 'disconnected', 'empty', 'truncated', 'invalid')
VTK_READ_SOURCES = ('tools/scientific-mesh-worker.py', 'tools/scientific_worker_contract.py',
                    'tools/scientific_vtk_read_scope.py', 'tools/scientific_vtk_read_qualification.py',
                    'tools/scientific-artifact-roundtrip.py', 'tools/scientific-vtk-interop.py',
                    'tools/math3d-vtk-import-handoff.mjs', 'tools/math3d-vtk-read-product.mjs',
                    'tools/math3d-vtk-read-viewer.mjs', 'tools/scientific-cgal-repair-m3dm-roundtrip.py',
                    'BatchLauncher/Form1.Scientific.VtkRead.cs', 'BatchLauncher/ScientificQualificationRecords.VtkRead.cs',
                    'BatchLauncher/ScientificRunFingerprint.cs', 'tools/runtime-lab/Program.cs',
                    'tools/scientific-broker/Program.cs', 'tools/scientific-broker/Program.VtkRead.cs',
                    'tools/scientific-broker/broker.py', 'tools/scientific-broker/vtk_read_adapter.py',
                    'tools/scientific-broker/vtk_read_broker_smoke.py')
ORIENTATION_CASES = ('tetra-inward', 'tetra-outward', 'cube-inward', 'cube-outward',
                     'octa-inward', 'octa-outward', 'affine-inward', 'affine-outward',
                     'open', 'disconnected', 'nonmanifold', 'degenerate')
ORIENTATION_SOURCES = ('scientific/cgal-worker/orientation.cpp', 'tools/scientific-cgal-worker.py',
                       'tools/scientific_worker_contract.py', 'tools/scientific_cgal_corpus.py',
                       'tools/scientific_cgal_orientation_fixture.py', 'tools/scientific_cgal_orientation_scope.py',
                       'tools/scientific_cgal_orientation_qualification.py', 'tools/scientific_cgal_orientation_l7.py',
                       'tools/scientific_cgal_orientation_l8.py', 'tools/scientific_cgal_orientation_l9.py',
                       'tools/math3d-cgal-orientation-product.mjs', 'tools/math3d-cgal-orientation-viewer.mjs',
                       'tools/scientific-cgal-repair-m3dm-roundtrip.py',
                       'BatchLauncher/Form1.Scientific.CgalOrientation.cs',
                       'BatchLauncher/ScientificQualificationRecords.Orientation.cs',
                       'BatchLauncher/ScientificRunFingerprint.cs', 'tools/runtime-lab/Program.cs',
                       'tools/scientific-broker/Program.cs', 'tools/scientific-broker/Program.Repair.cs',
                       'tools/scientific-broker/Program.Orientation.cs', 'tools/scientific-broker/broker.py',
                       'tools/scientific-broker/orientation_broker_smoke.py')
REMESH_CASES = ('accepted', 'volume-loss', 'affine-accepted', 'affine-volume-loss',
                'cube-accepted', 'cube-volume-loss', 'octa-accepted', 'octa-volume-loss')
REMESH_CONSUMER_FILES = ('renderer/src/mesh/surfaceMesh.ts', 'renderer/src/mesh/meshDocumentAdapter.ts',
                         'renderer/src/mesh/meshResourceStore.ts', 'packages/core/src/meshDocument.ts',
                         'src/main/python/nativeCgalProtocol.ts', 'renderer/src/workspace/MeshDocumentViewport.tsx')
REPAIR_CASES = ('triangle', 'square', 'two-squares', 'pentagon')
CONSUMER_FILES = {'renderer/src/mesh/surfaceMesh.ts', 'renderer/src/mesh/meshDocumentAdapter.ts',
                  'renderer/src/mesh/meshResourceStore.ts', 'renderer/src/workspace/MeshDocumentViewport.tsx',
                  'renderer/src/components/SurfaceViewer.tsx', 'packages/core/src/meshDocument.ts'}
VOLUME_CONSUMER_FILES = {'scientific/volume-consumer.v1.json', 'packages/core/src/tetrahedralMeshDocument.ts',
                         'renderer/src/volume/tetrahedralMeshDocumentAdapter.ts',
                         'renderer/src/volume/TetrahedralMeshViewport.tsx',
                         'renderer/src/workspace/MeshDocumentViewport.tsx',
                         'renderer/src/components/SurfaceViewer.tsx'}
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
        self.runtime_id = config.get('runtimeId', 'cgal-win-conda')
        if self.runtime_id not in ('cgal-win-conda', 'gmsh-win-conda', 'vtk-win-conda'):
            raise ValueError('Unsupported broker runtime profile.')
        self.gmsh = self.runtime_id == 'gmsh-win-conda'
        self.capability_id = config.get('capabilityId', 'mesh.generate' if self.gmsh else 'mesh.interop.vtk-math3d')
        if self.capability_id not in (('mesh.generate', 'mesh.generate3d') if self.gmsh else ('mesh.read',) if self.runtime_id == 'vtk-win-conda' else ('mesh.interop.vtk-math3d', 'mesh.repair', 'mesh.remesh', 'mesh.orient')):
            raise ValueError('Unsupported broker capability profile.')
        self.repair = self.capability_id == 'mesh.repair'
        self.remesh = self.capability_id == 'mesh.remesh'
        self.orientation = self.capability_id == 'mesh.orient'
        self.vtk_read = self.runtime_id == 'vtk-win-conda' and self.capability_id == 'mesh.read'
        self.volume = self.capability_id == 'mesh.generate3d'
        self.contract = VOLUME_CONTRACT if self.volume else REPAIR_CONTRACT if self.repair else REMESH_CONTRACT if self.remesh else ORIENTATION_CONTRACT if self.orientation else VTK_READ_CONTRACT if self.vtk_read else CONTRACT
        self.paths = {name: Path(config[name]).resolve(strict=True) for name in
                      ('manifest', 'runtimeManifest', 'adapter', 'workerContract', 'python', 'worker', 'prefix', 'datasetRoot')}
        if self.volume:
            self.paths['exporter'] = self.paths['worker'].with_name('scientific-gmsh-tetmesh-export.py').resolve(strict=True)
        elif self.gmsh:
            self.paths['converter'] = self.paths['worker'].with_name('scientific-gmsh-handoff.py').resolve(strict=True)
        self.math3d_root = Path(config['math3dRoot']).resolve(strict=True) if config.get('math3dRoot') else None
        self.jobs_root = Path(config['jobsRoot']).resolve()
        self.jobs_root.mkdir(parents=True, exist_ok=True)
        self.source_root = Path(config['sourceRoot']).resolve(strict=True) if config.get('sourceRoot') else Path(__file__).resolve().parents[2]
        self.max_concurrent_jobs = config.get('maxConcurrentJobs', 4)
        if isinstance(self.max_concurrent_jobs, bool) or not isinstance(self.max_concurrent_jobs, int) or not 1 <= self.max_concurrent_jobs <= 8:
            raise ValueError('maxConcurrentJobs must be an integer between 1 and 8.')
        self.memory_limit_mib = config.get('memoryLimitMiB')
        if self.memory_limit_mib is not None and (isinstance(self.memory_limit_mib, bool) or
                not isinstance(self.memory_limit_mib, int) or not 1 <= self.memory_limit_mib <= 65536):
            raise ValueError('memoryLimitMiB must be an integer between 1 and 65536.')
        self.jobs = {}
        self.lock = threading.RLock()
        self.batch_release_gate = None  # Controlled concurrency suite only.
        self.verify()
        for saved in self.jobs_root.glob('*/broker-result.json'):
            try:
                job = json.loads(saved.read_text(encoding='utf-8'))
                if (re.fullmatch('[0-9a-f]{32}', job.get('jobId', '')) and job.get('state') != 'running'
                        and job.get('runtimeId') == self.runtime_id
                        and job.get('capabilityId') == self.capability_id):
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
            identity = (entry.get('runtimeId'), entry.get('capabilityId'), entry.get('level'))
            if identity not in (('cgal-win-conda', 'mesh.interop.vtk-math3d', 'L9'),
                                ('gmsh-win-conda', 'mesh.generate', 'L9'),
                                ('gmsh-win-conda', 'mesh.generate3d', 'L9'),
                                ('cgal-win-conda', 'mesh.repair', 'L9'),
                                ('cgal-win-conda', 'mesh.remesh', 'L9'),
                                ('cgal-win-conda', 'mesh.orient', 'L9'),
                                ('vtk-win-conda', 'mesh.read', 'L9')):
                raise ValueError('Unqualified or unsupported provider in certified manifest.')
            if entry.get('runtimeId') != self.runtime_id or entry.get('capabilityId') != self.capability_id:
                continue
            if entry.get('productContract') != self.contract:
                raise ValueError('MATH3D product contract changed.')
            contract_hash = REPAIR_CONTRACT_SHA256 if self.repair else hashlib.sha256(
                json.dumps(self.contract, separators=(',', ':')).encode()).hexdigest()
            if entry.get('productContractSha256') != contract_hash:
                raise ValueError('MATH3D product contract hash mismatch.')
            if self.repair:
                require_hash(self.source_root / self.contract['fixtureManifest'],
                             entry.get('fixtureManifestSha256'), 'Repair fixture manifest')
                references = entry.get('referenceCases')
                if (not isinstance(references, list) or len(references) != 4
                        or [case.get('caseId') for case in references] != list(REPAIR_CASES)
                        or [case.get('recipeId') for case in references] !=
                           [case['recipeId'] for case in self.contract['cases']]):
                    raise ValueError('The certified repair case pack is incomplete.')
                fixtures = json.loads((self.source_root / self.contract['fixtureManifest']).read_text(encoding='utf-8'))
                for index, case in enumerate(references):
                    fixture = fixtures['fixtures'][index]
                    if case.get('inputSha256') != fixture.get('sha256') or not re.fullmatch(
                            '[0-9a-f]{64}', case.get('outputSha256', '')) or not re.fullmatch(
                            '[0-9a-f]{64}', case.get('m3dmSha256', '')):
                        raise ValueError('The certified repair fixture identity changed.')
                    require_hash(self.source_root / fixture['path'], case['inputSha256'], 'Repair fixture')
                if (entry.get('referenceInputSha256') != references[0]['inputSha256']
                        or entry.get('referenceArtifactSha256') != references[0]['outputSha256']):
                    raise ValueError('The certified repair reference differs from its case pack.')
            if self.remesh:
                fixture_path = self.source_root / 'scientific/fixtures/cgal-remesh-qualification/manifest.json'
                policy_path = self.source_root / 'schemas/scientific-remesh-guard.v2.json'
                guard_path = self.source_root / 'tools/scientific_cgal_remesh_guard.py'
                require_hash(fixture_path, entry.get('fixtureManifestSha256'), 'Remesh fixture manifest')
                require_hash(policy_path, entry.get('policySha256'), 'Remesh guard policy')
                require_hash(guard_path, entry.get('guardSourceSha256'), 'Remesh guard source')
                fixtures = {case['caseId']: case for case in json.loads(fixture_path.read_text())['cases']}
                references = entry.get('referenceCases')
                if not isinstance(references, list) or [case.get('caseId') for case in references] != list(REMESH_CASES):
                    raise ValueError('The guarded remesh case profile is incomplete.')
                for case in references:
                    fixture = fixtures[case['caseId']]
                    expected = fixture['expected']
                    if (case.get('inputSha256') != fixture['sha256'] or case.get('targetEdge') != fixture['targetEdge']
                            or case.get('iterations') != fixture['iterations'] or case.get('expected') != expected
                            or (expected == 'accepted') != bool(re.fullmatch('[0-9a-f]{64}', case.get('outputSha256') or ''))
                            or expected not in ('accepted', 'rejected')):
                        raise ValueError('The guarded remesh case identity changed.')
                    require_hash(self.source_root / fixture['path'], fixture['sha256'], 'Remesh fixture')
                if (entry.get('referenceInputSha256') != references[0]['inputSha256']
                        or entry.get('referenceArtifactSha256') != references[0]['outputSha256']):
                    raise ValueError('The guarded remesh reference differs from its case pack.')
            if self.orientation:
                fixture_path = self.source_root / 'scientific/fixtures/cgal/orientation/manifest.v2.json'
                require_hash(fixture_path, entry.get('fixtureManifestSha256'), 'Orientation fixture manifest')
                fixtures = json.loads(fixture_path.read_text(encoding='utf-8'))
                references = entry.get('referenceCases')
                if (fixtures.get('schemaVersion') != 2 or fixtures.get('capabilityId') != 'mesh.orient'
                        or not isinstance(references, list)
                        or [case.get('caseId') for case in references] != list(ORIENTATION_CASES)
                        or [case.get('caseId') for case in fixtures.get('cases', [])] != list(ORIENTATION_CASES)):
                    raise ValueError('The certified orientation case profile is incomplete.')
                for fixture, case in zip(fixtures['cases'], references):
                    expected = fixture['expected']
                    if (case.get('inputSha256') != fixture['sha256'] or case.get('expected') != expected
                            or case.get('orientation') != fixture.get('orientation')
                            or case.get('errorContains') != fixture.get('errorContains')
                            or (expected == 'accepted') != bool(re.fullmatch('[0-9a-f]{64}', case.get('outputSha256') or ''))
                            or expected not in ('accepted', 'rejected')):
                        raise ValueError('The certified orientation case identity changed.')
                    require_hash(self.source_root / fixture['path'], fixture['sha256'], 'Orientation fixture')
                if (entry.get('referenceInputSha256') != references[0]['inputSha256']
                        or entry.get('referenceArtifactSha256') != references[0]['outputSha256']):
                    raise ValueError('The certified orientation reference differs from its case pack.')
                sources = entry.get('orientationSources')
                if not isinstance(sources, dict) or set(sources) != set(ORIENTATION_SOURCES):
                    raise ValueError('Orientation qualification source identity is incomplete.')
                for name, digest in sources.items():
                    require_hash(self.source_root / name, digest, 'Orientation source ' + name)
                if hashlib.sha256(json.dumps(sources, separators=(',', ':')).encode()).hexdigest() != entry.get('orientationSourcesSha256'):
                    raise ValueError('Orientation qualification source digest changed.')
            if self.vtk_read:
                fixture_path = self.source_root / 'scientific/fixtures/vtk/read/manifest.v2.json'
                require_hash(fixture_path, entry.get('fixtureManifestSha256'), 'VTK read fixture manifest')
                fixtures = json.loads(fixture_path.read_text(encoding='utf-8'))
                references = entry.get('referenceCases')
                if (fixtures.get('schemaVersion') != 2 or fixtures.get('capabilityId') != 'mesh.read'
                        or not isinstance(references, list)
                        or [case.get('caseId') for case in references] != list(VTK_READ_CASES)
                        or [case.get('caseId') for case in fixtures.get('cases', [])] != list(VTK_READ_CASES)):
                    raise ValueError('The certified VTK read case profile is incomplete.')
                for fixture, case in zip(fixtures['cases'], references):
                    expected = fixture['expected']
                    if (case.get('inputSha256') != fixture['sha256'] or case.get('expected') != expected
                            or case.get('errorContains') != fixture.get('errorContains')
                            or case.get('inputExtension') != Path(fixture['path']).suffix.lower()
                            or (expected == 'accepted') != bool(re.fullmatch('[0-9a-f]{64}', case.get('outputSha256') or ''))
                            or (expected == 'accepted') != bool(re.fullmatch('[0-9a-f]{64}', case.get('objSha256') or ''))
                            or expected not in ('accepted', 'rejected')):
                        raise ValueError('The certified VTK read case identity changed.')
                    require_hash(self.source_root / fixture['path'], fixture['sha256'], 'VTK read fixture')
                if (entry.get('referenceInputSha256') != references[0]['inputSha256']
                        or entry.get('referenceArtifactSha256') != references[0]['outputSha256']):
                    raise ValueError('The certified VTK read reference differs from its case pack.')
                sources = entry.get('vtkReadSources')
                if not isinstance(sources, dict) or set(sources) != set(VTK_READ_SOURCES):
                    raise ValueError('VTK read qualification source identity is incomplete.')
                for name, digest in sources.items():
                    require_hash(self.source_root / name, digest, 'VTK read source ' + name)
                if hashlib.sha256(json.dumps(sources, separators=(',', ':')).encode()).hexdigest() != entry.get('vtkReadSourcesSha256'):
                    raise ValueError('VTK read qualification source digest changed.')
            for name, field in [('runtimeManifest', 'runtimeManifestSha256'), ('adapter', 'adapterSha256'),
                                ('workerContract', 'workerContractSha256'), ('python', 'pythonSha256'),
                                ('worker', 'workerBinarySha256')]:
                require_hash(self.paths[name], entry.get(field), name)
            if self.volume:
                require_hash(Path(__file__).resolve(), entry.get('brokerSha256'), 'Scientific broker')
                require_hash(self.paths['exporter'], entry.get('exporterSha256'), 'Gmsh volume exporter')
            elif self.gmsh:
                require_hash(self.paths['converter'], entry.get('converterSha256'), 'Gmsh converter')
                if self.math3d_root is not None:
                    require_hash(self.math3d_root / 'src/main/python/nativeCgalProtocol.ts',
                                 entry.get('codecSourceSha256'), 'MATH3D M3DM codec')
            if package_hash(self.paths['prefix']) != entry.get('packageRecordsSha256'):
                raise ValueError('Conda package inventory hash mismatch.')
            if any(not re.fullmatch('[0-9a-f]{64}', entry.get(key, '')) for key in
                   ('recordId', 'runFingerprintSha256', 'suiteRevisionSha256', 'qualificationSha256',
                    'referenceInputSha256', 'referenceArtifactSha256', 'sourceL8RecordId',
                    'consumerSourceSha256')):
                raise ValueError('Qualification identity is incomplete.')
            if self.volume and any(not re.fullmatch('[0-9a-f]{64}', entry.get(key, '')) for key in
                                   ('referenceWorkerArtifactSha256', 'exporterSha256', 'brokerSha256')):
                raise ValueError('Gmsh volume worker or exporter identity is incomplete.')
            if self.gmsh and not self.volume and any(not re.fullmatch('[0-9a-f]{64}', entry.get(key, '')) for key in
                                                     ('referenceWorkerArtifactSha256', 'converterSha256', 'codecSourceSha256')):
                raise ValueError('Gmsh 2D worker, converter or document codec identity is incomplete.')
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
            expected_files = VOLUME_CONSUMER_FILES if self.volume else set(REPAIR_CONTRACT['consumerSources']) if self.repair else set(REMESH_CONSUMER_FILES) if self.remesh or self.orientation or self.vtk_read else CONSUMER_FILES
            if not isinstance(entry.get('consumerSources'), dict) or set(entry['consumerSources']) != expected_files:
                raise ValueError('MATH3D consumer source identity is missing.')
            if (self.volume or self.repair or self.remesh or self.orientation or self.vtk_read) and self.math3d_root is not None:
                for name, expected in entry['consumerSources'].items():
                    require_hash(self.math3d_root / name, expected, 'MATH3D volume consumer ' + name)
                source_hash = hashlib.sha256(json.dumps(entry['consumerSources'], separators=(',', ':')).encode()).hexdigest()
                if source_hash != entry['consumerSourceSha256']:
                    raise ValueError('MATH3D volume consumer source fingerprint changed.')
        self.capabilities = [entry for entry in capabilities if entry['runtimeId'] == self.runtime_id
                             and entry['capabilityId'] == self.capability_id]
        return self.capabilities

    def discover(self):
        self.verify()
        return {'schemaVersion': 1, 'providers': [{'runtimeId': self.runtime_id, 'backend': 'windows-native',
                'capabilities': [{'capabilityId': entry['capabilityId'], 'level': entry['level'],
                                  'recordId': entry['recordId'], 'contractVersion': self.contract.get('version', 1)}]
                } for entry in self.capabilities]}

    def snapshot(self, job):
        with self.lock:
            return {key: value for key, value in job.items() if key not in ('process', 'cancel', 'pendingState')}

    def submit(self, body):
        self.verify()
        if body.get('schemaVersion') != 1 or body.get('runtimeId') != self.runtime_id or body.get('capabilityId') != self.capability_id:
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
        suffix = '.geo' if self.gmsh else '.obj'
        allowed_suffix = source.suffix.lower() in ('.obj', '.ply', '.vtp') if self.vtk_read else source.suffix.lower() == suffix
        if not allowed_suffix or not source.is_relative_to(self.paths['datasetRoot']) or source.stat().st_size > MAX_INPUT:
            raise ValueError(f'Input must be a bounded registered {suffix} dataset.')
        require_hash(source, input_info.get('sha256'), 'Input artifact')
        repair_case = None
        remesh_case = None
        orientation_case = None
        vtk_case = None
        if self.repair:
            case_id = body.get('caseId')
            repair_case = next((case for case in self.capabilities[0]['referenceCases']
                                if case['caseId'] == case_id), None)
            if repair_case is None or set(body) - {'schemaVersion', 'runtimeId', 'capabilityId', 'caseId', 'input', 'timeoutSeconds'}:
                raise ValueError('Only a certified repair caseId and typed input are allowed.')
            if input_info['sha256'] != repair_case['inputSha256']:
                raise ValueError('Input is outside the certified repair case fixture.')
        elif self.remesh:
            case_id = body.get('caseId')
            remesh_case = next((case for case in self.capabilities[0]['referenceCases']
                                if case['caseId'] == case_id), None)
            inspect = body.get('operation') == 'mesh.inspect'
            allowed = {'schemaVersion', 'runtimeId', 'capabilityId', 'caseId', 'input', 'timeoutSeconds'}
            if (remesh_case is None or set(body) != (allowed | {'operation'} if inspect else allowed)
                    or set(input_info) != {'path', 'sha256'}
                    or input_info['sha256'] != remesh_case['inputSha256']):
                raise ValueError('Only an allowlisted remesh case and its pinned typed input are accepted.')
            if inspect:
                shared = json.loads((self.source_root / 'schemas/scientific-mesh-inspect.v1.json').read_text(encoding='utf-8'))
                selected = next((tier for tier in shared['tiers'] if tier['cgalCase'] == case_id), None)
                if (shared.get('schemaVersion') != 1 or shared.get('operation') != 'mesh.inspect'
                        or selected is None or selected['cgalSha256'] != input_info['sha256']
                        or remesh_case['expected'] != 'accepted'):
                    raise ValueError('CGAL inspection input is outside the versioned shared scope.')
        elif self.orientation:
            orientation_case = next((case for case in self.capabilities[0]['referenceCases']
                                     if case['caseId'] == body.get('caseId')), None)
            if (orientation_case is None
                    or set(body) != {'schemaVersion', 'runtimeId', 'capabilityId', 'caseId', 'input', 'timeoutSeconds'}
                    or set(input_info) != {'path', 'sha256'}
                    or input_info['sha256'] != orientation_case['inputSha256']):
                raise ValueError('Only an allowlisted orientation case and its pinned typed input are accepted.')
        elif self.vtk_read:
            vtk_case = next((case for case in self.capabilities[0]['referenceCases']
                             if case['caseId'] == body.get('caseId')), None)
            if (vtk_case is None
                    or set(body) != {'schemaVersion', 'runtimeId', 'capabilityId', 'caseId', 'input', 'timeoutSeconds'}
                    or set(input_info) != {'path', 'sha256'}
                    or input_info['sha256'] != vtk_case['inputSha256']
                    or source.suffix.lower() != vtk_case['inputExtension']):
                raise ValueError('Only an allowlisted VTK read case and its pinned typed input are accepted.')
        elif input_info['sha256'] != self.capabilities[0]['referenceInputSha256']:
            raise ValueError('Input is outside the fixed L9 qualification fixture.')
        with self.lock:
            running = sum(job['state'] == 'running' for job in self.jobs.values())
            if running >= self.max_concurrent_jobs:
                raise ValueError(f'Worker capacity reached ({running}/{self.max_concurrent_jobs}); retry after a job finishes.')
            job_id = uuid.uuid4().hex
            directory = self.jobs_root / job_id
            dataset = directory / 'dataset'
            dataset.mkdir(parents=True)
            copied = dataset / ('input.geo' if self.gmsh else 'input' + source.suffix.lower() if self.vtk_read else 'input.obj')
            shutil.copyfile(source, copied)
            require_hash(copied, input_info['sha256'], 'Copied input artifact')
            source_snapshot = capture_sources({'devshell': self.source_root, 'math3d': self.math3d_root})
            source_path = directory / 'source-snapshot.json'
            with source_path.open('x', encoding='utf-8') as stream:
                json.dump(source_snapshot, stream, separators=(',', ':'))
            source_sha = sha(source_path)
            inspecting = self.remesh and body.get('operation') == 'mesh.inspect'
            recipe = 'gmsh.volume3d.cube' if self.volume else 'gmsh.mesh2d' if self.gmsh else repair_case['recipeId'] if self.repair else 'cgal.validate' if inspecting else 'cgal.remesh' if self.remesh else 'cgal.repair-orientation' if self.orientation else 'mesh.inspect' if self.vtk_read else 'cgal.validate'
            output_name = 'cube.msh' if self.volume else 'l5-positive.msh' if self.gmsh else 'repaired.obj' if self.repair else 'inspected.obj' if inspecting else 'remeshed.obj' if self.remesh else 'oriented.obj' if self.orientation else 'read.vtp' if self.vtk_read else 'l5-positive.obj'
            dataset_id = hashlib.sha256((repair_case['caseId'] + ':' + repair_case['inputSha256']).encode()).hexdigest() if self.repair else None
            request = {'schemaVersion': 1, 'runId': job_id, 'runtimeId': self.runtime_id,
                   'recipeId': recipe, 'operation': 'mesh.inspect' if inspecting else recipe,
                   'parameters': {'meshSize': 0.35 if self.volume else 0.2} if self.gmsh else
                                 {'inputId': dataset_id, 'outputName': output_name} if self.repair else
                                 {} if inspecting else {'targetEdge': remesh_case['targetEdge'], 'iterations': remesh_case['iterations'],
                                  'preserveBoundary': False} if self.remesh else {},
                   'workingDirectory': str(directory), 'datasetRoot': str(dataset),
                   'timeoutSeconds': timeout, 'inputArtifacts': [{'path': str(copied), 'sha256': input_info['sha256'],
                                                                  **({'datasetId': dataset_id} if self.repair else {})}],
                   'outputArtifacts': [{'path': output_name, 'mediaType': 'model/vnd.gmsh.msh' if self.gmsh else 'application/vnd.vtk.vtp' if self.vtk_read else 'model/obj'}],
                   'provenance': {'brokerContractVersion': 1, 'certificationRecordId': self.capabilities[0]['recordId'],
                                  'sourceSnapshotSha256': source_sha}}
            (directory / 'request.json').write_text(json.dumps(request, separators=(',', ':')), encoding='utf-8')
            job = {'jobId': job_id, 'runtimeId': self.runtime_id, 'capabilityId': self.capability_id,
               'state': 'running', 'stage': 'queued', 'progress': 0, 'contractVersion': 1,
               'certificationRecordId': self.capabilities[0]['recordId'], 'artifacts': [], 'diagnostics': [],
               'directory': str(directory), 'sourceSnapshotSha256': source_sha,
               **({'operation': 'mesh.inspect'} if inspecting else {}),
               **({'caseId': repair_case['caseId']} if self.repair else {'caseId': remesh_case['caseId']} if self.remesh else {'caseId': orientation_case['caseId']} if self.orientation else {'caseId': vtk_case['caseId']} if self.vtk_read else {}),
               'cancel': threading.Event(), 'process': None}
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

    def _finish_remesh(self, job, result, result_path, directory, exit_code):
        self.verify()
        entry = next((item for item in self.capabilities if item['recordId'] == job['certificationRecordId']), None)
        reference = next((case for case in entry['referenceCases'] if case['caseId'] == job['caseId']), None) if entry else None
        if entry is None or reference is None or not isinstance(result, dict):
            raise ValueError('Current guarded remesh qualification is unavailable.')
        request_path = directory / 'request.json'
        request = json.loads(request_path.read_text(encoding='utf-8'))
        evidence = result.get('guardEvidence') or {}
        relative = evidence.get('path')
        if not isinstance(relative, str):
            raise ValueError('Guarded remesh saved no guard evidence.')
        guard_path = (directory / relative).resolve(strict=True)
        if not guard_path.is_relative_to(directory) or guard_path.stat().st_size > 1048576:
            raise ValueError('Guard report escaped its bounded job directory.')
        require_hash(guard_path, evidence.get('sha256'), 'Guard report')
        guard = json.loads(guard_path.read_text(encoding='utf-8'))
        output = directory / 'remeshed.obj'
        copied = directory / 'dataset/input.obj'
        expected = reference['expected']
        if (request.get('recipeId') != 'cgal.remesh' or result.get('recipeId') != 'cgal.remesh'
                or request.get('runId') != job['jobId'] or result.get('runId') != job['jobId']
                or request.get('parameters') != {'targetEdge': reference['targetEdge'],
                                                 'iterations': reference['iterations'], 'preserveBoundary': False}
                or sha(copied) != reference['inputSha256']
                or guard.get('sourceSha256') != reference['inputSha256']
                or guard.get('policySha256') != entry['policySha256']
                or guard.get('policyVersion') != 2
                or guard.get('state') != expected or evidence.get('state') != expected
                or guard.get('candidateSha256') != sha(guard_path.parent / 'candidate.obj')
                or guard.get('measurements', {}).get('decision', {}).get('eligible') != (expected == 'accepted')):
            raise ValueError('Guarded remesh case or policy evidence changed.')
        if expected == 'rejected':
            if (exit_code == 0 or result.get('state') != 'failed' or output.exists()
                    or result.get('artifacts') or guard.get('acceptedSha256') is not None
                    or guard['measurements']['decision']['checks'].get('relativeVolume') is not False):
                raise ValueError('Adverse remesh did not reject without publication.')
            with self.lock:
                job.update(pendingState='rejected', stage='finalizing', progress=95,
                           diagnostics=['Guard rejected the pinned volume-loss candidate.'])
            return
        if (exit_code != 0 or result.get('state') != 'succeeded' or not output.is_file()
                or output.stat().st_size > MAX_INPUT or sha(output) != reference['outputSha256']
                or guard.get('acceptedSha256') != reference['outputSha256']
                or 'mesh.remesh' not in result.get('validatedCapabilities', [])
                or not any(item.get('path') == 'remeshed.obj' and item.get('sha256') == reference['outputSha256']
                           for item in result.get('artifacts', []))):
            raise ValueError('Accepted remesh does not match the L9 reference artifact.')
        handoff = {'schemaVersion': 1, 'contract': self.contract, 'runtimeId': self.runtime_id,
                   'capabilityId': self.capability_id, 'caseId': job['caseId'],
                   'sourceL9RunId': entry['sourceRunId'], 'sourceL9RecordId': entry['recordId'],
                   'sourceL8RunId': entry['sourceL8RunId'], 'sourceL8RecordId': entry['sourceL8RecordId'],
                   'workerRequest': {'path': str(request_path), 'sha256': sha(request_path)},
                   'workerResult': {'path': str(result_path), 'sha256': sha(result_path)},
                   'guardReport': {'path': str(guard_path), 'sha256': sha(guard_path)},
                   'artifact': {'path': str(output), 'sha256': sha(output)}}
        (directory / 'handoff.json').write_text(json.dumps(handoff, separators=(',', ':')), encoding='utf-8')
        shutil.copyfile(guard_path, directory / 'guarded.json')
        names = ('remeshed.obj', 'guarded.json', 'handoff.json')
        artifacts = [{'path': name, 'sha256': sha(directory / name), 'bytes': (directory / name).stat().st_size}
                     for name in names]
        with self.lock:
            job.update(pendingState='succeeded', stage='finalizing', progress=95, artifacts=artifacts)

    def _finish_inspect(self, job, result, result_path, directory, exit_code):
        self.verify()
        entry = next((item for item in self.capabilities if item['recordId'] == job['certificationRecordId']), None)
        reference = next((case for case in entry['referenceCases'] if case['caseId'] == job['caseId']), None) if entry else None
        request = json.loads((directory / 'request.json').read_text(encoding='utf-8'))
        output = directory / 'inspected.obj'
        if (entry is None or reference is None or not isinstance(result, dict)
                or request.get('recipeId') != 'cgal.validate' or request.get('operation') != 'mesh.inspect'
                or result.get('recipeId') != 'cgal.validate' or result.get('operation') != 'mesh.inspect'
                or result.get('runId') != job['jobId'] or result.get('state') != 'succeeded'
                or exit_code != 0 or not output.is_file() or output.stat().st_size > MAX_INPUT
                or sha(directory / 'dataset/input.obj') != reference['inputSha256']
                or 'mesh.validate' not in result.get('validatedCapabilities', [])
                or not any(item.get('path') == 'inspected.obj' and item.get('sha256') == sha(output)
                           for item in result.get('artifacts', []))):
            raise ValueError('CGAL shared inspection broker result changed.')
        before, after = result.get('before', {}), result.get('after', {})
        engine = result.get('engineDetails', {})
        if (before.get('points', 0) < 4 or before.get('triangles', 0) < 4
                or before.get('boundaryEdges') != 0 or before.get('closed') is not True
                or before.get('points') != after.get('points')
                or before.get('triangles') != after.get('triangles')
                or after.get('boundaryEdges') != 0 or engine.get('degenerateTriangles') != 0
                or engine.get('selfIntersections') is not False):
            raise ValueError('CGAL inspection topology or nonmutation check failed.')
        with self.lock:
            job.update(pendingState='succeeded', stage='finalizing', progress=95,
                       artifacts=[{'path': 'inspected.obj', 'sha256': sha(output), 'bytes': output.stat().st_size}])

    def _finish_orientation(self, job, result, result_path, directory, exit_code):
        self.verify()
        entry = next((item for item in self.capabilities if item['recordId'] == job['certificationRecordId']), None)
        reference = next((case for case in entry['referenceCases'] if case['caseId'] == job['caseId']), None) if entry else None
        if entry is None or reference is None or not isinstance(result, dict):
            raise ValueError('Current orientation qualification is unavailable.')
        request_path = directory / 'request.json'
        request = json.loads(request_path.read_text(encoding='utf-8'))
        copied = directory / 'dataset/input.obj'
        output = directory / 'oriented.obj'
        engine = result.get('engineDetails') or {}
        if (request.get('recipeId') != 'cgal.repair-orientation'
                or result.get('recipeId') != 'cgal.repair-orientation'
                or request.get('runId') != job['jobId'] or result.get('runId') != job['jobId']
                or request.get('parameters') != {} or sha(copied) != reference['inputSha256']
                or result.get('inputArtifacts', [{}])[0].get('sha256') != reference['inputSha256']):
            raise ValueError('Orientation typed request or fixture identity changed.')
        if reference['expected'] == 'rejected':
            if (exit_code == 0 or result.get('state') != 'failed' or output.exists()
                    or result.get('artifacts') or result.get('validatedCapabilities')
                    or reference['errorContains'] not in engine.get('error', '')):
                raise ValueError('Adverse orientation case published or changed its rejection.')
            with self.lock:
                job.update(pendingState='rejected', stage='finalizing', progress=95,
                           diagnostics=[engine['error']])
            return
        digest = reference['outputSha256']
        if (exit_code != 0 or result.get('state') != 'succeeded'
                or engine.get('operation') != 'orient'
                or engine.get('closed') is not True
                or engine.get('beforeOrientation') != reference['orientation']
                or engine.get('afterOrientation') != 'outward'
                or engine.get('orientationChanged') != (reference['orientation'] == 'inward')
                or not output.is_file() or output.stat().st_size > MAX_INPUT or sha(output) != digest
                or 'mesh.orient' not in result.get('validatedCapabilities', [])
                or not any(item.get('path') == 'oriented.obj' and item.get('sha256') == digest
                           for item in result.get('artifacts', []))):
            raise ValueError('Accepted orientation differs from its L9 case artifact.')
        scope = {'schemaVersion': 2, 'kind': 'scientific.cgal-orientation-broker-guard',
                 'capabilityId': 'mesh.orient', 'caseId': job['caseId'], 'expected': 'accepted',
                 'fixtureManifestSha256': entry['fixtureManifestSha256'],
                 'orientationSourcesSha256': entry['orientationSourcesSha256'],
                 'workerBinarySha256': entry['workerBinarySha256'],
                 'inputSha256': reference['inputSha256'], 'outputSha256': digest}
        scope_path = directory / 'scope.json'
        scope_path.write_text(json.dumps(scope, separators=(',', ':')), encoding='utf-8')
        handoff = {'schemaVersion': 1, 'contract': self.contract, 'runtimeId': self.runtime_id,
                   'capabilityId': self.capability_id, 'caseId': job['caseId'],
                   'sourceL9RunId': entry['sourceRunId'], 'sourceL9RecordId': entry['recordId'],
                   'sourceL8RunId': entry['sourceL8RunId'], 'sourceL8RecordId': entry['sourceL8RecordId'],
                   'workerRequest': {'path': str(request_path), 'sha256': sha(request_path)},
                   'workerResult': {'path': str(result_path), 'sha256': sha(result_path)},
                   'scopeGuard': {'path': str(scope_path), 'sha256': sha(scope_path)},
                   'artifact': {'path': str(output), 'sha256': digest}}
        (directory / 'handoff.json').write_text(json.dumps(handoff, separators=(',', ':')), encoding='utf-8')
        names = ('oriented.obj', 'scope.json', 'handoff.json')
        artifacts = [{'path': name, 'sha256': sha(directory / name), 'bytes': (directory / name).stat().st_size}
                     for name in names]
        with self.lock:
            job.update(pendingState='succeeded', stage='finalizing', progress=95, artifacts=artifacts)

    def _finish_vtk_read(self, job, result, result_path, directory, exit_code):
        self.verify()
        entry = next((item for item in self.capabilities if item['recordId'] == job['certificationRecordId']), None)
        reference = next((case for case in entry['referenceCases'] if case['caseId'] == job['caseId']), None) if entry else None
        if entry is None or reference is None or not isinstance(result, dict):
            raise ValueError('Current VTK read qualification is unavailable.')
        request_path = directory / 'request.json'
        request = json.loads(request_path.read_text(encoding='utf-8'))
        copied = directory / 'dataset' / ('input' + reference['inputExtension'])
        output = directory / 'read.vtp'
        if (request.get('recipeId') != 'mesh.inspect' or result.get('recipeId') != 'mesh.inspect'
                or request.get('runId') != job['jobId'] or result.get('runId') != job['jobId']
                or request.get('parameters') != {} or sha(copied) != reference['inputSha256']
                or result.get('inputArtifacts', [{}])[0].get('sha256') != reference['inputSha256']
                or result.get('versions', {}).get('vtk') != '9.6.1'):
            raise ValueError('VTK read typed request or fixture identity changed.')
        if reference['expected'] == 'rejected':
            diagnostics = [item.get('message', '') for item in result.get('diagnostics', [])]
            if (exit_code == 0 or result.get('state') != 'failed' or output.exists()
                    or result.get('artifacts') or result.get('validatedCapabilities')
                    or not any(reference['errorContains'] in message for message in diagnostics)):
                raise ValueError('Adverse VTK read case published or changed its rejection.')
            with self.lock:
                job.update(pendingState='rejected', stage='finalizing', progress=95, diagnostics=diagnostics)
            return
        digest = reference['outputSha256']
        if (exit_code != 0 or result.get('state') != 'succeeded'
                or not output.is_file() or output.stat().st_size > MAX_INPUT or sha(output) != digest
                or 'mesh.read' not in result.get('validatedCapabilities', [])
                or not any(item.get('path') == 'read.vtp' and item.get('sha256') == digest
                           for item in result.get('artifacts', []))):
            raise ValueError('Accepted VTK read differs from its L9 VTP reference.')
        parser = self.source_root / 'tools/scientific-artifact-roundtrip.py'
        obj = directory / 'read.obj'
        reload = directory / 'reload.json'
        converted = subprocess.run([str(self.paths['python']), str(parser), '--input', str(output),
                                    '--result', str(reload), '--export-obj', str(obj)],
                                   cwd=directory, capture_output=True, text=True, timeout=60)
        if converted.returncode or sha(obj) != reference['objSha256']:
            raise ValueError('VTK read handoff OBJ differs from current L7 evidence.')
        reload_result = json.loads(reload.read_text(encoding='utf-8'))
        if reload_result.get('artifactSha256') != digest or reload_result.get('exportObjSha256') != reference['objSha256']:
            raise ValueError('Independent VTK read reload changed.')
        scope = {'schemaVersion': 2, 'kind': 'scientific.vtk-read-broker-guard',
                 'capabilityId': 'mesh.read', 'caseId': job['caseId'], 'expected': 'accepted',
                 'fixtureManifestSha256': entry['fixtureManifestSha256'],
                 'vtkReadSourcesSha256': entry['vtkReadSourcesSha256'],
                 'workerBinarySha256': entry['workerBinarySha256'],
                 'inputSha256': reference['inputSha256'], 'outputSha256': digest,
                 'objSha256': reference['objSha256']}
        scope_path = directory / 'scope.json'
        scope_path.write_text(json.dumps(scope, separators=(',', ':')), encoding='utf-8')
        handoff = {'schemaVersion': 1, 'contract': self.contract, 'runtimeId': self.runtime_id,
                   'capabilityId': self.capability_id, 'caseId': job['caseId'],
                   'sourceL9RunId': entry['sourceRunId'], 'sourceL9RecordId': entry['recordId'],
                   'sourceL8RunId': entry['sourceL8RunId'], 'sourceL8RecordId': entry['sourceL8RecordId'],
                   'workerRequest': {'path': str(request_path), 'sha256': sha(request_path)},
                   'workerResult': {'path': str(result_path), 'sha256': sha(result_path)},
                   'scopeGuard': {'path': str(scope_path), 'sha256': sha(scope_path)},
                   'vtp': {'path': str(output), 'sha256': digest},
                   'artifact': {'path': str(obj), 'sha256': reference['objSha256']}}
        (directory / 'handoff.json').write_text(json.dumps(handoff, separators=(',', ':')), encoding='utf-8')
        names = ('read.vtp', 'read.obj', 'reload.json', 'scope.json', 'handoff.json')
        artifacts = [{'path': name, 'sha256': sha(directory / name), 'bytes': (directory / name).stat().st_size}
                     for name in names]
        with self.lock:
            job.update(pendingState='succeeded', stage='finalizing', progress=95, artifacts=artifacts)

    def _run(self, job, timeout):
        directory = Path(job['directory'])
        started = time.monotonic()
        process = None
        sampler = None
        try:
            self.verify()
            with self.lock:
                job.update(stage='worker', progress=20)
            env = os.environ.copy()
            prefix = self.paths['prefix']
            env['PATH'] = os.pathsep.join([str(prefix), str(prefix / 'Library' / 'bin'), str(prefix / 'Scripts'), env.get('PATH', '')])
            env['PYTHONNOUSERSITE'] = '1'
            env['PYTHONIOENCODING'] = 'utf-8'
            gate = directory / 'worker-start.gate'
            command = [str(self.paths['python']), str(Path(__file__).with_name('start_worker.py')),
                       '--gate', str(gate), '--python', str(self.paths['python']),
                       '--adapter', str(self.paths['adapter']), '--request', str(directory / 'request.json'),
                       '--worker', str(self.paths['worker'])]
            if self.remesh:
                command.extend(['--prefix', str(prefix)])
            if self.batch_release_gate is not None:
                command.extend(['--release', str(self.batch_release_gate)])
            log_path = directory / 'full.log'
            with log_path.open('w', encoding='utf-8') as log:
                process = subprocess.Popen(command, cwd=directory, env=env, stdout=log, stderr=subprocess.STDOUT,
                                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), start_new_session=os.name != 'nt')
                sampler = ResourceSampler(process.pid)
                observe_deadline = time.monotonic() + 0.1
                while True:
                    sampler._sample_processes()
                    if any(pid == process.pid for pid, _ in sampler.processes) or time.monotonic() >= observe_deadline:
                        break
                    time.sleep(0.005)
                sampler.start()
                gate.write_text('observed' if any(pid == process.pid for pid, _ in sampler.processes) else 'unavailable',
                                encoding='utf-8')
                with self.lock:
                    job['process'] = process
                    job['workerPid'] = process.pid
                memory_exceeded = None
                while process.poll() is None:
                    if job['cancel'].is_set() or time.monotonic() - started > timeout + 1:
                        self._stop_process(process)
                        break
                    if self.memory_limit_mib is not None and sampler.peak_rss is not None and sampler.peak_rss > self.memory_limit_mib * 1024 * 1024:
                        memory_exceeded = sampler.peak_rss
                        self._stop_process(process)
                        break
                    with self.lock:
                        job['progress'] = min(85, max(job['progress'], int((time.monotonic() - started) / timeout * 80) + 20))
                    time.sleep(0.1)
                process.wait(timeout=5)
                job['workerDurationMs'] = round((time.monotonic() - started) * 1000)
                if self.memory_limit_mib is not None and sampler.peak_rss is not None and sampler.peak_rss > self.memory_limit_mib * 1024 * 1024:
                    memory_exceeded = sampler.peak_rss
            if job['cancel'].is_set():
                with self.lock: job.update(pendingState='cancelled', stage='finalizing', diagnostics=['Job cancelled.'])
                return
            if memory_exceeded is not None:
                with self.lock: job.update(pendingState='resource-exhausted', stage='finalizing',
                    diagnostics=[f'Worker memory budget exceeded: {memory_exceeded} bytes > {self.memory_limit_mib} MiB.'])
                return
            if time.monotonic() - started >= timeout:
                with self.lock: job.update(pendingState='timed-out', stage='finalizing', diagnostics=['Job time limit exceeded.'])
                return
            result_path = directory / 'results.json'
            if result_path.is_file() and result_path.stat().st_size > 1048576:
                raise ValueError('Worker result exceeds 1 MiB.')
            result = json.loads(result_path.read_text(encoding='utf-8')) if result_path.is_file() else None
            if self.remesh and job.get('operation') == 'mesh.inspect':
                self._finish_inspect(job, result, result_path, directory, process.returncode)
                return
            if self.remesh:
                self._finish_remesh(job, result, result_path, directory, process.returncode)
                return
            if self.orientation:
                self._finish_orientation(job, result, result_path, directory, process.returncode)
                return
            if self.vtk_read:
                self._finish_vtk_read(job, result, result_path, directory, process.returncode)
                return
            worker_name = 'cube.msh' if self.volume else 'l5-positive.msh' if self.gmsh else 'repaired.obj' if self.repair else 'l5-positive.obj'
            artifact = directory / worker_name
            if artifact.is_file() and artifact.stat().st_size > MAX_INPUT:
                raise ValueError('Worker artifact exceeds 32 MiB.')
            if process.returncode != 0 or result is None or result.get('state') != 'succeeded':
                state = 'partial' if artifact.exists() else 'failed'
                with self.lock: job.update(pendingState=state, stage='finalizing', diagnostics=[
                    item.get('message', '') for item in (result or {}).get('diagnostics', [])] or ['Worker failed.'])
                return
            artifact_hash = sha(artifact)
            validated = 'mesh.generate3d' if self.volume else 'mesh.generate' if self.gmsh else 'mesh.repair' if self.repair else 'mesh.validate'
            if (result.get('runId') != job['jobId'] or validated not in result.get('validatedCapabilities', [])
                    or not any(item.get('path') == worker_name and item.get('sha256') == artifact_hash
                               for item in result.get('artifacts', []))):
                with self.lock: job.update(pendingState='partial', stage='finalizing', diagnostics=['Worker artifact verification failed.'])
                return
            self.verify()
            entry = next((item for item in self.capabilities if item['recordId'] == job['certificationRecordId']), None)
            reference = next((case for case in entry['referenceCases'] if case['caseId'] == job['caseId']), None) if self.repair and entry else None
            expected_artifact = reference['outputSha256'] if reference else entry['referenceWorkerArtifactSha256' if self.gmsh else 'referenceArtifactSha256'] if entry else None
            if entry is None or artifact_hash != expected_artifact:
                with self.lock: job.update(pendingState='partial', stage='finalizing', diagnostics=['Current qualification or reference artifact differs.'])
                return
            if self.volume:
                resource = directory / 'volume.m3dt'
                exporter_path = directory / 'exporter.json'
                if not resource.is_file() or not exporter_path.is_file() or resource.stat().st_size > MAX_INPUT:
                    raise ValueError('Gmsh adapter did not produce a bounded tetrahedral resource.')
                exported = json.loads(exporter_path.read_text(encoding='utf-8'))
                if (exported.get('schemaVersion') != 1 or exported.get('format') != 'M3DT'
                        or exported.get('version') != 1 or exported.get('sourceMshSha256') != artifact_hash
                        or exported.get('resourceSha256') != sha(resource)
                        or exported.get('exporterSha256') != entry['exporterSha256']
                        or exported.get('points') != 83 or exported.get('tetrahedra', 0) < 6
                        or exported.get('boundaryTriangles') != 156
                        or abs(exported.get('volume', 0) - 1) > 1e-6):
                    raise ValueError('Gmsh tetrahedral exporter result changed.')
                artifact = resource
                artifact_hash = sha(resource)
                if artifact_hash != entry['referenceArtifactSha256']:
                    raise ValueError('Gmsh tetrahedral resource differs from certified reference.')
            elif self.gmsh:
                obj = directory / 'l5-positive.obj'
                conversion_path = directory / 'conversion.json'
                if not obj.is_file() or not conversion_path.is_file():
                    raise ValueError('Gmsh adapter did not produce a checked OBJ handoff.')
                conversion = json.loads(conversion_path.read_text(encoding='utf-8'))
                if (conversion.get('sourceMshSha256') != artifact_hash
                        or conversion.get('outputObjSha256') != sha(obj)
                        or conversion.get('points') != 44 or conversion.get('triangles') != 66
                        or conversion.get('boundaryEdges') != 20 or conversion.get('nonManifoldEdges') != 0
                        or abs(conversion.get('signedAreaXY', 0) - 1) > 1e-6):
                    raise ValueError('Gmsh converter geometry or artifact hash changed.')
                artifact = obj
                artifact_hash = sha(obj)
                if artifact_hash != entry['referenceArtifactSha256']:
                    raise ValueError('Gmsh OBJ differs from certified reference artifact.')
            handoff = {'schemaVersion': 1, 'contract': self.contract, 'runtimeId': self.runtime_id,
                       'capabilityId': self.capability_id, 'sourceL8RunId': entry['sourceL8RunId'],
                       'sourceL8RecordId': entry['sourceL8RecordId'],
                       'workerRequest': {'path': str(directory / 'request.json'), 'sha256': sha(directory / 'request.json')},
                       'workerResult': {'path': str(result_path), 'sha256': sha(result_path)},
                       'artifact': {'path': str(artifact), 'sha256': artifact_hash}}
            if self.repair:
                handoff['caseId'] = job['caseId']
                handoff['recipeId'] = reference['recipeId']
                handoff['sourceL9RunId'] = entry['sourceRunId']
                handoff['sourceL9RecordId'] = entry['recordId']
                handoff['repairAudit'] = result.get('repairAudit')
            if self.volume:
                handoff['sourceMsh'] = {'path': str(directory / 'cube.msh'), 'sha256': sha(directory / 'cube.msh')}
                handoff['resource'] = {'path': str(directory / 'volume.m3dt'), 'sha256': sha(directory / 'volume.m3dt')}
                handoff['exporterReport'] = {'path': str(directory / 'exporter.json'),
                                             'sha256': sha(directory / 'exporter.json')}
            elif self.gmsh:
                handoff['workerArtifact'] = {'path': str(directory / 'l5-positive.msh'),
                                             'sha256': sha(directory / 'l5-positive.msh')}
            handoff_path = directory / 'handoff.json'
            handoff_path.write_text(json.dumps(handoff, separators=(',', ':')), encoding='utf-8')
            names = (('cube.msh', 'volume.m3dt', 'exporter.json', 'handoff.json') if self.volume else
                     ('l5-positive.msh', 'l5-positive.obj', 'conversion.json', 'handoff.json') if self.gmsh else
                     ('repaired.obj', 'handoff.json') if self.repair else
                     ('l5-positive.obj', 'handoff.json'))
            artifacts = [{'path': name, 'sha256': sha(directory / name), 'bytes': (directory / name).stat().st_size}
                         for name in names]
            with self.lock: job.update(pendingState='succeeded', stage='finalizing', progress=95, artifacts=artifacts)
        except Exception as error:
            with self.lock: job.update(pendingState='failed', stage='finalizing', diagnostics=[str(error)[:1000]])
        finally:
            if process is not None and process.poll() is None:
                self._stop_process(process)
            try:
                telemetry = sampler.finish() if sampler else ResourceSampler(-1).finish()
            except Exception as error:
                telemetry = {'schemaVersion': 1, 'state': 'unavailable', 'reason': str(error)[:200],
                             'observedProcesses': []}
            telemetry['sourceJobId'] = job['jobId']
            telemetry_path = directory / 'telemetry.json'
            telemetry_path.write_text(json.dumps(telemetry, separators=(',', ':')), encoding='utf-8')
            observed = telemetry.get('observedProcesses', [])
            active = active_processes(observed)
            orphan_pids = list(active or [])
            if active:
                active = stop_observed(observed)
            cleanup_state = 'passed' if active == [] else 'unverified' if active is None else 'failed'
            if process is not None and not any(item['pid'] == process.pid for item in observed):
                cleanup_state = 'unverified'
            pending = job.get('pendingState', 'failed')
            if pending == 'succeeded' and (cleanup_state != 'passed' or orphan_pids):
                pending = 'partial'
                job['diagnostics'].append('Worker process cleanup was not cleanly verified.')
            removed = []
            if pending != 'succeeded':
                for name in (('cube.msh', 'volume.m3dt', 'exporter.json', 'handoff.json') if self.volume else
                             ('l5-positive.msh', 'l5-positive.obj', 'conversion.json', 'handoff.json') if self.gmsh else
                             ('repaired.obj', 'handoff.json') if self.repair else
                             ('inspected.obj',) if self.remesh and job.get('operation') == 'mesh.inspect' else
                             ('l5-positive.obj', 'handoff.json')):
                    path = directory / name
                    if path.exists():
                        try:
                            path.unlink()
                            removed.append(name)
                        except OSError as error:
                            cleanup_state = 'failed'
                            job['diagnostics'].append(f'Could not remove partial {name}: {error}')
            with self.lock:
                job['process'] = None
                job.pop('pendingState', None)
                job['state'] = pending
                job['stage'] = 'completed'
                job['progress'] = 100 if pending == 'succeeded' else job['progress']
                job['artifacts'] = job['artifacts'] if pending == 'succeeded' else []
                job['telemetrySha256'] = sha(telemetry_path)
                job['cleanup'] = {'state': cleanup_state, 'observedPids': [item['pid'] for item in observed],
                                  'orphanPids': orphan_pids, 'activePids': active,
                                  'removedPartialArtifacts': removed}
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

    def telemetry(self, job_id):
        with self.lock:
            job = self.jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            if job['state'] == 'running' or not job.get('telemetrySha256'):
                raise ValueError('Job telemetry is not finalized.')
            path = Path(job['directory']) / 'telemetry.json'
            require_hash(path, job['telemetrySha256'], 'Job telemetry')
            return json.loads(path.read_text(encoding='utf-8'))

    def source(self, job_id):
        with self.lock:
            job = self.jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            path = Path(job['directory']) / 'source-snapshot.json'
            require_hash(path, job.get('sourceSnapshotSha256'), 'Source snapshot')
            return json.loads(path.read_text(encoding='utf-8'))

    def promote(self, job_id):
        if self.remesh:
            return self._promote_remesh(job_id)
        if self.orientation:
            return self._promote_orientation(job_id)
        if self.vtk_read:
            return self._promote_vtk_read(job_id)
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
            if job.get('sourceSnapshotSha256'):
                try:
                    self.source(job_id)
                except (ValueError, OSError) as error:
                    reasons.append('Source snapshot evidence changed: ' + str(error))
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
                    if self.gmsh and not self.volume:
                        try:
                            require_hash(self.math3d_root / 'src/main/python/nativeCgalProtocol.ts',
                                         entry['codecSourceSha256'], 'MATH3D M3DM codec')
                        except (ValueError, OSError) as error:
                            reasons.append(str(error))
                try:
                    handoff = json.loads(self.artifact(job_id, 'handoff.json'))
                    output = self.artifact(job_id, 'volume.m3dt' if self.volume else 'repaired.obj' if self.repair else 'l5-positive.obj')
                    worker_request = json.loads((Path(job['directory']) / 'request.json').read_text(encoding='utf-8'))
                    worker_result = json.loads((Path(job['directory']) / 'results.json').read_text(encoding='utf-8'))
                    gmsh_worker_ok = True
                    if self.volume:
                        msh = self.artifact(job_id, 'cube.msh')
                        exported = json.loads(self.artifact(job_id, 'exporter.json'))
                        gmsh_worker_ok = (hashlib.sha256(msh).hexdigest() == entry['referenceWorkerArtifactSha256']
                                          and handoff.get('sourceMsh', {}).get('sha256') == hashlib.sha256(msh).hexdigest()
                                          and handoff.get('resource', {}).get('sha256') == hashlib.sha256(output).hexdigest()
                                          and handoff.get('exporterReport', {}).get('sha256') == sha(Path(job['directory']) / 'exporter.json')
                                          and exported.get('sourceMshSha256') == hashlib.sha256(msh).hexdigest()
                                          and exported.get('resourceSha256') == hashlib.sha256(output).hexdigest()
                                          and exported.get('exporterSha256') == entry['exporterSha256'])
                    elif self.gmsh:
                        msh = self.artifact(job_id, 'l5-positive.msh')
                        conversion = json.loads(self.artifact(job_id, 'conversion.json'))
                        gmsh_worker_ok = (hashlib.sha256(msh).hexdigest() == entry['referenceWorkerArtifactSha256']
                                          and handoff.get('workerArtifact', {}).get('sha256') == hashlib.sha256(msh).hexdigest()
                                          and conversion.get('sourceMshSha256') == hashlib.sha256(msh).hexdigest()
                                          and conversion.get('outputObjSha256') == hashlib.sha256(output).hexdigest())
                    elif self.repair:
                        reference = next((case for case in entry['referenceCases'] if case['caseId'] == job['caseId']), None)
                        gmsh_worker_ok = (reference is not None
                                          and worker_request.get('recipeId') == reference['recipeId']
                                          and worker_result.get('recipeId') == reference['recipeId']
                                          and worker_request.get('inputArtifacts', [{}])[0].get('sha256') == reference['inputSha256']
                                          and hashlib.sha256(output).hexdigest() == reference['outputSha256']
                                          and handoff.get('caseId') == job['caseId']
                                          and handoff.get('recipeId') == reference['recipeId']
                                          and handoff.get('sourceL9RunId') == entry['sourceRunId']
                                          and handoff.get('sourceL9RecordId') == entry['recordId']
                                          and handoff.get('repairAudit') == worker_result.get('repairAudit')
                                          and worker_result.get('repairAudit', {}).get('patchSha256'))
                    validated = 'mesh.generate3d' if self.volume else 'mesh.generate' if self.gmsh else 'mesh.repair' if self.repair else 'mesh.validate'
                    if (handoff.get('contract') != self.contract or handoff.get('runtimeId') != job['runtimeId']
                            or handoff.get('capabilityId') != job['capabilityId']
                            or handoff.get('sourceL8RunId') != entry['sourceL8RunId']
                            or handoff.get('sourceL8RecordId') != entry['sourceL8RecordId']
                            or worker_request.get('runId') != job_id or worker_result.get('runId') != job_id
                            or worker_result.get('state') != 'succeeded'
                            or validated not in worker_result.get('validatedCapabilities', [])
                            or not gmsh_worker_ok
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
                      'contractVersion': self.contract.get('version', 1),
                      'sourceSnapshotSha256': job.get('sourceSnapshotSha256'),
                      'handoffSha256': sha(Path(job['directory']) / 'handoff.json') if decision == 'allowed' else None,
                      'artifactSha256': (next(case['outputSha256'] for case in entry['referenceCases']
                          if case['caseId'] == job['caseId']) if self.repair else entry['referenceArtifactSha256'])
                          if decision == 'allowed' else None}
            directory = Path(job['directory']) / 'promotions'
            directory.mkdir(exist_ok=True)
            path = directory / (promotion_id + '.json')
            with path.open('x', encoding='utf-8') as stream:
                json.dump(record, stream, separators=(',', ':'))
            return {**record, 'path': str(path), 'sha256': sha(path)}

    def _promote_remesh(self, job_id):
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
                    reasons.append('The L0-L9 remesh qualification is no longer certified.')
            except (ValueError, OSError) as error:
                reasons.append('Certified remesh identity changed: ' + str(error))
            if job['state'] != 'succeeded':
                reasons.append(f"Source job is {job['state']}; only accepted remesh can be promoted.")
            if self.math3d_root is None:
                reasons.append('MATH3D consumer checkout is unavailable.')
            elif entry is not None:
                try:
                    for name, digest in entry['consumerSources'].items():
                        require_hash(self.math3d_root / name, digest, 'MATH3D remesh consumer ' + name)
                except (ValueError, OSError) as error:
                    reasons.append(str(error))
            if entry is not None and job['state'] == 'succeeded':
                try:
                    self.source(job_id)
                    folder = Path(job['directory'])
                    handoff = json.loads(self.artifact(job_id, 'handoff.json'))
                    output = self.artifact(job_id, 'remeshed.obj')
                    guard = json.loads(self.artifact(job_id, 'guarded.json'))
                    request = json.loads((folder / 'request.json').read_text(encoding='utf-8'))
                    result = json.loads((folder / 'results.json').read_text(encoding='utf-8'))
                    reference = next(case for case in entry['referenceCases'] if case['caseId'] == job['caseId'])
                    digest = hashlib.sha256(output).hexdigest()
                    if (reference['expected'] != 'accepted' or digest != reference['outputSha256']
                            or handoff.get('contract') != self.contract
                            or handoff.get('caseId') != job['caseId']
                            or handoff.get('sourceL9RecordId') != entry['recordId']
                            or handoff.get('sourceL8RecordId') != entry['sourceL8RecordId']
                            or handoff.get('workerRequest', {}).get('sha256') != sha(folder / 'request.json')
                            or handoff.get('workerResult', {}).get('sha256') != sha(folder / 'results.json')
                            or handoff.get('artifact', {}).get('sha256') != digest
                            or handoff.get('guardReport', {}).get('sha256') != sha(folder / 'guarded.json')
                            or guard.get('policySha256') != entry['policySha256']
                            or guard.get('state') != 'accepted'
                            or guard.get('acceptedSha256') != digest
                            or request.get('parameters') != {'targetEdge': reference['targetEdge'],
                                                             'iterations': reference['iterations'], 'preserveBoundary': False}
                            or result.get('guardEvidence', {}).get('sha256') != sha(folder / 'guarded.json')):
                        reasons.append('Broker remesh handoff or accepted artifact changed.')
                except (ValueError, OSError, KeyError, json.JSONDecodeError) as error:
                    reasons.append('Verified remesh handoff is unavailable: ' + str(error))
            decision = 'allowed' if not reasons else 'blocked'
            promotion_id = uuid.uuid4().hex
            record = {'schemaVersion': 1, 'kind': 'scientific.math3d-promotion', 'promotionId': promotion_id,
                      'decision': decision, 'reasons': reasons, 'sourceJobId': job_id,
                      'sourceJobState': job['state'], 'capabilityId': job['capabilityId'],
                      'runtimeId': job['runtimeId'], 'certificationRecordId': job['certificationRecordId'],
                      'manifestSha256': sha(self.paths['manifest']) if self.paths['manifest'].is_file() else None,
                      'contractVersion': self.contract['version'],
                      'sourceSnapshotSha256': job.get('sourceSnapshotSha256'),
                      'handoffSha256': sha(Path(job['directory']) / 'handoff.json') if decision == 'allowed' else None,
                      'artifactSha256': next(case['outputSha256'] for case in entry['referenceCases']
                          if case['caseId'] == job['caseId']) if decision == 'allowed' else None}
            folder = Path(job['directory']) / 'promotions'
            folder.mkdir(exist_ok=True)
            path = folder / (promotion_id + '.json')
            path.write_text(json.dumps(record, separators=(',', ':')), encoding='utf-8')
            return {**record, 'path': str(path), 'sha256': sha(path)}

    def _promote_orientation(self, job_id):
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
                    reasons.append('The L0-L9 orientation qualification is no longer certified.')
            except (ValueError, OSError) as error:
                reasons.append('Certified orientation identity changed: ' + str(error))
            if job['state'] != 'succeeded':
                reasons.append(f"Source job is {job['state']}; only accepted orientation can be promoted.")
            if self.math3d_root is None:
                reasons.append('MATH3D consumer checkout is unavailable.')
            elif entry is not None:
                try:
                    for name, digest in entry['consumerSources'].items():
                        require_hash(self.math3d_root / name, digest, 'MATH3D orientation consumer ' + name)
                except (ValueError, OSError) as error:
                    reasons.append(str(error))
            if entry is not None and job['state'] == 'succeeded':
                try:
                    self.source(job_id)
                    folder = Path(job['directory'])
                    handoff = json.loads(self.artifact(job_id, 'handoff.json'))
                    output = self.artifact(job_id, 'oriented.obj')
                    scope = json.loads(self.artifact(job_id, 'scope.json'))
                    request = json.loads((folder / 'request.json').read_text(encoding='utf-8'))
                    result = json.loads((folder / 'results.json').read_text(encoding='utf-8'))
                    reference = next(case for case in entry['referenceCases'] if case['caseId'] == job['caseId'])
                    digest = hashlib.sha256(output).hexdigest()
                    if (reference['expected'] != 'accepted' or digest != reference['outputSha256']
                            or handoff.get('contract') != self.contract
                            or handoff.get('caseId') != job['caseId']
                            or handoff.get('sourceL9RecordId') != entry['recordId']
                            or handoff.get('sourceL8RecordId') != entry['sourceL8RecordId']
                            or handoff.get('workerRequest', {}).get('sha256') != sha(folder / 'request.json')
                            or handoff.get('workerResult', {}).get('sha256') != sha(folder / 'results.json')
                            or handoff.get('scopeGuard', {}).get('sha256') != sha(folder / 'scope.json')
                            or handoff.get('artifact', {}).get('sha256') != digest
                            or scope.get('fixtureManifestSha256') != entry['fixtureManifestSha256']
                            or scope.get('orientationSourcesSha256') != entry['orientationSourcesSha256']
                            or scope.get('workerBinarySha256') != entry['workerBinarySha256']
                            or scope.get('inputSha256') != reference['inputSha256']
                            or scope.get('outputSha256') != digest
                            or request.get('parameters') != {}
                            or result.get('engineDetails', {}).get('afterOrientation') != 'outward'):
                        reasons.append('Broker orientation handoff or accepted artifact changed.')
                except (ValueError, OSError, KeyError, json.JSONDecodeError) as error:
                    reasons.append('Verified orientation handoff is unavailable: ' + str(error))
            decision = 'allowed' if not reasons else 'blocked'
            promotion_id = uuid.uuid4().hex
            record = {'schemaVersion': 1, 'kind': 'scientific.math3d-promotion', 'promotionId': promotion_id,
                      'decision': decision, 'reasons': reasons, 'sourceJobId': job_id,
                      'sourceJobState': job['state'], 'capabilityId': job['capabilityId'],
                      'runtimeId': job['runtimeId'], 'certificationRecordId': job['certificationRecordId'],
                      'manifestSha256': sha(self.paths['manifest']) if self.paths['manifest'].is_file() else None,
                      'contractVersion': self.contract['version'],
                      'sourceSnapshotSha256': job.get('sourceSnapshotSha256'),
                      'handoffSha256': sha(Path(job['directory']) / 'handoff.json') if decision == 'allowed' else None,
                      'artifactSha256': next(case['outputSha256'] for case in entry['referenceCases']
                          if case['caseId'] == job['caseId']) if decision == 'allowed' else None}
            folder = Path(job['directory']) / 'promotions'
            folder.mkdir(exist_ok=True)
            path = folder / (promotion_id + '.json')
            path.write_text(json.dumps(record, separators=(',', ':')), encoding='utf-8')
            return {**record, 'path': str(path), 'sha256': sha(path)}

    def _promote_vtk_read(self, job_id):
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
                    reasons.append('The L0-L9 VTK read qualification is no longer certified.')
            except (ValueError, OSError) as error:
                reasons.append('Certified VTK read identity changed: ' + str(error))
            if job['state'] != 'succeeded':
                reasons.append(f"Source job is {job['state']}; only accepted VTK reads can be promoted.")
            if self.math3d_root is None:
                reasons.append('MATH3D consumer checkout is unavailable.')
            elif entry is not None:
                try:
                    for name, digest in entry['consumerSources'].items():
                        require_hash(self.math3d_root / name, digest, 'MATH3D VTK read consumer ' + name)
                except (ValueError, OSError) as error:
                    reasons.append(str(error))
            if entry is not None and job['state'] == 'succeeded':
                try:
                    self.source(job_id)
                    folder = Path(job['directory'])
                    handoff = json.loads(self.artifact(job_id, 'handoff.json'))
                    scope = json.loads(self.artifact(job_id, 'scope.json'))
                    vtp = self.artifact(job_id, 'read.vtp')
                    obj = self.artifact(job_id, 'read.obj')
                    reload = json.loads(self.artifact(job_id, 'reload.json'))
                    request = json.loads((folder / 'request.json').read_text(encoding='utf-8'))
                    result = json.loads((folder / 'results.json').read_text(encoding='utf-8'))
                    reference = next(case for case in entry['referenceCases'] if case['caseId'] == job['caseId'])
                    vtp_hash, obj_hash = hashlib.sha256(vtp).hexdigest(), hashlib.sha256(obj).hexdigest()
                    if (reference['expected'] != 'accepted' or vtp_hash != reference['outputSha256']
                            or obj_hash != reference['objSha256'] or handoff.get('contract') != self.contract
                            or handoff.get('caseId') != job['caseId']
                            or handoff.get('sourceL9RecordId') != entry['recordId']
                            or handoff.get('sourceL8RecordId') != entry['sourceL8RecordId']
                            or handoff.get('workerRequest', {}).get('sha256') != sha(folder / 'request.json')
                            or handoff.get('workerResult', {}).get('sha256') != sha(folder / 'results.json')
                            or handoff.get('scopeGuard', {}).get('sha256') != sha(folder / 'scope.json')
                            or handoff.get('vtp', {}).get('sha256') != vtp_hash
                            or handoff.get('artifact', {}).get('sha256') != obj_hash
                            or scope.get('fixtureManifestSha256') != entry['fixtureManifestSha256']
                            or scope.get('vtkReadSourcesSha256') != entry['vtkReadSourcesSha256']
                            or scope.get('workerBinarySha256') != entry['workerBinarySha256']
                            or scope.get('inputSha256') != reference['inputSha256']
                            or scope.get('outputSha256') != vtp_hash
                            or scope.get('objSha256') != obj_hash
                            or reload.get('artifactSha256') != vtp_hash
                            or reload.get('exportObjSha256') != obj_hash
                            or request.get('parameters') != {}
                            or result.get('recipeId') != 'mesh.inspect'):
                        reasons.append('Broker VTK read handoff or accepted artifact changed.')
                except (ValueError, OSError, KeyError, json.JSONDecodeError) as error:
                    reasons.append('Verified VTK read handoff is unavailable: ' + str(error))
            decision = 'allowed' if not reasons else 'blocked'
            promotion_id = uuid.uuid4().hex
            record = {'schemaVersion': 1, 'kind': 'scientific.math3d-promotion', 'promotionId': promotion_id,
                      'decision': decision, 'reasons': reasons, 'sourceJobId': job_id,
                      'sourceJobState': job['state'], 'capabilityId': job['capabilityId'],
                      'runtimeId': job['runtimeId'], 'certificationRecordId': job['certificationRecordId'],
                      'manifestSha256': sha(self.paths['manifest']) if self.paths['manifest'].is_file() else None,
                      'contractVersion': self.contract['version'],
                      'sourceSnapshotSha256': job.get('sourceSnapshotSha256'),
                      'handoffSha256': sha(Path(job['directory']) / 'handoff.json') if decision == 'allowed' else None,
                      'artifactSha256': reference['objSha256'] if decision == 'allowed' else None}
            folder = Path(job['directory']) / 'promotions'
            folder.mkdir(exist_ok=True)
            path = folder / (promotion_id + '.json')
            path.write_text(json.dumps(record, separators=(',', ':')), encoding='utf-8')
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
                if len(parts) == 4 and parts[:2] == ['v1', 'jobs'] and parts[3] == 'telemetry':
                    return self.reply(200, broker.telemetry(parts[2]))
                if len(parts) == 4 and parts[:2] == ['v1', 'jobs'] and parts[3] == 'source':
                    return self.reply(200, broker.source(parts[2]))
                if len(parts) == 5 and parts[:2] == ['v1', 'jobs'] and parts[3] == 'artifacts':
                    raw = broker.artifact(parts[2], parts[4])
                    self.send_response(200)
                    media_type = ('model/obj' if parts[4].endswith('.obj') else
                                  'application/vnd.vtk.vtp' if parts[4].endswith('.vtp') else
                                  'model/vnd.gmsh.msh' if parts[4].endswith('.msh') else
                                  'application/octet-stream' if parts[4].endswith('.m3dt') else 'application/json')
                    self.send_header('Content-Type', media_type)
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
