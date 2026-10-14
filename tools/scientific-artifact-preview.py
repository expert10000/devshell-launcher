"""Bounded triangle previews through VTK readers, without executing file content."""
import argparse
import json
import math
import os
from pathlib import Path
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--before')
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


def preview(filename):
    if not filename:
        return None
    path = Path(filename).resolve(strict=True)
    if path.stat().st_size > 67108864:
        raise ValueError('Preview input exceeds 64 MiB')
    readers = {'.obj': vtkOBJReader, '.stl': vtkSTLReader, '.ply': vtkPLYReader, '.vtp': vtkXMLPolyDataReader}
    reader_type = readers.get(path.suffix.lower())
    if not reader_type:
        raise ValueError('Preview supports OBJ/STL/PLY/VTP only')
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


print(json.dumps({'before': preview(args.before), 'after': preview(args.after)}, allow_nan=False), flush=True)
