"""Independent remesh metrics on authored canonical and pathological inputs."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_mesh_metrics import metrics


class MeshMetricChecks(unittest.TestCase):
    def test_closed_tetra_and_open_square_topology(self):
        corpus = ROOT / 'scientific/fixtures/cgal'
        tetra = metrics(corpus / 'closed-tetra.obj')
        self.assertEqual((tetra['components'], tetra['eulerCharacteristic'], tetra['boundaryLoops']),
                         (1, 2, 0))
        self.assertAlmostEqual(tetra['signedVolume'], 1/6)
        square = metrics(corpus / 'open-square.obj')
        self.assertEqual((square['components'], square['eulerCharacteristic'], square['boundaryLoops']),
                         (1, 1, 1))
        self.assertAlmostEqual(square['boundaryLength'], 4)
        self.assertAlmostEqual(square['area'], 1)

    def test_nonfinite_coordinate_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.obj'
            path.write_text('v 0 0 0\nv nan 0 0\nv 0 1 0\nf 1 2 3\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'non-finite'):
                metrics(path)


if __name__ == '__main__':
    unittest.main()
