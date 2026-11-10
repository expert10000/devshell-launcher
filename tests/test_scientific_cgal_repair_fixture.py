"""Authored one-face tetrahedron repair fixture checks."""
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_repair_fixture import FIXTURE_ROOT, verify


class RepairFixtureChecks(unittest.TestCase):
    def test_authored_hole_has_one_three_edge_boundary(self):
        result = verify()
        self.assertEqual((result['metrics']['faces'], result['metrics']['boundaryEdges'],
                          result['metrics']['boundaryLoops']), (3, 3, 1))

    def test_tampered_fixture_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('manifest.v1.json', 'tetra-one-hole.obj'):
                shutil.copyfile(FIXTURE_ROOT / name, root / name)
            path = root / 'tetra-one-hole.obj'
            path.write_bytes(path.read_bytes() + b' ')
            with self.assertRaisesRegex(ValueError, 'identity or rights changed'):
                verify(root)


if __name__ == '__main__':
    unittest.main()
