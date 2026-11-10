"""Native shrinking of a seeded remesh fidelity counterexample."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_remesh_failure_reduce import NEUTRAL, run, verify


@unittest.skipUnless(os.environ.get('SCIENTIFIC_CGAL_ADVERSE_REPORT'),
                     'A sealed local adverse affine report is required')
class FailureReductionChecks(unittest.TestCase):
    def test_seed_reduces_and_saved_step_tamper_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            target, report = run(os.environ['SCIENTIFIC_CGAL_ADVERSE_REPORT'], directory)
            self.assertEqual(report['final'], NEUTRAL)
            self.assertEqual(len(report['cases']), 4)
            self.assertEqual(verify(target)['verdict'], 'reduced')
            output = Path(report['cases'][-1]['directory']) / 'output.obj'
            original = output.read_bytes()
            try:
                output.write_bytes(original + b' ')
                with self.assertRaisesRegex(ValueError, 'evidence changed'):
                    verify(target)
            finally:
                output.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
