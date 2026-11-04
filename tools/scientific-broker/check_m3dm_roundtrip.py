"""Independent M3DM reload and mesh invariant check for the fixed CGAL pilot."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import struct


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_obj(path):
    vertices, faces = [], []
    for line in path.read_text(encoding='utf-8').splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == 'v':
            if len(parts) != 4:
                raise ValueError('Invalid OBJ vertex.')
            vertices.append(tuple(float(value) for value in parts[1:]))
        elif parts[0] == 'f':
            if len(parts) != 4:
                raise ValueError('Only OBJ triangles are qualified.')
            faces.append(tuple(int(value.split('/')[0]) - 1 for value in parts[1:]))
    return vertices, faces


def read_m3dm(path):
    data = path.read_bytes()
    if len(data) < 32 or len(data) > 32 * 1024 * 1024:
        raise ValueError('M3DM size is outside the qualified range.')
    magic, version, header, points, triangles, position_bytes, index_bytes, total, flags = struct.unpack_from('<4sHHIIIIII', data)
    if (magic != b'M3DM' or version != 1 or header != 32 or flags != 0
            or points != 4 or triangles != 4 or position_bytes != points * 12
            or index_bytes != triangles * 12 or total != len(data)
            or total != 32 + position_bytes + index_bytes):
        raise ValueError('M3DM header, version or byte lengths differ from the qualified contract.')
    vertices = [struct.unpack_from('<fff', data, 32 + index * 12) for index in range(points)]
    face_offset = 32 + position_bytes
    faces = [struct.unpack_from('<III', data, face_offset + index * 12) for index in range(triangles)]
    return vertices, faces


def cross(left, right):
    return (left[1] * right[2] - left[2] * right[1],
            left[2] * right[0] - left[0] * right[2],
            left[0] * right[1] - left[1] * right[0])


def metrics(vertices, faces):
    if len(vertices) != 4 or len(faces) != 4 or any(len(vertex) != 3 or
            any(not math.isfinite(value) for value in vertex) for vertex in vertices):
        raise ValueError('Mesh has non-finite or unexpected geometry.')
    edges = Counter()
    signed_volume = 0.0
    for face in faces:
        if len(set(face)) != 3 or any(index < 0 or index >= len(vertices) for index in face):
            raise ValueError('Mesh has an invalid triangle.')
        a, b, c = (vertices[index] for index in face)
        ab = tuple(b[i] - a[i] for i in range(3))
        ac = tuple(c[i] - a[i] for i in range(3))
        normal = cross(ab, ac)
        if math.sqrt(sum(value * value for value in normal)) <= 1e-9:
            raise ValueError('Mesh has a degenerate triangle.')
        signed_volume += sum(a[i] * cross(b, c)[i] for i in range(3)) / 6.0
        for start, end in zip(face, face[1:] + face[:1]):
            edges[(start, end)] += 1
    for start, end in edges:
        if edges[(start, end)] != 1 or edges[(end, start)] != 1:
            raise ValueError('Mesh is open, non-manifold or inconsistently oriented.')
    bounds = [value for axis in range(3) for value in
              (min(vertex[axis] for vertex in vertices), max(vertex[axis] for vertex in vertices))]
    return {'points': len(vertices), 'triangles': len(faces), 'closed': True,
            'oriented': True, 'signedVolume': signed_volume, 'bounds': bounds,
            'extents': [bounds[axis * 2 + 1] - bounds[axis * 2] for axis in range(3)]}


def check(obj_path, m3dm_path, writer_path):
    writer = json.loads(writer_path.read_text(encoding='utf-8'))
    if (writer.get('schemaVersion') != 1 or writer.get('format') != 'M3DM'
            or writer.get('version') != 1 or writer.get('math3dReload') != 'passed'
            or writer.get('sourceArtifactSha256') != sha(obj_path)
            or writer.get('m3dmSha256') != sha(m3dm_path)):
        raise ValueError('M3DM writer evidence or artifact hash changed.')
    source_vertices, source_faces = read_obj(obj_path)
    saved_vertices, saved_faces = read_m3dm(m3dm_path)
    source = metrics(source_vertices, source_faces)
    saved = metrics(saved_vertices, saved_faces)
    if saved_faces != source_faces:
        raise ValueError('M3DM triangle topology or winding changed.')
    maximum_delta = max(abs(left - right) for a, b in zip(source_vertices, saved_vertices)
                        for left, right in zip(a, b))
    if maximum_delta > 1e-6:
        raise ValueError('M3DM geometry moved outside float32 tolerance.')
    if (source['signedVolume'] <= 0 or abs(source['signedVolume'] - 8 / 3) > 1e-6
            or abs(saved['signedVolume'] - source['signedVolume']) > 1e-6
            or any(abs(value - expected) > 1e-6 for value, expected in
                   zip(saved['bounds'], (-1, 1, -1, 1, -1, 1)))):
        raise ValueError('M3DM orientation, volume or scale changed.')
    return {'schemaVersion': 1, 'sourceJobId': writer['sourceJobId'], 'promotionId': writer['promotionId'],
            'sourceArtifactSha256': sha(obj_path), 'm3dmSha256': sha(m3dm_path),
            'writerReportSha256': sha(writer_path), 'independentParser': 'python-struct-v1',
            'parserSourceSha256': sha(Path(__file__)),
            'maxCoordinateDelta': maximum_delta, 'geometry': 'passed', 'topology': 'passed',
            'orientation': 'passed', 'scale': 'passed', 'source': source, 'reloaded': saved,
            'verdict': 'passed'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--obj', type=Path, required=True)
    parser.add_argument('--m3dm', type=Path, required=True)
    parser.add_argument('--writer', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = check(args.obj, args.m3dm, args.writer)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, separators=(',', ':')), encoding='utf-8')
    print(json.dumps({'verdict': result['verdict'], 'sourceJobId': result['sourceJobId'],
                      'm3dmSha256': result['m3dmSha256']}))


if __name__ == '__main__':
    main()
