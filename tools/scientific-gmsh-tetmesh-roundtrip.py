"""Independent M3DT/document reload, without using the MATH3D writer or Gmsh API."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import struct


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure(document_path, resource_path, source_msh):
    document_path, resource_path, source_msh = map(lambda value: Path(value).resolve(strict=True),
                                                   (document_path, resource_path, source_msh))
    document = json.loads(document_path.read_text(encoding='utf-8'))
    resource = document['source']['resource']
    data = resource_path.read_bytes()
    if (document['format'] != 'math3d.tetrahedral-mesh-document'
            or document['schemaVersion'] != 1
            or document['source']['sourceMshSha256'] != sha(source_msh)
            or resource['encoding'] != 'math3d.tetmesh-buffers.v1'
            or resource['sha256'] != sha(resource_path)
            or resource['byteLength'] != len(data)
            or len(data) < 16 or len(data) > 32 * 1024 * 1024):
        raise ValueError('Tetrahedral document identity or resource hash changed.')
    magic, version, count, cell_count = struct.unpack_from('<4sIII', data)
    if (magic, version) != (b'M3DT', 1) or len(data) != 16 + 24 * count + 16 * cell_count:
        raise ValueError('M3DT header or exact length changed.')
    if count != resource['pointCount'] or cell_count != resource['tetrahedronCount']:
        raise ValueError('Document and M3DT resource counts differ.')
    points = list(struct.iter_unpack('<3d', data[16:16+24*count]))
    cells = list(struct.iter_unpack('<4I', data[16+24*count:]))
    if any(not all(math.isfinite(value) for value in point) for point in points):
        raise ValueError('Nonfinite tetrahedral coordinate.')
    faces = Counter()
    volume = 0.0
    for cell in cells:
        if len(set(cell)) != 4 or max(cell) >= count:
            raise ValueError('Invalid tetrahedral cell connectivity.')
        a, b, c, d = (points[index] for index in cell)
        u, v, w = ([other[index] - a[index] for index in range(3)] for other in (b, c, d))
        signed = (u[0]*(v[1]*w[2]-v[2]*w[1]) - u[1]*(v[0]*w[2]-v[2]*w[0])
                  + u[2]*(v[0]*w[1]-v[1]*w[0]))/6
        if signed <= 1e-12:
            raise ValueError('Inverted or degenerate tetrahedron.')
        volume += signed
        for face in ((cell[0],cell[1],cell[2]),(cell[0],cell[1],cell[3]),
                     (cell[0],cell[2],cell[3]),(cell[1],cell[2],cell[3])):
            faces[tuple(sorted(face))] += 1
    if any(number > 2 for number in faces.values()):
        raise ValueError('Nonmanifold tetrahedral face.')
    boundary = [face for face, number in faces.items() if number == 1]
    edges = Counter(tuple(sorted(pair)) for face in boundary
                    for pair in ((face[0],face[1]),(face[1],face[2]),(face[2],face[0])))
    bounds = [value for axis in range(3) for value in
              (min(point[axis] for point in points), max(point[axis] for point in points))]
    if (count < 8 or cell_count < 6 or len(boundary) < 12
            or any(number != 2 for number in edges.values())
            or abs(volume-1) > 1e-6
            or any(abs(value-target) > 1e-6 for value,target in zip(bounds,(0,1,0,1,0,1)))):
        raise ValueError('Fixed cube geometry, topology or scale changed.')
    return {'schemaVersion': 1, 'format': 'M3DT', 'version': 1,
            'documentSha256': sha(document_path), 'resourceSha256': sha(resource_path),
            'sourceMshSha256': sha(source_msh), 'points': count,
            'tetrahedra': cell_count, 'boundaryTriangles': len(boundary),
            'boundaryEdges': sum(number == 1 for number in edges.values()),
            'nonManifoldEdges': sum(number > 2 for number in edges.values()),
            'volume': volume, 'bounds': bounds, 'verdict': 'passed',
            'parserSourceSha256': sha(__file__)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--document', required=True)
    parser.add_argument('--resource', required=True)
    parser.add_argument('--source-msh', required=True)
    parser.add_argument('--result', required=True)
    args = parser.parse_args()
    report = measure(args.document, args.resource, args.source_msh)
    Path(args.result).write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))
