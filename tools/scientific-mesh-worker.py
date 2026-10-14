"""Structured VTK worker: registered operations, scoped artifacts, no shell."""
import argparse
import json
import math
import os
from pathlib import Path
import sys
import time
from scientific_worker_contract import ScientificContract

parser = argparse.ArgumentParser()
parser.add_argument('--request', required=True)
args = parser.parse_args()
contract = ScientificContract(args.request, 'vtk-win-conda', ('mesh.inspect', 'mesh.simplify', 'mesh.normals'))
request = contract.request
recipe = contract.recipe
directory = contract.directory
input_path = contract.input
output_name = contract.output_name
output_path = contract.output
parameters = request.get('parameters', {})
handles = []
if hasattr(os, 'add_dll_directory'):
    for folder in (Path(sys.prefix), Path(sys.prefix) / 'Library' / 'bin'):
        if folder.is_dir():
            handles.append(os.add_dll_directory(str(folder)))
from vtkmodules.vtkCommonCore import vtkVersion
from vtkmodules.vtkFiltersCore import vtkDecimatePro, vtkFeatureEdges, vtkPolyDataNormals, vtkTriangleFilter
from vtkmodules.vtkIOGeometry import vtkOBJReader, vtkSTLReader
from vtkmodules.vtkIOPLY import vtkPLYReader
from vtkmodules.vtkIOXML import vtkXMLPolyDataReader, vtkXMLPolyDataWriter
contract.versions = {'vtk': vtkVersion.GetVTKVersion()}

start = time.monotonic()
readers = {'.obj': vtkOBJReader, '.stl': vtkSTLReader, '.ply': vtkPLYReader, '.vtp': vtkXMLPolyDataReader}
reader_type = readers.get(input_path.suffix.lower())
if not reader_type:
    raise ValueError('Only OBJ, STL, PLY, VTP supported')
messages = []


def observe(obj):
    obj.AddObserver('ErrorEvent', lambda caller, event: messages.append(f'{caller.GetClassName()}: error'))
    obj.AddObserver('WarningEvent', lambda caller, event: print(f'Warning: {caller.GetClassName()}', file=sys.stderr))
    return obj


reader = observe(reader_type())
reader.SetFileName(str(input_path))
reader.Update()
source = reader.GetOutput()
if messages or reader.GetErrorCode() != 0 or source.GetNumberOfPoints() == 0 or source.GetNumberOfPolys() == 0:
    raise ValueError('Reader failed or surface is empty: ' + '; '.join(messages))
triangles = observe(vtkTriangleFilter())
triangles.SetInputData(source)
triangles.PassLinesOff()
triangles.PassVertsOff()
triangles.Update()
mesh = triangles.GetOutput()


def edge_count(data, boundary=False, non_manifold=False):
    edges = observe(vtkFeatureEdges())
    edges.SetInputData(data)
    edges.FeatureEdgesOff()
    edges.ManifoldEdgesOff()
    edges.SetBoundaryEdges(boundary)
    edges.SetNonManifoldEdges(non_manifold)
    edges.Update()
    return edges.GetOutput().GetNumberOfCells()


before = {'points': mesh.GetNumberOfPoints(), 'triangles': mesh.GetNumberOfPolys(),
          'boundaryEdges': edge_count(mesh, boundary=True), 'nonManifoldEdges': edge_count(mesh, non_manifold=True)}
if recipe == 'mesh.simplify':
    reduction = parameters.get('targetReduction', 0.5)
    if isinstance(reduction, bool) or not isinstance(reduction, (int, float)) or not math.isfinite(reduction) or not 0 <= reduction <= 0.95:
        raise ValueError('Target reduction must be between 0 and 0.95')
    for key in ('preserveTopology', 'preserveBoundary'):
        if key in parameters and not isinstance(parameters[key], bool):
            raise ValueError(f'{key} must be boolean')
    operation = observe(vtkDecimatePro())
    operation.SetInputData(mesh)
    operation.SetTargetReduction(reduction)
    operation.SetPreserveTopology(parameters.get('preserveTopology', True))
    operation.SetBoundaryVertexDeletion(not parameters.get('preserveBoundary', True))
    operation.Update()
    mesh = operation.GetOutput()
elif recipe == 'mesh.normals':
    angle = parameters.get('featureAngle', 30)
    if isinstance(angle, bool) or not isinstance(angle, (int, float)) or not math.isfinite(angle) or not 0 <= angle <= 180:
        raise ValueError('Feature angle must be between 0 and 180')
    if 'autoOrient' in parameters and not isinstance(parameters['autoOrient'], bool):
        raise ValueError('Auto orientation must be boolean')
    if parameters.get('autoOrient', False) and (before['boundaryEdges'] or before['nonManifoldEdges']):
        raise ValueError('Auto orientation requires a closed manifold surface')
    operation = observe(vtkPolyDataNormals())
    operation.SetInputData(mesh)
    operation.SetFeatureAngle(angle)
    operation.ConsistencyOn()
    operation.SetAutoOrientNormals(parameters.get('autoOrient', False))
    operation.SplittingOff()
    operation.Update()
    mesh = operation.GetOutput()
if messages or mesh.GetNumberOfPoints() == 0 or mesh.GetNumberOfPolys() == 0:
    raise ValueError('Operation failed or surface is empty')
writer = observe(vtkXMLPolyDataWriter())
writer.SetFileName(str(output_path))
writer.SetInputData(mesh)
if writer.Write() != 1 or messages:
    raise ValueError('Output write failed')
contract.finish(before=before, after={'points': mesh.GetNumberOfPoints(), 'triangles': mesh.GetNumberOfPolys(),
                                    'boundaryEdges': edge_count(mesh, boundary=True), 'nonManifoldEdges': edge_count(mesh, non_manifold=True)},
                capabilities=['geometry.polydata', 'mesh.read', 'mesh.write'] + (['mesh.filter'] if recipe != 'mesh.inspect' else []),
                scope='Basic triangulated-surface statistics only; no self-intersection or full mesh-validity guarantee.')
