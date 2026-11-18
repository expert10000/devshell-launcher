"""Extract the actual tetrahedral boundary for a typed VTK surface intake."""
import argparse
from collections import Counter
import hashlib
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


def difference(a, b):
    return tuple(a[index] - b[index] for index in range(3))


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def dot(a, b):
    return sum(a[index] * b[index] for index in range(3))


def extract(request_path):
    request_path = Path(request_path).resolve(strict=True)
    if request_path.stat().st_size > 65536:
        raise ValueError('Boundary request exceeds 64 KiB.')
    request = json.loads(request_path.read_text(encoding='utf-8'))
    directory = request_path.parent
    if (request.get('schemaVersion') != 1 or request.get('operation') != 'gmsh.extract-boundary'
            or request.get('workingDirectory') != str(directory)
            or not RUN.fullmatch(request.get('runId', '')) or not RUN.fullmatch(request.get('sourceRunId', ''))
            or not COMMIT.fullmatch(request.get('sourceCommit', ''))
            or not HEX.fullmatch(request.get('sourceSnapshotSha256', ''))
            or request.get('inputId') != 'gmsh-mesh'
            or request.get('lengthUnit') not in ('m', 'mm')
            or not isinstance(request.get('frame'), str) or not request['frame']):
        raise ValueError('Invalid typed boundary request.')
    record = request.get('inputArtifact')
    if not isinstance(record, dict) or not HEX.fullmatch(record.get('sha256', '')):
        raise ValueError('Gmsh MSH hash is missing.')
    root = Path(request.get('artifactRoot', '')).resolve(strict=True)
    source = Path(record.get('path', '')).resolve(strict=True)
    if (not source.is_relative_to(root) or source.suffix.lower() != '.msh' or not source.is_file()
            or source.stat().st_size > 64 * 1024 * 1024 or source.stat().st_size != record.get('bytes')
            or sha(source) != record['sha256']):
        raise ValueError('Gmsh MSH is outside the registered root, too large, or changed.')
    output = directory / 'boundary.obj'
    if output.exists() or (directory / 'results.json').exists():
        raise ValueError('Boundary output already exists.')
    if hasattr(os, 'add_dll_directory'):
        folder = Path(sys.prefix) / 'Library/bin'
        if folder.is_dir():
            _dll_handle = os.add_dll_directory(str(folder))
    import gmsh
    gmsh.initialize()
    try:
        gmsh.option.setNumber('General.Terminal', 0)
        gmsh.open(str(source))
        groups = {(dimension, gmsh.model.getPhysicalName(dimension, tag))
                  for dimension, tag in gmsh.model.getPhysicalGroups()}
        if (2, 'InputBoundary') not in groups or (3, 'BooleanVolume') not in groups:
            raise ValueError('Gmsh physical group dimension or name changed.')
        tags, coordinates, _ = gmsh.model.mesh.getNodes()
        elements, node_tags = gmsh.model.mesh.getElementsByType(4)
    finally:
        gmsh.finalize()
    if (not 4 <= len(tags) <= 500000 or not 1 <= len(elements) <= 500000
            or len(node_tags) != len(elements) * 4):
        raise ValueError('Gmsh tetrahedral count is outside the boundary budget.')
    points = {int(tag): tuple(float(value) for value in coordinates[index * 3:index * 3 + 3])
              for index, tag in enumerate(tags)}
    if any(not all(math.isfinite(value) for value in point) for point in points.values()):
        raise ValueError('Gmsh node coordinate is non-finite.')
    face_uses = {}
    volume = 0.0
    for index in range(0, len(node_tags), 4):
        tet = tuple(int(node_tags[index + offset]) for offset in range(4))
        if len(set(tet)) != 4 or any(tag not in points for tag in tet):
            raise ValueError('Tetrahedral connectivity is invalid.')
        a, b, c, d = (points[tag] for tag in tet)
        determinant = dot(difference(b, a), cross(difference(c, a), difference(d, a)))
        if abs(determinant) <= 1e-14:
            raise ValueError('Gmsh tetrahedron is degenerate.')
        volume += abs(determinant) / 6
        for face, opposite in (((tet[0], tet[1], tet[2]), tet[3]),
                               ((tet[0], tet[1], tet[3]), tet[2]),
                               ((tet[0], tet[2], tet[3]), tet[1]),
                               ((tet[1], tet[2], tet[3]), tet[0])):
            p, q, r = (points[tag] for tag in face)
            if dot(cross(difference(q, p), difference(r, p)), difference(points[opposite], p)) > 0:
                face = (face[0], face[2], face[1])
            face_uses.setdefault(tuple(sorted(face)), []).append(face)
    if any(len(uses) > 2 for uses in face_uses.values()):
        raise ValueError('Tetrahedral mesh has a nonmanifold face.')
    boundary = [uses[0] for uses in face_uses.values() if len(uses) == 1]
    edges = Counter(tuple(sorted((a, b))) for face in boundary
                    for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])))
    if not boundary or len(boundary) > 400000 or any(count != 2 for count in edges.values()):
        raise ValueError('Extracted boundary is empty, open or nonmanifold.')
    shell = sorted({tag for face in boundary for tag in face})
    indices = {tag: index + 1 for index, tag in enumerate(shell)}
    lines = ['# tetrahedral volume boundary for VTK intake']
    lines += ['v ' + ' '.join(format(value, '.17g') for value in points[tag]) for tag in shell]
    lines += ['f ' + ' '.join(str(indices[tag]) for tag in face) for face in boundary]
    with output.open('x', encoding='utf-8') as stream:
        stream.write('\n'.join(lines) + '\n')
    if output.stat().st_size > 32 * 1024 * 1024:
        output.unlink()
        raise ValueError('Boundary OBJ exceeds 32 MiB.')
    result = {'schemaVersion': 1, 'runId': request['runId'], 'operation': 'gmsh.extract-boundary',
              'state': 'succeeded', 'sourceRunId': request['sourceRunId'],
              'sourceCommit': request['sourceCommit'], 'sourceSnapshotSha256': request['sourceSnapshotSha256'],
              'inputHashes': {'gmsh-mesh': record['sha256']}, 'outputHashes': {'gmsh-boundary': sha(output)},
              'lengthUnit': request['lengthUnit'], 'frame': request['frame'], 'dimension': 2,
              'derivedFromDimension': 3, 'points': len(shell), 'triangles': len(boundary),
              'tetrahedra': len(elements), 'tetrahedralVolume': volume,
              'boundaryEdges': 0, 'nonManifoldEdges': 0,
              'output': {'path': 'boundary.obj', 'bytes': output.stat().st_size, 'sha256': sha(output)}}
    with (directory / 'results.json').open('x', encoding='utf-8') as stream:
        json.dump(result, stream, allow_nan=False, sort_keys=True)
        stream.write('\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', required=True)
    arguments = parser.parse_args()
    print(json.dumps(extract(arguments.request), allow_nan=False, sort_keys=True))
