"""Independent unit-square rim coverage check after protected CGAL remeshing."""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import uuid

from scientific_cgal_corpus import sha
from scientific_cgal_mesh_metrics import edge_data, parse_obj
from scientific_cgal_remesh import verify as verify_remesh


SIDES = ('bottom', 'right', 'top', 'left')
TOLERANCE = 1e-8


def side_interval(first, second):
    x1, y1, z1 = first
    x2, y2, z2 = second
    if abs(z1) > TOLERANCE or abs(z2) > TOLERANCE:
        raise ValueError('Protected boundary left the XY plane.')
    tests = ((abs(y1) <= TOLERANCE and abs(y2) <= TOLERANCE, 'bottom', x1, x2),
             (abs(x1-1) <= TOLERANCE and abs(x2-1) <= TOLERANCE, 'right', y1, y2),
             (abs(y1-1) <= TOLERANCE and abs(y2-1) <= TOLERANCE, 'top', x1, x2),
             (abs(x1) <= TOLERANCE and abs(x2) <= TOLERANCE, 'left', y1, y2))
    matching = [(name, min(start, end), max(start, end))
                for passed, name, start, end in tests if passed]
    if len(matching) != 1 or matching[0][1] < -TOLERANCE or matching[0][2] > 1+TOLERANCE:
        raise ValueError('Protected boundary edge left the unit-square rim.')
    return matching[0]


def verify_unit_square_boundary(path):
    vertices, faces = parse_obj(path)
    counts, _ = edge_data(vertices, faces)
    boundary = [edge for edge, count in counts.items() if count == 1]
    if not boundary:
        raise ValueError('Protected square has no boundary.')
    intervals = {name: [] for name in SIDES}
    for a, b in boundary:
        side, start, end = side_interval(vertices[a], vertices[b])
        if end-start <= TOLERANCE:
            raise ValueError('Protected boundary has a zero-length segment.')
        intervals[side].append((start, end))
    result = {}
    for side, pieces in intervals.items():
        pieces.sort()
        cursor = 0.0
        for start, end in pieces:
            if not math.isclose(start, cursor, abs_tol=TOLERANCE):
                raise ValueError('Protected boundary has a gap or overlap on ' + side + '.')
            cursor = end
        if not math.isclose(cursor, 1.0, abs_tol=TOLERANCE):
            raise ValueError('Protected boundary does not cover ' + side + '.')
        result[side] = {'segments': len(pieces), 'length': sum(end-start for start, end in pieces)}
    return {'boundaryEdges': len(boundary), 'sides': result, 'verdict': 'passed'}


def run(remesh_report, output_root):
    source = Path(remesh_report).resolve(strict=True)
    report = verify_remesh(source)
    case = next(item for item in report['cases'] if item['id'] == 'protected-open-square')
    output = Path(case['directory']) / 'output.obj'
    measured = verify_unit_square_boundary(output)
    directory = Path(output_root).resolve() / uuid.uuid4().hex
    directory.mkdir(parents=True)
    record = {'schemaVersion': 1, 'kind': 'scientific.cgal-protected-boundary-check',
              'createdAtUtc': datetime.now(timezone.utc).isoformat(),
              'remeshReport': str(source), 'remeshReportSha256': sha(source),
              'outputPath': str(output), 'outputSha256': sha(output),
              'checkerSourceSha256': sha(Path(__file__)), 'measurement': measured,
              'verdict': 'passed'}
    target = directory / 'boundary.json'
    with target.open('x', encoding='utf-8') as stream:
        json.dump(record, stream, separators=(',', ':'))
    Path(str(target) + '.sha256').write_text(sha(target), encoding='utf-8')
    verify(target)
    return target, record


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('CGAL protected boundary record hash mismatch.')
    record = json.loads(path.read_text(encoding='utf-8'))
    source = Path(record['remeshReport']).resolve(strict=True)
    report = verify_remesh(source)
    case = next(item for item in report['cases'] if item['id'] == 'protected-open-square')
    output = Path(case['directory']) / 'output.obj'
    if (record.get('schemaVersion') != 1
            or record.get('kind') != 'scientific.cgal-protected-boundary-check'
            or record.get('verdict') != 'passed'
            or sha(source) != record.get('remeshReportSha256')
            or Path(record['outputPath']).resolve() != output.resolve()
            or sha(output) != record.get('outputSha256')
            or sha(Path(__file__)) != record.get('checkerSourceSha256')
            or verify_unit_square_boundary(output) != record.get('measurement')):
        raise ValueError('CGAL protected boundary evidence changed.')
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('run', 'verify'))
    parser.add_argument('--remesh-report')
    parser.add_argument('--output-root')
    parser.add_argument('--report')
    options = parser.parse_args()
    if options.command == 'run':
        if not options.remesh_report or not options.output_root:
            parser.error('run requires remesh-report and output-root')
        target, value = run(options.remesh_report, options.output_root)
        print(json.dumps({'report': str(target), 'verdict': value['verdict'],
                          'boundaryEdges': value['measurement']['boundaryEdges']}))
    else:
        if not options.report:
            parser.error('verify requires report')
        value = verify(options.report)
        print(json.dumps({'report': str(Path(options.report).resolve()),
                          'verdict': value['verdict']}))
