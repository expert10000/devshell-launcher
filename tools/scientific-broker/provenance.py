"""Exact Sage-to-CGAL-to-MATH3D provenance for the fixed public tetrahedron."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

from broker import Broker, sha
from smoke import verify_saved_smoke

SAGE_CODE = (
    "import json\n"
    "from sage.all import PolynomialRing, QQ\n"
    "ring = PolynomialRing(QQ, 'x')\n"
    "x = ring.gen()\n"
    "polynomial = x*x - 1\n"
    "roots = sorted(root for root, multiplicity in polynomial.roots() if multiplicity == 1)\n"
    "assert roots == [QQ(-1), QQ(1)] and all(polynomial(root) == 0 for root in roots)\n"
    "print(json.dumps({'schemaVersion':1,'inputCoefficients':['-1','0','1'],"
    "'roots':[str(root) for root in roots],'verified':True},separators=(',',':')))\n"
)
FACES = ('f 1 3 2', 'f 1 2 4', 'f 1 4 3', 'f 2 3 4')


def exact_derivation(distro):
    script = ('for candidate in /usr/bin/sage /usr/local/bin/sage '
              '"$HOME/miniforge3/envs/sage/bin/sage" "$HOME/mambaforge/envs/sage/bin/sage" '
              '"$HOME/miniconda3/envs/sage/bin/sage"; do '
              'if test -x "$candidate"; then exec "$candidate" -python -c "$1"; fi; done; exit 127')
    result = subprocess.run(['wsl.exe', '-d', distro, '--exec', 'sh', '-lc', script, 'sh', SAGE_CODE],
                            capture_output=True, text=True, timeout=60,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise ValueError('Sage exact derivation failed: ' + result.stderr[-300:])
    lines = [line for line in result.stdout.splitlines() if line.strip().startswith('{')]
    value = json.loads(lines[-1]) if lines else {}
    if value != {'schemaVersion': 1, 'inputCoefficients': ['-1', '0', '1'],
                 'roots': ['-1', '1'], 'verified': True}:
        raise ValueError('Sage exact roots or proof changed.')
    return value


def sample_obj(exact):
    if exact.get('roots') != ['-1', '1'] or exact.get('verified') is not True:
        raise ValueError('Unverified exact roots cannot be sampled.')
    negative, positive = (int(value) for value in exact['roots'])
    points = [(positive, positive, positive), (negative, negative, positive),
              (negative, positive, negative), (positive, negative, negative)]
    lines = ['# Math3D generated benchmark mesh', '# minimal closed triangular manifold']
    lines += ['v ' + ' '.join(map(str, point)) for point in points]
    lines += list(FACES)
    return ('\r\n'.join(lines) + '\r\n').encode('ascii'), points


def build(config_path, output_root, distro):
    broker = Broker(config_path)
    if broker.math3d_root is None or len(broker.capabilities) != 1:
        raise ValueError('Current fixed CGAL certification and MATH3D checkout are required.')
    exact = exact_derivation(distro)
    sample, points = sample_obj(exact)
    expected = broker.capabilities[0]['referenceInputSha256']
    if hashlib.sha256(sample).hexdigest() != expected:
        raise ValueError('Exact Sage sample differs from the certified CGAL fixture.')
    run_id = uuid.uuid4().hex
    root = Path(output_root).resolve() / run_id
    root.mkdir(parents=True)
    source = broker.paths['datasetRoot'] / 'provenance' / run_id / 'tetra.obj'
    source.parent.mkdir(parents=True)
    with source.open('xb') as stream:
        stream.write(sample)
    sage_path = root / 'sage-exact.json'
    sage_path.write_text(json.dumps(exact, separators=(',', ':')), encoding='utf-8')
    command = [sys.executable, str(Path(__file__).with_name('smoke.py')), '--config', str(config_path),
               '--input-path', str(source)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=300)
    if result.returncode:
        raise RuntimeError('Broker-to-MATH3D smoke failed: ' + (result.stderr or result.stdout)[-1000:])
    lines = [line for line in result.stdout.splitlines() if line.startswith('{')]
    outcome = json.loads(lines[-1]) if lines else {}
    job_id = outcome.get('sourceJobId', '')
    if not re.fullmatch('[0-9a-f]{32}', job_id):
        raise ValueError('Smoke result did not identify a broker job.')
    job = broker.jobs_root / job_id
    smoke = verify_saved_smoke(job)
    request = json.loads((job / 'request.json').read_text(encoding='utf-8'))
    if (request['inputArtifacts'][0]['sha256'] != expected or sha(job / 'dataset' / 'input.obj') != expected
            or smoke['m3dmSha256'] != sha(job / 'product' / 'qualified-mesh.m3dm')):
        raise ValueError('Source, worker and document identities do not form one chain.')
    def node(name, kind, content_hash, **extra):
        return {'id': name, 'kind': kind, 'sha256': content_hash, **extra}
    nodes = [
        node('exact-input', 'sage.polynomial.coefficients.v1', hashlib.sha256(b'-1,0,1').hexdigest(), coefficients=['-1', '0', '1']),
        node('exact-derivation', 'sage.rational-roots.v1', sha(sage_path), path=str(sage_path),
             sageCodeSha256=hashlib.sha256(SAGE_CODE.encode()).hexdigest(), distro=distro),
        node('approximation', 'geometry.float64-points.v1', hashlib.sha256(json.dumps(points, separators=(',', ':')).encode()).hexdigest(),
             points=[list(point) for point in points], rounding='exact integers represented in IEEE-754 float64'),
        node('geometry-sample', 'geometry.exact-vertices.v1',
             hashlib.sha256(json.dumps(points, separators=(',', ':')).encode()).hexdigest(),
             points=[list(point) for point in points], method='Cartesian product of rational roots with fixed tetrahedral sign pattern'),
        node('mesh-generation', 'mesh.obj.v1', expected, path=str(source), faces=list(FACES)),
        node('cgal-validation', 'cgal.validated-mesh.obj.v1', sha(job / 'l5-positive.obj'), path=str(job / 'l5-positive.obj'),
             sourceJobId=job_id, workerContractVersion=1, certificationRecordId=smoke['certificationRecordId']),
        node('math3d-document', 'math3d.m3dm.v1', smoke['m3dmSha256'], path=str(job / 'product' / 'qualified-mesh.m3dm'),
             sourceJobId=job_id, smokeResultSha256=sha(job / 'smoke-result.json'),
             sceneDocumentSha256=smoke['sceneDocumentSha256'], viewerRegressionSha256=smoke['viewerRegressionSha256']),
    ]
    edges = [{'from': nodes[index]['id'], 'to': nodes[index + 1]['id'], 'relation': 'derived-from'}
             for index in range(len(nodes) - 1)]
    record = {'schemaVersion': 1, 'kind': 'scientific.mathematical-provenance',
              'createdAtUtc': datetime.now(timezone.utc).isoformat(), 'sourceJobId': job_id,
              'manifestSha256': sha(broker.paths['manifest']), 'nodes': nodes, 'edges': edges,
              'scope': 'fixed public exact-root tetrahedron; no general Sage mesh worker qualification'}
    path = root / 'provenance.json'
    with path.open('x', encoding='utf-8') as stream:
        json.dump(record, stream, indent=2)
    Path(str(path) + '.sha256').write_text(sha(path), encoding='utf-8')
    return path, record


def verify(path, config_path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text().strip():
        raise ValueError('Provenance record hash mismatch.')
    record = json.loads(path.read_text(encoding='utf-8'))
    names = ('exact-input', 'exact-derivation', 'approximation', 'geometry-sample',
             'mesh-generation', 'cgal-validation', 'math3d-document')
    if (record.get('schemaVersion') != 1 or record.get('kind') != 'scientific.mathematical-provenance'
            or tuple(item['id'] for item in record['nodes']) != names
            or [(edge['from'], edge['to'], edge['relation']) for edge in record['edges']]
            != [(left, right, 'derived-from') for left, right in zip(names, names[1:])]
            or record['nodes'][0]['coefficients'] != ['-1', '0', '1']
            or record['nodes'][0]['sha256'] != hashlib.sha256(b'-1,0,1').hexdigest()
            or record['nodes'][4]['faces'] != list(FACES)):
        raise ValueError('Provenance graph structure changed.')
    broker = Broker(config_path)
    if sha(broker.paths['manifest']) != record['manifestSha256']:
        raise ValueError('Certified manifest changed.')
    exact = json.loads(Path(record['nodes'][1]['path']).read_text(encoding='utf-8'))
    sample, points = sample_obj(exact)
    if (sha(record['nodes'][1]['path']) != record['nodes'][1]['sha256']
            or hashlib.sha256(SAGE_CODE.encode()).hexdigest() != record['nodes'][1]['sageCodeSha256']
            or hashlib.sha256(json.dumps(points, separators=(',', ':')).encode()).hexdigest() != record['nodes'][2]['sha256']
            or [list(point) for point in points] != record['nodes'][2]['points']
            or record['nodes'][3]['points'] != [list(point) for point in points]
            or record['nodes'][3]['sha256'] != record['nodes'][2]['sha256']
            or hashlib.sha256(sample).hexdigest() != record['nodes'][4]['sha256']
            or sha(record['nodes'][4]['path']) != record['nodes'][4]['sha256']):
        raise ValueError('Exact derivation or sampled geometry changed.')
    job_id = record['sourceJobId']
    if not re.fullmatch('[0-9a-f]{32}', job_id):
        raise ValueError('Source job identity changed.')
    job = broker.jobs_root / job_id
    smoke = verify_saved_smoke(job)
    request = json.loads((job / 'request.json').read_text(encoding='utf-8'))
    if (request['inputArtifacts'][0]['sha256'] != record['nodes'][4]['sha256']
            or sha(job / 'dataset' / 'input.obj') != record['nodes'][4]['sha256']
            or sha(record['nodes'][5]['path']) != record['nodes'][5]['sha256']
            or sha(record['nodes'][6]['path']) != record['nodes'][6]['sha256']
            or smoke['m3dmSha256'] != record['nodes'][6]['sha256']
            or smoke['sourceJobId'] != job_id
            or record['nodes'][5]['sourceJobId'] != job_id
            or record['nodes'][6]['sourceJobId'] != job_id
            or record['nodes'][6]['smokeResultSha256'] != sha(job / 'smoke-result.json')
            or record['nodes'][6]['sceneDocumentSha256'] != smoke['sceneDocumentSha256']
            or record['nodes'][6]['viewerRegressionSha256'] != smoke['viewerRegressionSha256']):
        raise ValueError('Worker or final MATH3D document chain changed.')
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['build', 'verify'])
    parser.add_argument('--config', required=True)
    parser.add_argument('--output-root')
    parser.add_argument('--distro', default=os.environ.get('MATH3D_WSL_DISTRO', 'Ubuntu'))
    parser.add_argument('--record')
    args = parser.parse_args()
    if args.command == 'build':
        if not args.output_root:
            parser.error('build requires --output-root')
        path, record = build(args.config, args.output_root, args.distro)
        print(json.dumps({'record': str(path), 'sourceJobId': record['sourceJobId'], 'nodes': len(record['nodes'])}))
    else:
        report = verify(args.record, args.config)
        print(json.dumps({'state': 'verified', 'sourceJobId': report['sourceJobId']}))


if __name__ == '__main__':
    main()
