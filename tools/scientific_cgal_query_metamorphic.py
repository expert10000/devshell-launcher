"""Seeded affine AABB distance relations for authored tetrahedra."""
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import subprocess
import uuid

from scientific_cgal_corpus import CORPUS, sha, verify_corpus
from scientific_cgal_metamorphic import generate, parameters_for


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scientific/cgal-worker/query.cpp'
GENERATOR = ROOT / 'tools/scientific_cgal_metamorphic.py'
PROBES = (('outside', (-1.0, 0.0, 0.0), 1.0),
          ('inside', (0.1, 0.1, 0.1), 0.01))


def transformed(point, parameters):
    scale, shift, axes = parameters['scale'], parameters['translation'], parameters['axes']
    return [scale * point[axes[index]] + shift[index] for index in range(3)]


def check_result(result, point, squared):
    if (result.get('schemaVersion') != 1 or result.get('state') != 'succeeded'
            or len(result.get('query', [])) != 3 or len(result.get('closestPoint', [])) != 3
            or result.get('faces') != 4 or result.get('squaredDistance', -1) < 0
            or not math.isclose(result['squaredDistance'], squared, abs_tol=1e-10)
            or not math.isclose(result.get('distance', float('nan')) ** 2, squared, abs_tol=1e-10)
            or any(not math.isclose(a, b, abs_tol=1e-10) for a, b in zip(result['query'], point))
            or not math.isclose(sum((a-b)**2 for a, b in zip(result['query'], result['closestPoint'])),
                                squared, abs_tol=1e-10)):
        raise ValueError('Affine CGAL query distance invariant failed.')


def run(worker, prefix, output_root, seed):
    corpus = verify_corpus()
    worker = Path(worker).resolve(strict=True)
    prefix = Path(prefix).resolve(strict=True)
    if worker.name.lower() != 'devshell_cgal_query.exe' or not (prefix / 'Library/bin').is_dir():
        raise ValueError('CGAL query worker and runtime prefix are required.')
    root = Path(output_root).resolve() / uuid.uuid4().hex
    root.mkdir(parents=True)
    environment = os.environ.copy()
    environment['PATH'] = os.pathsep.join((str(prefix), str(prefix / 'Library/bin'),
                                           str(prefix / 'Scripts'), environment.get('PATH', '')))
    cases = []
    for index, parameters in enumerate(parameters_for(seed)):
        for probe_id, base, base_squared in PROBES:
            directory = root / f'case-{index}-{probe_id}'
            directory.mkdir()
            mesh = directory / 'input.obj'
            mesh.write_bytes(generate(parameters))
            point = transformed(base, parameters)
            arguments = [format(value, '.12g') for value in point]
            process = subprocess.run([str(worker), str(mesh), *arguments], cwd=directory,
                                     env=environment, capture_output=True, text=True,
                                     encoding='utf-8', errors='replace', timeout=30)
            (directory / 'stdout.log').write_text(process.stdout, encoding='utf-8')
            (directory / 'stderr.log').write_text(process.stderr, encoding='utf-8')
            result_path = directory / 'results.json'
            result = json.loads(result_path.read_text(encoding='utf-8'))
            if process.returncode != 0:
                raise ValueError('Valid affine query was rejected: ' + str(result.get('error')))
            check_result(result, point, base_squared * parameters['scale'] ** 2)
            cases.append({'caseIndex': index, 'probeId': probe_id, 'parameters': parameters,
                          'directory': str(directory), 'inputSha256': sha(mesh),
                          'query': point, 'resultSha256': sha(result_path), 'exitCode': process.returncode})
    report = {'schemaVersion': 1, 'kind': 'scientific.cgal-aabb-metamorphic-run',
              'createdAtUtc': datetime.now(timezone.utc).isoformat(), 'seed': seed,
              'corpusManifestSha256': corpus['manifestSha256'],
              'generatorSha256': sha(GENERATOR), 'querySourceSha256': sha(SOURCE),
              'workerPath': str(worker), 'workerSha256': sha(worker),
              'runtimePrefix': str(prefix), 'cases': cases, 'verdict': 'passed'}
    target = root / 'query-metamorphic.json'
    with target.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, separators=(',', ':'))
    Path(str(target) + '.sha256').write_text(sha(target), encoding='utf-8')
    verify(target)
    return target, report


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('CGAL query metamorphic report hash mismatch.')
    report = json.loads(path.read_text(encoding='utf-8'))
    corpus = verify_corpus()
    if (report.get('schemaVersion') != 1 or report.get('kind') != 'scientific.cgal-aabb-metamorphic-run'
            or report.get('verdict') != 'passed' or report.get('corpusManifestSha256') != corpus['manifestSha256']
            or report.get('generatorSha256') != sha(GENERATOR)
            or report.get('querySourceSha256') != sha(SOURCE)
            or sha(Path(report['workerPath']).resolve(strict=True)) != report.get('workerSha256')):
        raise ValueError('CGAL query metamorphic identity changed.')
    planned = [(index, probe_id, parameters, base, base_squared)
               for index, parameters in enumerate(parameters_for(report['seed']))
               for probe_id, base, base_squared in PROBES]
    if len(report.get('cases', [])) != len(planned):
        raise ValueError('CGAL query metamorphic case count changed.')
    for item, (index, probe_id, parameters, base, base_squared) in zip(report['cases'], planned):
        directory = Path(item['directory']).resolve(strict=True)
        point = transformed(base, parameters)
        mesh = directory / 'input.obj'
        result_path = directory / 'results.json'
        if (directory.parent != path.parent or directory.name != f'case-{index}-{probe_id}'
                or item['caseIndex'] != index or item['probeId'] != probe_id
                or item['parameters'] != parameters or item['query'] != point
                or mesh.read_bytes() != generate(parameters) or sha(mesh) != item['inputSha256']
                or sha(result_path) != item['resultSha256'] or item['exitCode'] != 0):
            raise ValueError('CGAL query metamorphic evidence changed.')
        check_result(json.loads(result_path.read_text(encoding='utf-8')),
                     point, base_squared * parameters['scale'] ** 2)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('run', 'verify'))
    parser.add_argument('--worker')
    parser.add_argument('--prefix')
    parser.add_argument('--output-root')
    parser.add_argument('--seed', type=int, default=20261108)
    parser.add_argument('--report')
    options = parser.parse_args()
    if options.command == 'run':
        if not all((options.worker, options.prefix, options.output_root)):
            parser.error('run requires worker, prefix and output-root')
        target, value = run(options.worker, options.prefix, options.output_root, options.seed)
        print(json.dumps({'report': str(target), 'verdict': value['verdict'], 'cases': len(value['cases'])}))
    else:
        if not options.report:
            parser.error('verify requires report')
        value = verify(options.report)
        print(json.dumps({'report': str(Path(options.report).resolve()),
                          'verdict': value['verdict'], 'cases': len(value['cases'])}))
