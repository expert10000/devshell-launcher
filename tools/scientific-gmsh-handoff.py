"""Independently reload a bounded Gmsh 2D mesh and export a checked OBJ handoff."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

if hasattr(__import__('os'), 'add_dll_directory'):
    folder = Path(sys.prefix) / 'Library' / 'bin'
    if folder.is_dir():
        _dll_handle = __import__('os').add_dll_directory(str(folder))
import gmsh


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def convert(source, output):
    source = Path(source).resolve(strict=True)
    output = Path(output).resolve()
    if source.stat().st_size > 32 * 1024 * 1024 or output.exists():
        raise ValueError('Gmsh handoff is oversized or would overwrite an artifact.')
    gmsh.initialize()
    try:
        gmsh.option.setNumber('General.Terminal', 0)
        gmsh.open(str(source))
        tags, coordinates, _ = gmsh.model.mesh.getNodes()
        kinds, groups, nodes = gmsh.model.mesh.getElements(2)
        points = {int(tag): tuple(float(value) for value in coordinates[3*i:3*i+3])
                  for i, tag in enumerate(tags)}
        faces = [tuple(int(value) for value in group[3*i:3*i+3])
                 for kind, group in zip(kinds, nodes) if int(kind) == 2
                 for i in range(len(group)//3)]
    finally:
        gmsh.finalize()
    if not 4 <= len(points) <= 200_000 or not 2 <= len(faces) <= 400_000:
        raise ValueError('Gmsh mesh is empty or exceeds the surface budget.')
    if any(not all(math.isfinite(value) for value in point) for point in points.values()):
        raise ValueError('Gmsh mesh has non-finite coordinates.')
    ordered = sorted(points)
    index = {tag: i+1 for i, tag in enumerate(ordered)}
    edges = {}
    signed_area = 0.0
    for face in faces:
        if len(set(face)) != 3 or any(tag not in points for tag in face):
            raise ValueError('Gmsh mesh has invalid triangle connectivity.')
        a, b, c = (points[tag] for tag in face)
        area = ((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))/2
        if area <= 1e-12 or any(abs(p[2]) > 1e-9 for p in (a,b,c)):
            raise ValueError('Gmsh surface is degenerate, flipped or non-planar.')
        signed_area += area
        for u, v in ((face[0],face[1]),(face[1],face[2]),(face[2],face[0])):
            key = tuple(sorted((u,v)))
            edges[key] = edges.get(key, 0)+1
    bounds = [value for axis in range(3) for value in
              (min(point[axis] for point in points.values()), max(point[axis] for point in points.values()))]
    if any(abs(value-expected) > 1e-9 for value, expected in zip(bounds, (0,1,0,1,0,0))):
        raise ValueError('Gmsh surface scale changed.')
    if abs(signed_area-1) > 1e-9 or sum(count > 2 for count in edges.values()):
        raise ValueError('Gmsh surface area or topology changed.')
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = ['# Gmsh fixed-square 2D handoff']
    lines += ['v ' + ' '.join(format(value, '.17g') for value in points[tag]) for tag in ordered]
    lines += ['f ' + ' '.join(str(index[tag]) for tag in face) for face in faces]
    output.write_text('\n'.join(lines)+'\n', encoding='utf-8')
    return {'sourceMshSha256': sha(source), 'outputObjSha256': sha(output),
            'points': len(points), 'triangles': len(faces), 'bounds': bounds,
            'boundaryEdges': sum(value == 1 for value in edges.values()),
            'nonManifoldEdges': sum(value > 2 for value in edges.values()),
            'signedAreaXY': signed_area, 'gmshVersion': gmsh.__version__}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--result', required=True)
    args = parser.parse_args()
    result = convert(args.input, args.output)
    Path(args.result).write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))
