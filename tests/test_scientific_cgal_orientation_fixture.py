"""Independent orientation fixture identity and tamper checks."""
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_orientation_fixture import ROOT as FIXTURE_ROOT, verify


class OrientationFixtureChecks(unittest.TestCase):
    def test_exact_reverse_of_authored_tetrahedron(self):
        self.assertEqual(verify()['signedVolume'], -1 / 6)

    def test_changed_inward_geometry_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / 'orientation'
            shutil.copytree(FIXTURE_ROOT, destination)
            inward = destination / 'inward-tetra.obj'
            inward.write_bytes(inward.read_bytes() + b' ')
            with self.assertRaisesRegex(ValueError, 'provenance or hash'):
                verify(destination)


if __name__ == '__main__':
    unittest.main()
