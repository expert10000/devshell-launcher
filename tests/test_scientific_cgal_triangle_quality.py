"""Intrinsic triangle-quality measurements."""
import math
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_triangle_quality import quality, triangle_quality


class TriangleQualityChecks(unittest.TestCase):
    def test_equilateral_and_scaled_shapes(self):
        a, b, c = (0, 0, 0), (1, 0, 0), (0.5, math.sqrt(3)/2, 0)
        angle, maximum, shape = triangle_quality(a, b, c)
        self.assertAlmostEqual(angle, 60)
        self.assertAlmostEqual(maximum, 60)
        self.assertAlmostEqual(shape, 1)
        scaled = triangle_quality(*(tuple(3*value for value in point) for point in (a, b, c)))
        for actual, expected in zip(scaled, (angle, maximum, shape)):
            self.assertAlmostEqual(actual, expected)

    def test_right_triangle_and_degenerate_rejection(self):
        angle, maximum, shape = triangle_quality((0, 0, 0), (1, 0, 0), (0, 1, 0))
        self.assertAlmostEqual(angle, 45)
        self.assertAlmostEqual(maximum, 90)
        self.assertGreater(shape, 0)
        with self.assertRaisesRegex(ValueError, 'degenerate'):
            triangle_quality((0, 0, 0), (1, 0, 0), (2, 0, 0))

    def test_obj_face_count(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'triangle.obj'
            path.write_text('v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n', encoding='utf-8')
            self.assertEqual(quality(path)['faces'], 1)


if __name__ == '__main__':
    unittest.main()
