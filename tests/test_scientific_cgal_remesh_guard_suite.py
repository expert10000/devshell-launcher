"""Sealed six-setting native replay of the guarded remesh path."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_remesh_guard_suite import run, verify


@unittest.skipUnless(os.environ.get('SCIENTIFIC_CGAL_FIDELITY_REPORT'),
                     'A sealed local CGAL fidelity profile is required')
class GuardSuiteChecks(unittest.TestCase):
    def test_six_settings_match_baseline_and_rejected_output_stays_private(self):
        with tempfile.TemporaryDirectory() as directory:
            target, report = run(os.environ['SCIENTIFIC_CGAL_FIDELITY_REPORT'], directory)
            self.assertEqual(report['acceptedCount'], 5)
            self.assertEqual(verify(target)['verdict'], 'passed')
            rejected = Path(report['cases'][-1]['guardReport']).parent
            self.assertTrue((rejected / 'candidate.obj').is_file())
            self.assertFalse((rejected / 'accepted.obj').exists())
            accepted = Path(report['cases'][0]['guardReport']).parent / 'accepted.obj'
            original = accepted.read_bytes()
            try:
                accepted.write_bytes(original + b' ')
                with self.assertRaisesRegex(ValueError, 'accepted output changed'):
                    verify(target)
            finally:
                accepted.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
