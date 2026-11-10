"""Verify a saved managed repair through MATH3D's actual OBJ importer."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys

from scientific_cgal_mesh_metrics import metrics


ROOT = Path(__file__).resolve().parents[1]
CONSUMER = ROOT / 'tools/math3d-vtk-import-handoff.mjs'
ADAPTER = ROOT / 'tools/scientific-cgal-hole-repair-worker.py'
spec = importlib.util.spec_from_file_location('managed_repair_handoff', ADAPTER)
repair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify(run_directory, checkout, node, report_path):
    directory = Path(run_directory).resolve(strict=True)
    checkout = Path(checkout).resolve(strict=True)
    node = Path(node).resolve(strict=True) if Path(node).is_file() else node
    request = json.loads((directory / 'request.json').read_text(encoding='utf-8-sig'))
    result = json.loads((directory / 'results.json').read_text(encoding='utf-8-sig'))
    recipe = request.get('recipeId')
    if (recipe not in repair.OPERATIONS or result.get('recipeId') != recipe
            or result.get('runId') != request.get('runId') or result.get('state') != 'succeeded'
            or Path(request.get('workingDirectory', '')).resolve() != directory
            or 'mesh.repair' not in result.get('validatedCapabilities', [])):
        raise ValueError('Run is not a successful managed CGAL repair')
    dataset_root = Path(request['datasetRoot']).resolve(strict=True)
    source = Path(request['inputArtifacts'][0]['path']).resolve(strict=True)
    if not source.is_relative_to(dataset_root) or sha(source) != request['inputArtifacts'][0]['sha256']:
        raise ValueError('Registered source copy changed')
    output_name = request['outputArtifacts'][0]['path']
    if not isinstance(output_name, str) or not output_name.endswith('.obj') or Path(output_name).name != output_name:
        raise ValueError('Saved output is not a scoped OBJ basename')
    output = (directory / output_name).resolve(strict=True)
    if (output.parent != directory or result['artifacts'][0].get('path') != output_name
            or sha(output) != result['artifacts'][0]['sha256']):
        raise ValueError('Saved repair artifact changed')
    before, after = metrics(source), metrics(output)
    before['boundaryLoopEdgeCounts'] = repair.boundary_sizes(source)
    repair.check_geometry(before, after, result['engineDetails'], recipe)
    audit = repair.audit_patch(source, output, result['engineDetails']['patchFaces'])
    if result.get('repairAudit') != audit:
        raise ValueError('Saved repair audit changed')
    destination = Path(report_path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    consumer_path = destination.parent / 'math3d-consumed.json'
    process = subprocess.run([str(node), str(CONSUMER), '--checkout', str(checkout),
                              '--input', str(output), '--result', str(consumer_path)],
                             cwd=ROOT, capture_output=True, text=True, timeout=120)
    if process.returncode != 0:
        raise ValueError('MATH3D importer failed: ' + (process.stderr or process.stdout)[-2000:])
    consumer = json.loads(consumer_path.read_text(encoding='utf-8'))
    if (consumer.get('consumer') != 'MATH3D desktop loadSurfaceMeshFromFile'
            or consumer.get('inputObjSha256') != sha(output)
            or consumer.get('format') != 'obj'
            or consumer.get('points') != after['vertices']
            or consumer.get('triangles') != after['faces']
            or consumer.get('boundaryEdges') != 0 or consumer.get('nonManifoldEdges') != 0
            or consumer.get('closed') is not True or consumer.get('indicesInRange') is not True
            or any(not math.isclose(actual, expected, rel_tol=1e-6, abs_tol=1e-6)
                   for actual, expected in zip(consumer.get('bounds', []),
                                               [value for pair in after['bounds'] for value in pair]))
            or len(consumer.get('bounds', [])) != 6
            or not math.isclose(consumer.get('signedVolume', float('nan')), after['signedVolume'], rel_tol=1e-6, abs_tol=1e-6)
            or not math.isclose(consumer.get('surfaceArea', float('nan')), after['area'], rel_tol=1e-6, abs_tol=1e-6)):
        raise ValueError('MATH3D imported geometry disagrees with the saved repair')
    report = {'schemaVersion': 1, 'kind': 'scientific.cgal-repair-math3d-handoff', 'verdict': 'passed',
              'runId': request['runId'], 'recipeId': recipe, 'requestSha256': sha(directory / 'request.json'),
              'resultSha256': sha(directory / 'results.json'), 'inputSha256': sha(source),
              'outputSha256': sha(output), 'repairAudit': audit,
              'consumerSourceSha256': sha(CONSUMER), 'importerSourceSha256': consumer['importerSourceSha256'],
              'consumerResultSha256': sha(consumer_path), 'consumer': consumer}
    destination.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps({'report': str(destination), 'verdict': 'passed', 'recipeId': recipe}))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-directory', required=True)
    parser.add_argument('--checkout', required=True)
    parser.add_argument('--node', default='node')
    parser.add_argument('--report', required=True)
    args = parser.parse_args()
    verify(args.run_directory, args.checkout, args.node, args.report)
