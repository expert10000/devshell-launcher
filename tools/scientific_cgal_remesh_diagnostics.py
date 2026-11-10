"""Seal triangle quality and sampled surface movement for a fidelity profile."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

from scientific_cgal_corpus import CORPUS, sha
from scientific_cgal_remesh_fidelity import verify as verify_fidelity
from scientific_cgal_surface_samples import surface_samples
from scientific_cgal_triangle_quality import quality


ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / 'tools/scientific_cgal_surface_samples.py'
QUALITY = ROOT / 'tools/scientific_cgal_triangle_quality.py'
ORACLE = ROOT / 'tools/scientific_cgal_query_oracle.py'


def measurements(source_report):
    fidelity = verify_fidelity(source_report)
    fixture = CORPUS / 'closed-tetra.obj'
    results = []
    for case in fidelity['cases']:
        output = Path(case['directory']) / 'output.obj'
        if sha(output) != case['outputSha256']:
            raise ValueError('Remesh diagnostic source artifact changed.')
        results.append({'name': case['name'], 'outputSha256': sha(output),
                        'volumeEligible': case['fidelity']['volumeEligible'],
                        'quality': quality(output), 'surfaceSamples': surface_samples(fixture, output)})
    return results


def run(source_report, output_root):
    source = Path(source_report).resolve(strict=True)
    results = measurements(source)
    directory = Path(output_root).resolve() / uuid.uuid4().hex
    directory.mkdir(parents=True)
    report = {'schemaVersion': 1, 'kind': 'scientific.cgal-remesh-diagnostics',
              'createdAtUtc': datetime.now(timezone.utc).isoformat(),
              'sourceReport': str(source), 'sourceReportSha256': sha(source),
              'fixtureSha256': sha(CORPUS / 'closed-tetra.obj'),
              'samplesSourceSha256': sha(SAMPLES), 'qualitySourceSha256': sha(QUALITY),
              'oracleSourceSha256': sha(ORACLE), 'cases': results, 'verdict': 'measured'}
    target = directory / 'diagnostics.json'
    with target.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, separators=(',', ':'))
    Path(str(target) + '.sha256').write_text(sha(target), encoding='utf-8')
    verify(target)
    return target, report


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('Remesh diagnostic report hash mismatch.')
    report = json.loads(path.read_text(encoding='utf-8'))
    source = Path(report['sourceReport']).resolve(strict=True)
    if (report.get('schemaVersion') != 1 or report.get('kind') != 'scientific.cgal-remesh-diagnostics'
            or report.get('verdict') != 'measured' or sha(source) != report.get('sourceReportSha256')
            or sha(CORPUS / 'closed-tetra.obj') != report.get('fixtureSha256')
            or sha(SAMPLES) != report.get('samplesSourceSha256')
            or sha(QUALITY) != report.get('qualitySourceSha256')
            or sha(ORACLE) != report.get('oracleSourceSha256')
            or report.get('cases') != measurements(source)):
        raise ValueError('Remesh diagnostic measurements changed.')
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
    print(json.dumps({'report': str(target), 'verdict': value['verdict'],
                      'cases': len(value['cases'])}))
