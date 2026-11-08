"""Affine protected-boundary remesh checks."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_remesh_open_affine import inverse, run, transform, verify


class AffineSquareChecks(unittest.TestCase):
    def test_inverse_restores_square_corner(self):
        parameters = {'scale': 1.5, 'translation': [2, -3, 1], 'axes': [1, 2, 0]}
        point = (1, 0, 0)
        self.assertEqual(inverse(transform(point, parameters), parameters), list(point))


@unittest.skipUnless(os.environ.get('SCIENTIFIC_CGAL_CORPUS_WORKER') and
                     os.environ.get('SCIENTIFIC_CGAL_CORPUS_PREFIX'),
                     'Local CGAL worker and prefix are required')
class LiveAffineSquareChecks(unittest.TestCase):
    def test_seeded_protected_remesh_and_inverse_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            target, report = run(os.environ['SCIENTIFIC_CGAL_CORPUS_WORKER'],
                                 os.environ['SCIENTIFIC_CGAL_CORPUS_PREFIX'], directory, 20261108)
            self.assertEqual(len(report['cases']), 4)
            self.assertEqual(verify(target)['verdict'], 'passed')
            output = Path(report['cases'][0]['directory']) / 'normalized.obj'
            original = output.read_bytes()
            try:
                output.write_bytes(original + b' ')
                with self.assertRaisesRegex(ValueError, 'evidence changed'):
                    verify(target)
            finally:
                output.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
