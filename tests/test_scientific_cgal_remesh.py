"""Fixed CGAL remesh invariants and optional native evidence replay."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_remesh import CASES, check_case, run, verify


class RemeshContractChecks(unittest.TestCase):
    def test_budget_rejection_cannot_have_an_output(self):
        result = {'schemaVersion': 1, 'runtimeId': 'cgal-win-conda',
                  'recipeId': 'cgal.remesh', 'state': 'failed', 'exitCode': 2,
                  'error': 'Target edge is too small for the conservative laboratory budget'}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'output.obj'
            self.assertIsNone(check_case(CASES[4], result, 2, output))
            output.write_text('partial', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'wrote output'):
                check_case(CASES[4], result, 2, output)


@unittest.skipUnless(os.environ.get('SCIENTIFIC_CGAL_CORPUS_WORKER') and
                     os.environ.get('SCIENTIFIC_CGAL_CORPUS_PREFIX'),
                     'Local CGAL worker and prefix are required')
class LiveRemeshChecks(unittest.TestCase):
    def test_fixed_remesh_and_artifact_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            target, report = run(os.environ['SCIENTIFIC_CGAL_CORPUS_WORKER'],
                                 os.environ['SCIENTIFIC_CGAL_CORPUS_PREFIX'], directory)
            self.assertEqual([item['exitCode'] for item in report['cases']], [0, 0, 2, 2, 2, 2, 2])
            self.assertEqual(verify(target)['verdict'], 'passed')
            output = Path(report['cases'][0]['directory']) / 'output.obj'
            original = output.read_bytes()
            try:
                output.write_bytes(original + b' ')
                with self.assertRaisesRegex(ValueError, 'case evidence changed'):
                    verify(target)
            finally:
                output.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
