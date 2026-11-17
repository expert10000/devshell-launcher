"""Candidate closed-Boolean-OBJ to tetrahedral Gmsh volume bridge."""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sys


HEX = re.compile(r'^[0-9a-f]{64}$')
RUN = re.compile(r'^[0-9a-f]{32}$')
COMMIT = re.compile(r'^[0-9a-f]{40}$')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_surface(path):
    source = Path(__file__).with_name('scientific-artifact-roundtrip.py')
    spec = importlib.util.spec_from_file_location('scientific_artifact_roundtrip', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.inspect(path)


def mesh(request_path):
    request_path = Path(request_path).resolve(strict=True)
    if request_path.stat().st_size > 65536:
        raise ValueError('Gmsh request exceeds 64 KiB.')
    request = json.loads(request_path.read_text(encoding='utf-8'))
    directory = request_path.parent
    if (request.get('schemaVersion') != 1 or request.get('operation') != 'gmsh.mesh'
            or request.get('workingDirectory') != str(directory)
            or not RUN.fullmatch(request.get('runId', ''))
            or not RUN.fullmatch(request.get('sourceRunId', ''))
            or not COMMIT.fullmatch(request.get('sourceCommit', ''))
            or not HEX.fullmatch(request.get('sourceSnapshotSha256', ''))
            or request.get('inputId') != 'boolean-surface'
            or request.get('lengthUnit') not in ('m', 'mm')
            or not isinstance(request.get('frame'), str) or not request['frame']):
        raise ValueError('Invalid typed Gmsh request.')
    mesh_size = request.get('meshSize')
    if isinstance(mesh_size, bool) or not isinstance(mesh_size, (float, int)) or not math.isfinite(mesh_size) or not 0.01 <= mesh_size <= 2:
        raise ValueError('meshSize must be finite and between 0.01 and 2 input units.')
    record = request.get('inputArtifact')
    if not isinstance(record, dict) or not HEX.fullmatch(record.get('sha256', '')):
        raise ValueError('Boolean surface hash is missing.')
    root = Path(request.get('artifactRoot', '')).resolve(strict=True)
    source = Path(record.get('path', '')).resolve(strict=True)
    if (not source.is_relative_to(root) or source.suffix.lower() != '.obj' or not source.is_file()
            or source.stat().st_size > 32 * 1024 * 1024
            or source.stat().st_size != record.get('bytes') or sha(source) != record['sha256']):
        raise ValueError('Boolean surface is outside the registered root, too large, or changed.')
    summary, points, faces = read_surface(source)
    if (not summary['closed'] or summary['nonManifoldEdges'] or summary['boundaryEdges']
            or summary['signedVolume'] <= 0 or len(points) > 20000 or len(faces) > 40000):
        raise ValueError('Gmsh intake requires a bounded outward closed manifold surface.')
    if (directory / 'volume.msh').exists() or (directory / 'results.json').exists():
        raise ValueError('Gmsh output already exists.')
    if hasattr(os, 'add_dll_directory'):
        folder = Path(sys.prefix) / 'Library/bin'
        if folder.is_dir():
            _dll_handle = os.add_dll_directory(str(folder))
    import gmsh
    gmsh.initialize()
    try:
        gmsh.option.setNumber('General.Terminal', 0)
        gmsh.option.setNumber('Mesh.RandomFactor', 0)
        gmsh.option.setNumber('Mesh.MeshSizeMin', mesh_size)
        gmsh.option.setNumber('Mesh.MeshSizeMax', mesh_size)
        gmsh.option.setNumber('Mesh.MshFileVersion', 4.1)
        gmsh.option.setNumber('Mesh.Binary', 0)
        gmsh.model.add('BooleanSurfaceVolume')
        gmsh.model.addDiscreteEntity(2, 1)
        gmsh.model.mesh.addNodes(2, 1, list(range(1, len(points) + 1)), [value for point in points for value in point])
        gmsh.model.mesh.addElementsByType(1, 2, list(range(1, len(faces) + 1)),
                                          [index + 1 for face in faces for index in face])
        gmsh.model.mesh.classifySurfaces(math.pi / 4, True, True, math.pi / 4)
        gmsh.model.mesh.createGeometry()
        surfaces = [tag for dimension, tag in gmsh.model.getEntities(2) if dimension == 2]
        if not surfaces:
            raise ValueError('Gmsh could not classify the Boolean boundary.')
        loop = gmsh.model.geo.addSurfaceLoop(surfaces)
        volume = gmsh.model.geo.addVolume([loop])
        gmsh.model.geo.synchronize()
        gmsh.model.addPhysicalGroup(2, surfaces, tag=2, name='InputBoundary')
        gmsh.model.addPhysicalGroup(3, [volume], tag=1, name='BooleanVolume')
        gmsh.model.mesh.generate(3)
        node_tags, coordinates, _ = gmsh.model.mesh.getNodes()
        tetra_tags, tetra_nodes = gmsh.model.mesh.getElementsByType(4)
        if len(node_tags) < 4 or len(tetra_tags) < 1 or len(tetra_tags) > 500000:
            raise ValueError('Gmsh produced no bounded tetrahedral volume.')
        coords = {int(tag): tuple(float(value) for value in coordinates[index * 3:index * 3 + 3])
                  for index, tag in enumerate(node_tags)}
        volume_sum = 0.0
        for index in range(0, len(tetra_nodes), 4):
            a, b, c, d = (coords[int(tetra_nodes[index + offset])] for offset in range(4))
            u = [b[axis] - a[axis] for axis in range(3)]
            v = [c[axis] - a[axis] for axis in range(3)]
            w = [d[axis] - a[axis] for axis in range(3)]
            determinant = u[0] * (v[1] * w[2] - v[2] * w[1]) - u[1] * (v[0] * w[2] - v[2] * w[0]) + u[2] * (v[0] * w[1] - v[1] * w[0])
            volume_sum += abs(determinant) / 6
        if not math.isfinite(volume_sum) or abs(volume_sum - summary['signedVolume']) > max(1e-6, summary['signedVolume'] * 0.02):
            raise ValueError('Gmsh tetrahedral volume differs from the Boolean boundary.')
        output = directory / 'volume.msh'
        gmsh.write(str(output))
        if output.stat().st_size > 64 * 1024 * 1024:
            output.unlink()
            raise ValueError('Gmsh output exceeds 64 MiB.')
        result = {'schemaVersion': 1, 'runId': request['runId'], 'operation': 'gmsh.mesh',
                  'state': 'succeeded', 'sourceRunId': request['sourceRunId'],
                  'sourceCommit': request['sourceCommit'], 'sourceSnapshotSha256': request['sourceSnapshotSha256'],
                  'inputHashes': {'boolean-surface': record['sha256']},
                  'outputHashes': {'gmsh-mesh': sha(output)}, 'lengthUnit': request['lengthUnit'],
                  'frame': request['frame'], 'dimension': 3, 'cellType': 'tetrahedron4',
                  'nodes': len(node_tags), 'tetrahedra': len(tetra_tags),
                  'boundaryVolume': summary['signedVolume'], 'tetrahedralVolume': volume_sum,
                  'physicalGroups': {'InputBoundary': {'dimension': 2, 'tag': 2},
                                     'BooleanVolume': {'dimension': 3, 'tag': 1}},
                  'gmshVersion': gmsh.__version__, 'output': {'path': 'volume.msh',
                  'bytes': output.stat().st_size, 'sha256': sha(output)}}
        with (directory / 'results.json').open('x', encoding='utf-8') as stream:
            json.dump(result, stream, allow_nan=False, sort_keys=True)
            stream.write('\n')
        return result
    finally:
        gmsh.finalize()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', required=True)
    arguments = parser.parse_args()
    print(json.dumps(mesh(arguments.request), allow_nan=False, sort_keys=True))
