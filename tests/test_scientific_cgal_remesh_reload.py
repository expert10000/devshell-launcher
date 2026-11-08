"""Native reload evidence for CGAL remeshing."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_mesh_metrics import metrics
from scientific_cgal_remesh_reload import equivalent, run, verify


class ReloadGeometryChecks(unittest.TestCase):
    def test_changed_geometry_is_rejected(self):
        original = metrics(ROOT / 'scientific/fixtures/cgal/closed-tetra.obj')
        changed = dict(original, signedVolume=original['signedVolume'] / 2)
        with self.assertRaisesRegex(ValueError, 'geometry changed: signedVolume'):
            equivalent(original, changed)


@unittest.skipUnless(os.environ.get('SCIENTIFIC_CGAL_REMESH_REPORT'),
                     'A sealed local CGAL remesh suite is required')
class LiveReloadChecks(unittest.TestCase):
    def test_native_reopen_and_output_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            target, report = run(os.environ['SCIENTIFIC_CGAL_REMESH_REPORT'], directory)
            self.assertEqual(len(report['cases']), 2)
            self.assertEqual(verify(target)['verdict'], 'passed')
            output = Path(report['cases'][0]['directory']) / 'output.obj'
            original = output.read_bytes()
            try:
                output.write_bytes(original + b' ')
                with self.assertRaisesRegex(ValueError, 'artifact changed'):
                    verify(target)
            finally:
                output.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
