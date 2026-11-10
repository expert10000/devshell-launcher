"""Live coverage for every pinned guarded remesh shape and rejection."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_remesh_qualification import fixture_manifest, run_l5, verify_l5


class FixtureCoverage(unittest.TestCase):
    def test_shape_and_pathology_matrix_is_pinned(self):
        cases = fixture_manifest()['cases']
        self.assertEqual(len(cases), 12)
        self.assertEqual({state: sum(case['expected'] == state for case in cases)
                          for state in ('accepted', 'rejected', 'invalid-input')},
                         {'accepted': 4, 'rejected': 4, 'invalid-input': 4})
        self.assertEqual({Path(case['path']).name for case in cases if case['expected'] == 'accepted'},
                         {'closed-tetra.obj', 'affine-tetra.obj', 'cube-closed.obj', 'octahedron.obj'})


@unittest.skipUnless(os.environ.get('SCIENTIFIC_CGAL_WORKER') and
                     os.environ.get('SCIENTIFIC_CGAL_PREFIX'),
                     'A built CGAL worker and prefix are required')
class LiveFixtureCoverage(unittest.TestCase):
    def test_managed_guard_matrix(self):
        with tempfile.TemporaryDirectory() as directory:
            target = run_l5(os.environ['SCIENTIFIC_CGAL_WORKER'],
                            os.environ['SCIENTIFIC_CGAL_PREFIX'], directory)
            cases = verify_l5(target)['cases']
            self.assertEqual(sum(item['state'] == 'succeeded' for item in cases), 4)
            self.assertEqual(sum(item['state'] == 'failed' and item['outputSha256'] is None
                                 for item in cases), 8)


if __name__ == '__main__':
    unittest.main()
