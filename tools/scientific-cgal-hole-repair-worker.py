"""Managed JSON boundary for the three explicitly scoped CGAL hole repairs."""
import argparse
import json
import math
from pathlib import Path
import subprocess
import sys

from scientific_worker_contract import ScientificContract
from scientific_cgal_mesh_metrics import edge_data, metrics, parse_obj


OPERATIONS = {
    'cgal.fill-one-hole': ('fill-one-hole', 1, 3, 1),
    'cgal.fill-quad-hole': ('fill-quad-hole', 1, 4, 2),
    'cgal.fill-two-quad-holes': ('fill-two-quad-holes', 2, 8, 4),
    'cgal.fill-bounded-holes': ('fill-bounded-holes', None, None, None),
}


def boundary_sizes(path):
    vertices, faces = parse_obj(path)
    counts, _ = edge_data(vertices, faces)
    adjacent = {}
    for (a, b), count in counts.items():
        if count != 1:
            continue
        adjacent.setdefault(a, set()).add(b)
        adjacent.setdefault(b, set()).add(a)
    if any(len(neighbors) != 2 for neighbors in adjacent.values()):
        raise ValueError('Boundary is not a union of simple loops')
    sizes, visited = [], set()
    for start in adjacent:
        if start in visited:
            continue
        current, previous, size = start, None, 0
        while current not in visited:
            visited.add(current)
            size += 1
            next_vertex = next(vertex for vertex in adjacent[current] if vertex != previous)
            previous, current = current, next_vertex
        if current != start:
            raise ValueError('Boundary loops share a vertex')
        sizes.append(size)
    return sorted(sizes)


def check_geometry(before, after, engine, recipe):
    _, loops, edges, patches = OPERATIONS[recipe]
    sizes = before['boundaryLoopEdgeCounts']
    if recipe == 'cgal.fill-bounded-holes':
        if not 1 <= len(sizes) <= 8 or any(not 3 <= size <= 12 for size in sizes) or sum(sizes) > 64:
            raise ValueError('Bounded repair requires 1-8 loops of 3-12 edges, at most 64 total')
        loops, edges, patches = len(sizes), sum(sizes), sum(size - 2 for size in sizes)
    elif (before['boundaryLoops'], before['boundaryEdges']) != (loops, edges):
        raise ValueError('Input does not match the selected boundary-loop scope')
    if before['boundaryLoops'] != len(sizes) or before['boundaryEdges'] != sum(sizes):
        raise ValueError('Boundary-loop measurements disagree')
    if before['components'] != 1 or before['maximumEdgeIncidence'] > 2 or before['degenerateFaces']:
        raise ValueError('Input must be one nondegenerate manifold component')
    if (after['boundaryLoops'] != 0 or after['boundaryEdges'] != 0 or after['components'] != 1
            or after['maximumEdgeIncidence'] != 2 or after['degenerateFaces']
            or after['faces'] != before['faces'] + patches
            or after['vertices'] != before['vertices']
            or not math.isfinite(after['signedVolume']) or after['signedVolume'] <= 0):
        raise ValueError('Repaired OBJ failed independent closure and face-count checks')
    expected_counts = sorted(size - 2 for size in sizes)
    expected = {'beforeFaces': before['faces'], 'afterFaces': after['faces'],
                'boundaryLoopsBefore': loops, 'boundaryEdgesBefore': edges,
                'holesFilled': loops, 'patchFaces': patches}
    if any(engine.get(key) != value for key, value in expected.items()):
        raise ValueError('CGAL repair evidence disagrees with the saved OBJ geometry')
    if sorted(engine.get('patchFaceCounts', [])) != expected_counts:
        raise ValueError('CGAL patch sizes disagree with the input boundary loops')
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
    before['boundaryLoopEdgeCounts'] = boundary_sizes(contract.input)
    operation, loops, edges, _ = OPERATIONS[contract.recipe]
    if loops is not None and (before['boundaryLoops'] != loops or before['boundaryEdges'] != edges):
        raise ValueError('Input does not match the selected boundary-loop scope')
    if loops is None and (not 1 <= len(before['boundaryLoopEdgeCounts']) <= 8
            or any(not 3 <= size <= 12 for size in before['boundaryLoopEdgeCounts'])
            or sum(before['boundaryLoopEdgeCounts']) > 64):
        raise ValueError('Bounded repair requires 1-8 loops of 3-12 edges, at most 64 total')
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
                    scope='One connected triangle manifold; explicit small-hole recipes or bounded 1-8 loops of 3-12 edges each, at most 64 boundary edges; no soup repair',
                    extra={'engine': 'CGAL C++', 'engineDetails': engine,
                           'repairEvidence': {'boundaryLoopsBefore': before['boundaryLoops'], 'boundaryEdgesBefore': before['boundaryEdges'],
                                              'boundaryLoopEdgeCounts': before['boundaryLoopEdgeCounts'],
                                              'holesFilled': engine['holesFilled'], 'patchFaces': engine['patchFaces'],
                                              'outputClosed': True, 'outwardVolume': after['signedVolume']}})
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', required=True)
    parser.add_argument('--worker', required=True)
    args = parser.parse_args()
    sys.exit(run(args.request, args.worker))
