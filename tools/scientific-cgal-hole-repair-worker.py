"""Managed JSON boundary for the three explicitly scoped CGAL hole repairs."""
import argparse
import json
import math
from pathlib import Path
import subprocess
import sys

from scientific_worker_contract import ScientificContract
from scientific_cgal_mesh_metrics import metrics


OPERATIONS = {
    'cgal.fill-one-hole': ('fill-one-hole', 1, 3, 1),
    'cgal.fill-quad-hole': ('fill-quad-hole', 1, 4, 2),
    'cgal.fill-two-quad-holes': ('fill-two-quad-holes', 2, 8, 4),
}


def check_geometry(before, after, engine, recipe):
    _, loops, edges, patches = OPERATIONS[recipe]
    if (before['boundaryLoops'], before['boundaryEdges']) != (loops, edges):
        raise ValueError('Input does not match the selected boundary-loop scope')
    if before['components'] != 1 or before['maximumEdgeIncidence'] > 2 or before['degenerateFaces']:
        raise ValueError('Input must be one nondegenerate manifold component')
    if (after['boundaryLoops'] != 0 or after['boundaryEdges'] != 0 or after['components'] != 1
            or after['maximumEdgeIncidence'] != 2 or after['degenerateFaces']
            or after['faces'] != before['faces'] + patches
            or after['vertices'] != before['vertices']
            or not math.isfinite(after['signedVolume']) or after['signedVolume'] <= 0):
        raise ValueError('Repaired OBJ failed independent closure and face-count checks')
    expected_counts = [patches // loops] * loops
    expected = {'beforeFaces': before['faces'], 'afterFaces': after['faces'],
                'boundaryLoopsBefore': loops, 'boundaryEdgesBefore': edges,
                'holesFilled': loops, 'patchFaces': patches, 'patchFaceCounts': expected_counts}
    if any(engine.get(key) != value for key, value in expected.items()):
        raise ValueError('CGAL repair evidence disagrees with the saved OBJ geometry')
    volume = engine.get('signedVolumeAfter')
    if not isinstance(volume, (int, float)) or not math.isclose(volume, after['signedVolume'], rel_tol=1e-7, abs_tol=1e-9):
        raise ValueError('CGAL repair volume disagrees with the saved OBJ geometry')


def run(request, worker):
    contract = ScientificContract(request, 'cgal-win-conda', OPERATIONS)
    worker = Path(worker).resolve(strict=True)
    if worker.name.lower() != 'devshell_cgal_hole_repair.exe':
        raise ValueError('Only the registered CGAL hole-repair worker is allowed')
    if contract.input.suffix.lower() != '.obj':
        raise ValueError('Hole repair requires a registered OBJ input')
    if contract.request.get('parameters') != {'inputId': contract.input_record.get('datasetId'),
                                             'outputName': contract.output_name}:
        raise ValueError('Repair parameters must match the registered input and output')
    timeout = contract.request.get('timeoutSeconds', 120)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 1 <= timeout <= 120:
        raise ValueError('Invalid repair timeout')
    before = metrics(contract.input)
    operation, loops, edges, _ = OPERATIONS[contract.recipe]
    if before['boundaryLoops'] != loops or before['boundaryEdges'] != edges:
        raise ValueError('Input does not match the selected boundary-loop scope')
    process = subprocess.run([str(worker), operation, str(contract.input), str(contract.output)],
                             cwd=contract.directory, timeout=timeout, capture_output=True,
                             text=True, encoding='utf-8', errors='replace',
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if process.stdout:
        print(process.stdout, end='', flush=True)
    if process.stderr:
        print(process.stderr, end='', file=sys.stderr, flush=True)
    result_file = contract.directory / 'results.json'
    engine = json.loads(result_file.read_text(encoding='utf-8-sig')) if result_file.is_file() else {}
    contract.versions = engine.get('versions', {})
    try:
        if process.returncode != 0:
            raise ValueError(engine.get('error') or f'CGAL repair worker exited {process.returncode}')
        if engine.get('recipeId') != contract.recipe or engine.get('state') != 'succeeded' or engine.get('exitCode') != 0:
            raise ValueError('CGAL repair result did not match the request')
        if not contract.output.is_file():
            raise ValueError('CGAL repair did not write an OBJ artifact')
        after = metrics(contract.output)
        check_geometry(before, after, engine, contract.recipe)
    except Exception as error:
        contract.output.unlink(missing_ok=True)
        contract.finish(state='failed', exit_code=process.returncode or 1, before=before,
                        diagnostics=[{'severity': 'error', 'message': str(error)}],
                        extra={'engine': 'CGAL C++', 'engineDetails': engine})
        return process.returncode or 1
    contract.finish(before=before, after=after,
                    capabilities=['mesh.read', 'mesh.write', 'mesh.validate', 'mesh.repair'],
                    scope='One connected triangle manifold with the explicitly selected three-edge, four-edge, or two four-edge boundary loops; no general repair',
                    extra={'engine': 'CGAL C++', 'engineDetails': engine,
                           'repairEvidence': {'boundaryLoopsBefore': loops, 'boundaryEdgesBefore': edges,
                                              'holesFilled': loops, 'patchFaces': engine['patchFaces'],
                                              'outputClosed': True, 'outwardVolume': after['signedVolume']}})
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', required=True)
    parser.add_argument('--worker', required=True)
    args = parser.parse_args()
    sys.exit(run(args.request, args.worker))
