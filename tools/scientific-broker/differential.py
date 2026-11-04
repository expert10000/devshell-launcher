"""Bounded, provider-neutral mesh, field and exact-result comparisons."""
import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import uuid


PARSER = Path(__file__).resolve().parents[1] / 'scientific-artifact-roundtrip.py'
spec = importlib.util.spec_from_file_location('scientific_artifact_roundtrip', PARSER)
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)
MAX_TRIANGLES = 500


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical_hash(value):
    return digest(json.dumps(value, sort_keys=True, separators=(',', ':')).encode())


def subtract(a, b):
    return tuple(x - y for x, y in zip(a, b))


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def triangle_distance_sq(point, a, b, c):
    """Squared distance to the closest point on a triangle, including its edges."""
    ab, ac, ap = subtract(b, a), subtract(c, a), subtract(point, a)
    d1, d2 = dot(ab, ap), dot(ac, ap)
    if d1 <= 0 and d2 <= 0:
        return dot(ap, ap)
    bp = subtract(point, b)
    d3, d4 = dot(ab, bp), dot(ac, bp)
    if d3 >= 0 and d4 <= d3:
        return dot(bp, bp)
    vc = d1 * d4 - d3 * d2
    if vc <= 0 and d1 >= 0 and d3 <= 0:
        projection = tuple(a[i] + d1 / (d1 - d3) * ab[i] for i in range(3))
        return dot(subtract(point, projection), subtract(point, projection))
    cp = subtract(point, c)
    d5, d6 = dot(ab, cp), dot(ac, cp)
    if d6 >= 0 and d5 <= d6:
        return dot(cp, cp)
    vb = d5 * d2 - d1 * d6
    if vb <= 0 and d2 >= 0 and d6 <= 0:
        projection = tuple(a[i] + d2 / (d2 - d6) * ac[i] for i in range(3))
        return dot(subtract(point, projection), subtract(point, projection))
    va = d3 * d6 - d5 * d4
    if va <= 0 and d4 - d3 >= 0 and d5 - d6 >= 0:
        bc = subtract(c, b)
        fraction = (d4 - d3) / ((d4 - d3) + (d5 - d6))
        projection = tuple(b[i] + fraction * bc[i] for i in range(3))
        return dot(subtract(point, projection), subtract(point, projection))
    normal = cross(ab, ac)
    return dot(normal, ap) ** 2 / dot(normal, normal)


def topology(points, faces):
    parent = list(range(len(points)))

    def find(item):
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    edges = {}
    for a, b, c in faces:
        for left, right in ((a, b), (b, c), (c, a)):
            parent[find(left)] = find(right)
            edge = tuple(sorted((left, right)))
            edges[edge] = edges.get(edge, 0) + 1
    return {'components': len({find(index) for index in range(len(points))}),
            'eulerCharacteristic': len(points) - len(edges) + len(faces),
            'closed': all(count == 2 for count in edges.values()),
            'manifold': all(count <= 2 for count in edges.values()),
            'boundaryEdges': sum(count == 1 for count in edges.values())}


def samples(points, faces):
    for a, b, c in faces:
        vertices = [points[index] for index in (a, b, c)]
        for point in vertices:
            yield point
        for left, right in ((0, 1), (1, 2), (2, 0)):
            yield tuple((vertices[left][axis] + vertices[right][axis]) / 2 for axis in range(3))
        yield tuple(sum(point[axis] for point in vertices) / 3 for axis in range(3))


def directed_deviation(points, faces, target_points, target_faces):
    triangles = [tuple(target_points[index] for index in face) for face in target_faces]
    return max(math.sqrt(min(triangle_distance_sq(point, *triangle) for triangle in triangles))
               for point in samples(points, faces))


def orientation_agrees(points, faces, target_points, target_faces, tolerance):
    triangles = [tuple(target_points[index] for index in face) for face in target_faces]
    for face in faces:
        vertices = [points[index] for index in face]
        centroid = tuple(sum(point[axis] for point in vertices) / 3 for axis in range(3))
        source_normal = cross(subtract(vertices[1], vertices[0]), subtract(vertices[2], vertices[0]))
        nearest = min(triangles, key=lambda triangle: triangle_distance_sq(centroid, *triangle))
        if triangle_distance_sq(centroid, *nearest) > tolerance * tolerance:
            return False
        target_normal = cross(subtract(nearest[1], nearest[0]), subtract(nearest[2], nearest[0]))
        similarity = dot(source_normal, target_normal) / math.sqrt(dot(source_normal, source_normal) * dot(target_normal, target_normal))
        if similarity < 1 - 1e-6:
            return False
    return True


def close(left, right, tolerance):
    return abs(left - right) <= tolerance * max(1, abs(left), abs(right))


def compare_mesh(left_path, right_path, tolerance=1e-6):
    left, lp, lf = reader.inspect(Path(left_path))
    right, rp, rf = reader.inspect(Path(right_path))
    if len(lf) > MAX_TRIANGLES or len(rf) > MAX_TRIANGLES:
        return {'verdict': 'inconclusive', 'reason': f'Mesh exceeds the {MAX_TRIANGLES}-triangle differential budget.',
                'left': left, 'right': right}
    lt, rt = topology(lp, lf), topology(rp, rf)
    deviation = max(directed_deviation(lp, lf, rp, rf), directed_deviation(rp, rf, lp, lf))
    scale = max(1, *(abs(value) for value in left['bounds'] + right['bounds']))
    checks = {'topology': all(lt[key] == rt[key] for key in ('components', 'eulerCharacteristic', 'closed', 'manifold')),
              'surface': deviation <= tolerance * scale,
              'orientation': orientation_agrees(lp, lf, rp, rf, tolerance * scale)
                  and orientation_agrees(rp, rf, lp, lf, tolerance * scale),
              'bounds': all(close(a, b, tolerance) for a, b in zip(left['bounds'], right['bounds'])),
              'area': close(left['surfaceArea'], right['surfaceArea'], tolerance),
              'signedVolume': close(left['signedVolume'], right['signedVolume'], tolerance)}
    return {'verdict': 'equivalent' if all(checks.values()) else 'different', 'checks': checks,
            'sampledSurfaceDeviation': deviation, 'tolerance': tolerance, 'left': left, 'right': right,
            'leftTopology': lt, 'rightTopology': rt,
            'method': 'symmetric vertices, edge midpoints and centroids to triangles; bounded sampling'}


def compare_field(left, right, tolerance=1e-9):
    if left.get('unit') != right.get('unit') or left.get('components') != right.get('components'):
        return {'verdict': 'incompatible', 'reason': 'Field unit or component contract differs.'}
    a, b = left.get('samples'), right.get('samples')
    if not isinstance(a, dict) or not isinstance(b, dict) or set(a) != set(b) or len(a) > 100000:
        return {'verdict': 'incompatible', 'reason': 'Canonical field sample IDs differ or exceed the budget.'}
    dimensions = left['components']
    if not isinstance(dimensions, int) or not 1 <= dimensions <= 16:
        raise ValueError('Field component count is invalid.')
    max_delta = 0.0
    for name in sorted(a):
        lv, rv = a[name], b[name]
        if dimensions == 1:
            lv, rv = [lv], [rv]
        if len(lv) != dimensions or len(rv) != dimensions:
            raise ValueError('Field component length is invalid.')
        for x, y in zip(lv, rv):
            if not isinstance(x, (int, float)) or not isinstance(y, (int, float)) or not math.isfinite(x) or not math.isfinite(y):
                raise ValueError('Field values must be finite numbers.')
            max_delta = max(max_delta, abs(x - y))
            if not close(x, y, tolerance):
                return {'verdict': 'different', 'sampleId': name, 'maxDelta': max_delta, 'tolerance': tolerance}
    return {'verdict': 'equivalent', 'sampleCount': len(a), 'maxDelta': max_delta, 'tolerance': tolerance}


def exact_value(data):
    kind = data.get('type')
    if kind == 'rational':
        return str(Fraction(data['value']))
    if kind == 'polynomial':
        terms = data.get('terms')
        if not isinstance(terms, dict) or len(terms) > 10000:
            raise ValueError('Exact polynomial terms are invalid.')
        return {name: str(Fraction(value)) for name, value in sorted(terms.items()) if Fraction(value) != 0}
    raise ValueError('Only rational and polynomial exact results are supported.')


def compare_exact(left, right):
    if left.get('type') != right.get('type') or left.get('unit') != right.get('unit'):
        return {'verdict': 'incompatible', 'reason': 'Exact result type or unit differs.'}
    a, b = exact_value(left), exact_value(right)
    return {'verdict': 'equivalent' if a == b else 'different', 'leftCanonical': a, 'rightCanonical': b}


def load_descriptor(path):
    descriptor = json.loads(Path(path).read_text(encoding='utf-8'))
    if descriptor.get('schemaVersion') != 1 or descriptor.get('kind') not in ('mesh', 'field', 'exact') or not descriptor.get('runtimeId') or not descriptor.get('runId'):
        raise ValueError('Differential input descriptor is incomplete.')
    if descriptor['kind'] == 'mesh':
        artifact = Path(descriptor['artifactPath']).resolve(strict=True)
        actual = digest(artifact.read_bytes())
        if actual != descriptor.get('artifactSha256'):
            raise ValueError('Differential artifact hash mismatch.')
        descriptor['artifactPath'] = str(artifact)
    else:
        descriptor['dataSha256'] = canonical_hash(descriptor['data'])
    return descriptor


def load_saved_mesh(result_path, relative_artifact):
    """Bind a mesh comparison to a successful saved run and its registered hash."""
    result_path = Path(result_path).resolve(strict=True)
    result = json.loads(result_path.read_text(encoding='utf-8'))
    if result.get('state') != 'succeeded' or not result.get('runtimeId') or not result.get('runId'):
        raise ValueError('Differential source run must be successful and identified.')
    artifact = next((item for item in result.get('artifacts', []) if item.get('path') == relative_artifact), None)
    if artifact is None:
        raise ValueError('Differential artifact is not registered by its source run.')
    path = (result_path.parent / relative_artifact).resolve(strict=True)
    if not path.is_relative_to(result_path.parent) or digest(path.read_bytes()) != artifact.get('sha256'):
        raise ValueError('Differential source artifact hash or path changed.')
    descriptor = {'schemaVersion': 1, 'kind': 'mesh', 'runtimeId': result['runtimeId'],
                  'runId': result['runId'], 'recipeId': result.get('recipeId'),
                  'artifactPath': str(path), 'artifactSha256': artifact['sha256'],
                  'sourceResultPath': str(result_path), 'sourceResultSha256': digest(result_path.read_bytes())}
    if result.get('runFingerprintSha256'):
        fingerprint_path = result_path.parent / 'fingerprint.json'
        if not fingerprint_path.is_file():
            raise ValueError('Differential source fingerprint hash changed.')
        fingerprint = json.loads(fingerprint_path.read_text(encoding='utf-8'))
        components_sha = digest(json.dumps(fingerprint['components'], separators=(',', ':'), ensure_ascii=False).encode())
        if fingerprint.get('sha256') != result['runFingerprintSha256'] or components_sha != result['runFingerprintSha256']:
            raise ValueError('Differential source fingerprint hash changed.')
        descriptor['runFingerprintSha256'] = result['runFingerprintSha256']
        descriptor['contractFingerprintSha256'] = canonical_hash(fingerprint['components']['contract'])
    return descriptor


def compare_descriptors(left, right, tolerance=1e-6):
    if left['kind'] != right['kind']:
        return {'verdict': 'incompatible', 'reason': 'Scientific result kinds differ.'}
    if left['kind'] == 'mesh':
        return compare_mesh(left['artifactPath'], right['artifactPath'], tolerance)
    if left['kind'] == 'field':
        return compare_field(left['data'], right['data'], tolerance)
    return compare_exact(left['data'], right['data'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--left')
    parser.add_argument('--right')
    parser.add_argument('--left-result')
    parser.add_argument('--right-result')
    parser.add_argument('--left-artifact')
    parser.add_argument('--right-artifact')
    parser.add_argument('--output-root', required=True)
    parser.add_argument('--tolerance', type=float, default=1e-6)
    args = parser.parse_args()
    if not math.isfinite(args.tolerance) or not 0 < args.tolerance <= 0.01:
        raise ValueError('Tolerance must be finite and between zero and 0.01.')
    if bool(args.left) == bool(args.left_result) or bool(args.right) == bool(args.right_result):
        raise ValueError('Give one descriptor or saved run for each side.')
    if args.left_result and not args.left_artifact or args.right_result and not args.right_artifact:
        raise ValueError('Saved run comparisons require registered artifact paths.')
    left = load_descriptor(args.left) if args.left else load_saved_mesh(args.left_result, args.left_artifact)
    right = load_descriptor(args.right) if args.right else load_saved_mesh(args.right_result, args.right_artifact)
    comparison = compare_descriptors(left, right, args.tolerance)
    report = {'schemaVersion': 1, 'suiteId': 'scientific-differential-v1',
              'comparisonId': uuid.uuid4().hex, 'createdAtUtc': datetime.now(timezone.utc).isoformat(),
              'left': left, 'right': right, 'comparison': comparison,
              'comparatorSha256': digest(Path(__file__).read_bytes()),
              'meshParserSha256': digest(PARSER.read_bytes()) if left['kind'] == 'mesh' else None}
    root = Path(args.output_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    path = root / (report['comparisonId'] + '.json')
    with path.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, separators=(',', ':'))
    print(json.dumps({'record': str(path), 'verdict': comparison['verdict'], 'comparison': comparison}, indent=2))


if __name__ == '__main__':
    main()
