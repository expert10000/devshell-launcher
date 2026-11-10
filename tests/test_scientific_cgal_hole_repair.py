"""Fixed native triangular-hole repair and refusal evidence."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_hole_repair import oriented_faces, run, verify


class FaceOrientationChecks(unittest.TestCase):
    def test_authored_face_rotation_does_not_change_surface(self):
        original = ROOT / 'scientific/fixtures/cgal/closed-tetra.obj'
        with tempfile.TemporaryDirectory() as directory:
            rotated = Path(directory) / 'rotated.obj'
            rotated.write_text(original.read_text(encoding='utf-8').replace('f 2 3 4', 'f 4 2 3'),
                               encoding='utf-8')
            self.assertEqual(oriented_faces(original), oriented_faces(rotated))


@unittest.skipUnless(os.environ.get('SCIENTIFIC_CGAL_HOLE_REPAIR_WORKER') and
                     os.environ.get('SCIENTIFIC_CGAL_CORPUS_PREFIX'),
                     'Local CGAL hole-repair worker and prefix are required')
class LiveHoleRepairChecks(unittest.TestCase):
    def test_fixed_suite_and_output_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            target, report = run(os.environ['SCIENTIFIC_CGAL_HOLE_REPAIR_WORKER'],
                                 os.environ['SCIENTIFIC_CGAL_CORPUS_PREFIX'], directory)
            self.assertEqual(len(report['cases']), 5)
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
