"""Fail-closed tiny-transform and bounded closed-mesh inspection classes."""
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICY = 'schemas/scientific-mesh-inspect-classes.v2.json'
IDS = ('tetra-uniform-4', 'octa-uniform-8', 'cube-uniform-12',
       'star-closed-64-128', 'star-closed-256-512', 'star-closed-1024-2048')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def mesh(path, maximum_bytes=131072):
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


def _star_closed(vertices, faces, item, value):
    if not item['minimumTriangles'] <= len(faces) <= item['maximumTriangles']:
        return None
    if len(vertices) != len(faces) // 2 + 2 or len(faces) % 2:
        return None  # A connected closed orientable genus-zero surface has V = F/2 + 2.
    bounds = value['starBounds']
    if (any(abs(axis) > bounds['maximumAbsoluteCoordinate'] for point in vertices for axis in point)
            or len({tuple(round(axis, 7) for axis in point) for point in vertices}) != len(vertices)):
        return None
    center = tuple(sum(point[axis] for point in vertices) / len(vertices) for axis in range(3))
    if any(abs(axis) > bounds['maximumAbsoluteCenter'] for axis in center):
        return None
    radii = [math.dist(point, center) for point in vertices]
    if min(radii) < bounds['minimumRadius'] or max(radii) > bounds['maximumRadius']:
        return None
    edges, neighbors, used, volume = {}, [set() for _ in vertices], set(), 0.0
    for a, b, c in faces:
        used.update((a, b, c))
        for start, end in ((a, b), (b, c), (c, a)):
            key = tuple(sorted((start, end)))
            edges.setdefault(key, []).append((start, end))
            neighbors[start].add(end)
            neighbors[end].add(start)
        va, vb, vc = vertices[a], vertices[b], vertices[c]
        ab = tuple(vb[axis] - va[axis] for axis in range(3))
        ac = tuple(vc[axis] - va[axis] for axis in range(3))
        normal = (ab[1] * ac[2] - ab[2] * ac[1],
                  ab[2] * ac[0] - ab[0] * ac[2],
                  ab[0] * ac[1] - ab[1] * ac[0])
        area = math.sqrt(sum(axis * axis for axis in normal)) / 2
        outward = sum(normal[axis] * ((va[axis] + vb[axis] + vc[axis]) / 3 - center[axis])
                      for axis in range(3))
        if area < bounds['minimumFaceArea'] or outward <= 0:
            return None
        volume += sum(va[axis] * normal[axis] for axis in range(3)) / 6
    if len(used) != len(vertices) or len(vertices) - len(edges) + len(faces) != 2:
        return None
    if any(len(incidents) != 2 or incidents[0] != tuple(reversed(incidents[1]))
           for incidents in edges.values()):
        return None
    reached, pending = {0}, [0]
    while pending:
        for neighbor in neighbors[pending.pop()]:
            if neighbor not in reached:
                reached.add(neighbor)
                pending.append(neighbor)
    if len(reached) != len(vertices) or volume < bounds['minimumVolume']:
        return None
    return {'points': len(vertices), 'triangles': len(faces), 'center': center,
            'radiusRange': [min(radii), max(radii)], 'signedVolume': volume}


def _matches(vertices, faces, item, repo, value):
    if item['mode'] == 'uniform':
        return _match(vertices, faces, repo / item['baseFixture'], value)
    if item['mode'] == 'star-closed':
        return _star_closed(vertices, faces, item, value)
    raise ValueError('Unsupported inspection class mode.')


def policy(repo=ROOT):
    repo = Path(repo).resolve(strict=True)
    path = repo / POLICY
    value = json.loads(path.read_text(encoding='utf-8'))
    if (value.get('schemaVersion') != 2 or value.get('kind') != 'scientific.mesh-inspect-input-classes'
            or value.get('operation') != 'mesh.inspect'
            or [item.get('id') for item in value.get('classes', [])] != list(IDS)
            or value.get('minimumScale') != .5 or value.get('maximumScale') != 2
            or value.get('maximumAbsoluteTranslation') != 2
            or value.get('coordinateTolerance') != 1e-6
            or value.get('maximumInputBytes') != 131072
            or value.get('starBounds') != {'minimumRadius': .6, 'maximumRadius': 1.4,
                'maximumAbsoluteCenter': 2., 'maximumAbsoluteCoordinate': 3.5,
                'minimumFaceArea': 1e-8, 'minimumVolume': .1}):
        raise ValueError('Shared inspection class policy changed.')
    for item in value['classes']:
        expected_ranges = {'star-closed-64-128': (64, 128),
                           'star-closed-256-512': (256, 512),
                           'star-closed-1024-2048': (1024, 2048)}
        if item['id'] in expected_ranges:
            if (item.get('mode') != 'star-closed' or
                    (item.get('minimumTriangles'), item.get('maximumTriangles')) != expected_ranges[item['id']]):
                raise ValueError('Shared inspection class tier changed.')
        elif item.get('mode') != 'uniform':
            raise ValueError('Shared inspection tiny class mode changed.')
        base = (repo / item['baseFixture']).resolve(strict=True)
        holdout = (repo / item['holdoutFixture']).resolve(strict=True)
        if (not base.is_relative_to(repo) or not holdout.is_relative_to(repo)
                or sha(base) != item['baseSha256'] or sha(holdout) != item['holdoutSha256']
                or not _matches(*mesh(base), item, repo, value)
                or not _matches(*mesh(holdout), item, repo, value)
                or item['mode'] == 'star-closed' and mesh(base)[1] == mesh(holdout)[1]):
            raise ValueError('Shared inspection class holdout changed: ' + item['id'])
    for item in value['rejectedFixtures']:
        path = (repo / item['path']).resolve(strict=True)
        if not path.is_relative_to(repo) or sha(path) != item['sha256']:
            raise ValueError('Shared inspection class rejection fixture changed.')
        try:
            vertices, faces = mesh(path)
        except ValueError:
            continue
        if any(_matches(vertices, faces, entry, repo, value) for entry in value['classes']):
            raise ValueError('Adverse inspection fixture entered a class.')
    return value, sha(repo / POLICY)


def classify(path, repo=ROOT):
    value, policy_hash = policy(repo)
    vertices, faces = mesh(path, value['maximumInputBytes'])
    for item in value['classes']:
        transform = _matches(vertices, faces, item, Path(repo), value)
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
