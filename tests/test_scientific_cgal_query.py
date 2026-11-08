"""Fixed AABB distance equations and optional native replay."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_query import CASES, check_result, run, verify
from scientific_cgal_corpus import sha


class QueryContractChecks(unittest.TestCase):
    def test_inconsistent_closest_point_is_rejected(self):
        result = {'schemaVersion': 1, 'state': 'succeeded', 'query': [-1, 0, 0],
                  'closestPoint': [0, 0, 0], 'squaredDistance': 1,
                  'distance': 1, 'faces': 4}
        check_result(CASES[1], result, 0)
        result['closestPoint'] = [0, 1, 0]
        with self.assertRaisesRegex(ValueError, 'distance or closest point'):
            check_result(CASES[1], result, 0)


@unittest.skipUnless(os.environ.get('SCIENTIFIC_CGAL_QUERY_WORKER') and
                     os.environ.get('SCIENTIFIC_CGAL_CORPUS_PREFIX'),
                     'Local CGAL query worker and prefix are required')
class LiveQueryChecks(unittest.TestCase):
    def test_native_fixed_suite_and_result_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            report_path, report = run(os.environ['SCIENTIFIC_CGAL_QUERY_WORKER'],
                                      os.environ['SCIENTIFIC_CGAL_CORPUS_PREFIX'], directory)
            self.assertEqual(len(report['cases']), 9)
            self.assertEqual(verify(report_path)['verdict'], 'passed')
            result_path = Path(report['cases'][0]['directory']) / 'results.json'
            original = result_path.read_bytes()
            try:
                result_path.write_bytes(original + b' ')
                with self.assertRaisesRegex(ValueError, 'result hash mismatch'):
                    verify(report_path)
            finally:
                result_path.write_bytes(original)
            self.assertEqual(sha(result_path), report['cases'][0]['resultSha256'])


if __name__ == '__main__':
    unittest.main()
