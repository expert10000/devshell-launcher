"""Typed candidate worker for one public unit-cube tetrahedral fixture."""
import argparse
import math
import os
from pathlib import Path
import sys

from scientific_worker_contract import ScientificContract, fingerprint


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', required=True)
    args = parser.parse_args()
    contract = ScientificContract(args.request, 'gmsh-win-conda', ('gmsh.volume3d.cube',))
    fixture = Path(__file__).resolve().parents[1] / 'scientific/fixtures/gmsh/cube.geo'
    if contract.input.suffix.lower() != '.geo' or fingerprint(contract.input) != fingerprint(fixture):
        raise ValueError('Only the registered unit-cube GEO fixture is accepted.')
    parameters = contract.request.get('parameters', {})
    if not isinstance(parameters, dict) or set(parameters) - {'meshSize'}:
        raise ValueError('Only meshSize is supported for the cube recipe.')
    size = parameters.get('meshSize', 0.35)
    if isinstance(size, bool) or not isinstance(size, (int, float)) or not math.isfinite(size) or not 0.15 <= size <= 0.5:
        raise ValueError('meshSize must be finite and between 0.15 and 0.5.')
    if hasattr(os, 'add_dll_directory'):
        folder = Path(sys.prefix) / 'Library/bin'
        if folder.is_dir():
            _dll_handle = os.add_dll_directory(str(folder))
    import gmsh
    contract.versions = {'gmsh': gmsh.__version__}
    gmsh.initialize()
    try:
        gmsh.option.setNumber('General.Terminal', 0)
        gmsh.option.setNumber('Mesh.RandomFactor', 0)
        gmsh.open(str(contract.input))
        gmsh.option.setNumber('Mesh.MeshSizeMin', size)
        gmsh.option.setNumber('Mesh.MeshSizeMax', size)
        gmsh.model.mesh.generate(3)
        tags, coordinates, _ = gmsh.model.mesh.getNodes()
        kinds, groups, nodes = gmsh.model.mesh.getElements(3)
        tetrahedra = sum(len(group) for kind, group in zip(kinds, groups) if int(kind) == 4)
        if len(tags) < 8 or tetrahedra < 6 or any(not math.isfinite(value) for value in coordinates):
            raise ValueError('Gmsh produced an empty or non-finite tetrahedral volume.')
        if any(int(kind) != 4 for kind in kinds):
            raise ValueError('The bounded volume worker accepts tetrahedra only.')
        bounds = [value for axis in range(3) for value in
                  (min(coordinates[axis::3]), max(coordinates[axis::3]))]
        if any(abs(value - expected) > 1e-8 for value, expected in zip(bounds, (0, 1, 0, 1, 0, 1))):
            raise ValueError('Generated volume bounds differ from the unit cube.')
        gmsh.write(str(contract.output))
        contract.finish(before={'vertices': 8, 'tetrahedra': 0},
                        after={'vertices': len(tags), 'tetrahedra': tetrahedra},
                        capabilities=['mesh.generate3d'],
                        scope='Candidate public unit cube tetrahedra only; no volume release certification.',
                        extra={'meshSize': size, 'bounds': bounds, 'elementTypes': [int(kind) for kind in kinds]})
    finally:
        gmsh.finalize()


if __name__ == '__main__':
    main()
