"""Independent triangle-distance adjudication for saved CGAL AABB queries."""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import uuid

from scientific_cgal_corpus import CORPUS, sha
from scientific_cgal_query import verify as verify_fixed
from scientific_cgal_query_metamorphic import verify as verify_metamorphic


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def minus(a, b):
    return tuple(x-y for x, y in zip(a, b))


def squared(a, b):
    delta = minus(a, b)
    return dot(delta, delta)


def segment_closest(point, start, end):
    direction = minus(end, start)
    length = dot(direction, direction)
    if length <= 0:
        raise ValueError('Oracle received a zero-length edge.')
    factor = max(0.0, min(1.0, dot(minus(point, start), direction) / length))
    return tuple(start[index] + factor*direction[index] for index in range(3))


def triangle_closest(point, a, b, c):
    ab, ac, ap = minus(b, a), minus(c, a), minus(point, a)
    d00, d01, d11 = dot(ab, ab), dot(ab, ac), dot(ac, ac)
    denominator = d00*d11 - d01*d01
    if denominator <= 1e-24:
        raise ValueError('Oracle received a degenerate triangle.')
    u = (d11*dot(ap, ab) - d01*dot(ap, ac)) / denominator
    v = (d00*dot(ap, ac) - d01*dot(ap, ab)) / denominator
    if u >= 0 and v >= 0 and u+v <= 1:
        return tuple(a[index] + u*ab[index] + v*ac[index] for index in range(3))
    return min((segment_closest(point, a, b), segment_closest(point, b, c),
                segment_closest(point, c, a)), key=lambda candidate: squared(point, candidate))


def triangles(path):
    vertices, faces = [], []
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        parts = line.split()
        if not parts or parts[0] == '#':
            continue
        if parts[0] == 'v' and len(parts) == 4:
            vertices.append(tuple(float(value) for value in parts[1:]))
        elif parts[0] == 'f' and len(parts) == 4:
            faces.append(tuple(int(value)-1 for value in parts[1:]))
        else:
            raise ValueError('Oracle supports only triangular OBJ geometry.')
    if not vertices or not faces or len(faces) > 2048:
        raise ValueError('Oracle mesh is empty or over budget.')
    return [tuple(vertices[index] for index in face) for face in faces]


def adjudicate(mesh, result):
    point = result['query']
    closest = result['closestPoint']
    if (len(point) != 3 or len(closest) != 3
            or not all(math.isfinite(value) for value in point + closest)):
        raise ValueError('Oracle query coordinates are invalid.')
    surface = triangles(mesh)
    oracle_squared = min(squared(point, triangle_closest(point, *face)) for face in surface)
    surface_residual = min(squared(closest, triangle_closest(closest, *face)) for face in surface)
    if (not math.isclose(oracle_squared, result['squaredDistance'], abs_tol=1e-10)
            or surface_residual > 1e-18
            or not math.isclose(squared(point, closest), oracle_squared, abs_tol=1e-10)):
        raise ValueError('CGAL AABB result differs from independent triangle-distance oracle.')
    return {'squaredDistance': oracle_squared, 'closestPointSurfaceResidual': surface_residual}


def source_cases(path):
    kind = json.loads(Path(path).read_text(encoding='utf-8')).get('kind')
    if kind == 'scientific.cgal-aabb-fixed-suite':
        report = verify_fixed(path)
        return [(item['id'], CORPUS / (item['fixtureId'] + '.obj'),
                 Path(item['directory']) / 'results.json')
                for item in report['cases'] if item['state'] == 'succeeded']
    if kind == 'scientific.cgal-aabb-metamorphic-run':
        report = verify_metamorphic(path)
        return [(f"{item['caseIndex']}-{item['probeId']}", Path(item['directory']) / 'input.obj',
                 Path(item['directory']) / 'results.json') for item in report['cases']]
    raise ValueError('Unsupported source query suite for oracle.')


def check_source(path):
    cases = source_cases(path)
    results = []
    for name, mesh, result_path in cases:
        result = json.loads(result_path.read_text(encoding='utf-8'))
        measured = adjudicate(mesh, result)
        results.append({'caseId': name, 'meshSha256': sha(mesh),
                        'resultSha256': sha(result_path), **measured})
    return results


def run(source_report, output_root):
    source = Path(source_report).resolve(strict=True)
    results = check_source(source)
    directory = Path(output_root).resolve() / uuid.uuid4().hex
    directory.mkdir(parents=True)
    report = {'schemaVersion': 1, 'kind': 'scientific.cgal-aabb-oracle-check',
              'createdAtUtc': datetime.now(timezone.utc).isoformat(),
              'sourceReport': str(source), 'sourceReportSha256': sha(source),
              'oracleSourceSha256': sha(Path(__file__)), 'cases': results, 'verdict': 'passed'}
    target = directory / 'oracle.json'
    with target.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, separators=(',', ':'))
    Path(str(target) + '.sha256').write_text(sha(target), encoding='utf-8')
    verify(target)
    return target, report


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('CGAL oracle report hash mismatch.')
    report = json.loads(path.read_text(encoding='utf-8'))
    source = Path(report['sourceReport']).resolve(strict=True)
    if (report.get('schemaVersion') != 1 or report.get('kind') != 'scientific.cgal-aabb-oracle-check'
            or report.get('verdict') != 'passed'
            or sha(source) != report.get('sourceReportSha256')
            or sha(Path(__file__)) != report.get('oracleSourceSha256')
            or report.get('cases') != check_source(source)):
        raise ValueError('CGAL oracle evidence changed.')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('run', 'verify'))
    parser.add_argument('--source-report')
    parser.add_argument('--output-root')
    parser.add_argument('--report')
    options = parser.parse_args()
    if options.command == 'run':
        if not options.source_report or not options.output_root:
            parser.error('run requires source-report and output-root')
        target, value = run(options.source_report, options.output_root)
        print(json.dumps({'report': str(target), 'verdict': value['verdict'], 'cases': len(value['cases'])}))
    else:
        if not options.report:
            parser.error('verify requires report')
        value = verify(options.report)
        print(json.dumps({'report': str(Path(options.report).resolve()),
                          'verdict': value['verdict'], 'cases': len(value['cases'])}))
