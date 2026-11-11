"""Broker transport and MATH3D product smoke for all nine VTK read cases."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import time
import uuid

from broker import Broker, VTK_READ_CASES, sha

ROOT = Path(__file__).resolve().parents[2]
PRODUCT_FILES = ('vtk-mesh-document.json', 'vtk-mesh-resource.bin', 'read.m3dm',
                 'product.json', 'viewer.png', 'viewer.json')


def run(config):
    broker = Broker(config)
    if not broker.vtk_read or broker.math3d_root is None or len(broker.capabilities) != 1:
        raise ValueError('One current guarded-VTK read broker profile with MATH3D is required.')
    node = shutil.which('node')
    if node is None:
        raise ValueError('Node.js is required for VTK read product smoke.')
    fixture_path = broker.source_root / 'scientific/fixtures/vtk/read/manifest.v3.json'
    fixtures = {item['caseId']: item for item in json.loads(fixture_path.read_text())['cases']}
    references = {item['caseId']: item for item in broker.capabilities[0]['referenceCases']}
    outcomes = []
    for case_id in VTK_READ_CASES:
        fixture, reference = fixtures[case_id], references[case_id]
        source = broker.paths['datasetRoot'] / f"vtk-read-{case_id}{reference['inputExtension']}"
        shutil.copyfile(broker.source_root / fixture['path'], source)
        if sha(source) != reference['inputSha256']:
            raise ValueError('Registered VTK read fixture hash changed.')
        request = {'schemaVersion': 1, 'runtimeId': broker.runtime_id, 'capabilityId': 'mesh.read',
                   'caseId': case_id, 'input': {'path': str(source), 'sha256': sha(source)},
                   'timeoutSeconds': 120}
        job_id = broker.submit(request)['jobId']
        deadline = time.monotonic() + 130
        while broker.jobs[job_id]['state'] == 'running' and time.monotonic() < deadline:
            time.sleep(.1)
        job = broker.snapshot(broker.jobs[job_id])
        if job['state'] != ('succeeded' if reference['expected'] == 'accepted' else 'rejected'):
            raise ValueError('VTK read broker outcome changed: ' + case_id + ' / ' + str(job['diagnostics']))
        promotion = broker.promote(job_id)
        if promotion['decision'] != ('allowed' if job['state'] == 'succeeded' else 'blocked'):
            raise ValueError('VTK read promotion decision changed: ' + case_id)
        item = {'caseId': case_id, 'jobId': job_id, 'state': job['state'],
                'promotionPath': promotion['path'], 'promotionSha256': promotion['sha256'],
                'requestSha256': sha(Path(job['directory']) / 'request.json'),
                'resultSha256': sha(Path(job['directory']) / 'results.json')}
        if job['state'] == 'succeeded':
            output = Path(job['directory']) / 'read.vtp'
            if sha(output) != reference['outputSha256']:
                raise ValueError('Broker output differs from current L9 reference.')
            product = Path(job['directory']) / 'product'
            for command in ([node, str(ROOT / 'tools/math3d-vtk-read-product.mjs'),
                             '--checkout', str(broker.math3d_root), '--source', str(Path(job['directory']) / 'read.obj'),
                             '--expected-sha', reference['objSha256'], '--output', str(product)],
                            [node, str(ROOT / 'tools/math3d-vtk-read-viewer.mjs'),
                             '--checkout', str(broker.math3d_root), '--product', str(product)]):
                completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=240)
                if completed.returncode:
                    raise ValueError('VTK read MATH3D product failed: ' + (completed.stderr or completed.stdout)[-1500:])
            item['outputSha256'] = sha(output)
            item['objSha256'] = sha(Path(job['directory']) / 'read.obj')
            item['reloadSha256'] = sha(Path(job['directory']) / 'reload.json')
            item['handoffSha256'] = sha(Path(job['directory']) / 'handoff.json')
            item['scopeSha256'] = sha(Path(job['directory']) / 'scope.json')
            item['productFiles'] = {name: sha(product / name) for name in PRODUCT_FILES}
        else:
            if (Path(job['directory']) / 'read.vtp').exists():
                raise ValueError('Rejected VTK read published a mesh.')
        outcomes.append(item)
    target = broker.jobs_root / ('vtk-read-smoke-' + uuid.uuid4().hex + '.json')
    record = {'schemaVersion': 1, 'kind': 'scientific.vtk-read-broker-product-smoke',
              'verdict': 'passed', 'manifestSha256': sha(broker.paths['manifest']),
              'certificationRecordId': broker.capabilities[0]['recordId'], 'cases': outcomes}
    target.write_text(json.dumps(record, separators=(',', ':')), encoding='utf-8')
    Path(str(target) + '.sha256').write_text(sha(target), encoding='utf-8')
    verify(target, config)
    return target, record


def verify(path, config):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text().strip():
        raise ValueError('VTK read smoke seal changed.')
    record = json.loads(path.read_text(encoding='utf-8'))
    broker = Broker(config)
    if (not broker.vtk_read or record.get('kind') != 'scientific.vtk-read-broker-product-smoke'
            or record.get('verdict') != 'passed' or record.get('manifestSha256') != sha(broker.paths['manifest'])
            or record.get('certificationRecordId') != broker.capabilities[0]['recordId']
            or [item['caseId'] for item in record.get('cases', [])] != list(VTK_READ_CASES)):
        raise ValueError('VTK read smoke certification differs from current broker profile.')
    references = {item['caseId']: item for item in broker.capabilities[0]['referenceCases']}
    for item in record['cases']:
        job = broker.jobs.get(item['jobId'])
        if job is None or job['state'] != item['state'] or item['state'] != (
                'succeeded' if references[item['caseId']]['expected'] == 'accepted' else 'rejected'):
            raise ValueError('VTK read smoke job identity changed.')
        folder = Path(job['directory'])
        if (sha(folder / 'request.json') != item['requestSha256']
                or sha(folder / 'results.json') != item['resultSha256']
                or sha(item['promotionPath']) != item['promotionSha256']):
            raise ValueError('VTK read smoke request, result or promotion changed.')
        promotion = json.loads(Path(item['promotionPath']).read_text())
        if promotion['decision'] != ('allowed' if item['state'] == 'succeeded' else 'blocked'):
            raise ValueError('VTK read smoke promotion changed.')
        if item['state'] == 'succeeded':
            if (sha(folder / 'read.vtp') != item['outputSha256']
                    or item['outputSha256'] != references[item['caseId']]['outputSha256']
                    or sha(folder / 'read.obj') != item['objSha256']
                    or item['objSha256'] != references[item['caseId']]['objSha256']
                    or sha(folder / 'reload.json') != item['reloadSha256']
                    or sha(folder / 'handoff.json') != item['handoffSha256']
                    or sha(folder / 'scope.json') != item['scopeSha256']
                    or any(sha(folder / 'product' / name) != digest for name, digest in item['productFiles'].items())
                    or set(item['productFiles']) != set(PRODUCT_FILES)):
                raise ValueError('VTK read broker or MATH3D product changed.')
        elif (folder / 'read.vtp').exists():
            raise ValueError('Rejected VTK read gained a published output.')
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('run', 'verify'))
    parser.add_argument('--config', required=True)
    parser.add_argument('--record')
    args = parser.parse_args()
    path, record = run(args.config) if args.command == 'run' else (args.record, verify(args.record, args.config))
    print(json.dumps({'record': str(path), 'verdict': record['verdict']}))
