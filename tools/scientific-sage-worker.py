"""Bounded, typed exact-math worker for SageMath in WSL (DS-SCI-016).

Run with the Python interpreter from a Sage environment. The JSON request and
results.json live in one owned run directory. No expression strings are eval'd.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time


RUNTIME = 'sage-wsl'
RECIPE = 'sage.exact.v1'
OPERATIONS = ('rational.add', 'polynomial.factor', 'matrix.solve', 'number-field.quadratic.inspect')
INTEGER = re.compile(r'-?(?:0|[1-9][0-9]{0,17})\Z')
RUN_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z')


class RequestError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def integer(value):
    if not isinstance(value, str) or not INTEGER.fullmatch(value):
        raise RequestError('invalid-exact-value', 'Exact integers must be bounded decimal strings.')
    return int(value)


def rational(value, QQ):
    if not isinstance(value, dict) or set(value) != {'numerator', 'denominator'}:
        raise RequestError('invalid-exact-value', 'A rational needs numerator and denominator strings.')
    numerator, denominator = integer(value['numerator']), integer(value['denominator'])
    if denominator == 0:
        raise RequestError('zero-denominator', 'A rational denominator cannot be zero.')
    return QQ(numerator) / QQ(denominator)


def encoded(value):
    return {'numerator': str(value.numerator()), 'denominator': str(value.denominator())}


def bounded_list(value, minimum, maximum, name):
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise RequestError('invalid-shape', f'{name} must have {minimum} to {maximum} entries.')
    return value


def compute(request):
    # Import Sage only after the transport envelope has been checked.
    from sage.all import QQ, ZZ, NumberField, PolynomialRing, matrix, vector
    from sage.version import version as sage_version

    operation = request['operation']
    parameters = request['parameters']
    if not isinstance(parameters, dict):
        raise RequestError('invalid-parameters', 'parameters must be an object.')

    if operation == 'rational.add':
        if set(parameters) != {'left', 'right'}:
            raise RequestError('invalid-parameters', 'rational.add needs left and right.')
        left, right = rational(parameters['left'], QQ), rational(parameters['right'], QQ)
        result = {'left': encoded(left), 'right': encoded(right), 'sum': encoded(left + right)}
    elif operation == 'polynomial.factor':
        if set(parameters) != {'coefficients'}:
            raise RequestError('invalid-parameters', 'polynomial.factor needs coefficients.')
        coefficients = [rational(item, QQ) for item in bounded_list(parameters['coefficients'], 2, 7, 'coefficients')]
        if coefficients[-1] == 0:
            raise RequestError('invalid-polynomial', 'The leading coefficient must be nonzero.')
        ring = PolynomialRing(QQ, 'x')
        polynomial = ring(coefficients)
        factorization = polynomial.factor()
        factors = [{'coefficients': [encoded(item) for item in factor.list()], 'multiplicity': int(multiplicity)}
                   for factor, multiplicity in factorization]
        reconstructed = ring(factorization.unit())
        for factor, multiplicity in factorization:
            reconstructed *= factor ** multiplicity
        if reconstructed != polynomial:
            raise RuntimeError('Sage factorization failed exact reconstruction.')
        result = {'coefficients': [encoded(item) for item in coefficients],
                  'unit': encoded(factorization.unit()), 'factors': factors, 'verified': True}
    elif operation == 'matrix.solve':
        if set(parameters) != {'matrix', 'rhs'}:
            raise RequestError('invalid-parameters', 'matrix.solve needs matrix and rhs.')
        rows = bounded_list(parameters['matrix'], 1, 6, 'matrix')
        size = len(rows)
        entries = [[rational(item, QQ) for item in bounded_list(row, size, size, 'matrix row')] for row in rows]
        rhs = [rational(item, QQ) for item in bounded_list(parameters['rhs'], size, size, 'rhs')]
        a, b = matrix(QQ, entries), vector(QQ, rhs)
        if a.det() == 0:
            raise RequestError('singular-matrix', 'The matrix is singular; a unique solution is required.')
        solution = a.solve_right(b)
        if a * solution != b:
            raise RuntimeError('Sage matrix solution failed exact reconstruction.')
        result = {'matrix': [[encoded(item) for item in row] for row in entries],
                  'rhs': [encoded(item) for item in rhs],
                  'solution': [encoded(item) for item in solution], 'verified': True}
    else:
        if set(parameters) != {'radicand', 'primes'}:
            raise RequestError('invalid-parameters', 'number-field.quadratic.inspect needs radicand and primes.')
        d = ZZ(integer(parameters['radicand']))
        if d <= 1 or not d.is_squarefree():
            raise RequestError('non-squarefree-field', 'The radicand must be squarefree and greater than one.')
        if d != 2:
            raise RequestError('unsupported-field', 'This qualified fixture accepts only Q(sqrt(2)).')
        prime_values = [ZZ(integer(item)) for item in bounded_list(parameters['primes'], 3, 3, 'primes')]
        if any(not item.is_prime() for item in prime_values):
            raise RequestError('invalid-prime', 'Each prime must be a positive prime integer.')
        if prime_values != [2, 3, 7]:
            raise RequestError('unsupported-primes', 'The fixed splitting fixture uses primes 2, 3, and 7.')
        ring = PolynomialRing(QQ, 'x')
        x = ring.gen()
        field = NumberField(x*x - d, 'a')
        integral_basis = [element.list() for element in field.integral_basis()]
        if field.degree() != 2 or field.discriminant() != 8 or len(integral_basis) != 2:
            raise RuntimeError('Quadratic field identity changed.')
        splitting = []
        for prime in prime_values:
            ideal = field.ideal(prime)
            factors = []
            reconstructed = field.ideal(1)
            norm_product = ZZ(1)
            ef_sum = 0
            for prime_ideal, exponent in ideal.factor():
                generators = [[encoded(item) for item in generator.list()]
                              for generator in prime_ideal.gens_reduced()]
                if field.ideal(prime_ideal.gens_reduced()) != prime_ideal:
                    raise RuntimeError('Prime ideal generators failed reconstruction.')
                e, f = int(exponent), int(prime_ideal.residue_class_degree())
                norm = int(prime_ideal.norm())
                factors.append({'generators': generators, 'exponent': e,
                                'residueDegree': f, 'norm': str(norm)})
                reconstructed *= prime_ideal ** exponent
                norm_product *= norm ** e
                ef_sum += e * f
            if reconstructed != ideal or norm_product != prime ** 2 or ef_sum != 2:
                raise RuntimeError('Prime splitting failed exact ideal or norm reconstruction.')
            splitting.append({'prime': str(prime), 'factors': factors, 'verified': True})
        group = field.galois_group()
        if group.order() != 2:
            raise RuntimeError('Quadratic Galois order changed.')
        result = {'radicand': '2', 'definingPolynomial': [encoded(QQ(-d)), encoded(QQ(0)), encoded(QQ(1))],
                  'degree': 2, 'discriminant': '8',
                  'integralBasis': [[encoded(item) for item in basis] for basis in integral_basis],
                  'splitting': splitting, 'galoisOrder': 2, 'verified': True,
                  'limitations': 'Only Q(sqrt(2)) and primes 2, 3, 7; quadratic group order only.'}

    return result, {'sage': sage_version}


def validate(request_path):
    if request_path.stat().st_size > 65536:
        raise RequestError('request-too-large', 'Request exceeds 64 KiB.')
    request = json.loads(request_path.read_text(encoding='utf-8-sig'))
    if not isinstance(request, dict) or request.get('schemaVersion') != 1:
        raise RequestError('unsupported-schema', 'A version 1 request object is required.')
    if request.get('runtimeId') != RUNTIME or request.get('recipeId') != RECIPE:
        raise RequestError('unsupported-runtime', 'The Sage exact worker requires sage-wsl / sage.exact.v1.')
    if not isinstance(request.get('runId'), str) or not RUN_ID.fullmatch(request['runId']):
        raise RequestError('invalid-run-id', 'A bounded runId is required.')
    if request.get('operation') not in OPERATIONS:
        raise RequestError('unsupported-operation', 'The requested exact operation is not registered.')
    if set(request) - {'schemaVersion', 'runId', 'runtimeId', 'recipeId', 'operation', 'parameters', 'workingDirectory', 'timeoutSeconds'}:
        raise RequestError('unknown-field', 'The request contains an unsupported field.')
    if not isinstance(request.get('workingDirectory'), str) or Path(request['workingDirectory']).resolve(strict=True) != request_path.parent:
        raise RequestError('invalid-workdir', 'workingDirectory must be the request directory.')
    return request


def write_result(directory, result):
    temporary = directory / 'results.json.tmp'
    with temporary.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    os.replace(temporary, directory / 'results.json')
    print(json.dumps(result, separators=(',', ':'), allow_nan=False), flush=True)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', required=True)
    args = parser.parse_args()
    request_path = Path(args.request).resolve(strict=True)
    if (request_path.parent / 'results.json').exists():
        print('The run already has a result; use a new run directory.', file=sys.stderr)
        return 2
    started = time.monotonic()
    request = {}
    try:
        request = validate(request_path)
        value, versions = compute(request)
        state, exit_code, diagnostics = 'succeeded', 0, []
    except RequestError as error:
        value, versions = None, {}
        state, exit_code = 'failed', 2
        diagnostics = [{'severity': 'error', 'code': error.code, 'message': str(error)}]
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        value, versions = None, {}
        state, exit_code = 'failed', 2
        diagnostics = [{'severity': 'error', 'code': 'invalid-request', 'message': str(error)[:400]}]
    except Exception as error:
        value, versions = None, {}
        state, exit_code = 'failed', 1
        diagnostics = [{'severity': 'error', 'code': 'worker-error', 'message': str(error)[:400]}]
    result = {'schemaVersion': 1, 'runId': request.get('runId'), 'runtimeId': RUNTIME,
              'recipeId': RECIPE, 'operation': request.get('operation'), 'state': state,
              'exitCode': exit_code, 'durationMs': round((time.monotonic() - started) * 1000),
              'versions': versions, 'validatedCapabilities': [], 'result': value,
              'diagnostics': diagnostics, 'artifacts': [], 'logReference': 'full.log',
              'provenance': {'requestSha256': sha256(request_path),
                             'workerSha256': sha256(Path(__file__).resolve())},
              'scope': 'DS-SCI-016 typed worker; no L4-L9 or MATH3D certification.'}
    write_result(request_path.parent, result)
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
