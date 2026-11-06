"""Read Gmsh's OBJ handoff with VTK and check 2D orientation/topology."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from vtkmodules.vtkCommonCore import vtkIdList, vtkVersion
from vtkmodules.vtkIOGeometry import vtkOBJReader


def inspect(path):
    path = Path(path).resolve(strict=True)
    data = path.read_bytes()
    if not data or len(data) > 32 * 1024 * 1024:
        raise ValueError('OBJ handoff is empty or oversized.')
    reader = vtkOBJReader()
    reader.SetFileName(str(path))
    reader.Update()
    mesh = reader.GetOutput()
    points = [mesh.GetPoint(i) for i in range(mesh.GetNumberOfPoints())]
    if not 4 <= len(points) <= 200_000:
        raise ValueError('VTK did not read bounded Gmsh points.')
    faces = []
    ids = vtkIdList()
    polygons = mesh.GetPolys()
    polygons.InitTraversal()
    while polygons.GetNextCell(ids):
        if ids.GetNumberOfIds() != 3:
            raise ValueError('VTK received a non-triangle cell.')
        faces.append(tuple(ids.GetId(i) for i in range(3)))
    if not 2 <= len(faces) <= 400_000:
        raise ValueError('VTK did not read bounded Gmsh triangles.')
    edges = {}
    signed_area = 0.0
    for face in faces:
        if len(set(face)) != 3 or min(face) < 0 or max(face) >= len(points):
            raise ValueError('VTK triangle connectivity is invalid.')
        a, b, c = (points[i] for i in face)
        area = ((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))/2
        if not math.isfinite(area) or area <= 1e-12:
            raise ValueError('VTK triangle orientation is flipped or degenerate.')
        signed_area += area
        for u, v in ((face[0],face[1]),(face[1],face[2]),(face[2],face[0])):
            key = tuple(sorted((u,v)))
            edges[key] = edges.get(key, 0)+1
    bounds = [value for axis in range(3) for value in
              (min(point[axis] for point in points), max(point[axis] for point in points))]
    if any(not math.isfinite(value) for value in bounds):
        raise ValueError('VTK handoff has non-finite bounds.')
    return {'state': 'accepted', 'inputObjSha256': hashlib.sha256(data).hexdigest(),
            'vtkVersion': vtkVersion.GetVTKVersion(), 'points': len(points),
            'triangles': len(faces), 'bounds': bounds, 'signedAreaXY': signed_area,
            'boundaryEdges': sum(v == 1 for v in edges.values()),
            'nonManifoldEdges': sum(v > 2 for v in edges.values())}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--result', required=True)
    parser.add_argument('--expect-reject', action='store_true')
    args = parser.parse_args()
    try:
        report = inspect(args.input)
    except ValueError as error:
        if not args.expect_reject:
            raise
        report = {'state': 'rejected', 'inputObjSha256': hashlib.sha256(Path(args.input).read_bytes()).hexdigest(),
                  'reason': str(error)}
    else:
        if args.expect_reject:
            raise ValueError('Malformed OBJ was accepted by VTK.')
    Path(args.result).write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))
