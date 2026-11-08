"""Seeded affine tetrahedron validation with saved failure minimization."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import subprocess
import uuid

from scientific_cgal_corpus import CORPUS, geometry, sha, verify_corpus


AXES = ((0, 1, 2), (1, 2, 0), (2, 0, 1))
SCALES = (0.5, 1.0, 1.5, 2.0)


def source_mesh():
    lines = (CORPUS / 'closed-tetra.obj').read_text(encoding='utf-8').splitlines()
    vertices = [tuple(float(value) for value in line.split()[1:])
                for line in lines if line.startswith('v ')]
    faces = [tuple(int(value) for value in line.split()[1:])
             for line in lines if line.startswith('f ')]
    return vertices, faces


def generate(parameters):
    vertices, faces = source_mesh()
    scale, shift, axes = parameters['scale'], parameters['translation'], parameters['axes']
    transformed = [tuple(scale * vertex[axes[index]] + shift[index] for index in range(3))
                   for vertex in vertices]
    lines = ['# Generated from authored closed-tetra.obj']
    lines.extend('v ' + ' '.join(format(value, '.12g') for value in vertex)
                 for vertex in transformed)
    lines.extend('f ' + ' '.join(map(str, face)) for face in faces)
    return ('\n'.join(lines) + '\n').encode('utf-8')


def parameters_for(seed, count=4):
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 2**32 - 1:
        raise ValueError('Seed must be an unsigned 32-bit integer.')
    randomizer = random.Random(seed)
    return [{'scale': SCALES[randomizer.randrange(len(SCALES))],
             'translation': [randomizer.randint(-3, 3) for _ in range(3)],
             'axes': list(AXES[randomizer.randrange(len(AXES))])} for _ in range(count)]


def minimize_failure(parameters, still_fails):
    current = {'scale': parameters['scale'], 'translation': list(parameters['translation']),
               'axes': list(parameters['axes'])}
    trials = []
    for index in range(3):
        trial = {**current, 'translation': list(current['translation'])}
        trial['translation'][index] = 0
        if trial != current and still_fails(trial):
            current = trial
            trials.append(trial)
    for key, neutral in (('scale', 1.0), ('axes', [0, 1, 2])):
        trial = {**current, key: neutral}
        if trial != current and still_fails(trial):
            current = trial
            trials.append(trial)
    return current, trials


def failure_reason(code, result, measured, scale, stderr):
    if code != 0 or result.get('state') != 'succeeded' or measured is None:
        return 'Worker rejected a valid affine tetrahedron: ' + str(result.get('error') or stderr[-300:])
    if (measured['vertices'] != 4 or measured['faces'] != 4 or measured['boundaryEdges'] != 0
            or measured['maximumEdgeIncidence'] != 2 or measured['degenerateFaces'] != 0
            or abs(measured['signedVolume'] - scale ** 3 / 6) > 1e-10):
        return 'Worker output violated tetrahedral topology or scaled volume.'
    return None


def evaluate(worker, environment, parameters, directory):
    directory.mkdir(parents=True)
    source = directory / 'input.obj'
    source.write_bytes(generate(parameters))
    try:
        process = subprocess.run([str(worker), 'validate', str(source), str(directory / 'output.obj'),
                                  '0.25', '1', '1'], cwd=directory, env=environment,
                                 capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
        code, stdout, stderr = process.returncode, process.stdout, process.stderr
    except subprocess.TimeoutExpired as error:
        code = 124
        stdout = error.stdout or b''
        stderr = error.stderr or b''
        if isinstance(stdout, bytes):
            stdout = stdout.decode('utf-8', errors='replace')
        if isinstance(stderr, bytes):
            stderr = stderr.decode('utf-8', errors='replace')
        stderr += '\nWorker exceeded the 30-second metamorphic budget.'
    (directory / 'stdout.log').write_text(stdout, encoding='utf-8')
    (directory / 'stderr.log').write_text(stderr, encoding='utf-8')
    result_path = directory / 'results.json'
    result = json.loads(result_path.read_text(encoding='utf-8-sig')) if result_path.is_file() else {}
    output = directory / 'output.obj'
    try:
        measured = geometry(output) if output.is_file() else None
    except ValueError:
        measured = None
    reason = failure_reason(code, result, measured, parameters['scale'], stderr)
    return {'directory': str(directory), 'parameters': parameters, 'inputSha256': sha(source),
            'resultSha256': sha(result_path) if result_path.is_file() else None,
            'outputSha256': sha(output) if output.is_file() else None,
            'exitCode': code, 'geometry': measured, 'reason': reason}


def run(worker, prefix, output_root, seed):
    corpus = verify_corpus()
    worker = Path(worker).resolve(strict=True)
    prefix = Path(prefix).resolve(strict=True)
    if worker.name.lower() != 'devshell_cgal_worker.exe' or not (prefix / 'Library/bin').is_dir():
        raise ValueError('A CGAL worker executable and matching runtime prefix are required.')
    directory = Path(output_root).resolve() / uuid.uuid4().hex
    directory.mkdir(parents=True)
    environment = os.environ.copy()
    environment['PATH'] = os.pathsep.join((str(prefix), str(prefix / 'Library/bin'),
                                           str(prefix / 'Scripts'), environment.get('PATH', '')))
    cases, minimized = [], None
    for index, parameters in enumerate(parameters_for(seed)):
        observed = evaluate(worker, environment, parameters, directory / f'case-{index}')
        cases.append(observed)
        if observed['reason']:
            attempts = []

            def still_fails(trial):
                candidate = evaluate(worker, environment, trial,
                                     directory / f'shrink-{len(attempts)}')
                attempts.append(candidate)
                return candidate['reason'] is not None

            simple, _ = minimize_failure(parameters, still_fails)
            minimized = evaluate(worker, environment, simple, directory / 'minimized')
            if minimized['reason'] is None:
                raise ValueError('Minimized CGAL failure did not reproduce.')
            break
    report = {'schemaVersion': 1, 'kind': 'scientific.cgal-metamorphic-run',
              'createdAtUtc': datetime.now(timezone.utc).isoformat(), 'seed': seed,
              'corpusManifestSha256': corpus['manifestSha256'],
              'generatorSha256': sha(Path(__file__)), 'workerPath': str(worker),
              'workerSha256': sha(worker), 'runtimePrefix': str(prefix),
              'cases': cases, 'minimized': minimized,
              'verdict': 'failed' if minimized else 'passed'}
    target = directory / 'metamorphic.json'
    with target.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, separators=(',', ':'))
    Path(str(target) + '.sha256').write_text(sha(target), encoding='utf-8')
    verify(target)
    return target, report


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('CGAL metamorphic report hash mismatch.')
    report = json.loads(path.read_text(encoding='utf-8'))
    corpus = verify_corpus()
    if (report.get('schemaVersion') != 1 or report.get('kind') != 'scientific.cgal-metamorphic-run'
            or report.get('corpusManifestSha256') != corpus['manifestSha256']
            or report.get('generatorSha256') != sha(Path(__file__))
            or sha(Path(report['workerPath']).resolve(strict=True)) != report.get('workerSha256')
            or report.get('verdict') not in ('passed', 'failed')):
        raise ValueError('CGAL metamorphic run identity changed.')
    planned = parameters_for(report['seed'])
    cases = report['cases']
    if not 1 <= len(cases) <= len(planned) or [item['parameters'] for item in cases] != planned[:len(cases)]:
        raise ValueError('CGAL metamorphic generated cases changed.')
    for item in cases + ([report['minimized']] if report.get('minimized') else []):
        directory = Path(item['directory']).resolve(strict=True)
        if directory.parent != path.parent or sha(directory / 'input.obj') != item['inputSha256'] or (directory / 'input.obj').read_bytes() != generate(item['parameters']):
            raise ValueError('CGAL metamorphic input changed.')
        result = directory / 'results.json'
        output = directory / 'output.obj'
        try:
            measured = geometry(output) if output.is_file() else None
        except ValueError:
            measured = None
        if (result.is_file() != (item['resultSha256'] is not None)
                or (result.is_file() and sha(result) != item['resultSha256'])
                or output.is_file() != (item['outputSha256'] is not None)
                or (output.is_file() and (sha(output) != item['outputSha256']
                                         or measured != item['geometry']))):
            raise ValueError('CGAL metamorphic worker evidence changed.')
        saved_result = json.loads(result.read_text(encoding='utf-8-sig')) if result.is_file() else {}
        stderr = (directory / 'stderr.log').read_text(encoding='utf-8')
        if item['reason'] != failure_reason(item['exitCode'], saved_result, item['geometry'],
                                            item['parameters']['scale'], stderr):
            raise ValueError('CGAL metamorphic verdict differs from worker evidence.')
    if report['verdict'] == 'passed':
        if len(cases) != len(planned) or report.get('minimized') is not None or any(item['reason'] for item in cases):
            raise ValueError('CGAL metamorphic passing verdict is invalid.')
    elif not cases[-1]['reason'] or not report.get('minimized', {}).get('reason'):
        raise ValueError('CGAL metamorphic failure does not reproduce.')
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
        if value['verdict'] != 'passed':
            raise SystemExit(1)
    else:
        if not options.report:
            parser.error('verify requires report')
        value = verify(options.report)
        print(json.dumps({'report': str(Path(options.report).resolve()), 'verdict': value['verdict']}))
