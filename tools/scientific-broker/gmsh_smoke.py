"""Repeatable certified Gmsh broker -> MATH3D fixed 2D document smoke."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from broker import Broker, sha

ROOT = Path(__file__).resolve().parents[2]


def run(config):
    broker = Broker(config)
    if not broker.gmsh or broker.math3d_root is None or len(broker.capabilities) != 1:
        raise ValueError('A single certified Gmsh L9 broker profile with MATH3D is required.')
    fixture = broker.paths['datasetRoot'] / 'gmsh' / 'fixed-square.geo'
    request = {'schemaVersion': 1, 'runtimeId': 'gmsh-win-conda', 'capabilityId': 'mesh.generate',
               'input': {'path': str(fixture), 'sha256': sha(fixture)}, 'timeoutSeconds': 120}
    job = broker.submit(request)
    deadline = time.monotonic() + 130
    while broker.jobs[job['jobId']]['state'] == 'running' and time.monotonic() < deadline:
        time.sleep(.1)
    job = broker.snapshot(broker.jobs[job['jobId']])
    if job['state'] != 'succeeded' or job.get('cleanup', {}).get('state') != 'passed':
        raise ValueError('Gmsh broker job did not finish with verified cleanup: ' + str(job.get('diagnostics')))
    for name in ('l5-positive.msh', 'l5-positive.obj', 'conversion.json', 'handoff.json'):
        broker.artifact(job['jobId'], name)
    promotion = broker.promote(job['jobId'])
    if promotion['decision'] != 'allowed':
        raise ValueError('Gmsh MATH3D promotion was blocked: ' + '; '.join(promotion['reasons']))
    directory = Path(job['directory'])
    product = directory / 'product'
    node = shutil.which('node')
    if not node:
        raise ValueError('Node.js is required for the MATH3D product check.')
    subprocess.run([node, str(ROOT / 'tools/math3d-l9-product-handoff.mjs'),
                    '--checkout', str(broker.math3d_root), '--handoff', str(directory / 'handoff.json'),
                    '--output', str(product)], check=True, timeout=240, cwd=ROOT)
    subprocess.run([str(broker.paths['python']), str(ROOT / 'tools/scientific-gmsh-m3dm-roundtrip.py'),
                    '--input-obj', str(directory / 'l5-positive.obj'),
                    '--input-m3dm', str(product / 'qualified-mesh.m3dm'),
                    '--result', str(product / 'roundtrip.json')], check=True, timeout=60, cwd=ROOT)
    regression = json.loads((product / 'regression.json').read_text(encoding='utf-8'))
    roundtrip = json.loads((product / 'roundtrip.json').read_text(encoding='utf-8'))
    if (regression.get('regression') != 'passed' or regression.get('viewerState') != 'mounted'
            or regression.get('points') != 44 or regression.get('triangles') != 66
            or roundtrip.get('verdict') != 'passed'):
        raise ValueError('Gmsh broker document/viewer regression failed.')
    files = {name: sha(directory / name) for name in (
        'l5-positive.msh', 'l5-positive.obj', 'conversion.json', 'handoff.json',
        'product/mesh-document.json', 'product/mesh-resource.bin', 'product/viewer.png',
        'product/regression.json', 'product/qualified-mesh.m3dm', 'product/roundtrip.json')}
    record = {'schemaVersion': 1, 'kind': 'scientific.gmsh-broker-product-smoke',
              'sourceJobId': job['jobId'], 'sourceJobState': job['state'],
              'promotionId': promotion['promotionId'], 'promotionPath': promotion['path'],
              'promotionSha256': promotion['sha256'],
              'certificationRecordId': broker.capabilities[0]['recordId'],
              'manifestSha256': sha(broker.paths['manifest']),
              'contractVersion': 1, 'files': files,
              'viewerState': regression['viewerState'], 'm3dmVerdict': roundtrip['verdict'],
              'verdict': 'passed'}
    target = directory / 'gmsh-smoke.json'
    with target.open('x', encoding='utf-8') as stream:
        json.dump(record, stream, separators=(',', ':'))
    Path(str(target) + '.sha256').write_text(sha(target), encoding='utf-8')
    verify(target, config)
    return target, record


def verify(path, config):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('Gmsh smoke record hash mismatch.')
    record = json.loads(path.read_text(encoding='utf-8'))
    if (record.get('schemaVersion') != 1 or record.get('kind') != 'scientific.gmsh-broker-product-smoke'
            or record.get('verdict') != 'passed'
            or not re.fullmatch('[0-9a-f]{32}', record.get('sourceJobId', ''))
            or record.get('contractVersion') != 1):
        raise ValueError('Gmsh smoke identity is invalid.')
    broker = Broker(config)
    if sha(broker.paths['manifest']) != record.get('manifestSha256'):
        raise ValueError('Certified manifest changed after smoke.')
    entry = broker.capabilities[0]
    if entry['recordId'] != record.get('certificationRecordId'):
        raise ValueError('Gmsh L9 certification changed after smoke.')
    directory = path.parent
    saved = json.loads((directory / 'broker-result.json').read_text(encoding='utf-8'))
    if (saved.get('jobId') != record['sourceJobId'] or saved.get('state') != 'succeeded'
            or saved.get('cleanup', {}).get('state') != 'passed'):
        raise ValueError('Source broker job is not verified successful.')
    if record['sourceJobId'] not in broker.jobs:
        raise ValueError('Source broker job is unavailable.')
    promotion = Path(record['promotionPath']).resolve(strict=True)
    decision = json.loads(promotion.read_text(encoding='utf-8'))
    if (promotion.parent.parent != directory or sha(promotion) != record.get('promotionSha256')
            or decision.get('decision') != 'allowed' or decision.get('sourceJobId') != record['sourceJobId']
            or decision.get('certificationRecordId') != entry['recordId']):
        raise ValueError('Gmsh promotion evidence changed.')
    for name, expected in record['files'].items():
        target = (directory / name).resolve(strict=True)
        if not target.is_relative_to(directory) or sha(target) != expected:
            raise ValueError('Gmsh smoke artifact changed: ' + name)
    broker.source(record['sourceJobId'])
    for name in ('l5-positive.msh', 'l5-positive.obj', 'conversion.json', 'handoff.json'):
        broker.artifact(record['sourceJobId'], name)
    if (record['files']['l5-positive.msh'] != entry['referenceWorkerArtifactSha256']
            or record['files']['l5-positive.obj'] != entry['referenceArtifactSha256']):
        raise ValueError('Gmsh smoke artifact differs from L9 reference.')
    regression = json.loads((directory / 'product/regression.json').read_text(encoding='utf-8'))
    roundtrip = json.loads((directory / 'product/roundtrip.json').read_text(encoding='utf-8'))
    if (regression.get('viewerState') != 'mounted' or regression.get('regression') != 'passed'
            or regression.get('points') != 44 or regression.get('triangles') != 66
            or regression.get('m3dmSha256') != record['files']['product/qualified-mesh.m3dm']
            or roundtrip.get('verdict') != 'passed'
            or roundtrip.get('m3dmSha256') != record['files']['product/qualified-mesh.m3dm']):
        raise ValueError('Gmsh smoke document or viewer evidence changed.')
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
