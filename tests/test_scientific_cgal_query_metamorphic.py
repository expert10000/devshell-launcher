"""Affine AABB relations and optional native replay evidence."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_query_metamorphic import check_result, run, transformed, verify


class AffineQueryChecks(unittest.TestCase):
    def test_transform_scales_and_permutes_coordinates(self):
        parameters = {'scale': 2.0, 'translation': [1, -2, 3], 'axes': [1, 2, 0]}
        self.assertEqual(transformed((-1.0, 0.0, 0.0), parameters), [1.0, -2.0, 1.0])

    def test_distance_must_match_reported_closest_point(self):
        result = {'schemaVersion': 1, 'state': 'succeeded', 'query': [-1, 0, 0],
                  'closestPoint': [0, 0, 0], 'squaredDistance': 1, 'distance': 1,
                  'faces': 4}
        check_result(result, [-1, 0, 0], 1)
        result['closestPoint'] = [0, 1, 0]
        with self.assertRaisesRegex(ValueError, 'distance invariant'):
            check_result(result, [-1, 0, 0], 1)


@unittest.skipUnless(os.environ.get('SCIENTIFIC_CGAL_QUERY_WORKER') and
                     os.environ.get('SCIENTIFIC_CGAL_CORPUS_PREFIX'),
                     'Local CGAL query worker and prefix are required')
class LiveAffineQueryChecks(unittest.TestCase):
    def test_seeded_native_queries_and_input_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            target, report = run(os.environ['SCIENTIFIC_CGAL_QUERY_WORKER'],
                                 os.environ['SCIENTIFIC_CGAL_CORPUS_PREFIX'], directory, 20261108)
            self.assertEqual(len(report['cases']), 8)
            self.assertEqual(verify(target)['verdict'], 'passed')
            mesh = Path(report['cases'][0]['directory']) / 'input.obj'
            original = mesh.read_bytes()
            try:
                mesh.write_bytes(original + b' ')
                with self.assertRaisesRegex(ValueError, 'evidence changed'):
                    verify(target)
            finally:
                mesh.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
