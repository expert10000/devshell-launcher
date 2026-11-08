"""Independent triangle distance and optional native evidence checks."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_query import run as run_fixed
from scientific_cgal_query_oracle import adjudicate, run, verify


class TriangleOracleChecks(unittest.TestCase):
    def test_oracle_checks_distance_and_surface_membership(self):
        mesh = ROOT / 'scientific/fixtures/cgal/open-square.obj'
        result = {'query': [0.25, 0.75, 2.0], 'closestPoint': [0.25, 0.75, 0.0],
                  'squaredDistance': 4.0}
        self.assertEqual(adjudicate(mesh, result)['squaredDistance'], 4.0)
        result['closestPoint'] = [0.25, 0.75, 0.1]
        with self.assertRaisesRegex(ValueError, 'independent triangle-distance'):
            adjudicate(mesh, result)


@unittest.skipUnless(os.environ.get('SCIENTIFIC_CGAL_QUERY_WORKER') and
                     os.environ.get('SCIENTIFIC_CGAL_CORPUS_PREFIX'),
                     'Local CGAL query worker and prefix are required')
class LiveOracleChecks(unittest.TestCase):
    def test_fixed_native_queries_match_independent_oracle(self):
        with tempfile.TemporaryDirectory() as directory:
            worker = os.environ['SCIENTIFIC_CGAL_QUERY_WORKER']
            prefix = os.environ['SCIENTIFIC_CGAL_CORPUS_PREFIX']
            source, _ = run_fixed(worker, prefix, Path(directory) / 'fixed')
            target, report = run(source, Path(directory) / 'oracle')
            self.assertEqual(len(report['cases']), 5)
            self.assertEqual(verify(target)['verdict'], 'passed')


if __name__ == '__main__':
    unittest.main()
