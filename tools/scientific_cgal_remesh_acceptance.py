"""Fixture-scoped remesh acceptance using sealed fidelity and diagnostics."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

from scientific_cgal_corpus import sha
from scientific_cgal_remesh_diagnostics import verify as verify_diagnostics


SURFACE_TOLERANCE = 1e-8
MINIMUM_ANGLE_DEGREES = 20.0
MINIMUM_SHAPE_SCORE = 0.5


def assess(case):
    samples = case['surfaceSamples']
    maximum = max(item['maximumDistance'] for item in samples.values())
    quality = case['quality']
    checks = {'volume': case['volumeEligible'],
              'sampledSurface': maximum <= SURFACE_TOLERANCE,
              'minimumAngle': quality['minimumAngleDegrees'] >= MINIMUM_ANGLE_DEGREES,
              'minimumShape': quality['minimumShapeScore'] >= MINIMUM_SHAPE_SCORE}
    return {'name': case['name'], 'outputSha256': case['outputSha256'],
            'maximumSampledDistance': maximum, 'checks': checks,
            'eligible': all(checks.values())}


def decisions(source):
    report = verify_diagnostics(source)
    return [assess(case) for case in report['cases']]


def run(source_report, output_root):
    source = Path(source_report).resolve(strict=True)
    cases = decisions(source)
    directory = Path(output_root).resolve() / uuid.uuid4().hex
    directory.mkdir(parents=True)
    report = {'schemaVersion': 1, 'kind': 'scientific.cgal-remesh-acceptance',
              'createdAtUtc': datetime.now(timezone.utc).isoformat(),
              'sourceReport': str(source), 'sourceReportSha256': sha(source),
              'policy': {'surfaceTolerance': SURFACE_TOLERANCE,
                         'minimumAngleDegrees': MINIMUM_ANGLE_DEGREES,
                         'minimumShapeScore': MINIMUM_SHAPE_SCORE},
              'cases': cases, 'eligibleCount': sum(case['eligible'] for case in cases),
              'verdict': 'fixture-scoped'}
    target = directory / 'acceptance.json'
    with target.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, separators=(',', ':'))
    Path(str(target) + '.sha256').write_text(sha(target), encoding='utf-8')
    verify(target)
    return target, report


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('Remesh acceptance report hash mismatch.')
    report = json.loads(path.read_text(encoding='utf-8'))
    source = Path(report['sourceReport']).resolve(strict=True)
    cases = decisions(source)
    if (report.get('schemaVersion') != 1 or report.get('kind') != 'scientific.cgal-remesh-acceptance'
            or report.get('verdict') != 'fixture-scoped'
            or sha(source) != report.get('sourceReportSha256')
            or report.get('policy') != {'surfaceTolerance': SURFACE_TOLERANCE,
                                        'minimumAngleDegrees': MINIMUM_ANGLE_DEGREES,
                                        'minimumShapeScore': MINIMUM_SHAPE_SCORE}
            or report.get('cases') != cases
            or report.get('eligibleCount') != sum(case['eligible'] for case in cases)):
        raise ValueError('Remesh acceptance decisions changed.')
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
    else:
        if not options.report:
            parser.error('verify requires report')
        target, value = Path(options.report).resolve(), verify(options.report)
    print(json.dumps({'report': str(target), 'eligible': value['eligibleCount'],
                      'cases': len(value['cases'])}))
