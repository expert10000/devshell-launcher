"""Bounded fixed-square Gmsh surface worker using the shared typed result contract."""
import argparse
import math
import os
from pathlib import Path
import sys

from scientific_worker_contract import ScientificContract, fingerprint

parser = argparse.ArgumentParser()
parser.add_argument('--request', required=True)
args = parser.parse_args()
contract = ScientificContract(args.request, 'gmsh-win-conda', ('gmsh.mesh2d',))
fixture = Path(__file__).resolve().parents[1] / 'scientific' / 'fixtures' / 'gmsh' / 'square.geo'
if contract.input.suffix.lower() != '.geo' or fingerprint(contract.input) != fingerprint(fixture):
    raise ValueError('Only the registered fixed square GEO fixture is accepted.')
parameters = contract.request.get('parameters', {})
if not isinstance(parameters, dict) or set(parameters) - {'meshSize'}:
    raise ValueError('Only meshSize is supported for the fixed Gmsh recipe.')
size = parameters.get('meshSize', 0.2)
if isinstance(size, bool) or not isinstance(size, (int, float)) or not math.isfinite(size) or not 0.05 <= size <= 0.5:
    raise ValueError('meshSize must be finite and between 0.05 and 0.5.')
handles = []
if hasattr(os, 'add_dll_directory'):
    folder = Path(sys.prefix) / 'Library' / 'bin'
    if folder.is_dir():
        handles.append(os.add_dll_directory(str(folder)))
import gmsh

contract.versions = {'gmsh': gmsh.__version__}
gmsh.initialize()
try:
    gmsh.option.setNumber('General.Terminal', 0)
    gmsh.open(str(contract.input))
    gmsh.option.setNumber('Mesh.MeshSizeMin', size)
    gmsh.option.setNumber('Mesh.MeshSizeMax', size)
    gmsh.model.mesh.generate(2)
    node_tags, coordinates, _ = gmsh.model.mesh.getNodes()
    types, element_groups, _ = gmsh.model.mesh.getElements(2)
    triangles = sum(len(tags) for kind, tags in zip(types, element_groups) if kind == 2)
    if len(node_tags) < 4 or triangles < 2 or not all(math.isfinite(value) for value in coordinates):
        raise ValueError('Gmsh produced an empty or non-finite surface mesh.')
    bounds = [min(coordinates[index::3]) for index in range(3)] + [max(coordinates[index::3]) for index in range(3)]
    if any(abs(value - expected) > 1e-9 for value, expected in zip(bounds, (0, 0, 0, 1, 1, 0))):
        raise ValueError('Generated surface bounds differ from the fixed square.')
    gmsh.write(str(contract.output))
    contract.finish(before={'vertices': 4, 'faces': 1},
                    after={'vertices': len(node_tags), 'faces': triangles},
                    capabilities=['mesh.generate'],
                    scope='Fixed public unit square, 2D triangles only; no volume-mesh or MATH3D qualification.',
                    extra={'meshSize': size, 'bounds': bounds, 'elementTypes': [int(kind) for kind in types]})
finally:
    gmsh.finalize()
