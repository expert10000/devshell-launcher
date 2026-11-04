"""Independent reload checks for a valid tetrahedron and malformed mesh data."""
import base64
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

script = Path(__file__).resolve().parents[1] / "tools" / "scientific-artifact-roundtrip.py"
spec = importlib.util.spec_from_file_location("scientific_artifact_roundtrip", script)
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


def encoded(raw):
    compressed = zlib.compress(raw)
    header = struct.pack("<IIII", 1, 32768, len(raw), len(compressed))
    return base64.b64encode(header).decode() + base64.b64encode(compressed).decode()


def tetra_vtp(last_index=3):
    points = [(1, 1, 1), (-1, -1, 1), (-1, 1, -1), (1, -1, -1)]
    faces = [0, 2, 1, 0, 1, 3, 0, 3, 2, 1, 2, last_index]
    chunks = [encoded(struct.pack("<12d", *(value for point in points for value in point))),
              encoded(struct.pack("<12q", *faces)), encoded(struct.pack("<4q", 3, 6, 9, 12))]
    offsets = [0, len(chunks[0]), len(chunks[0]) + len(chunks[1])]
    return (f'<VTKFile type="PolyData" byte_order="LittleEndian" header_type="UInt32" compressor="vtkZLibDataCompressor">'
            f'<PolyData><Piece NumberOfPoints="4" NumberOfPolys="4"><Points>'
            f'<DataArray type="Float64" format="appended" offset="{offsets[0]}"/></Points><Polys>'
            f'<DataArray type="Int64" Name="connectivity" format="appended" offset="{offsets[1]}"/>'
            f'<DataArray type="Int64" Name="offsets" format="appended" offset="{offsets[2]}"/>'
            f'</Polys></Piece></PolyData><AppendedData encoding="base64">_{"".join(chunks)}'
            f'</AppendedData></VTKFile>').encode()


class RoundTripTests(unittest.TestCase):
    def test_obj_and_vtp_reload_same_closed_tetrahedron(self):
        obj = b'v 1 1 1\nv -1 -1 1\nv -1 1 -1\nv 1 -1 -1\nf 1 3 2\nf 1 2 4\nf 1 4 3\nf 2 3 4\n'
        with tempfile.TemporaryDirectory() as folder:
            for name, content in (("mesh.obj", obj), ("mesh.vtp", tetra_vtp())):
                path = Path(folder) / name
                path.write_bytes(content)
                summary, _, _ = reader.inspect(path)
                self.assertEqual((summary["points"], summary["triangles"], summary["boundaryEdges"],
                                  summary["nonManifoldEdges"], summary["closed"]), (4, 4, 0, 0, True))
                self.assertEqual(summary["bounds"], [-1, 1, -1, 1, -1, 1])

    def test_out_of_range_vtp_index_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.vtp"
            path.write_bytes(tetra_vtp(last_index=9))
            with self.assertRaisesRegex(ValueError, "invalid indices"):
                reader.inspect(path)


if __name__ == "__main__":
    unittest.main()
