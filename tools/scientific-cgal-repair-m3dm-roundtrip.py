"""Independently parse and compare a saved CGAL repair M3DM resource."""
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
    vertices, faces = [], []
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        fields = line.split()
        if not fields or fields[0] == '#':
            continue
        if fields[0] == 'v' and len(fields) == 4:
            vertices.append(tuple(float(value) for value in fields[1:]))
        elif fields[0] == 'f' and len(fields) == 4:
            faces.append(tuple(int(value.split('/')[0]) - 1 for value in fields[1:]))
        else:
            raise ValueError('Saved OBJ has an unsupported directive')
    return vertices, faces


def read_m3dm(path):
    data = Path(path).read_bytes()
    if not 32 <= len(data) <= 32 * 1024 * 1024:
        raise ValueError('M3DM is outside the resource budget')
    magic, version, header, points, triangles, positions, indices, total, flags = struct.unpack_from('<4sHHIIIIII', data)
    if (magic != b'M3DM' or version != 1 or header != 32 or flags != 0
            or not 3 <= points <= 200000 or not 1 <= triangles <= 200000
            or positions != points * 12 or indices != triangles * 12
            or total != len(data) or total != 32 + positions + indices):
        raise ValueError('M3DM header or lengths changed')
    vertices = [struct.unpack_from('<fff', data, 32 + 12 * i) for i in range(points)]
    faces = [struct.unpack_from('<III', data, 32 + positions + 12 * i) for i in range(triangles)]
    return vertices, faces


def inspect(vertices, faces):
    if not vertices or not faces or any(not all(math.isfinite(value) for value in point) for point in vertices):
        raise ValueError('Mesh coordinates are empty or non-finite')
    edges, area, volume = Counter(), 0.0, 0.0
    for face in faces:
        if len(set(face)) != 3 or min(face) < 0 or max(face) >= len(vertices):
            raise ValueError('Triangle connectivity changed')
        a, b, c = (vertices[index] for index in face)
        u = tuple(b[i] - a[i] for i in range(3))
        v = tuple(c[i] - a[i] for i in range(3))
        cross = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        twice_area = math.sqrt(sum(value * value for value in cross))
        if twice_area <= 1e-12:
            raise ValueError('M3DM contains a degenerate triangle')
        area += twice_area / 2
        volume += sum(a[i] * cross[i] for i in range(3)) / 6
        for i in range(3):
            edges[tuple(sorted((face[i], face[(i + 1) % 3])))] += 1
    if any(count != 2 for count in edges.values()) or volume <= 0:
        raise ValueError('M3DM is open, non-manifold or inward')
    return {'points': len(vertices), 'triangles': len(faces), 'boundaryEdges': 0,
            'surfaceArea': area, 'signedVolume': volume,
            'bounds': [value for axis in range(3) for value in
                       (min(point[axis] for point in vertices), max(point[axis] for point in vertices))]}


def oriented_faces(vertices, faces):
    def rounded(index):
        return tuple(round(value, 5) for value in vertices[index])
    def canonical(face):
        corners = tuple(rounded(index) for index in face)
        return min(corners, corners[1:] + corners[:1], corners[2:] + corners[:2])
    return Counter(canonical(face) for face in faces)


def verify(run_directory, handoff_path, product_directory, report_path):
    run, handoff_path, product = (Path(path).resolve(strict=True)
                                  for path in (run_directory, handoff_path, product_directory))
    request = json.loads((run / 'request.json').read_text(encoding='utf-8-sig'))
    result = json.loads((run / 'results.json').read_text(encoding='utf-8-sig'))
    handoff = json.loads(handoff_path.read_text(encoding='utf-8-sig'))
    record = json.loads((product / 'product.json').read_text(encoding='utf-8-sig'))
    source = (run / request['outputArtifacts'][0]['path']).resolve(strict=True)
    m3dm = product / 'repaired.m3dm'
    document = product / 'repair-mesh-document.json'
    resource = product / 'repair-mesh-resource.bin'
    if (source.parent != run or record.get('verdict') != 'passed'
            or record.get('runId') != result.get('runId') or handoff.get('runId') != result.get('runId')
            or record.get('sourceObjSha256') != sha(source)
            or record.get('sourceResultSha256') != sha(run / 'results.json')
            or record.get('handoffSha256') != sha(handoff_path)
            or record.get('documentSha256') != sha(document)
            or record.get('resourceSha256') != sha(resource)
            or record.get('m3dmSha256') != sha(m3dm)):
        raise ValueError('Saved MATH3D product identity changed')
    source_points, source_faces = read_obj(source)
    saved_points, saved_faces = read_m3dm(m3dm)
    source_metrics, saved_metrics = inspect(source_points, source_faces), inspect(saved_points, saved_faces)
    if (oriented_faces(source_points, source_faces) != oriented_faces(saved_points, saved_faces)
            or source_metrics['points'] != saved_metrics['points']
            or source_metrics['triangles'] != saved_metrics['triangles']
            or record['points'] != saved_metrics['points'] or record['triangles'] != saved_metrics['triangles']
            or any(not math.isclose(a, b, rel_tol=1e-5, abs_tol=1e-5)
                   for a, b in zip(source_metrics['bounds'], saved_metrics['bounds']))
            or not math.isclose(source_metrics['surfaceArea'], saved_metrics['surfaceArea'], rel_tol=1e-5, abs_tol=1e-5)
            or not math.isclose(source_metrics['signedVolume'], saved_metrics['signedVolume'], rel_tol=1e-5, abs_tol=1e-5)):
        raise ValueError('Saved M3DM geometry, winding or scale differs from repaired OBJ')
    report = {'schemaVersion': 1, 'kind': 'scientific.cgal-repair-m3dm-roundtrip', 'verdict': 'passed',
              'runId': result['runId'], 'sourceObjSha256': sha(source), 'm3dmSha256': sha(m3dm),
              'productSha256': sha(product / 'product.json'), 'parserSourceSha256': sha(__file__),
              'source': source_metrics, 'reloaded': saved_metrics}
    Path(report_path).write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'verdict': 'passed', 'report': str(Path(report_path).resolve())}))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-directory', required=True)
    parser.add_argument('--handoff', required=True)
    parser.add_argument('--product-directory', required=True)
    parser.add_argument('--report', required=True)
    args = parser.parse_args()
    verify(args.run_directory, args.handoff, args.product_directory, args.report)
