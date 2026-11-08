"""Native reopen of independently checked CGAL remesh outputs."""
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import subprocess
import uuid

from scientific_cgal_corpus import sha
from scientific_cgal_mesh_metrics import metrics
from scientific_cgal_remesh import verify as verify_remesh


POSITIVE = ('closed-tetra-remesh', 'protected-open-square')


def equivalent(first, second):
    for key in ('vertices', 'faces', 'edges', 'components', 'boundaryEdges',
                'boundaryLoops', 'maximumEdgeIncidence', 'degenerateFaces', 'eulerCharacteristic'):
        if first[key] != second[key]:
            raise ValueError('Native remesh reload topology changed: ' + key)
    for key in ('area', 'signedVolume', 'boundaryLength', 'minimumEdgeLength', 'maximumEdgeLength'):
        if not math.isclose(first[key], second[key], rel_tol=1e-10, abs_tol=1e-10):
            raise ValueError('Native remesh reload geometry changed: ' + key)
    for first_axis, second_axis in zip(first['bounds'], second['bounds']):
        if any(not math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-10)
               for a, b in zip(first_axis, second_axis)):
            raise ValueError('Native remesh reload bounds changed.')


def check_case(item, source_case):
    directory = Path(item['directory']).resolve(strict=True)
    input_path = Path(source_case['directory']) / 'output.obj'
    output = directory / 'output.obj'
    result_path = directory / 'results.json'
    if (sha(input_path) != item['inputSha256'] or sha(output) != item['outputSha256']
            or sha(result_path) != item['resultSha256']):
        raise ValueError('Native remesh reload artifact changed.')
    result = json.loads(result_path.read_text(encoding='utf-8-sig'))
    before, after = metrics(input_path), metrics(output)
    if (result.get('schemaVersion') != 1 or result.get('recipeId') != 'cgal.validate'
            or result.get('state') != 'succeeded' or result.get('exitCode') != 0
            or result.get('before', {}).get('faces') != before['faces']
            or result.get('after', {}).get('faces') != after['faces']
            or result['after'].get('boundaryEdges') != after['boundaryEdges']):
        raise ValueError('Native remesh reload worker state changed.')
    equivalent(before, after)
    if item['beforeMetrics'] != before or item['afterMetrics'] != after:
        raise ValueError('Native remesh reload independent metrics changed.')


def run(remesh_report, output_root):
    source = Path(remesh_report).resolve(strict=True)
    report = verify_remesh(source)
    worker = Path(report['workerPath']).resolve(strict=True)
    prefix = Path(report['runtimePrefix']).resolve(strict=True)
    environment = os.environ.copy()
    environment['PATH'] = os.pathsep.join((str(prefix), str(prefix / 'Library/bin'),
                                           str(prefix / 'Scripts'), environment.get('PATH', '')))
    root = Path(output_root).resolve() / uuid.uuid4().hex
    root.mkdir(parents=True)
    source_cases = {item['id']: item for item in report['cases']}
    cases = []
    for name in POSITIVE:
        original = source_cases[name]
        input_path = Path(original['directory']) / 'output.obj'
        directory = root / name
        directory.mkdir()
        output = directory / 'output.obj'
        process = subprocess.run([str(worker), 'validate', str(input_path), str(output),
                                  '0.75', '1', '0'], cwd=directory, env=environment,
                                 capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
        (directory / 'stdout.log').write_text(process.stdout, encoding='utf-8')
        (directory / 'stderr.log').write_text(process.stderr, encoding='utf-8')
        if process.returncode:
            raise ValueError('Native validation rejected a remesh output: ' + process.stderr[-300:])
        result_path = directory / 'results.json'
        item = {'id': name, 'directory': str(directory), 'inputSha256': sha(input_path),
                'outputSha256': sha(output), 'resultSha256': sha(result_path),
                'beforeMetrics': metrics(input_path), 'afterMetrics': metrics(output)}
        check_case(item, original)
        cases.append(item)
    saved = {'schemaVersion': 1, 'kind': 'scientific.cgal-remesh-native-reload',
             'createdAtUtc': datetime.now(timezone.utc).isoformat(),
             'sourceReport': str(source), 'sourceReportSha256': sha(source),
             'workerSha256': sha(worker), 'cases': cases, 'verdict': 'passed'}
    target = root / 'native-reload.json'
    with target.open('x', encoding='utf-8') as stream:
        json.dump(saved, stream, separators=(',', ':'))
    Path(str(target) + '.sha256').write_text(sha(target), encoding='utf-8')
    verify(target)
    return target, saved


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('Native remesh reload report hash mismatch.')
    saved = json.loads(path.read_text(encoding='utf-8'))
    source = Path(saved['sourceReport']).resolve(strict=True)
    report = verify_remesh(source)
    source_cases = {item['id']: item for item in report['cases']}
    if (saved.get('schemaVersion') != 1 or saved.get('kind') != 'scientific.cgal-remesh-native-reload'
            or saved.get('verdict') != 'passed' or sha(source) != saved.get('sourceReportSha256')
            or sha(Path(report['workerPath'])) != saved.get('workerSha256')
            or [item.get('id') for item in saved.get('cases', [])] != list(POSITIVE)):
        raise ValueError('Native remesh reload report identity changed.')
    for item in saved['cases']:
        directory = Path(item['directory']).resolve(strict=True)
        if directory.parent != path.parent or directory.name != item['id']:
            raise ValueError('Native remesh reload case escaped its run directory.')
        check_case(item, source_cases[item['id']])
    return saved


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
        print(json.dumps({'report': str(target), 'verdict': value['verdict'], 'cases': len(value['cases'])}))
    else:
        if not options.report:
            parser.error('verify requires report')
        value = verify(options.report)
        print(json.dumps({'report': str(Path(options.report).resolve()),
                          'verdict': value['verdict'], 'cases': len(value['cases'])}))
