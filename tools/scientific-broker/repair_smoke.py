"""Run and verify the certified four-case repair transport and MATH3D product smoke."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

from broker import Broker, REPAIR_CASES, sha

ROOT = Path(__file__).resolve().parents[2]


def invoke(*args, timeout=180):
    result = subprocess.run([str(item) for item in args], cwd=ROOT, timeout=timeout,
                            capture_output=True, text=True, encoding='utf-8', errors='replace')
    if result.returncode:
        raise ValueError((result.stderr or result.stdout)[-1500:])
    return result


def run(config):
    broker = Broker(config)
    if not broker.repair or broker.math3d_root is None or len(broker.capabilities) != 1:
        raise ValueError('A single certified four-case repair profile with MATH3D is required.')
    node = shutil.which('node')
    if node is None:
        raise ValueError('Node.js is required for the MATH3D repair smoke.')
    fixtures = json.loads((broker.source_root / broker.contract['fixtureManifest']).read_text(encoding='utf-8'))['fixtures']
    outcomes = []
    for case_id, fixture in zip(REPAIR_CASES, fixtures):
        stem = Path(fixture['path']).stem
        source = broker.paths['datasetRoot'] / 'imported' / fixture['sha256'] / ('mesh-' + stem + '.obj')
        if not source.is_file() or sha(source) != fixture['sha256']:
            raise ValueError('Registered broker repair fixture is unavailable: ' + case_id)
        request = {'schemaVersion': 1, 'runtimeId': broker.runtime_id, 'capabilityId': 'mesh.repair',
                   'caseId': case_id, 'input': {'path': str(source), 'sha256': sha(source)},
                   'timeoutSeconds': 120}
        job = broker.submit(request)
        deadline = time.monotonic() + 130
        while broker.jobs[job['jobId']]['state'] == 'running' and time.monotonic() < deadline:
            time.sleep(.1)
        job = broker.snapshot(broker.jobs[job['jobId']])
        if job['state'] != 'succeeded' or job.get('cleanup', {}).get('state') != 'passed':
            raise ValueError('Repair broker job failed: ' + str(job.get('diagnostics')))
        output = broker.artifact(job['jobId'], 'repaired.obj')
        broker.artifact(job['jobId'], 'handoff.json')
        promotion = broker.promote(job['jobId'])
        if promotion['decision'] != 'allowed':
            raise ValueError('Repair promotion blocked: ' + '; '.join(promotion['reasons']))
        directory = Path(job['directory'])
        product = directory / 'product'
        product.mkdir()
        handoff = product / 'handoff.json'
        invoke(broker.paths['python'], ROOT / 'tools/scientific-cgal-repair-math3d-handoff.py',
               '--run-directory', directory, '--checkout', broker.math3d_root,
               '--node', node, '--report', handoff)
        invoke(node, ROOT / 'tools/math3d-cgal-repair-product.mjs', '--checkout', broker.math3d_root,
               '--run-directory', directory, '--handoff', handoff, '--output', product, timeout=240)
        invoke(broker.paths['python'], ROOT / 'tools/scientific-cgal-repair-m3dm-roundtrip.py',
               '--run-directory', directory, '--handoff', handoff, '--product-directory', product,
               '--report', product / 'roundtrip.json')
        invoke(node, ROOT / 'tools/math3d-cgal-repair-viewer.mjs', '--checkout', broker.math3d_root,
               '--product', product, timeout=240)
        reports = [json.loads((product / name).read_text(encoding='utf-8'))
                   for name in ('handoff.json', 'product.json', 'roundtrip.json', 'viewer.json')]
        if any(report.get('verdict') != 'passed' for report in reports) or reports[-1].get('blueMeshPixels', 0) <= 1000:
            raise ValueError('Repair MATH3D product did not pass. ' + case_id)
        names = ('handoff.json', 'math3d-consumed.json', 'repair-mesh-document.json',
                 'repair-mesh-resource.bin', 'repaired.m3dm', 'product.json', 'roundtrip.json',
                 'viewer.png', 'viewer.json')
        outcomes.append({'caseId': case_id, 'sourceJobId': job['jobId'], 'promotionPath': promotion['path'],
                         'promotionSha256': promotion['sha256'], 'outputSha256': sha(directory / 'repaired.obj'),
                         'files': {name: sha(product / name) for name in names}})
    target = Path(outcomes[-1]['promotionPath']).parent.parent / 'repair-smoke.json'
    record = {'schemaVersion': 1, 'kind': 'scientific.cgal-repair-broker-product-smoke',
              'manifestSha256': sha(broker.paths['manifest']),
              'certificationRecordId': broker.capabilities[0]['recordId'],
              'cases': outcomes, 'verdict': 'passed'}
    with target.open('x', encoding='utf-8') as stream:
        json.dump(record, stream, separators=(',', ':'))
    Path(str(target) + '.sha256').write_text(sha(target), encoding='utf-8')
    verify(target, config)
    return target, record


def verify(path, config):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('Repair smoke record hash mismatch.')
    record = json.loads(path.read_text(encoding='utf-8'))
    broker = Broker(config)
    if (not broker.repair or record.get('kind') != 'scientific.cgal-repair-broker-product-smoke'
            or record.get('verdict') != 'passed' or record.get('schemaVersion') != 1
            or record.get('manifestSha256') != sha(broker.paths['manifest'])
            or record.get('certificationRecordId') != broker.capabilities[0]['recordId']
            or [case.get('caseId') for case in record.get('cases', [])] != list(REPAIR_CASES)):
        raise ValueError('Repair smoke certification or case pack changed.')
    for case, reference in zip(record['cases'], broker.capabilities[0]['referenceCases']):
        directory = broker.jobs_root / case['sourceJobId']
        saved = json.loads((directory / 'broker-result.json').read_text(encoding='utf-8'))
        promotion = Path(case['promotionPath']).resolve(strict=True)
        decision = json.loads(promotion.read_text(encoding='utf-8'))
        if (saved.get('state') != 'succeeded' or saved.get('caseId') != case['caseId']
                or saved.get('cleanup', {}).get('state') != 'passed'
                or sha(directory / 'repaired.obj') != case['outputSha256']
                or case['outputSha256'] != reference['outputSha256']
                or promotion.parent.parent != directory or sha(promotion) != case['promotionSha256']
                or decision.get('decision') != 'allowed'
                or decision.get('certificationRecordId') != record['certificationRecordId']):
            raise ValueError('Repair broker output or promotion changed.')
        product = directory / 'product'
        if set(case['files']) != {'handoff.json', 'math3d-consumed.json', 'repair-mesh-document.json',
                'repair-mesh-resource.bin', 'repaired.m3dm', 'product.json', 'roundtrip.json',
                'viewer.png', 'viewer.json'}:
            raise ValueError('Repair product file set changed.')
        for name, digest in case['files'].items():
            if sha(product / name) != digest:
                raise ValueError('Repair product artifact changed: ' + name)
        reports = [json.loads((product / name).read_text(encoding='utf-8'))
                   for name in ('handoff.json', 'product.json', 'roundtrip.json', 'viewer.json')]
        if (any(report.get('verdict') != 'passed' for report in reports)
                or reports[1].get('sourceObjSha256') != case['outputSha256']
                or reports[1].get('m3dmSha256') != case['files']['repaired.m3dm']
                or reports[2].get('m3dmSha256') != case['files']['repaired.m3dm']
                or reports[3].get('viewerState') != 'mounted'
                or reports[3].get('screenshotSha256') != case['files']['viewer.png']):
            raise ValueError('Repair MATH3D product evidence changed.')
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('run', 'verify'))
    parser.add_argument('--config', required=True)
    parser.add_argument('--record')
    args = parser.parse_args()
    path, result = run(args.config) if args.command == 'run' else (args.record, verify(args.record, args.config))
    print(json.dumps({'record': str(path), 'verdict': result['verdict']}))
