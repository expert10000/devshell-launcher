"""Bounded, independent OBJ/VTP reload for scientific artifact qualification."""
import argparse
import base64
import hashlib
import json
import math
from pathlib import Path
import struct
import xml.etree.ElementTree as ET
import zlib

MAX_BYTES = 32 * 1024 * 1024
MAX_POINTS = 200_000
MAX_TRIANGLES = 400_000


def obj_mesh(data):
    points, faces = [], []
    for line in data.decode("utf-8", "strict").splitlines():
        parts = line.strip().split()
        if not parts or parts[0].startswith("#"):
            continue
        if parts[0] == "v":
            if len(parts) != 4:
                raise ValueError("OBJ vertex must have three coordinates")
            points.append(tuple(float(value) for value in parts[1:]))
        elif parts[0] == "f":
            if len(parts) != 4:
                raise ValueError("OBJ fixture must have triangular faces")
            face = []
            for token in parts[1:]:
                index = int(token.split("/")[0])
                if index < 1 or index > len(points):
                    raise ValueError("OBJ face index is out of range")
                face.append(index - 1)
            faces.append(tuple(face))
    return points, faces


def vtk_array(piece, appended, section, name=None):
    element = piece.find(section)
    if element is None:
        raise ValueError(f"VTP {section} is missing")
    arrays = element.findall("DataArray")
    array = next((item for item in arrays if name is None or item.get("Name") == name), None)
    if array is None or array.get("format") != "appended":
        raise ValueError(f"VTP {section}/{name or 'data'} must be appended")
    offset = int(array.get("offset", "-1"))
    if offset < 0 or offset >= len(appended):
        raise ValueError("VTP array offset is invalid")
    all_offsets = sorted(int(item.get("offset", "-1")) for item in piece.iter("DataArray")
                         if item.get("format") == "appended")
    following = next((value for value in all_offsets if value > offset), len(appended))
    segment = appended[offset:following]
    blocks = struct.unpack("<I", base64.b64decode(segment[:8])[:4])[0]
    if blocks != 1:
        raise ValueError("VTP fixed fixture requires one compressed block")
    header_chars = 4 * math.ceil((3 + blocks) * 4 / 3)
    header = base64.b64decode(segment[:header_chars], validate=True)
    _, _, uncompressed_bytes, compressed_bytes = struct.unpack("<IIII", header)
    if uncompressed_bytes > MAX_BYTES or compressed_bytes > MAX_BYTES:
        raise ValueError("VTP array exceeds the reload budget")
    compressed = base64.b64decode(segment[header_chars:], validate=True)
    if len(compressed) != compressed_bytes:
        raise ValueError("VTP compressed array length changed")
    decoder = zlib.decompressobj()
    raw = decoder.decompress(compressed, uncompressed_bytes + 1)
    if len(raw) != uncompressed_bytes or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise ValueError("VTP uncompressed array length changed")
    return array.get("type"), raw


def vtp_mesh(data):
    root = ET.fromstring(data)
    if (root.tag != "VTKFile" or root.get("type") != "PolyData"
            or root.get("byte_order") != "LittleEndian" or root.get("header_type") != "UInt32"
            or root.get("compressor") != "vtkZLibDataCompressor"):
        raise ValueError("Unsupported VTP XML contract")
    pieces = root.findall("./PolyData/Piece")
    appended_element = root.find("AppendedData")
    if len(pieces) != 1 or appended_element is None or appended_element.get("encoding") != "base64":
        raise ValueError("VTP must have one piece and appended base64 data")
    piece = pieces[0]
    appended = "".join((appended_element.text or "").split())
    if not appended.startswith("_"):
        raise ValueError("VTP appended data marker is missing")
    appended = appended[1:]
    point_type, point_data = vtk_array(piece, appended, "Points")
    connectivity_type, connectivity_data = vtk_array(piece, appended, "Polys", "connectivity")
    offset_type, offset_data = vtk_array(piece, appended, "Polys", "offsets")
    if point_type not in ("Float32", "Float64") or connectivity_type not in ("Int32", "Int64") or offset_type != connectivity_type:
        raise ValueError("Unsupported VTP point or polygon type")
    point_code = "f" if point_type == "Float32" else "d"
    index_code = "i" if connectivity_type == "Int32" else "q"
    point_size = struct.calcsize("<" + point_code)
    index_size = struct.calcsize("<" + index_code)
    if len(point_data) % (point_size * 3) or len(connectivity_data) % index_size or len(offset_data) % index_size:
        raise ValueError("VTP array has an invalid length")
    coordinates = [item[0] for item in struct.iter_unpack("<" + point_code, point_data)]
    points = [tuple(coordinates[index:index + 3]) for index in range(0, len(coordinates), 3)]
    connectivity = [item[0] for item in struct.iter_unpack("<" + index_code, connectivity_data)]
    offsets = [item[0] for item in struct.iter_unpack("<" + index_code, offset_data)]
    faces, start = [], 0
    for end in offsets:
        if end - start != 3 or end > len(connectivity):
            raise ValueError("VTP fixture contains a non-triangular polygon")
        faces.append(tuple(connectivity[start:end]))
        start = end
    if (start != len(connectivity) or len(points) != int(piece.get("NumberOfPoints", "-1"))
            or len(faces) != int(piece.get("NumberOfPolys", "-1"))):
        raise ValueError("VTP declarations do not match decoded arrays")
    return points, faces


def inspect(path):
    data = path.read_bytes()
    if not data or len(data) > MAX_BYTES:
        raise ValueError("Artifact is empty or exceeds the reload budget")
    parser = {".obj": obj_mesh, ".vtp": vtp_mesh}.get(path.suffix.lower())
    if parser is None:
        raise ValueError("Independent reload supports OBJ and VTP only")
    points, faces = parser(data)
    if not (0 < len(points) <= MAX_POINTS and 0 < len(faces) <= MAX_TRIANGLES):
        raise ValueError("Reloaded mesh count is outside the fixture budget")
    if any(len(point) != 3 or any(not math.isfinite(value) for value in point) for point in points):
        raise ValueError("Reloaded mesh has non-finite coordinates")
    edges = {}
    signed_volume = 0.0
    surface_area = 0.0
    for a, b, c in faces:
        if min(a, b, c) < 0 or max(a, b, c) >= len(points) or len({a, b, c}) != 3:
            raise ValueError("Reloaded triangle has invalid indices")
        pa, pb, pc = points[a], points[b], points[c]
        cross = ((pb[1] - pa[1]) * (pc[2] - pa[2]) - (pb[2] - pa[2]) * (pc[1] - pa[1]),
                 (pb[2] - pa[2]) * (pc[0] - pa[0]) - (pb[0] - pa[0]) * (pc[2] - pa[2]),
                 (pb[0] - pa[0]) * (pc[1] - pa[1]) - (pb[1] - pa[1]) * (pc[0] - pa[0]))
        double_area = math.sqrt(sum(value * value for value in cross))
        if double_area <= 1e-12:
            raise ValueError("Reloaded triangle is degenerate")
        surface_area += double_area / 2.0
        signed_volume += sum(pa[axis] * cross[axis] for axis in range(3)) / 6.0
        for left, right in ((a, b), (b, c), (c, a)):
            key = tuple(sorted((left, right)))
            edges[key] = edges.get(key, 0) + 1
    bounds = [value for axis in range(3) for value in (min(point[axis] for point in points),
                                                         max(point[axis] for point in points))]
    return {"parserVersion": 1, "format": path.suffix.lower()[1:],
            "artifactSha256": hashlib.sha256(data).hexdigest(), "points": len(points),
            "triangles": len(faces), "bounds": bounds,
            "boundaryEdges": sum(count == 1 for count in edges.values()),
            "nonManifoldEdges": sum(count > 2 for count in edges.values()),
            "closed": all(count == 2 for count in edges.values()), "absoluteVolume": abs(signed_volume),
            "signedVolume": signed_volume, "surfaceArea": surface_area}, points, faces


def main():
    command = argparse.ArgumentParser()
    command.add_argument("--input", required=True)
    command.add_argument("--result", required=True)
    command.add_argument("--export-obj")
    arguments = command.parse_args()
    path = Path(arguments.input).resolve(strict=True)
    summary, points, faces = inspect(path)
    summary["parserSourceSha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    if arguments.export_obj:
        target = Path(arguments.export_obj)
        if path.suffix.lower() != ".vtp" or target.suffix.lower() != ".obj":
            raise ValueError("OBJ export requires a VTP input and OBJ output")
        target.parent.mkdir(parents=True, exist_ok=True)
        lines = ["# independent VTP reload for MATH3D handoff"]
        lines += ["v " + " ".join(format(value, ".17g") for value in point) for point in points]
        lines += ["f " + " ".join(str(index + 1) for index in face) for face in faces]
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        summary["exportObjSha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
    output = Path(arguments.result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    main()
