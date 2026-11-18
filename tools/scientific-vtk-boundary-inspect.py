"""Candidate typed inspection and offscreen preview of a Gmsh volume boundary."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys


HEX = re.compile(r'^[0-9a-f]{64}$')
RUN = re.compile(r'^[0-9a-f]{32}$')
COMMIT = re.compile(r'^[0-9a-f]{40}$')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect(request_path):
    request_path = Path(request_path).resolve(strict=True)
    if request_path.stat().st_size > 65536:
        raise ValueError('VTK request exceeds 64 KiB.')
    request = json.loads(request_path.read_text(encoding='utf-8'))
    directory = request_path.parent
    if (request.get('schemaVersion') != 1 or request.get('operation') != 'mesh.inspect'
            or request.get('workingDirectory') != str(directory)
            or not RUN.fullmatch(request.get('runId', '')) or not RUN.fullmatch(request.get('sourceRunId', ''))
            or not COMMIT.fullmatch(request.get('sourceCommit', ''))
            or not HEX.fullmatch(request.get('sourceSnapshotSha256', ''))
            or request.get('inputId') != 'gmsh-boundary'
            or request.get('lengthUnit') not in ('m', 'mm')
            or not isinstance(request.get('frame'), str) or not request['frame']):
        raise ValueError('Invalid typed VTK inspection request.')
    record = request.get('inputArtifact')
    if not isinstance(record, dict) or not HEX.fullmatch(record.get('sha256', '')):
        raise ValueError('Gmsh boundary hash is missing.')
    root = Path(request.get('artifactRoot', '')).resolve(strict=True)
    source = Path(record.get('path', '')).resolve(strict=True)
    if (not source.is_relative_to(root) or source.suffix.lower() != '.obj' or not source.is_file()
            or source.stat().st_size > 32 * 1024 * 1024 or source.stat().st_size != record.get('bytes')
            or sha(source) != record['sha256']):
        raise ValueError('Gmsh boundary is outside the registered root, too large, or changed.')
    output = directory / 'analysis.vtp'
    preview = directory / 'preview.png'
    if output.exists() or preview.exists() or (directory / 'results.json').exists():
        raise ValueError('VTK inspection output already exists.')
    if hasattr(os, 'add_dll_directory'):
        folder = Path(sys.prefix) / 'Library/bin'
        if folder.is_dir():
            _dll_handle = os.add_dll_directory(str(folder))
    import vtk
    reader = vtk.vtkOBJReader()
    reader.SetFileName(str(source))
    reader.Update()
    triangles = vtk.vtkTriangleFilter()
    triangles.SetInputConnection(reader.GetOutputPort())
    triangles.Update()
    mesh = triangles.GetOutput()
    points, faces = mesh.GetNumberOfPoints(), mesh.GetNumberOfPolys()
    if not 4 <= points <= 200000 or not 4 <= faces <= 400000:
        raise ValueError('VTK boundary counts are outside the inspection budget.')
    bounds = list(mesh.GetBounds())
    if not all(math.isfinite(value) for value in bounds):
        raise ValueError('VTK boundary bounds are non-finite.')
    feature = vtk.vtkFeatureEdges()
    feature.SetInputData(mesh)
    feature.FeatureEdgesOff()
    feature.ManifoldEdgesOff()
    feature.BoundaryEdgesOn()
    feature.NonManifoldEdgesOn()
    feature.Update()
    if feature.GetOutput().GetNumberOfCells() != 0:
        raise ValueError('VTK boundary is open or nonmanifold.')
    mass = vtk.vtkMassProperties()
    mass.SetInputData(mesh)
    mass.Update()
    area, volume = mass.GetSurfaceArea(), mass.GetVolume()
    if not math.isfinite(area) or area <= 0 or not math.isfinite(volume) or volume <= 0:
        raise ValueError('VTK mass properties are invalid.')
    writer = vtk.vtkXMLPolyDataWriter()
    writer.SetFileName(str(output))
    writer.SetInputData(mesh)
    writer.SetDataModeToAppended()
    writer.SetEncodeAppendedData(1)
    if writer.Write() != 1:
        raise ValueError('VTK could not save the analysis VTP.')
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(mesh)
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    actor.GetProperty().SetColor(0.28, 0.73, 0.84)
    renderer = vtk.vtkRenderer()
    renderer.SetBackground(0.08, 0.12, 0.18)
    renderer.AddActor(actor)
    renderer.ResetCamera()
    window = vtk.vtkRenderWindow()
    window.SetOffScreenRendering(1)
    window.SetSize(640, 480)
    window.AddRenderer(renderer)
    window.Render()
    capture = vtk.vtkWindowToImageFilter()
    capture.SetInput(window)
    capture.Update()
    png = vtk.vtkPNGWriter()
    png.SetFileName(str(preview))
    png.SetInputConnection(capture.GetOutputPort())
    png.Write()
    if not preview.is_file() or preview.stat().st_size < 100 or not preview.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('VTK could not save the preview PNG.')
    window.Finalize()
    if output.stat().st_size > 32 * 1024 * 1024 or preview.stat().st_size > 8 * 1024 * 1024:
        raise ValueError('VTK output exceeds the inspection budget.')
    result = {'schemaVersion': 1, 'runId': request['runId'], 'operation': 'mesh.inspect',
              'state': 'succeeded', 'sourceRunId': request['sourceRunId'],
              'sourceCommit': request['sourceCommit'], 'sourceSnapshotSha256': request['sourceSnapshotSha256'],
              'inputHashes': {'gmsh-boundary': record['sha256']},
              'outputHashes': {'vtk-analysis': sha(output)}, 'lengthUnit': request['lengthUnit'],
              'frame': request['frame'], 'points': points, 'triangles': faces,
              'boundaryEdges': 0, 'nonManifoldEdges': 0, 'surfaceArea': area,
              'areaUnit': request['lengthUnit'] + '2', 'enclosedVolume': volume,
              'volumeUnit': request['lengthUnit'] + '3', 'bounds': bounds,
              'vtkVersion': vtk.vtkVersion.GetVTKVersion(),
              'output': {'path': 'analysis.vtp', 'bytes': output.stat().st_size, 'sha256': sha(output)},
              'preview': {'path': 'preview.png', 'bytes': preview.stat().st_size, 'sha256': sha(preview)}}
    with (directory / 'results.json').open('x', encoding='utf-8') as stream:
        json.dump(result, stream, allow_nan=False, sort_keys=True)
        stream.write('\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', required=True)
    arguments = parser.parse_args()
    print(json.dumps(inspect(arguments.request), allow_nan=False, sort_keys=True))
