"""Seeded affine native CGAL hole-fill evidence."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_hole_repair_affine import run, verify


@unittest.skipUnless(os.environ.get('SCIENTIFIC_CGAL_HOLE_REPAIR_WORKER') and
                     os.environ.get('SCIENTIFIC_CGAL_CORPUS_PREFIX'),
                     'Local CGAL hole-repair worker and prefix are required')
class AffineHoleRepairChecks(unittest.TestCase):
    def test_four_affine_fills_and_input_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            target, report = run(os.environ['SCIENTIFIC_CGAL_HOLE_REPAIR_WORKER'],
                                 os.environ['SCIENTIFIC_CGAL_CORPUS_PREFIX'], directory, 20261108)
            self.assertEqual(len(report['cases']), 4)
            self.assertEqual(verify(target)['verdict'], 'passed')
            source = Path(report['cases'][0]['directory']) / 'input.obj'
            original = source.read_bytes()
            try:
                source.write_bytes(original + b' ')
                with self.assertRaisesRegex(ValueError, 'artifact changed'):
                    verify(target)
            finally:
                source.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
