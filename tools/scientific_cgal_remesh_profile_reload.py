"""Native validation replay of every sealed remesh fidelity-profile output."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import uuid

from scientific_cgal_corpus import sha
from scientific_cgal_mesh_metrics import metrics
from scientific_cgal_remesh_fidelity import verify as verify_fidelity
from scientific_cgal_remesh_reload import check_case


def run(source_report, output_root):
    source = Path(source_report).resolve(strict=True)
    profile = verify_fidelity(source)
    worker = Path(profile['workerPath']).resolve(strict=True)
    prefix = Path(profile['runtimePrefix']).resolve(strict=True)
    environment = os.environ.copy()
    environment['PATH'] = os.pathsep.join((str(prefix), str(prefix / 'Library/bin'),
                                           str(prefix / 'Scripts'), environment.get('PATH', '')))
    root = Path(output_root).resolve() / uuid.uuid4().hex
    root.mkdir(parents=True)
    cases = []
    for original in profile['cases']:
        directory = root / original['name']
        directory.mkdir()
        input_path = Path(original['directory']) / 'output.obj'
        output = directory / 'output.obj'
        process = subprocess.run([str(worker), 'validate', str(input_path), str(output),
                                  '0.75', '1', '0'], cwd=directory, env=environment,
                                 capture_output=True, text=True, encoding='utf-8',
                                 errors='replace', timeout=60)
        (directory / 'stdout.log').write_text(process.stdout, encoding='utf-8')
        (directory / 'stderr.log').write_text(process.stderr, encoding='utf-8')
        if process.returncode:
            raise ValueError('Native profile validation failed: ' + process.stderr[-300:])
        result_path = directory / 'results.json'
        item = {'id': original['name'], 'directory': str(directory),
                'inputSha256': sha(input_path), 'outputSha256': sha(output),
                'resultSha256': sha(result_path),
                'beforeMetrics': metrics(input_path), 'afterMetrics': metrics(output)}
        check_case(item, original)
        cases.append(item)
    report = {'schemaVersion': 1, 'kind': 'scientific.cgal-remesh-profile-reload',
              'createdAtUtc': datetime.now(timezone.utc).isoformat(),
              'sourceReport': str(source), 'sourceReportSha256': sha(source),
              'workerSha256': sha(worker), 'cases': cases, 'verdict': 'passed'}
    target = root / 'profile-reload.json'
    with target.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, separators=(',', ':'))
    Path(str(target) + '.sha256').write_text(sha(target), encoding='utf-8')
    verify(target)
    return target, report


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('Remesh profile reload report hash mismatch.')
    report = json.loads(path.read_text(encoding='utf-8'))
    source = Path(report['sourceReport']).resolve(strict=True)
    profile = verify_fidelity(source)
    if (report.get('schemaVersion') != 1 or report.get('kind') != 'scientific.cgal-remesh-profile-reload'
            or report.get('verdict') != 'passed' or sha(source) != report.get('sourceReportSha256')
            or sha(Path(profile['workerPath'])) != report.get('workerSha256')
            or len(report.get('cases', [])) != len(profile['cases'])):
        raise ValueError('Remesh profile reload identity changed.')
    for item, original in zip(report['cases'], profile['cases']):
        directory = Path(item['directory']).resolve(strict=True)
        if (item['id'] != original['name'] or directory.parent != path.parent
                or directory.name != item['id']):
            raise ValueError('Remesh profile reload case identity changed.')
        check_case(item, original)
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
