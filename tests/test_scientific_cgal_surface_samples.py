"""Bidirectional vertex-to-surface distance checks."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_surface_samples import directed_samples, surface_samples


class SurfaceSampleChecks(unittest.TestCase):
    def test_parallel_triangles_one_unit_apart(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / 'source.obj', Path(directory) / 'target.obj'
            source.write_text('v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n', encoding='utf-8')
            target.write_text('v 0 0 1\nv 1 0 1\nv 0 1 1\nf 1 2 3\n', encoding='utf-8')
            result = surface_samples(source, target)
            for direction in result.values():
                self.assertEqual(direction['samples'], 3)
                self.assertAlmostEqual(direction['maximumDistance'], 1)
                self.assertAlmostEqual(direction['rootMeanSquareDistance'], 1)
            self.assertAlmostEqual(surface_samples(source, source)
                                   ['targetVerticesToSource']['maximumDistance'], 0)

    def test_comparison_budget(self):
        points = [(0, 0, 0)] * 4097
        with self.assertRaisesRegex(ValueError, 'budget'):
            directed_samples(points, [(0, 1, 2)], points, [(0, 1, 2)])


if __name__ == '__main__':
    unittest.main()
