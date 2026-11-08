"""Repeat native remeshing in fresh directories and seal byte-level evidence."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import uuid

from scientific_cgal_corpus import CORPUS, sha
from scientific_cgal_remesh import CASES, check_case, verify as verify_remesh


POSITIVE = CASES[:2]
REPETITIONS = 3


def check_item(item, case, baseline):
    directory = Path(item['directory']).resolve(strict=True)
    output = directory / 'output.obj'
    result_path = directory / 'results.json'
    if (sha(output) != item['outputSha256'] or sha(result_path) != item['resultSha256']
            or item['outputSha256'] != baseline['outputSha256']):
        raise ValueError('Repeat CGAL remesh byte evidence changed.')
    result = json.loads(result_path.read_text(encoding='utf-8-sig'))
    measured = check_case(case, result, 0, output)
    if measured != item['metrics'] or measured != baseline['metrics']:
        raise ValueError('Repeat CGAL remesh geometry changed.')


def run(remesh_report, output_root):
    source = Path(remesh_report).resolve(strict=True)
    baseline = verify_remesh(source)
    worker = Path(baseline['workerPath']).resolve(strict=True)
    prefix = Path(baseline['runtimePrefix']).resolve(strict=True)
    environment = os.environ.copy()
    environment['PATH'] = os.pathsep.join((str(prefix), str(prefix / 'Library/bin'),
                                           str(prefix / 'Scripts'), environment.get('PATH', '')))
    root = Path(output_root).resolve() / uuid.uuid4().hex
    root.mkdir(parents=True)
    reference = {item['id']: item for item in baseline['cases']}
    cases = []
    for case in POSITIVE:
        name, fixture, target, iterations, boundary, _, _ = case
        for index in range(REPETITIONS):
            directory = root / f'{name}-{index}'
            directory.mkdir()
            output = directory / 'output.obj'
            process = subprocess.run([str(worker), 'remesh', str(CORPUS / (fixture + '.obj')),
                                      str(output), target, iterations, boundary], cwd=directory,
                                     env=environment, capture_output=True, text=True,
                                     encoding='utf-8', errors='replace', timeout=60)
            (directory / 'stdout.log').write_text(process.stdout, encoding='utf-8')
            (directory / 'stderr.log').write_text(process.stderr, encoding='utf-8')
            if process.returncode:
                raise ValueError('Repeat CGAL remesh failed: ' + process.stderr[-300:])
            result_path = directory / 'results.json'
            item = {'id': name, 'repetition': index, 'directory': str(directory),
                    'outputSha256': sha(output), 'resultSha256': sha(result_path),
                    'metrics': check_case(case, json.loads(result_path.read_text(encoding='utf-8-sig')),
                                          process.returncode, output)}
            check_item(item, case, reference[name])
            cases.append(item)
    report = {'schemaVersion': 1, 'kind': 'scientific.cgal-remesh-repeat',
              'createdAtUtc': datetime.now(timezone.utc).isoformat(),
              'sourceReport': str(source), 'sourceReportSha256': sha(source),
              'workerSha256': sha(worker), 'repetitions': REPETITIONS,
              'cases': cases, 'verdict': 'passed'}
    target = root / 'repeat.json'
    with target.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, separators=(',', ':'))
    Path(str(target) + '.sha256').write_text(sha(target), encoding='utf-8')
    verify(target)
    return target, report


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('Repeat CGAL remesh report hash mismatch.')
    report = json.loads(path.read_text(encoding='utf-8'))
    source = Path(report['sourceReport']).resolve(strict=True)
    baseline = verify_remesh(source)
    if (report.get('schemaVersion') != 1 or report.get('kind') != 'scientific.cgal-remesh-repeat'
            or report.get('verdict') != 'passed' or report.get('repetitions') != REPETITIONS
            or sha(source) != report.get('sourceReportSha256')
            or sha(Path(baseline['workerPath'])) != report.get('workerSha256')):
        raise ValueError('Repeat CGAL remesh report identity changed.')
    expected = [(case, index) for case in POSITIVE for index in range(REPETITIONS)]
    if len(report.get('cases', [])) != len(expected):
        raise ValueError('Repeat CGAL remesh case count changed.')
    reference = {item['id']: item for item in baseline['cases']}
    for item, (case, index) in zip(report['cases'], expected):
        directory = Path(item['directory']).resolve(strict=True)
        if (item['id'] != case[0] or item['repetition'] != index or directory.parent != path.parent
                or directory.name != f'{case[0]}-{index}'):
            raise ValueError('Repeat CGAL remesh case identity changed.')
        check_item(item, case, reference[case[0]])
    return report


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
    else:
        if not options.report:
            parser.error('verify requires report')
        target, value = Path(options.report).resolve(), verify(options.report)
    print(json.dumps({'report': str(target), 'verdict': value['verdict'], 'cases': len(value['cases'])}))
