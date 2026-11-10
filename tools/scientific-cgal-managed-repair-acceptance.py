"""Replay all registered managed CGAL repair recipes against copied datasets."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid


ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / 'tools/scientific-cgal-hole-repair-worker.py'
CASES = (
    ('fill-one-hole', ROOT / 'scientific/fixtures/cgal-repair/tetra-one-hole.obj'),
    ('fill-quad-hole', ROOT / 'scientific/fixtures/cgal-repair-quad/cube-one-quad-hole.obj'),
    ('fill-two-quad-holes', ROOT / 'scientific/fixtures/cgal-repair-multi/cube-two-square-holes.obj'),
    ('fill-bounded-holes', ROOT / 'scientific/fixtures/cgal-repair-bounded/pentagonal-pyramid-open-base.obj'),
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def replay(python, worker, prefix, output_root, math3d_checkout=None, node='node'):
    python, worker, prefix = (Path(path).resolve(strict=True) for path in (python, worker, prefix))
    if worker.name.lower() != 'devshell_cgal_hole_repair.exe':
        raise ValueError('Expected the registered CGAL hole-repair executable')
    root = Path(output_root).resolve() / uuid.uuid4().hex
    dataset = root / 'datasets'
    dataset.mkdir(parents=True)
    env = os.environ.copy()
    env['PATH'] = os.pathsep.join((str(prefix), str(prefix / 'Library/bin'), str(prefix / 'Scripts'), env.get('PATH', '')))
    cases = []
    for operation, source in CASES:
        copied = dataset / source.name
        shutil.copyfile(source, copied)
        case_dir = root / operation
        case_dir.mkdir()
        output = case_dir / 'repaired.obj'
        recipe = 'cgal.' + operation
        request = {'schemaVersion': 1, 'runId': uuid.uuid4().hex, 'runtimeId': 'cgal-win-conda',
                   'recipeId': recipe, 'operation': recipe, 'parameters': {'inputId': copied.name, 'outputName': output.name},
                   'workingDirectory': str(case_dir), 'datasetRoot': str(dataset), 'timeoutSeconds': 120,
                   'inputArtifacts': [{'path': str(copied), 'datasetId': copied.name, 'sha256': sha(copied), 'bytes': copied.stat().st_size}],
                   'outputArtifacts': [{'path': output.name, 'mediaType': 'model/obj'}]}
        (case_dir / 'request.json').write_text(json.dumps(request, indent=2), encoding='utf-8')
        process = subprocess.run([str(python), str(ADAPTER), '--request', str(case_dir / 'request.json'), '--worker', str(worker)],
                                 cwd=case_dir, env=env, capture_output=True, text=True, timeout=150)
        (case_dir / 'full.log').write_text(process.stdout + process.stderr, encoding='utf-8')
        result = json.loads((case_dir / 'results.json').read_text(encoding='utf-8'))
        if (process.returncode != 0 or result['state'] != 'succeeded'
                or 'mesh.repair' not in result['validatedCapabilities']
                or result['artifacts'][0]['sha256'] != sha(output)
                or result['repairAudit']['retainedFaces'] != result['before']['faces']
                or result['repairAudit']['addedFaces'] != result['repairEvidence']['patchFaces']
                or result['repairAudit']['boundaryEdgesCovered'] != result['before']['boundaryEdges']
                or not result['repairEvidence']['outputClosed']):
            raise ValueError(f'{operation}: managed repair evidence failed')
        consumer_hash = None
        if math3d_checkout:
            handoff_path = case_dir / 'handoff.json'
            handoff = subprocess.run([sys.executable, str(ROOT / 'tools/scientific-cgal-repair-math3d-handoff.py'),
                                      '--run-directory', str(case_dir), '--checkout', str(math3d_checkout),
                                      '--node', str(node), '--report', str(handoff_path)],
                                     cwd=ROOT, capture_output=True, text=True, timeout=150)
            if handoff.returncode != 0 or json.loads(handoff_path.read_text(encoding='utf-8'))['verdict'] != 'passed':
                raise ValueError(f'{operation}: MATH3D importer handoff failed: {handoff.stderr[-1000:]}')
            consumer_hash = sha(handoff_path)
        cases.append({'recipeId': recipe, 'requestSha256': sha(case_dir / 'request.json'),
                      'resultSha256': sha(case_dir / 'results.json'), 'outputSha256': sha(output),
                      'before': result['before'], 'after': result['after'], 'repairAudit': result['repairAudit'],
                      'math3dHandoffSha256': consumer_hash})

    # A valid dataset copy with the wrong selected operation must fail without an artifact.
    negative = root / 'wrong-operation'
    negative.mkdir()
    request['runId'] = uuid.uuid4().hex
    request['workingDirectory'] = str(negative)
    request['recipeId'] = request['operation'] = 'cgal.fill-one-hole'
    request['outputArtifacts'][0]['path'] = request['parameters']['outputName'] = 'refused.obj'
    (negative / 'request.json').write_text(json.dumps(request, indent=2), encoding='utf-8')
    process = subprocess.run([str(python), str(ADAPTER), '--request', str(negative / 'request.json'), '--worker', str(worker)],
                             cwd=negative, env=env, capture_output=True, text=True, timeout=150)
    (negative / 'full.log').write_text(process.stdout + process.stderr, encoding='utf-8')
    rejected = json.loads((negative / 'results.json').read_text(encoding='utf-8'))
    if (process.returncode == 0 or rejected['state'] != 'failed' or rejected['validatedCapabilities']
            or (negative / 'refused.obj').exists()
            or 'boundary-loop scope' not in rejected['diagnostics'][0]['message']):
        raise ValueError('Wrong operation was not safely rejected')
    closed = dataset / 'closed-tetra.obj'
    shutil.copyfile(ROOT / 'scientific/fixtures/cgal/closed-tetra.obj', closed)
    closed_case = root / 'closed-rejection'
    closed_case.mkdir()
    request['runId'] = uuid.uuid4().hex
    request['workingDirectory'] = str(closed_case)
    request['recipeId'] = request['operation'] = 'cgal.fill-bounded-holes'
    request['inputArtifacts'][0].update(path=str(closed), datasetId=closed.name,
                                        sha256=sha(closed), bytes=closed.stat().st_size)
    request['parameters']['inputId'] = closed.name
    request['outputArtifacts'][0]['path'] = request['parameters']['outputName'] = 'closed-refused.obj'
    (closed_case / 'request.json').write_text(json.dumps(request, indent=2), encoding='utf-8')
    process = subprocess.run([str(python), str(ADAPTER), '--request', str(closed_case / 'request.json'), '--worker', str(worker)],
                             cwd=closed_case, env=env, capture_output=True, text=True, timeout=150)
    (closed_case / 'full.log').write_text(process.stdout + process.stderr, encoding='utf-8')
    closed_result = json.loads((closed_case / 'results.json').read_text(encoding='utf-8'))
    if (process.returncode == 0 or closed_result['state'] != 'failed' or closed_result['validatedCapabilities']
            or (closed_case / 'closed-refused.obj').exists()
            or 'Bounded repair requires' not in closed_result['diagnostics'][0]['message']):
        raise ValueError('Closed mesh was not safely rejected')
    tamper = root / 'changed-dataset-hash'
    tamper.mkdir()
    request['runId'] = uuid.uuid4().hex
    request['workingDirectory'] = str(tamper)
    request['inputArtifacts'][0]['sha256'] = '0' * 64
    request['outputArtifacts'][0]['path'] = request['parameters']['outputName'] = 'refused.obj'
    (tamper / 'request.json').write_text(json.dumps(request, indent=2), encoding='utf-8')
    process = subprocess.run([str(python), str(ADAPTER), '--request', str(tamper / 'request.json'), '--worker', str(worker)],
                             cwd=tamper, env=env, capture_output=True, text=True, timeout=150)
    (tamper / 'full.log').write_text(process.stdout + process.stderr, encoding='utf-8')
    denied = json.loads((tamper / 'results.json').read_text(encoding='utf-8'))
    if (process.returncode == 0 or denied['state'] != 'failed' or denied['validatedCapabilities']
            or (tamper / 'refused.obj').exists()
            or 'Dataset hash changed' not in denied['diagnostics'][0]['message']):
        raise ValueError('Changed dataset hash was not safely rejected')
    report = {'schemaVersion': 1, 'kind': 'scientific.cgal-managed-repair-acceptance',
              'workerSha256': sha(worker), 'adapterSha256': sha(ADAPTER),
              'cases': cases, 'wrongOperationResultSha256': sha(negative / 'results.json'),
              'closedResultSha256': sha(closed_case / 'results.json'),
              'changedHashResultSha256': sha(tamper / 'results.json'), 'verdict': 'passed'}
    (root / 'acceptance.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'report': str(root / 'acceptance.json'), 'verdict': 'passed', 'recipes': len(cases)}))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--python', required=True)
    parser.add_argument('--worker', required=True)
    parser.add_argument('--prefix', required=True)
    parser.add_argument('--output-root', required=True)
    parser.add_argument('--math3d-checkout')
    parser.add_argument('--node', default='node')
    args = parser.parse_args()
    replay(args.python, args.worker, args.prefix, args.output_root, args.math3d_checkout, args.node)
