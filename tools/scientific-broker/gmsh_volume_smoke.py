"""Certified fixed-cube broker transport, promotion and MATH3D product smoke."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

from broker import Broker, sha

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ('cube.msh', 'volume.m3dt', 'exporter.json', 'handoff.json')
PRODUCT = ('tetra-document.json', 'tetra-resource.m3dt', 'viewer.png',
           'regression.json', 'roundtrip.json')


def run(config):
    broker = Broker(config)
    if not broker.volume or broker.math3d_root is None or len(broker.capabilities) != 1:
        raise ValueError('A single certified fixed-cube volume profile with MATH3D is required.')
    fixture = broker.paths['datasetRoot'] / 'gmsh' / 'fixed-cube.geo'
    request = {'schemaVersion': 1, 'runtimeId': broker.runtime_id,
               'capabilityId': broker.capability_id,
               'input': {'path': str(fixture), 'sha256': sha(fixture)}, 'timeoutSeconds': 120}
    job = broker.submit(request)
    deadline = time.monotonic() + 130
    while broker.jobs[job['jobId']]['state'] == 'running' and time.monotonic() < deadline:
        time.sleep(.1)
    job = broker.snapshot(broker.jobs[job['jobId']])
    if job['state'] != 'succeeded' or job.get('cleanup', {}).get('state') != 'passed':
        raise ValueError('Gmsh volume broker job failed: ' + str(job.get('diagnostics')))
    for name in ARTIFACTS:
        broker.artifact(job['jobId'], name)
    promotion = broker.promote(job['jobId'])
    if promotion['decision'] != 'allowed':
        raise ValueError('Gmsh volume promotion was blocked: ' + '; '.join(promotion['reasons']))
    directory = Path(job['directory'])
    product = directory / 'product'
    node = shutil.which('node')
    if node is None:
        raise ValueError('Node.js is required for the MATH3D volume product check.')
    subprocess.run([node, str(ROOT / 'tools/math3d-gmsh-tetmesh-product.mjs'),
                    '--checkout', str(broker.math3d_root), '--handoff', str(directory / 'handoff.json'),
                    '--output', str(product)], check=True, timeout=240, cwd=ROOT)
    subprocess.run([str(broker.paths['python']), str(ROOT / 'tools/scientific-gmsh-tetmesh-roundtrip.py'),
                    '--document', str(product / 'tetra-document.json'),
                    '--resource', str(product / 'tetra-resource.m3dt'),
                    '--source-msh', str(directory / 'cube.msh'),
                    '--result', str(product / 'roundtrip.json')], check=True, timeout=60, cwd=ROOT)
    regression = json.loads((product / 'regression.json').read_text(encoding='utf-8'))
    roundtrip = json.loads((product / 'roundtrip.json').read_text(encoding='utf-8'))
    if (regression.get('regression') != 'passed' or regression.get('viewerState') != 'mounted'
            or regression.get('points') != 83 or regression.get('tetrahedra') != 204
            or regression.get('boundaryTriangles') != 156 or not regression.get('tamperRejected')
            or roundtrip.get('verdict') != 'passed'):
        raise ValueError('Gmsh volume document, reload or viewer regression failed.')
    files = {name: sha(directory / name) for name in ARTIFACTS}
    files.update({f'product/{name}': sha(product / name) for name in PRODUCT})
    record = {'schemaVersion': 1, 'kind': 'scientific.gmsh-volume-broker-product-smoke',
              'sourceJobId': job['jobId'], 'sourceJobState': job['state'],
              'promotionId': promotion['promotionId'], 'promotionPath': promotion['path'],
              'promotionSha256': promotion['sha256'],
              'certificationRecordId': broker.capabilities[0]['recordId'],
              'manifestSha256': sha(broker.paths['manifest']),
              'contractVersion': 1, 'files': files, 'verdict': 'passed'}
    target = directory / 'volume-smoke.json'
    with target.open('x', encoding='utf-8') as stream:
        json.dump(record, stream, separators=(',', ':'))
    Path(str(target) + '.sha256').write_text(sha(target), encoding='utf-8')
    verify(target, config)
    return target, record


def verify(path, config):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('Gmsh volume smoke record hash mismatch.')
    record = json.loads(path.read_text(encoding='utf-8'))
    if (record.get('schemaVersion') != 1 or record.get('kind') != 'scientific.gmsh-volume-broker-product-smoke'
            or record.get('verdict') != 'passed'
            or not re.fullmatch('[0-9a-f]{32}', record.get('sourceJobId', ''))):
        raise ValueError('Gmsh volume smoke identity is invalid.')
    broker = Broker(config)
    entry = broker.capabilities[0]
    if (not broker.volume or sha(broker.paths['manifest']) != record.get('manifestSha256')
            or entry['recordId'] != record.get('certificationRecordId')):
        raise ValueError('Gmsh volume L9 certification changed after smoke.')
    directory = path.parent
    saved = json.loads((directory / 'broker-result.json').read_text(encoding='utf-8'))
    if (saved.get('jobId') != record['sourceJobId'] or saved.get('state') != 'succeeded'
            or saved.get('cleanup', {}).get('state') != 'passed'):
        raise ValueError('Source broker job is not verified successful.')
    promotion = Path(record['promotionPath']).resolve(strict=True)
    decision = json.loads(promotion.read_text(encoding='utf-8'))
    if (promotion.parent.parent != directory or sha(promotion) != record.get('promotionSha256')
            or decision.get('decision') != 'allowed' or decision.get('sourceJobId') != record['sourceJobId']
            or decision.get('certificationRecordId') != entry['recordId']):
        raise ValueError('Gmsh volume promotion evidence changed.')
    for name, expected in record['files'].items():
        target = (directory / name).resolve(strict=True)
        if not target.is_relative_to(directory) or sha(target) != expected:
            raise ValueError('Gmsh volume smoke artifact changed: ' + name)
    broker.source(record['sourceJobId'])
    for name in ARTIFACTS:
        broker.artifact(record['sourceJobId'], name)
    if (record['files']['cube.msh'] != entry['referenceWorkerArtifactSha256']
            or record['files']['volume.m3dt'] != entry['referenceArtifactSha256']):
        raise ValueError('Gmsh volume artifact differs from L9 reference.')
    regression = json.loads((directory / 'product/regression.json').read_text(encoding='utf-8'))
    roundtrip = json.loads((directory / 'product/roundtrip.json').read_text(encoding='utf-8'))
    if (regression.get('viewerState') != 'mounted' or regression.get('regression') != 'passed'
            or regression.get('resourceSha256') != record['files']['product/tetra-resource.m3dt']
            or roundtrip.get('verdict') != 'passed'
            or roundtrip.get('resourceSha256') != record['files']['product/tetra-resource.m3dt']
            or roundtrip.get('sourceMshSha256') != record['files']['cube.msh']):
        raise ValueError('Gmsh volume document or viewer evidence changed.')
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('run', 'verify'))
    parser.add_argument('--config', required=True)
    parser.add_argument('--record')
    args = parser.parse_args()
    if args.command == 'run':
        path, value = run(args.config)
        print(json.dumps({'record': str(path), 'verdict': value['verdict']}))
    else:
        if not args.record:
            parser.error('verify requires --record')
        value = verify(args.record, args.config)
        print(json.dumps({'record': args.record, 'verdict': value['verdict']}))
