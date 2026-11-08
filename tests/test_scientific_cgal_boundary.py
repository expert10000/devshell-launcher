"""Protected square rim coverage and optional sealed native replay."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_boundary import run, verify, verify_unit_square_boundary
from scientific_cgal_remesh import run as run_remesh


class BoundaryGeometryChecks(unittest.TestCase):
    def test_original_square_covers_every_side(self):
        measured = verify_unit_square_boundary(ROOT / 'scientific/fixtures/cgal/open-square.obj')
        self.assertEqual(measured['boundaryEdges'], 4)
        self.assertEqual({name: item['segments'] for name, item in measured['sides'].items()},
                         {'bottom': 1, 'right': 1, 'top': 1, 'left': 1})

    def test_interior_boundary_vertex_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            mesh = Path(directory) / 'bad.obj'
            mesh.write_text('v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0.1 0.1 0\nf 1 2 3\nf 1 3 4\n',
                            encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'left the unit-square rim'):
                verify_unit_square_boundary(mesh)


@unittest.skipUnless(os.environ.get('SCIENTIFIC_CGAL_CORPUS_WORKER') and
                     os.environ.get('SCIENTIFIC_CGAL_CORPUS_PREFIX'),
                     'Local CGAL worker and prefix are required')
class LiveBoundaryChecks(unittest.TestCase):
    def test_protected_native_remesh_covers_square_rim(self):
        with tempfile.TemporaryDirectory() as directory:
            source, _ = run_remesh(os.environ['SCIENTIFIC_CGAL_CORPUS_WORKER'],
                                   os.environ['SCIENTIFIC_CGAL_CORPUS_PREFIX'],
                                   Path(directory) / 'remesh')
            target, report = run(source, Path(directory) / 'boundary')
            self.assertEqual(report['measurement']['boundaryEdges'], 16)
            self.assertEqual(verify(target)['verdict'], 'passed')


if __name__ == '__main__':
    unittest.main()
