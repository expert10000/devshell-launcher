"""Repeatable broker → promotion → MATH3D scene/viewer → M3DM round-trip smoke."""
import argparse
import hashlib
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
from urllib.request import Request, urlopen

from broker import Broker, handler_for, sha


def verify_saved_smoke(directory):
    directory = Path(directory)
    report = json.loads((directory / 'smoke-result.json').read_text(encoding='utf-8'))
    if (report.get('schemaVersion') != 1 or report.get('state') != 'passed'
            or report.get('sourceJobId') != directory.name or report.get('contractVersion') != 1):
        raise ValueError('Saved smoke result is incomplete or belongs to another job.')
    product = directory / 'product'
    files = {'handoffSha256': directory / 'handoff.json',
             'sceneDocumentSha256': product / 'mesh-document.json',
             'sceneResourceSha256': product / 'mesh-resource.bin',
             'viewerSha256': product / 'viewer.png',
             'viewerRegressionSha256': product / 'regression.json',
             'm3dmSha256': product / 'qualified-mesh.m3dm',
             'm3dmRoundTripSha256': product / 'm3dm-roundtrip.json',
             'documentQualificationSha256': product / 'document-qualification.json'}
    for field, path in files.items():
        if sha(path) != report.get(field):
            raise ValueError(f'Saved {field} hash mismatch for job {directory.name}.')
    promotion_path = directory / 'promotions' / (report['promotionId'] + '.json')
    if sha(promotion_path) != report.get('promotionSha256'):
        raise ValueError('Saved promotion hash mismatch.')
    promotion = json.loads(promotion_path.read_text(encoding='utf-8'))
    qualification = json.loads((product / 'document-qualification.json').read_text(encoding='utf-8'))
    qualification_identity = qualification.copy()
    record_id = qualification_identity.pop('recordId', None)
    if (record_id != hashlib.sha256(json.dumps(qualification_identity, separators=(',', ':')).encode()).hexdigest()
            or record_id != report.get('documentQualificationRecordId')):
        raise ValueError('Saved document qualification record identity changed.')
    regression = json.loads((product / 'regression.json').read_text(encoding='utf-8'))
    roundtrip = json.loads((product / 'm3dm-roundtrip.json').read_text(encoding='utf-8'))
    if (promotion.get('decision') != 'allowed' or promotion.get('sourceJobId') != directory.name
            or qualification.get('state') != 'passed' or qualification.get('sourceJobId') != directory.name
            or qualification.get('sourceL9RecordId') != report.get('certificationRecordId')
            or qualification.get('promotionSha256') != report.get('promotionSha256')
            or regression.get('regression') != 'passed' or regression.get('viewerState') != 'mounted'
            or roundtrip.get('verdict') != 'passed' or roundtrip.get('sourceJobId') != directory.name):
        raise ValueError('Saved promotion, scene, or round-trip evidence is inconsistent.')
    return report


def request(base, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    with urlopen(Request(base + path, data=data, headers={'Content-Type': 'application/json'}), timeout=15) as response:
        return json.loads(response.read())


def run(command):
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=180)
    if result.returncode:
        raise RuntimeError(f"{Path(command[0]).name} exited {result.returncode}: {(result.stderr or result.stdout)[-1500:]}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('--verify-job')
    args = parser.parse_args()
    broker = Broker(args.config)
    if args.verify_job:
        if not re.fullmatch('[0-9a-f]{32}', args.verify_job):
            raise ValueError('A 32-character broker job ID is required.')
        verified = verify_saved_smoke(broker.jobs_root / args.verify_job)
        print(json.dumps({'state': 'verified', 'sourceJobId': verified['sourceJobId']}))
        return
    if broker.math3d_root is None:
        raise ValueError('math3dRoot is required for the MATH3D end-to-end smoke.')
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(broker))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    job_id = None
    stage = 'discovery'
    directory = None
    try:
        providers = request(base, '/v1/providers')['providers']
        if len(providers) != 1 or providers[0]['runtimeId'] != 'cgal-win-conda':
            raise ValueError('The fixed CGAL capability is not certified.')
        source = broker.paths['datasetRoot'] / 'math3d' / 'basic' / '01_tetrahedron.obj'
        stage = 'broker-job'
        job = request(base, '/v1/jobs', {'schemaVersion': 1, 'runtimeId': 'cgal-win-conda',
            'capabilityId': 'mesh.interop.vtk-math3d', 'input': {'path': str(source), 'sha256': sha(source)}})
        job_id = job['jobId']
        directory = Path(job['directory'])
        deadline = time.monotonic() + 150
        while job['state'] == 'running' and time.monotonic() < deadline:
            time.sleep(0.1)
            job = request(base, '/v1/jobs/' + job_id)
        if job['state'] != 'succeeded':
            raise RuntimeError(f"Broker job {job_id} ended {job['state']}: {job['diagnostics']}")
        stage = 'promotion'
        promotion = request(base, '/v1/jobs/' + job_id + '/promote', {})
        if promotion['decision'] != 'allowed':
            raise RuntimeError(f"Promotion blocked for job {job_id}: {promotion['reasons']}")
        handoff = directory / 'handoff.json'
        product = directory / 'product'
        tool_root = Path(__file__).resolve().parent.parent
        stage = 'math3d-scene-viewer'
        run(['node', str(tool_root / 'math3d-l9-product-handoff.mjs'), '--checkout', str(broker.math3d_root),
             '--handoff', str(handoff), '--output', str(product)])
        regression_path = product / 'regression.json'
        regression = json.loads(regression_path.read_text(encoding='utf-8'))
        if regression.get('regression') != 'passed' or regression.get('viewerState') != 'mounted':
            raise ValueError('MATH3D document import or viewer regression failed.')
        stage = 'm3dm-write'
        run(['node', str(Path(__file__).parent / 'write-m3dm.mjs'), '--checkout', str(broker.math3d_root),
             '--handoff', str(handoff), '--promotion', promotion['path'],
             '--promotion-sha256', promotion['sha256'], '--output', str(product)])
        stage = 'm3dm-independent-reload'
        reload_path = product / 'm3dm-roundtrip.json'
        run([sys.executable, str(Path(__file__).parent / 'check_m3dm_roundtrip.py'),
             '--obj', str(directory / 'l5-positive.obj'), '--m3dm', str(product / 'qualified-mesh.m3dm'),
             '--writer', str(product / 'm3dm-write.json'), '--output', str(reload_path)])
        reload = json.loads(reload_path.read_text(encoding='utf-8'))
        if reload.get('verdict') != 'passed' or reload.get('sourceJobId') != job_id:
            raise ValueError('Independent M3DM round-trip evidence is incomplete.')
        entry = next(item for item in broker.capabilities if item['recordId'] == job['certificationRecordId'])
        writer_path = product / 'm3dm-write.json'
        writer = json.loads(writer_path.read_text(encoding='utf-8'))
        document_qualification = {'schemaVersion': 1, 'kind': 'scientific.document-roundtrip',
            'scope': 'fixed-cgal-mesh', 'state': 'passed', 'sourceJobId': job_id,
            'sourceL9RecordId': entry['recordId'], 'sourceFingerprintSha256': entry['runFingerprintSha256'],
            'suiteRevisionSha256': entry['suiteRevisionSha256'], 'promotionId': promotion['promotionId'],
            'promotionSha256': promotion['sha256'], 'handoffContractSha256': entry['productContractSha256'],
            'm3dmFormatVersion': 1, 'sourceArtifactSha256': sha(directory / 'l5-positive.obj'),
            'm3dmSha256': sha(product / 'qualified-mesh.m3dm'),
            'm3dmCodecSourceSha256': writer['codecSourceSha256'],
            'm3dmWriterSourceSha256': sha(Path(__file__).parent / 'write-m3dm.mjs'),
            'independentParserSourceSha256': reload['parserSourceSha256'],
            'sceneDocumentSha256': sha(product / 'mesh-document.json'),
            'sceneResourceSha256': sha(product / 'mesh-resource.bin'),
            'viewerRegressionSha256': sha(regression_path), 'roundTripEvidenceSha256': sha(reload_path),
            'geometry': reload['geometry'], 'topology': reload['topology'],
            'orientation': reload['orientation'], 'scale': reload['scale']}
        document_qualification['recordId'] = hashlib.sha256(
            json.dumps(document_qualification, separators=(',', ':')).encode()).hexdigest()
        qualification_path = product / 'document-qualification.json'
        with qualification_path.open('x', encoding='utf-8') as stream:
            json.dump(document_qualification, stream, separators=(',', ':'))
        record = {'schemaVersion': 1, 'suiteId': 'scientific-broker-math3d-smoke-v1',
                  'state': 'passed', 'sourceJobId': job_id, 'certificationRecordId': job['certificationRecordId'],
                  'promotionId': promotion['promotionId'], 'promotionSha256': promotion['sha256'],
                  'handoffSha256': sha(handoff), 'contractVersion': 1,
                  'sceneDocumentSha256': sha(product / 'mesh-document.json'),
                  'sceneResourceSha256': sha(product / 'mesh-resource.bin'),
                  'viewerSha256': sha(product / 'viewer.png'), 'viewerRegressionSha256': sha(regression_path),
                  'm3dmSha256': sha(product / 'qualified-mesh.m3dm'), 'm3dmRoundTripSha256': sha(reload_path),
                  'documentQualificationSha256': sha(qualification_path),
                  'documentQualificationRecordId': document_qualification['recordId'],
                  'points': regression['points'], 'triangles': regression['triangles'],
                  'viewerState': regression['viewerState'], 'roundTrip': reload['verdict']}
        (directory / 'smoke-result.json').write_text(json.dumps(record, separators=(',', ':')), encoding='utf-8')
        verify_saved_smoke(directory)
        print(json.dumps({'state': 'passed', 'sourceJobId': job_id, 'promotionId': promotion['promotionId'],
                          'viewerState': regression['viewerState'], 'roundTrip': reload['verdict']}))
    except Exception as error:
        record = {'schemaVersion': 1, 'suiteId': 'scientific-broker-math3d-smoke-v1',
                  'state': 'failed', 'stage': stage, 'sourceJobId': job_id, 'reason': str(error)[:2000]}
        target = directory / 'smoke-result.json' if directory else broker.jobs_root / 'smoke-failed.json'
        target.write_text(json.dumps(record, separators=(',', ':')), encoding='utf-8')
        raise
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
