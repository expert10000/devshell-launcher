"""Affine pass/reject checks for guarded CGAL remeshing."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_remesh_guard_affine import run, verify


@unittest.skipUnless(os.environ.get('SCIENTIFIC_CGAL_ADVERSE_REPORT'),
                     'A sealed local adverse affine report is required')
class AffineGuardChecks(unittest.TestCase):
    def test_four_passes_four_rejections_and_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            target, report = run(os.environ['SCIENTIFIC_CGAL_ADVERSE_REPORT'], directory)
            self.assertEqual((report['acceptedCount'], len(report['cases'])), (4, 8))
            self.assertEqual(verify(target)['verdict'], 'passed')
            for item in report['cases']:
                output = Path(item['guardReport']).parent / 'accepted.obj'
                self.assertEqual(output.exists(), item['state'] == 'accepted')
            candidate = Path(report['cases'][-1]['guardReport']).parent / 'candidate.obj'
            original = candidate.read_bytes()
            try:
                candidate.write_bytes(original + b' ')
                with self.assertRaisesRegex(ValueError, 'artifact changed'):
                    verify(target)
            finally:
                candidate.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
