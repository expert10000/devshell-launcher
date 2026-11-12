"""Fail-closed uniform-transform classes for shared, nonmutating mesh inspection."""
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICY = 'schemas/scientific-mesh-inspect-classes.v1.json'
IDS = ('tetra-uniform-4', 'octa-uniform-8', 'cube-uniform-12')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def mesh(path, maximum_bytes=65536):
    path = Path(path).resolve(strict=True)
    if path.suffix.lower() != '.obj' or path.stat().st_size > maximum_bytes:
        raise ValueError('Input class requires a bounded OBJ file.')
    vertices, faces = [], []
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        tokens = line.strip().split()
        if not tokens or tokens[0].startswith('#'):
            continue
        if tokens[0] == 'v' and len(tokens) == 4:
            point = tuple(float(item) for item in tokens[1:])
            if not all(math.isfinite(item) for item in point):
                raise ValueError('Input class rejects nonfinite coordinates.')
            vertices.append(point)
        elif tokens[0] == 'f' and len(tokens) == 4 and all(item.isdecimal() for item in tokens[1:]):
            face = tuple(int(item) - 1 for item in tokens[1:])
            if len(set(face)) != 3 or any(item < 0 or item >= len(vertices) for item in face):
                raise ValueError('Input class rejects invalid triangles.')
            faces.append(face)
        else:
            raise ValueError('Input class permits only vertex and triangular face records.')
    if len(vertices) < 4 or len(faces) < 4:
        raise ValueError('Input class requires a closed triangular surface.')
    return vertices, faces


def _match(vertices, faces, base, value):
    points, base_faces = mesh(base, value['maximumInputBytes'])
    if len(vertices) != len(points) or faces != base_faces:
        return None
    pair = next(((a, axis) for a in range(1, len(points)) for axis in range(3)
                 if abs(points[a][axis] - points[0][axis]) > 1e-9), None)
    if pair is None:
        return None
    a, axis = pair
    scale = (vertices[a][axis] - vertices[0][axis]) / (points[a][axis] - points[0][axis])
    translation = tuple(vertices[0][i] - scale * points[0][i] for i in range(3))
    tolerance = value['coordinateTolerance']
    if (not value['minimumScale'] <= scale <= value['maximumScale']
            or any(abs(item) > value['maximumAbsoluteTranslation'] for item in translation)
            or any(not math.isclose(observed[i], scale * expected[i] + translation[i],
                                     rel_tol=tolerance, abs_tol=tolerance)
                   for observed, expected in zip(vertices, points) for i in range(3))):
        return None
    return {'scale': scale, 'translation': translation, 'points': len(points), 'triangles': len(faces)}


def policy(repo=ROOT):
    repo = Path(repo).resolve(strict=True)
    path = repo / POLICY
    value = json.loads(path.read_text(encoding='utf-8'))
    if (value.get('schemaVersion') != 1 or value.get('kind') != 'scientific.mesh-inspect-input-classes'
            or value.get('operation') != 'mesh.inspect'
            or [item.get('id') for item in value.get('classes', [])] != list(IDS)
            or value.get('minimumScale') != .5 or value.get('maximumScale') != 2
            or value.get('maximumAbsoluteTranslation') != 2
            or value.get('coordinateTolerance') != 1e-6
            or value.get('maximumInputBytes') != 65536):
        raise ValueError('Shared inspection class policy changed.')
    for item in value['classes']:
        base = (repo / item['baseFixture']).resolve(strict=True)
        holdout = (repo / item['holdoutFixture']).resolve(strict=True)
        if (not base.is_relative_to(repo) or not holdout.is_relative_to(repo)
                or sha(base) != item['baseSha256'] or sha(holdout) != item['holdoutSha256']
                or not _match(*mesh(holdout), base, value)):
            raise ValueError('Shared inspection class holdout changed: ' + item['id'])
    for item in value['rejectedFixtures']:
        path = (repo / item['path']).resolve(strict=True)
        if not path.is_relative_to(repo) or sha(path) != item['sha256']:
            raise ValueError('Shared inspection class rejection fixture changed.')
        vertices, faces = mesh(path)
        if any(_match(vertices, faces, repo / entry['baseFixture'], value)
               for entry in value['classes']):
            raise ValueError('Adverse inspection fixture entered a class.')
    return value, sha(repo / POLICY)


def classify(path, repo=ROOT):
    value, policy_hash = policy(repo)
    vertices, faces = mesh(path, value['maximumInputBytes'])
    for item in value['classes']:
        transform = _match(vertices, faces, Path(repo) / item['baseFixture'], value)
        if transform:
            return {'classId': item['id'], 'tier': item['tier'], 'inputSha256': sha(path),
                    'policySha256': policy_hash, **transform}
    raise ValueError('Input is outside the qualified bounded inspection classes.')


def equivalent(source, output, tolerance=1e-6):
    left_points, left_faces = mesh(source)
    right_points, right_faces = mesh(output)
    if len(left_points) != len(right_points) or len(left_faces) != len(right_faces):
        return False

    def oriented(points, faces):
        rounded = [tuple(round(value / tolerance) for value in point) for point in points]
        return sorted(min((rounded[a], rounded[b], rounded[c]),
                          (rounded[b], rounded[c], rounded[a]),
                          (rounded[c], rounded[a], rounded[b])) for a, b, c in faces)

    return oriented(left_points, left_faces) == oriented(right_points, right_faces)
