"""Verified fixed and affine two-hole repair exports."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_multi_hole_export import export, verify


@unittest.skipUnless(os.environ.get('SCIENTIFIC_CGAL_MULTI_REPORT') and
                     os.environ.get('SCIENTIFIC_CGAL_MULTI_AFFINE_REPORT'),
                     'Sealed fixed and affine two-hole reports are required')
class MultiExportChecks(unittest.TestCase):
    def test_only_verified_positive_cases_export(self):
        with tempfile.TemporaryDirectory() as directory:
            fixed = os.environ['SCIENTIFIC_CGAL_MULTI_REPORT']
            affine = os.environ['SCIENTIFIC_CGAL_MULTI_AFFINE_REPORT']
            with self.assertRaisesRegex(ValueError, 'Only the accepted fixed'):
                export(fixed, 1, directory)
            self.assertEqual(list(Path(directory).iterdir()), [])
            first, _ = export(fixed, 0, directory)
            second, _ = export(affine, 1, directory)
            self.assertEqual(verify(first)['state'], 'exported')
            self.assertEqual(verify(second)['state'], 'exported')
            mesh = first.parent / 'mesh.obj'
            original = mesh.read_bytes()
            try:
                mesh.write_bytes(original + b' ')
                with self.assertRaisesRegex(ValueError, 'provenance or mesh changed'):
                    verify(first)
            finally:
                mesh.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
