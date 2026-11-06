"""Independently reload a bounded cube MSH and extract its oriented boundary OBJ."""
import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import sys

if hasattr(os, 'add_dll_directory'):
    folder = Path(sys.prefix) / 'Library/bin'
    if folder.is_dir():
        _dll_handle = os.add_dll_directory(str(folder))
import gmsh


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def subtract(a, b):
    return tuple(x-y for x, y in zip(a, b))


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def inspect(source, output=None):
    source = Path(source).resolve(strict=True)
    if source.suffix.lower() != '.msh' or source.stat().st_size > 32 * 1024 * 1024:
        raise ValueError('Expected a bounded Gmsh MSH volume.')
    gmsh.initialize()
    try:
        gmsh.option.setNumber('General.Terminal', 0)
        gmsh.open(str(source))
        tags, coordinates, _ = gmsh.model.mesh.getNodes()
        kinds, _, groups = gmsh.model.mesh.getElements(3)
        points = {int(tag): tuple(float(v) for v in coordinates[3*i:3*i+3]) for i, tag in enumerate(tags)}
        tets = [tuple(int(v) for v in group[4*i:4*i+4])
                for kind, group in zip(kinds, groups) if int(kind) == 4
                for i in range(len(group)//4)]
    finally:
        gmsh.finalize()
    if (not 8 <= len(points) <= 200_000 or not 6 <= len(tets) <= 400_000
            or any(int(kind) != 4 for kind in kinds)
            or any(not all(math.isfinite(v) for v in point) for point in points.values())):
        raise ValueError('Volume nodes or element types are outside the cube contract.')
    faces = {}
    volume = 0.0
    for tet in tets:
        if len(set(tet)) != 4 or any(tag not in points for tag in tet):
            raise ValueError('Tetrahedron connectivity is invalid.')
        a, b, c, d = (points[tag] for tag in tet)
        signed = dot(subtract(b, a), cross(subtract(c, a), subtract(d, a))) / 6
        if abs(signed) <= 1e-12:
            raise ValueError('Degenerate tetrahedron.')
        volume += abs(signed)
        for face, opposite in (((tet[0],tet[1],tet[2]),tet[3]),
                               ((tet[0],tet[1],tet[3]),tet[2]),
                               ((tet[0],tet[2],tet[3]),tet[1]),
                               ((tet[1],tet[2],tet[3]),tet[0])):
            p, q, r = (points[tag] for tag in face)
            if dot(cross(subtract(q,p), subtract(r,p)), subtract(points[opposite],p)) > 0:
                face = (face[0], face[2], face[1])
            faces.setdefault(tuple(sorted(face)), []).append(face)
    if any(len(group) > 2 for group in faces.values()):
        raise ValueError('Nonmanifold tetrahedron face.')
    boundary = [group[0] for group in faces.values() if len(group) == 1]
    edges = Counter(tuple(sorted((u,v))) for face in boundary
                    for u,v in ((face[0],face[1]),(face[1],face[2]),(face[2],face[0])))
    area = sum(math.sqrt(dot(cross(subtract(points[b], points[a]), subtract(points[c], points[a])),
                             cross(subtract(points[b], points[a]), subtract(points[c], points[a]))))/2
               for a,b,c in boundary)
    bounds = [value for axis in range(3) for value in
              (min(p[axis] for p in points.values()), max(p[axis] for p in points.values()))]
    if (any(abs(value-target) > 1e-6 for value,target in zip(bounds,(0,1,0,1,0,1)))
            or abs(volume-1) > 1e-6 or abs(area-6) > 1e-5
            or any(count != 2 for count in edges.values()) or len(boundary) < 12):
        raise ValueError('Cube volume, boundary orientation or topology changed.')
    shell = sorted({tag for face in boundary for tag in face})
    report = {'format': 'msh', 'sourceMshSha256': sha(source), 'gmshVersion': gmsh.__version__,
              'points': len(points), 'tetrahedra': len(tets), 'boundaryPoints': len(shell),
              'boundaryTriangles': len(boundary), 'boundaryEdges': sum(v == 1 for v in edges.values()),
              'nonManifoldEdges': sum(v > 2 for v in edges.values()),
              'bounds': bounds, 'volume': volume, 'surfaceArea': area,
              'parserSourceSha256': sha(__file__)}
    if output is not None:
        output = Path(output).resolve()
        if output.exists():
            raise ValueError('Boundary OBJ would overwrite an existing artifact.')
        output.parent.mkdir(parents=True, exist_ok=True)
        indices = {tag:i+1 for i,tag in enumerate(shell)}
        lines = ['# Gmsh candidate unit-cube boundary, outward triangles']
        lines.extend('v '+' '.join(format(v,'.17g') for v in points[tag]) for tag in shell)
        lines.extend('f '+' '.join(str(indices[tag]) for tag in face) for face in boundary)
        output.write_text('\n'.join(lines)+'\n', encoding='utf-8')
        report['outputObjSha256'] = sha(output)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output')
    parser.add_argument('--result', required=True)
    args = parser.parse_args()
    result = inspect(args.input, args.output)
    Path(args.result).write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))
