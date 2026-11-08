"""Seed replay, shrink ordering and optional live CGAL evidence checks."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_metamorphic import minimize_failure, parameters_for, run, verify


class SeededGeometryChecks(unittest.TestCase):
    def test_seed_is_repeatable_and_bounded(self):
        self.assertEqual(parameters_for(20261108), parameters_for(20261108))
        with self.assertRaisesRegex(ValueError, 'Seed'):
            parameters_for(-1)

    def test_shrinker_keeps_the_smallest_reproducing_transform(self):
        original = {'scale': 2.0, 'translation': [3, -2, 1], 'axes': [1, 2, 0]}
        simple, trials = minimize_failure(original, lambda value: value['scale'] == 2.0)
        self.assertEqual(simple, {'scale': 2.0, 'translation': [0, 0, 0], 'axes': [0, 1, 2]})
        self.assertEqual(len(trials), 4)


@unittest.skipUnless(os.environ.get('SCIENTIFIC_CGAL_CORPUS_WORKER') and
                     os.environ.get('SCIENTIFIC_CGAL_CORPUS_PREFIX'),
                     'Local CGAL worker and prefix are required')
class LiveMetamorphicChecks(unittest.TestCase):
    def test_seeded_worker_outputs_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as directory:
            report_path, report = run(os.environ['SCIENTIFIC_CGAL_CORPUS_WORKER'],
                                      os.environ['SCIENTIFIC_CGAL_CORPUS_PREFIX'], directory, 20261108)
            self.assertEqual(report['verdict'], 'passed')
            self.assertEqual(len(report['cases']), 4)
            self.assertEqual(verify(report_path)['verdict'], 'passed')
            source = Path(report['cases'][0]['directory']) / 'input.obj'
            original = source.read_bytes()
            try:
                source.write_bytes(original + b' ')
                with self.assertRaisesRegex(ValueError, 'input changed'):
                    verify(report_path)
            finally:
                source.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
