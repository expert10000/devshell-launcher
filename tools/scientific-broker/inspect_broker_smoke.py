"""Dedicated mesh.inspect broker transport and MATH3D product smoke."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import time
import uuid

from broker import Broker, INSPECT_CASES, sha

ROOT = Path(__file__).resolve().parents[2]
PRODUCT_FILES = ('vtk-mesh-document.json', 'vtk-mesh-resource.bin', 'read.m3dm',
                 'product.json', 'viewer.png', 'viewer.json')


def wait(broker, job_id):
    deadline = time.monotonic() + 150
    while broker.jobs[job_id]['state'] == 'running' and time.monotonic() < deadline:
        time.sleep(.1)
    return broker.snapshot(broker.jobs[job_id])


def run(config):
    broker = Broker(config)
    if not broker.inspect or broker.math3d_root is None or len(broker.capabilities) != 1:
        raise ValueError('One current dedicated inspection broker profile is required.')
    node = shutil.which('node')
    if node is None:
        raise ValueError('Node.js is required for inspection product smoke.')
    fixtures = {item['caseId']: item for item in json.loads((broker.source_root /
        'scientific/fixtures/cgal-inspect/manifest.v1.json').read_text())['cases']}
    references = {item['caseId']: item for item in broker.capabilities[0]['referenceCases']}
    outcomes = []
    for case_id in INSPECT_CASES:
        fixture, reference = fixtures[case_id], references[case_id]
        source = broker.paths['datasetRoot'] / f'inspect-{case_id}.obj'
        shutil.copyfile(broker.source_root / fixture['path'], source)
        if sha(source) != reference['inputSha256']:
            raise ValueError('Inspection fixture hash changed.')
        request = {'schemaVersion': 1, 'runtimeId': broker.runtime_id,
                   'capabilityId': 'mesh.inspect', 'caseId': case_id,
                   'input': {'path': str(source), 'sha256': sha(source)}, 'timeoutSeconds': 120}
        if case_id == 'open':
            try:
                broker.submit(request)
            except ValueError as error:
                if 'closed inspection scope' not in str(error):
                    raise
                outcomes.append({'caseId': case_id, 'state': 'scope-rejected',
                                 'inputSha256': sha(source)})
                continue
            raise ValueError('Open inspection was accepted by the broker.')
        job_id = broker.submit(request)['jobId']
        job = wait(broker, job_id)
        expected = 'succeeded' if reference['expected'] == 'accepted' else 'rejected'
        if job['state'] != expected:
            raise ValueError('Inspection broker outcome changed: ' + case_id + ' / ' + str(job['diagnostics']))
        promotion = broker.promote(job_id)
        if promotion['decision'] != ('allowed' if expected == 'succeeded' else 'blocked'):
            raise ValueError('Inspection promotion outcome changed: ' + case_id)
        folder = Path(job['directory'])
        item = {'caseId': case_id, 'jobId': job_id, 'state': job['state'],
                'requestSha256': sha(folder / 'request.json'), 'resultSha256': sha(folder / 'results.json'),
                'promotionPath': promotion['path'], 'promotionSha256': promotion['sha256']}
        if expected == 'succeeded':
            output = folder / 'inspected.obj'
            if sha(output) != reference['outputSha256']:
                raise ValueError('Inspection output differs from L9 reference.')
            product = folder / 'product'
            for command in ([node, str(ROOT / 'tools/math3d-vtk-read-product.mjs'),
                             '--checkout', str(broker.math3d_root), '--source', str(output),
                             '--expected-sha', reference['outputSha256'], '--output', str(product)],
                            [node, str(ROOT / 'tools/math3d-vtk-read-viewer.mjs'),
                             '--checkout', str(broker.math3d_root), '--product', str(product)]):
                completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=240)
                if completed.returncode:
                    raise ValueError('Inspection MATH3D product failed: ' +
                                     (completed.stderr or completed.stdout)[-1200:])
            item.update(outputSha256=sha(output), handoffSha256=sha(folder / 'handoff.json'),
                        productFiles={name: sha(product / name) for name in PRODUCT_FILES})
        elif (folder / 'inspected.obj').exists():
            raise ValueError('Rejected inspection published geometry.')
        outcomes.append(item)
    target = broker.jobs_root / ('inspect-smoke-' + uuid.uuid4().hex + '.json')
    record = {'schemaVersion': 1, 'kind': 'scientific.cgal-inspect-broker-product-smoke',
              'verdict': 'passed', 'manifestSha256': sha(broker.paths['manifest']),
              'certificationRecordId': broker.capabilities[0]['recordId'], 'cases': outcomes}
    target.write_text(json.dumps(record, separators=(',', ':')), encoding='utf-8')
    Path(str(target) + '.sha256').write_text(sha(target), encoding='utf-8')
    verify(target, config)
    return target, record


def verify(path, config):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text().strip():
        raise ValueError('Inspection broker smoke seal changed.')
    record = json.loads(path.read_text(encoding='utf-8'))
    broker = Broker(config)
    if (not broker.inspect or record.get('kind') != 'scientific.cgal-inspect-broker-product-smoke'
            or record.get('verdict') != 'passed'
            or record.get('manifestSha256') != sha(broker.paths['manifest'])
            or record.get('certificationRecordId') != broker.capabilities[0]['recordId']
            or [item['caseId'] for item in record.get('cases', [])] != list(INSPECT_CASES)):
        raise ValueError('Inspection smoke certification changed.')
    references = {item['caseId']: item for item in broker.capabilities[0]['referenceCases']}
    for item in record['cases']:
        if item['caseId'] == 'open':
            if item['state'] != 'scope-rejected' or item['inputSha256'] != references['open']['inputSha256']:
                raise ValueError('Open inspection rejection changed.')
            continue
        job = broker.jobs.get(item['jobId'])
        if job is None or job['state'] != item['state']:
            raise ValueError('Inspection smoke job changed.')
        folder = Path(job['directory'])
        if (sha(folder / 'request.json') != item['requestSha256']
                or sha(folder / 'results.json') != item['resultSha256']
                or sha(item['promotionPath']) != item['promotionSha256']):
            raise ValueError('Inspection request, result or promotion changed.')
        decision = 'allowed' if item['state'] == 'succeeded' else 'blocked'
        if json.loads(Path(item['promotionPath']).read_text())['decision'] != decision:
            raise ValueError('Inspection promotion decision changed.')
        if item['state'] == 'succeeded':
            if (sha(folder / 'inspected.obj') != references[item['caseId']]['outputSha256']
                    or sha(folder / 'handoff.json') != item['handoffSha256']
                    or set(item['productFiles']) != set(PRODUCT_FILES)
                    or any(sha(folder / 'product' / name) != digest
                           for name, digest in item['productFiles'].items())):
                raise ValueError('Inspection product changed.')
        elif (folder / 'inspected.obj').exists():
            raise ValueError('Rejected inspection gained an output.')
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('run', 'verify'))
    parser.add_argument('--config', required=True)
    parser.add_argument('--record')
    options = parser.parse_args()
    path, record = run(options.config) if options.command == 'run' else (options.record, verify(options.record, options.config))
    print(json.dumps({'record': str(path), 'verdict': record['verdict']}))
