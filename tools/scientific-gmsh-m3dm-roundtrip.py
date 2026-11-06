"""Independently reload Gmsh's fixed 2D MATH3D document with Python struct."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import struct


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_obj(path):
    points, faces = [], []
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        parts = line.split()
        if parts[:1] == ['v']:
            if len(parts) != 4:
                raise ValueError('Invalid OBJ vertex.')
            points.append(tuple(float(value) for value in parts[1:]))
        elif parts[:1] == ['f']:
            if len(parts) != 4:
                raise ValueError('Invalid OBJ triangle.')
            faces.append(tuple(int(value.split('/')[0]) - 1 for value in parts[1:]))
    return points, faces


def read_m3dm(path):
    data = Path(path).read_bytes()
    if not 32 <= len(data) <= 32 * 1024 * 1024:
        raise ValueError('M3DM size is outside the bounded contract.')
    magic, version, header, points, triangles, positions, indices, total, flags = struct.unpack_from('<4sHHIIIIII', data)
    if (magic != b'M3DM' or version != 1 or header != 32 or flags != 0
            or points != 44 or triangles != 66 or positions != points * 12
            or indices != triangles * 12 or total != len(data)
            or total != 32 + positions + indices):
        raise ValueError('M3DM header, version or lengths changed.')
    vertices = [struct.unpack_from('<fff', data, 32 + 12 * i) for i in range(points)]
    faces = [struct.unpack_from('<III', data, 32 + positions + 12 * i) for i in range(triangles)]
    return vertices, faces


def inspect(points, faces):
    if len(points) != 44 or len(faces) != 66 or any(
            not all(math.isfinite(value) for value in point) for point in points):
        raise ValueError('2D mesh geometry is invalid.')
    edges = Counter()
    area = 0.0
    for face in faces:
        if len(set(face)) != 3 or min(face) < 0 or max(face) >= len(points):
            raise ValueError('Triangle connectivity is invalid.')
        a, b, c = (points[index] for index in face)
        signed = ((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) / 2
        if signed <= 1e-12 or any(abs(point[2]) > 1e-6 for point in (a, b, c)):
            raise ValueError('A triangle is flipped, degenerate or out of plane.')
        area += signed
        for u, v in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
            edges[tuple(sorted((u, v)))] += 1
    bounds = [value for axis in range(3) for value in
              (min(point[axis] for point in points), max(point[axis] for point in points))]
    if (sum(count == 1 for count in edges.values()) != 20
            or any(count > 2 for count in edges.values())
            or any(abs(value - expected) > 1e-6 for value, expected in
                   zip(bounds, (0, 1, 0, 1, 0, 0)))
            or abs(area - 1) > 1e-6):
        raise ValueError('2D boundary, orientation or scale changed.')
    return {'points': len(points), 'triangles': len(faces), 'boundaryEdges': 20,
            'nonManifoldEdges': 0, 'signedAreaXY': area, 'bounds': bounds}


def triangles(points, faces):
    def rounded(index):
        return tuple(round(value, 6) for value in points[index])
    def canonical(face):
        values = tuple(rounded(index) for index in face)
        return min(values, values[1:] + values[:1], values[2:] + values[:2])
    return Counter(canonical(face) for face in faces)


def check(obj, m3dm):
    source_points, source_faces = read_obj(obj)
    saved_points, saved_faces = read_m3dm(m3dm)
    source = inspect(source_points, source_faces)
    saved = inspect(saved_points, saved_faces)
    if triangles(source_points, source_faces) != triangles(saved_points, saved_faces):
        raise ValueError('M3DM changed triangle topology or winding.')
    return {'schemaVersion': 1, 'format': 'M3DM', 'version': 1,
            'sourceObjSha256': sha(obj), 'm3dmSha256': sha(m3dm),
            'parserSourceSha256': sha(__file__), 'geometry': 'passed',
            'topology': 'passed', 'orientation': 'passed', 'scale': 'passed',
            'source': source, 'reloaded': saved, 'verdict': 'passed'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-obj', required=True, type=Path)
    parser.add_argument('--input-m3dm', required=True, type=Path)
    parser.add_argument('--result', required=True, type=Path)
    args = parser.parse_args()
    report = check(args.input_obj, args.input_m3dm)
    args.result.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))
