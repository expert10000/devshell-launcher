"""Seeded orientation reversal and optional native repair replay."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_corpus import geometry
from scientific_cgal_metamorphic import parameters_for
from scientific_cgal_orientation_metamorphic import inward_bytes, run, verify


class GeneratedOrientationChecks(unittest.TestCase):
    def test_face_reversal_negates_scaled_volume(self):
        parameters = parameters_for(20261108)[0]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'inward.obj'
            path.write_bytes(inward_bytes(parameters))
            self.assertAlmostEqual(geometry(path)['signedVolume'], -parameters['scale'] ** 3 / 6)


@unittest.skipUnless(os.environ.get('SCIENTIFIC_CGAL_ORIENTATION_WORKER') and
                     os.environ.get('SCIENTIFIC_CGAL_CORPUS_PREFIX'),
                     'Local CGAL orientation worker and prefix are required')
class LiveGeneratedOrientationChecks(unittest.TestCase):
    def test_seeded_repair_reopen_and_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            target, report = run(os.environ['SCIENTIFIC_CGAL_ORIENTATION_WORKER'],
                                 os.environ['SCIENTIFIC_CGAL_CORPUS_PREFIX'], directory, 20261108)
            self.assertEqual(len(report['cases']), 4)
            self.assertEqual(verify(target)['verdict'], 'passed')
            output = Path(report['cases'][0]['directory']) / 'outward.obj'
            original = output.read_bytes()
            try:
                output.write_bytes(original + b' ')
                with self.assertRaisesRegex(ValueError, 'artifact hash'):
                    verify(target)
            finally:
                output.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
