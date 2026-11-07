"""DS-SCI-016 contract checks and optional real WSL/Sage round trips."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid


ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / 'tools/scientific-sage-worker.py'
ADAPTER = ROOT / 'tools/scientific-sage-wsl.py'


def exact(numerator, denominator='1'):
    return {'numerator': str(numerator), 'denominator': str(denominator)}


def request(directory, operation, parameters):
    value = {'schemaVersion': 1, 'runId': uuid.uuid4().hex, 'runtimeId': 'sage-wsl',
             'recipeId': 'sage.exact.v1', 'operation': operation, 'parameters': parameters,
             'workingDirectory': str(directory)}
    path = directory / 'request.json'
    path.write_text(json.dumps(value), encoding='utf-8')
    return path


class SageWorkerContractChecks(unittest.TestCase):
    def test_unregistered_operation_writes_typed_error_and_cannot_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            path = request(directory, 'python.eval', {'expression': '1 + 1'})
            command = [sys.executable, str(WORKER), '--request', str(path)]
            first = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(first.returncode, 2, first.stderr)
            saved = (directory / 'results.json').read_bytes()
            result = json.loads(saved)
            self.assertEqual(result['state'], 'failed')
            self.assertEqual(result['diagnostics'][0]['code'], 'unsupported-operation')
            self.assertEqual(result['artifacts'], [])
            second = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(second.returncode, 2)
            self.assertEqual((directory / 'results.json').read_bytes(), saved)

    def test_invalid_run_id_is_rejected_without_sage_import(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            path = request(directory, 'rational.add', {'left': exact(1), 'right': exact(2)})
            value = json.loads(path.read_text(encoding='utf-8'))
            value['runId'] = '../escape'
            path.write_text(json.dumps(value), encoding='utf-8')
            process = subprocess.run([sys.executable, str(WORKER), '--request', str(path)],
                                     capture_output=True, text=True, timeout=10)
            self.assertEqual(process.returncode, 2, process.stderr)
            result = json.loads((directory / 'results.json').read_text(encoding='utf-8'))
            self.assertEqual(result['diagnostics'][0]['code'], 'invalid-run-id')

    def test_real_sage_round_trips(self):
        probe = subprocess.run([sys.executable, str(ADAPTER), 'probe'], capture_output=True,
                               text=True, timeout=115)
        if probe.returncode:
            self.skipTest('WSL/Sage unavailable: ' + probe.stderr.strip()[-300:])
        self.assertEqual(json.loads(probe.stdout)['operations'],
                         ['rational.add', 'polynomial.factor', 'matrix.solve'])

        cases = [
            ('rational.add', {'left': exact(1, 3), 'right': exact(1, 6)},
             lambda result: self.assertEqual(result['sum'], exact(1, 2))),
            ('polynomial.factor', {'coefficients': [exact(-1), exact(0), exact(1)]},
             lambda result: (self.assertTrue(result['verified']), self.assertEqual(len(result['factors']), 2))),
            ('matrix.solve', {'matrix': [[exact(2), exact(1)], [exact(1), exact(1)]],
                              'rhs': [exact(5), exact(3)]},
             lambda result: self.assertEqual(result['solution'], [exact(2), exact(1)])),
        ]
        for operation, parameters, check in cases:
            with self.subTest(operation=operation), tempfile.TemporaryDirectory(prefix='sage ü path ') as folder:
                directory = Path(folder)
                path = request(directory, operation, parameters)
                process = subprocess.run([sys.executable, str(ADAPTER), 'run', '--request', str(path)],
                                         capture_output=True, text=True, timeout=180)
                self.assertEqual(process.returncode, 0, process.stderr + process.stdout[-500:])
                result = json.loads((directory / 'results.json').read_text(encoding='utf-8'))
                self.assertEqual(result['state'], 'succeeded')
                self.assertEqual(result['runId'], json.loads(path.read_text())['runId'])
                self.assertEqual(result['artifacts'], [])
                self.assertEqual(len(result['provenance']['workerSha256']), 64)
                self.assertEqual(len(result['provenance']['requestSha256']), 64)
                check(result['result'])

        rejections = [
            ('polynomial.factor', {'coefficients': [exact(1), {'numerator': 'bad', 'denominator': '1'}]}, 'invalid-exact-value'),
            ('matrix.solve', {'matrix': [[exact(1), exact(1)], [exact(2), exact(2)]],
                              'rhs': [exact(1), exact(2)]}, 'singular-matrix'),
        ]
        for operation, parameters, code in rejections:
            with self.subTest(code=code), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                path = request(directory, operation, parameters)
                process = subprocess.run([sys.executable, str(ADAPTER), 'run', '--request', str(path)],
                                         capture_output=True, text=True, timeout=180)
                self.assertEqual(process.returncode, 1, process.stderr)
                result = json.loads((directory / 'results.json').read_text(encoding='utf-8'))
                self.assertEqual(result['state'], 'failed')
                self.assertEqual(result['diagnostics'][0]['code'], code)
                self.assertIsNone(result['result'])
                self.assertEqual(result['artifacts'], [])

        with tempfile.TemporaryDirectory(prefix='sage timeout ') as folder:
            directory = Path(folder)
            path = request(directory, 'rational.add', {'left': exact(1), 'right': exact(2)})
            process = subprocess.run([sys.executable, str(ADAPTER), 'run', '--request', str(path), '--timeout', '1'],
                                     capture_output=True, text=True, timeout=120)
            self.assertEqual(process.returncode, 1, process.stderr)
            result = json.loads((directory / 'results.json').read_text(encoding='utf-8'))
            self.assertEqual(result['state'], 'timed-out')
            self.assertEqual(result['diagnostics'][0]['code'], 'transport-timeout')
            self.assertEqual(result['artifacts'], [])


if __name__ == '__main__':
    unittest.main()
