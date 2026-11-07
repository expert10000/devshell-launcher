"""Managed DS-SCI-017 fixed exact-algebra and quadratic-field acceptance suite."""

import argparse
from fractions import Fraction
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import uuid


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('scientific_sage_wsl', HERE / 'scientific-sage-wsl.py')
ADAPTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADAPTER)
SUITE = 'sage-exact-qualification-v1'


def exact(numerator, denominator='1'):
    return {'numerator': str(numerator), 'denominator': str(denominator)}


def fraction(value):
    return Fraction(int(value['numerator']), int(value['denominator']))


def multiply(left, right):
    output = [Fraction(0)] * (len(left) + len(right) - 1)
    for i, a in enumerate(left):
        for j, b in enumerate(right):
            output[i + j] += a * b
    return output


def positive_check(case_id, value):
    if case_id == 'rational-positive':
        return fraction(value['left']) + fraction(value['right']) == fraction(value['sum']) == Fraction(1, 2)
    if case_id == 'polynomial-positive':
        coefficients = [fraction(item) for item in value['coefficients']]
        reconstructed = [fraction(value['unit'])]
        for factor in value['factors']:
            for _ in range(factor['multiplicity']):
                reconstructed = multiply(reconstructed, [fraction(item) for item in factor['coefficients']])
        return value['verified'] is True and coefficients == [Fraction(-1), Fraction(0), Fraction(1)] and reconstructed == coefficients
    if case_id == 'matrix-positive':
        matrix = [[fraction(item) for item in row] for row in value['matrix']]
        rhs = [fraction(item) for item in value['rhs']]
        solution = [fraction(item) for item in value['solution']]
        return value['verified'] is True and solution == [Fraction(2), Fraction(1)] and all(
            sum(a * b for a, b in zip(row, solution)) == rhs[index] for index, row in enumerate(matrix))
    if case_id == 'field-positive':
        if (value['verified'] is not True or value['degree'] != 2 or value['discriminant'] != '8'
                or value['galoisOrder'] != 2 or value['radicand'] != '2'
                or value['limitations'] != 'Only Q(sqrt(2)) and primes 2, 3, 7; quadratic group order only.'):
            return False
        basis = [[fraction(item) for item in row] for row in value['integralBasis']]
        if basis != [[Fraction(1), Fraction(0)], [Fraction(0), Fraction(1)]]:
            return False
        splitting = value['splitting']
        if [item['prime'] for item in splitting] != ['2', '3', '7']:
            return False
        patterns = [[(2, 1, 2)], [(1, 2, 9)], [(1, 1, 7), (1, 1, 7)]]
        for item, pattern in zip(splitting, patterns):
            factors = [(entry['exponent'], entry['residueDegree'], int(entry['norm'])) for entry in item['factors']]
            if item['verified'] is not True or sorted(factors) != sorted(pattern):
                return False
            if sum(e * f for e, f, _ in factors) != 2:
                return False
            product = 1
            for e, _, norm in factors:
                product *= norm ** e
            if product != int(item['prime']) ** 2:
                return False
        return True
    return False


CASES = [
    ('rational-positive', 'math.rational.add', 'rational.add',
     {'left': exact(1, 3), 'right': exact(1, 6)}, None),
    ('rational-rejection', 'math.rational.add', 'rational.add',
     {'left': exact(1, 0), 'right': exact(1, 6)}, 'zero-denominator'),
    ('polynomial-positive', 'math.polynomial.factor', 'polynomial.factor',
     {'coefficients': [exact(-1), exact(0), exact(1)]}, None),
    ('polynomial-rejection', 'math.polynomial.factor', 'polynomial.factor',
     {'coefficients': [exact(1), {'numerator': 'bad', 'denominator': '1'}]}, 'invalid-exact-value'),
    ('matrix-positive', 'math.matrix.solve', 'matrix.solve',
     {'matrix': [[exact(2), exact(1)], [exact(1), exact(1)]], 'rhs': [exact(5), exact(3)]}, None),
    ('matrix-rejection', 'math.matrix.solve', 'matrix.solve',
     {'matrix': [[exact(1), exact(1)], [exact(2), exact(2)]], 'rhs': [exact(1), exact(2)]}, 'singular-matrix'),
    ('field-positive', 'math.number-field.quadratic', 'number-field.quadratic.inspect',
     {'radicand': '2', 'primes': ['2', '3', '7']}, None),
    ('field-rejection', 'math.number-field.quadratic', 'number-field.quadratic.inspect',
     {'radicand': '4', 'primes': ['2', '3', '7']}, 'non-squarefree-field'),
    ('prime-rejection', 'math.number-field.quadratic', 'number-field.quadratic.inspect',
     {'radicand': '2', 'primes': ['2', '9', '7']}, 'invalid-prime'),
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_result(directory, result):
    temporary = directory / 'results.json.tmp'
    temporary.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    os.replace(temporary, directory / 'results.json')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--distro', default=os.environ.get('MATH3D_WSL_DISTRO', 'Ubuntu'))
    args = parser.parse_args()
    directory = args.output_root.resolve(strict=True)
    parent = json.loads((directory / 'request.json').read_text(encoding='utf-8-sig'))
    if (parent.get('schemaVersion') != 1 or parent.get('runtimeId') != 'sage-wsl'
            or parent.get('recipeId') != 'sage.qualify-exact' or not ADAPTER.DISTRO.fullmatch(args.distro)
            or (directory / 'results.json').exists()):
        raise ValueError('Expected a fresh managed Sage qualification request.')
    cases_root = directory / 'cases'
    cases_root.mkdir(exist_ok=False)
    started = time.monotonic()
    entries = []
    error = None
    versions = {}
    try:
        for case_id, capability, operation, parameters, rejection in CASES:
            print(f'[case] {case_id}', flush=True)
            child = cases_root / case_id
            child.mkdir()
            request = {'schemaVersion': 1, 'runId': uuid.uuid4().hex, 'runtimeId': 'sage-wsl',
                       'recipeId': 'sage.exact.v1', 'operation': operation, 'parameters': parameters}
            input_path = child / 'request.json'
            input_path.write_text(json.dumps(request, indent=2) + '\n', encoding='utf-8')
            result = ADAPTER.run(args.distro, input_path, 120)
            worker_request = child / 'worker-request.json'
            worker_result = child / 'results.json'
            if not worker_request.is_file() or not worker_result.is_file():
                raise RuntimeError(f'{case_id}: worker request/result is missing.')
            if (result.get('runId') != request['runId'] or result.get('operation') != operation
                    or result.get('artifacts') != []):
                raise RuntimeError(f'{case_id}: worker identity or artifact contract changed.')
            if rejection is None:
                if result.get('state') != 'succeeded' or not positive_check(case_id, result.get('result')):
                    raise RuntimeError(f'{case_id}: exact positive invariant failed.')
                versions = result.get('versions', versions)
            elif (result.get('state') != 'failed' or result.get('result') is not None
                  or [item.get('code') for item in result.get('diagnostics', [])] != [rejection]):
                raise RuntimeError(f'{case_id}: expected {rejection} rejection was not recorded.')
            entries.append({'caseId': case_id, 'capabilityId': capability, 'operation': operation,
                            'expected': 'succeeded' if rejection is None else rejection,
                            'state': result['state'], 'requestPath': f'cases/{case_id}/worker-request.json',
                            'requestSha256': sha(worker_request), 'resultPath': f'cases/{case_id}/results.json',
                            'resultSha256': sha(worker_result), 'workerSha256': result.get('provenance', {}).get('workerSha256')})
            print(f'[pass] {case_id}', flush=True)
    except Exception as exception:
        error = str(exception)[:400]
        print(f'[fail] {error}', flush=True)
    passed = error is None and len(entries) == len(CASES)
    evidence = {'suiteId': SUITE, 'scope': 'Fixed exact and Q(sqrt(2)) cases only; no L5–L9 or MATH3D certification.',
                'fixtureRevision': 1, 'distro': args.distro, 'cases': entries,
                'workerSha256': sha(HERE / 'scientific-sage-worker.py'),
                'adapterSha256': sha(HERE / 'scientific-sage-wsl.py'),
                'suiteSha256': sha(Path(__file__).resolve()),
                'schemaSha256': sha(HERE.parent / 'schemas/scientific-sage-exact.v1.json'),
                'verdict': 'passed' if passed else 'failed'}
    result = {'schemaVersion': 1, 'runId': parent['runId'], 'runtimeId': 'sage-wsl',
              'recipeId': 'sage.qualify-exact', 'operation': 'sage.qualify-exact',
              'state': 'succeeded' if passed else 'failed', 'exitCode': 0 if passed else 1,
              'durationMs': round((time.monotonic() - started) * 1000), 'versions': versions,
              'validatedCapabilities': sorted({item[1] for item in CASES}) if passed else [],
              'diagnostics': [] if passed else [{'severity': 'error', 'code': 'qualification-failed', 'message': error}],
              'sageExactEvidence': evidence, 'artifacts': []}
    write_result(directory, result)
    return 0 if passed else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exception:
        print(f'Sage qualification: {exception}', file=sys.stderr)
        sys.exit(1)
