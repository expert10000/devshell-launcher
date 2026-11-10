"""Minimize a seeded low-fidelity remesh case with sealed native replays."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import uuid

from scientific_cgal_corpus import sha
from scientific_cgal_mesh_metrics import metrics
from scientific_cgal_metamorphic import generate, minimize_failure
from scientific_cgal_remesh_adverse_affine import check_case, verify as verify_adverse
from scientific_cgal_remesh_fidelity import classify
from scientific_cgal_surface_samples import surface_samples


NEUTRAL = {'scale': 1.0, 'translation': [0, 0, 0], 'axes': [0, 1, 2]}


def execute(worker, environment, directory, parameters):
    directory.mkdir()
    source, output = directory / 'input.obj', directory / 'output.obj'
    source.write_bytes(generate(parameters))
    process = subprocess.run([str(worker), 'remesh', str(source), str(output),
                              format(0.5 * parameters['scale'], '.12g'), '2', '0'],
                             cwd=directory, env=environment, capture_output=True,
                             text=True, encoding='utf-8', errors='replace', timeout=60)
    (directory / 'stdout.log').write_text(process.stdout, encoding='utf-8')
    (directory / 'stderr.log').write_text(process.stderr, encoding='utf-8')
    if process.returncode:
        raise ValueError('Reduced remesh worker failed: ' + process.stderr[-300:])
    original, measured = metrics(source), metrics(output)
    item = {'name': directory.name, 'parameters': parameters, 'directory': str(directory),
            'inputSha256': sha(source), 'outputSha256': sha(output),
            'resultSha256': sha(directory / 'results.json'),
            'inputMetrics': original, 'outputMetrics': measured,
            'fidelity': classify(measured, original),
            'surfaceSamples': surface_samples(source, output)}
    check_case(item, parameters)
    return item


def run(source_report, output_root):
    source = Path(source_report).resolve(strict=True)
    adverse = verify_adverse(source)
    start = adverse['cases'][0]['parameters']
    worker = Path(adverse['workerPath']).resolve(strict=True)
    prefix = Path(adverse['runtimePrefix']).resolve(strict=True)
    environment = os.environ.copy()
    environment['PATH'] = os.pathsep.join((str(prefix), str(prefix / 'Library/bin'),
                                           str(prefix / 'Scripts'), environment.get('PATH', '')))
    root = Path(output_root).resolve() / uuid.uuid4().hex
    root.mkdir(parents=True)
    cases = []

    def still_fails(parameters):
        item = execute(worker, environment, root / f'step-{len(cases)}', parameters)
        cases.append(item)
        return True

    final, planned = minimize_failure(start, still_fails)
    if final != NEUTRAL or [item['parameters'] for item in cases] != planned:
        raise ValueError('Seeded remesh failure did not minimize to neutral parameters.')
    report = {'schemaVersion': 1, 'kind': 'scientific.cgal-remesh-failure-reduction',
              'createdAtUtc': datetime.now(timezone.utc).isoformat(),
              'sourceReport': str(source), 'sourceReportSha256': sha(source),
              'workerSha256': sha(worker), 'start': start, 'final': final,
              'cases': cases, 'verdict': 'reduced'}
    target = root / 'failure-reduction.json'
    with target.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, separators=(',', ':'))
    Path(str(target) + '.sha256').write_text(sha(target), encoding='utf-8')
    verify(target)
    return target, report


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('Reduced remesh report hash mismatch.')
    report = json.loads(path.read_text(encoding='utf-8'))
    source = Path(report['sourceReport']).resolve(strict=True)
    adverse = verify_adverse(source)
    start = adverse['cases'][0]['parameters']
    final, planned = minimize_failure(start, lambda _: True)
    if (report.get('schemaVersion') != 1
            or report.get('kind') != 'scientific.cgal-remesh-failure-reduction'
            or report.get('verdict') != 'reduced' or sha(source) != report.get('sourceReportSha256')
            or sha(Path(adverse['workerPath'])) != report.get('workerSha256')
            or report.get('start') != start or report.get('final') != final
            or final != NEUTRAL or len(report.get('cases', [])) != len(planned)):
        raise ValueError('Reduced remesh report identity changed.')
    for index, (item, parameters) in enumerate(zip(report['cases'], planned)):
        directory = Path(item['directory']).resolve(strict=True)
        if (item['name'] != f'step-{index}' or item['parameters'] != parameters
                or directory.parent != path.parent or directory.name != item['name']):
            raise ValueError('Reduced remesh step identity changed.')
        check_case(item, parameters)
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
                      'steps': len(value['cases'])}))
