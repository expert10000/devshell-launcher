"""Two-square-hole cube provenance and independent topology checks."""
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_multi_fixture import FIXTURE_ROOT, verify


class MultiFixtureChecks(unittest.TestCase):
    def test_two_four_edge_loops_and_four_missing_faces(self):
        result = verify()
        self.assertEqual((result['metrics']['faces'], result['metrics']['boundaryEdges'],
                          result['metrics']['boundaryLoops']), (8, 8, 2))
        self.assertAlmostEqual(result['metrics']['area'], 4)

    def test_tampered_open_mesh_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('manifest.v1.json', 'cube-two-square-holes.obj'):
                shutil.copyfile(FIXTURE_ROOT / name, root / name)
            path = root / 'cube-two-square-holes.obj'
            path.write_bytes(path.read_bytes() + b' ')
            with self.assertRaisesRegex(ValueError, 'identity or rights changed'):
                verify(root)


if __name__ == '__main__':
    unittest.main()
