"""Accepted-only mesh export from sealed local guarded runs."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_remesh_guard_export import export, verify
from scientific_cgal_remesh_guard_suite import verify as verify_suite


@unittest.skipUnless(os.environ.get('SCIENTIFIC_CGAL_GUARD_SUITE_REPORT'),
                     'A sealed local guarded remesh suite is required')
class GuardExportChecks(unittest.TestCase):
    def test_only_accepted_mesh_exports_and_tamper_fails(self):
        suite = verify_suite(os.environ['SCIENTIFIC_CGAL_GUARD_SUITE_REPORT'])
        with tempfile.TemporaryDirectory() as directory:
            accepted = suite['cases'][0]['guardReport']
            rejected = suite['cases'][-1]['guardReport']
            with self.assertRaisesRegex(ValueError, 'cannot be exported'):
                export(rejected, directory)
            self.assertEqual(list(Path(directory).iterdir()), [])
            target, manifest = export(accepted, directory)
            self.assertEqual(verify(target)['state'], 'accepted')
            self.assertEqual(manifest['meshSha256'], json.loads(target.read_text())['meshSha256'])
            mesh = target.parent / 'mesh.obj'
            original = mesh.read_bytes()
            try:
                mesh.write_bytes(original + b' ')
                with self.assertRaisesRegex(ValueError, 'provenance or mesh changed'):
                    verify(target)
            finally:
                mesh.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
