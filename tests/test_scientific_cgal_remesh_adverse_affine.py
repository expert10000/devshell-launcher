"""Seeded reproduction of the remesh fidelity failure."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_remesh_adverse_affine import run, verify


@unittest.skipUnless(os.environ.get('SCIENTIFIC_CGAL_CORPUS_WORKER') and
                     os.environ.get('SCIENTIFIC_CGAL_CORPUS_PREFIX'),
                     'Local CGAL worker and prefix are required')
class AdverseAffineChecks(unittest.TestCase):
    def test_four_seeded_failures_and_input_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            target, report = run(os.environ['SCIENTIFIC_CGAL_CORPUS_WORKER'],
                                 os.environ['SCIENTIFIC_CGAL_CORPUS_PREFIX'], directory, 20261108)
            self.assertEqual(len(report['cases']), 4)
            self.assertTrue(all(not item['fidelity']['volumeEligible']
                                for item in report['cases']))
            self.assertEqual(verify(target)['verdict'], 'reproduced')
            source = Path(report['cases'][0]['directory']) / 'input.obj'
            original = source.read_bytes()
            try:
                source.write_bytes(original + b' ')
                with self.assertRaisesRegex(ValueError, 'evidence changed'):
                    verify(target)
            finally:
                source.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
