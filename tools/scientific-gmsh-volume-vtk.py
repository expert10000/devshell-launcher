"""Validate the candidate cube boundary OBJ through VTK's reader."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
from vtkmodules.vtkCommonCore import vtkIdList, vtkVersion
from vtkmodules.vtkIOGeometry import vtkOBJReader


def check(path):
    path = Path(path).resolve(strict=True)
    data = path.read_bytes()
    if not data or len(data) > 32 * 1024 * 1024:
        raise ValueError('OBJ boundary is empty or oversized.')
    reader = vtkOBJReader()
    reader.SetFileName(str(path))
    reader.Update()
    mesh = reader.GetOutput()
    points = [mesh.GetPoint(i) for i in range(mesh.GetNumberOfPoints())]
    ids = vtkIdList()
    faces = []
    polygons = mesh.GetPolys()
    polygons.InitTraversal()
    while polygons.GetNextCell(ids):
        if ids.GetNumberOfIds() != 3:
            raise ValueError('VTK boundary has a non-triangle face.')
        faces.append(tuple(ids.GetId(i) for i in range(3)))
    if not 8 <= len(points) <= 200_000 or not 12 <= len(faces) <= 400_000:
        raise ValueError('VTK boundary has invalid counts.')
    edges = Counter()
    area = volume = 0.0
    for face in faces:
        if len(set(face)) != 3 or min(face) < 0 or max(face) >= len(points):
            raise ValueError('VTK boundary has invalid connectivity.')
        a,b,c = (points[i] for i in face)
        u = [b[i]-a[i] for i in range(3)]
        v = [c[i]-a[i] for i in range(3)]
        n = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
        center = [(a[i]+b[i]+c[i])/3 - 0.5 for i in range(3)]
        if sum(n[i]*center[i] for i in range(3)) <= 1e-9:
            raise ValueError('VTK boundary orientation is inward or degenerate.')
        area += math.sqrt(sum(x*x for x in n))/2
        volume += sum(a[i]*n[i] for i in range(3))/6
        edges.update(tuple(sorted(edge)) for edge in ((face[0],face[1]),(face[1],face[2]),(face[2],face[0])))
    bounds = [value for axis in range(3) for value in
              (min(p[axis] for p in points), max(p[axis] for p in points))]
    if (any(abs(x-y) > 1e-6 for x,y in zip(bounds,(0,1,0,1,0,1)))
            or abs(area-6) > 1e-5 or abs(volume-1) > 1e-5 or any(v != 2 for v in edges.values())):
        raise ValueError('VTK boundary geometry or topology differs from the unit cube.')
    return {'state':'accepted','inputObjSha256':hashlib.sha256(data).hexdigest(),
            'vtkVersion':vtkVersion.GetVTKVersion(),'points':len(points),'triangles':len(faces),
            'bounds':bounds,'surfaceArea':area,'signedVolume':volume,
            'boundaryEdges':sum(v==1 for v in edges.values()),
            'nonManifoldEdges':sum(v>2 for v in edges.values())}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input',required=True)
    parser.add_argument('--result',required=True)
    parser.add_argument('--expect-reject',action='store_true')
    args = parser.parse_args()
    try:
        result = check(args.input)
    except ValueError as error:
        if not args.expect_reject:
            raise
        result = {'state':'rejected','inputObjSha256':hashlib.sha256(Path(args.input).read_bytes()).hexdigest(),
                  'reason':str(error)}
    else:
        if args.expect_reject:
            raise ValueError('Invalid cube boundary was accepted by VTK.')
    Path(args.result).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))
