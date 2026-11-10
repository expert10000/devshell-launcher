"""Independent M3DM parser catches changed headers and open surfaces."""
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('repair_roundtrip', ROOT / 'tools/scientific-cgal-repair-m3dm-roundtrip.py')
roundtrip = importlib.util.module_from_spec(spec)
spec.loader.exec_module(roundtrip)


class RepairM3DMTests(unittest.TestCase):
    def test_closed_tetra_and_corrupt_header(self):
        points = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)]
        faces = [(0, 2, 1), (0, 1, 3), (0, 3, 2), (1, 2, 3)]
        positions = b''.join(struct.pack('<fff', *point) for point in points)
        indices = b''.join(struct.pack('<III', *face) for face in faces)
        data = struct.pack('<4sHHIIIIII', b'M3DM', 1, 32, 4, 4, len(positions),
                           len(indices), 32 + len(positions) + len(indices), 0) + positions + indices
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'mesh.m3dm'
            path.write_bytes(data)
            vertices, triangles = roundtrip.read_m3dm(path)
            measured = roundtrip.inspect(vertices, triangles)
            self.assertEqual((measured['points'], measured['triangles'], measured['boundaryEdges']), (4, 4, 0))
            self.assertAlmostEqual(measured['signedVolume'], 1 / 6)
            path.write_bytes(b'BAD!' + data[4:])
            with self.assertRaisesRegex(ValueError, 'header'):
                roundtrip.read_m3dm(path)
            with self.assertRaisesRegex(ValueError, 'open'):
                roundtrip.inspect(vertices, triangles[:3])


if __name__ == '__main__':
    unittest.main()
