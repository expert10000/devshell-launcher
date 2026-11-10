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
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def replay(python, worker, prefix, output_root):
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
                or not result['repairEvidence']['outputClosed']):
            raise ValueError(f'{operation}: managed repair evidence failed')
        cases.append({'recipeId': recipe, 'requestSha256': sha(case_dir / 'request.json'),
                      'resultSha256': sha(case_dir / 'results.json'), 'outputSha256': sha(output),
                      'before': result['before'], 'after': result['after']})

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
    tamper = root / 'changed-dataset-hash'
    tamper.mkdir()
    request['runId'] = uuid.uuid4().hex
    request['workingDirectory'] = str(tamper)
    request['inputArtifacts'][0]['sha256'] = '0' * 64
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
    args = parser.parse_args()
    replay(args.python, args.worker, args.prefix, args.output_root)
