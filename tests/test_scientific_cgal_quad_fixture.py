"""Authored closed cube and exact square-hole fixture checks."""
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_quad_fixture import FIXTURE_ROOT, verify


class QuadFixtureChecks(unittest.TestCase):
    def test_four_edge_hole_and_unit_closed_volume(self):
        result = verify()
        self.assertEqual(result['metrics']['open']['boundaryEdges'], 4)
        self.assertEqual(result['metrics']['open']['boundaryLoops'], 1)
        self.assertAlmostEqual(result['metrics']['closed']['signedVolume'], 1)

    def test_open_fixture_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('manifest.v1.json', 'cube-closed.obj', 'cube-one-quad-hole.obj'):
                shutil.copyfile(FIXTURE_ROOT / name, root / name)
            path = root / 'cube-one-quad-hole.obj'
            path.write_bytes(path.read_bytes() + b' ')
            with self.assertRaisesRegex(ValueError, 'identity or rights changed'):
                verify(root)


if __name__ == '__main__':
    unittest.main()
