"""Bounded triangle previews through VTK readers, without executing file content."""
import argparse
import json
import math
import os
from pathlib import Path
import struct
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--before')
parser.add_argument('--second-translate-x', type=float)
parser.add_argument('--after', required=True)
args = parser.parse_args()
handles = []
for folder in (Path(sys.prefix), Path(sys.prefix) / 'Library' / 'bin'):
    if hasattr(os, 'add_dll_directory') and folder.is_dir():
        handles.append(os.add_dll_directory(str(folder)))
from vtkmodules.vtkFiltersCore import vtkTriangleFilter
from vtkmodules.vtkIOGeometry import vtkOBJReader, vtkSTLReader
from vtkmodules.vtkIOPLY import vtkPLYReader
from vtkmodules.vtkIOXML import vtkXMLPolyDataReader


def preview_math3d(path):
    data = path.read_bytes()
    if len(data) < 32:
        raise ValueError('Incomplete MATH3D mesh header')
    magic, version, header_bytes, points, triangles, vertex_bytes, face_bytes, total_bytes, reserved = struct.unpack_from('<4sHHIIIIII', data)
    if (magic != b'M3DM' or version != 1 or header_bytes != 32 or reserved != 0
            or total_bytes != len(data) or vertex_bytes != points * 12 or face_bytes != triangles * 12
            or len(data) != 32 + vertex_bytes + face_bytes):
        raise ValueError('Invalid MATH3D mesh header or length')
    if not (0 < points <= 2000000 and 0 < triangles <= 2000000):
        raise ValueError('Empty mesh or preview geometry budget exceeded')
    minimum = [math.inf] * 3
    maximum = [-math.inf] * 3
    for index in range(points):
        vertex = struct.unpack_from('<fff', data, 32 + index * 12)
        for axis, value in enumerate(vertex):
            if not math.isfinite(value):
                raise ValueError('Non-finite MATH3D mesh coordinate')
            minimum[axis] = min(minimum[axis], value)
            maximum[axis] = max(maximum[axis], value)
    limit = min(triangles, 12000)
    samples = {sample * triangles // limit for sample in range(limit)}
    positions = []
    face_offset = 32 + vertex_bytes
    for index in range(triangles):
        face = struct.unpack_from('<III', data, face_offset + index * 12)
        if any(vertex >= points for vertex in face):
            raise ValueError('Invalid MATH3D mesh face index')
        if index in samples:
            for vertex in face:
                positions.extend(round(value, 7) for value in struct.unpack_from('<fff', data, 32 + vertex * 12))
    bounds = [value for axis in range(3) for value in (minimum[axis], maximum[axis])]
    return {'name': path.name, 'points': points, 'triangles': triangles, 'bounds': bounds,
            'positions': positions, 'previewTriangles': len(positions) // 9,
            'sampled': triangles > limit,
            'note': 'Uniform triangle sample for display only; not simplified geometry.' if triangles > limit else 'Full triangle preview.'}


def preview(filename):
    if not filename:
        return None
    path = Path(filename).resolve(strict=True)
    if path.stat().st_size > 67108864:
        raise ValueError('Preview input exceeds 64 MiB')
    if path.suffix.lower() == '.m3dm':
        return preview_math3d(path)
    readers = {'.obj': vtkOBJReader, '.stl': vtkSTLReader, '.ply': vtkPLYReader, '.vtp': vtkXMLPolyDataReader}
    reader_type = readers.get(path.suffix.lower())
    if not reader_type:
        raise ValueError('Preview supports OBJ/STL/PLY/VTP/M3DM only')
    errors = []
    reader = reader_type()
    reader.AddObserver('ErrorEvent', lambda *_: errors.append('Mesh reader failed'))
    reader.SetFileName(str(path))
    reader.Update()
    if errors or reader.GetErrorCode():
        raise ValueError('; '.join(errors) or 'Mesh reader failed')
    triangles = vtkTriangleFilter()
    triangles.SetInputData(reader.GetOutput())
    triangles.PassLinesOff()
    triangles.PassVertsOff()
    triangles.Update()
    mesh = triangles.GetOutput()
    count = mesh.GetNumberOfPolys()
    if count == 0 or mesh.GetNumberOfPoints() == 0 or count > 2000000 or mesh.GetNumberOfPoints() > 2000000:
        raise ValueError('Empty mesh or preview geometry budget exceeded')
    limit = min(count, 12000)
    positions = []
    bounds = list(mesh.GetBounds())
    if not all(math.isfinite(value) for value in bounds):
        raise ValueError('Non-finite mesh bounds')
    for sample in range(limit):
        cell = mesh.GetCell(sample * count // limit)
        if cell.GetNumberOfPoints() != 3:
            continue
        for corner in range(3):
            point = mesh.GetPoint(cell.GetPointId(corner))
            if not all(math.isfinite(value) for value in point):
                raise ValueError('Non-finite mesh coordinate')
            positions.extend(round(value, 7) for value in point)
    return {'name': path.name, 'points': mesh.GetNumberOfPoints(), 'triangles': count, 'bounds': bounds,
            'positions': positions, 'previewTriangles': len(positions) // 9,
            'sampled': count > limit, 'note': 'Uniform triangle sample for display only; not simplified geometry.' if count > limit else 'Full triangle preview.'}


before = preview(args.before)
before_second = None
if args.second_translate_x is not None:
    if before is None or not math.isfinite(args.second_translate_x) or abs(args.second_translate_x) > 1000:
        raise ValueError('Invalid second input translation')
    before_second = preview(args.before)
    before_second['name'] = f"{before_second['name']} ({args.second_translate_x:+g} X)"
    before_second['positions'][0::3] = [round(value + args.second_translate_x, 7)
                                        for value in before_second['positions'][0::3]]
    before_second['bounds'][0] += args.second_translate_x
    before_second['bounds'][1] += args.second_translate_x
print(json.dumps({'before': before, 'beforeSecond': before_second, 'after': preview(args.after)}, allow_nan=False), flush=True)
