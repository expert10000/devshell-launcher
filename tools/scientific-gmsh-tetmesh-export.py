"""Export a bounded Gmsh tetrahedral MSH to the MATH3D M3DT v1 resource."""
import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import sys

if hasattr(os, 'add_dll_directory'):
    dlls = Path(sys.prefix) / 'Library/bin'
    if dlls.is_dir():
        _dll_handle = os.add_dll_directory(str(dlls))
import gmsh


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def signed_volume(a, b, c, d):
    u = [b[i] - a[i] for i in range(3)]
    v = [c[i] - a[i] for i in range(3)]
    w = [d[i] - a[i] for i in range(3)]
    return (u[0] * (v[1] * w[2] - v[2] * w[1])
            - u[1] * (v[0] * w[2] - v[2] * w[0])
            + u[2] * (v[0] * w[1] - v[1] * w[0])) / 6


def export(source, output, report_path):
    source = Path(source).resolve(strict=True)
    output = Path(output).resolve()
    report_path = Path(report_path).resolve()
    if source.suffix.lower() != '.msh' or source.stat().st_size > 32 * 1024 * 1024:
        raise ValueError('A bounded Gmsh MSH is required.')
    if output.exists() or report_path.exists():
        raise ValueError('Product resource or report would overwrite evidence.')
    gmsh.initialize()
    try:
        gmsh.option.setNumber('General.Terminal', 0)
        gmsh.open(str(source))
        node_tags, coordinates, _ = gmsh.model.mesh.getNodes()
        kinds, element_tags, groups = gmsh.model.mesh.getElements(3)
    finally:
        gmsh.finalize()
    if not 8 <= len(node_tags) <= 200_000 or any(int(kind) != 4 for kind in kinds):
        raise ValueError('Only bounded four-node tetrahedra are supported.')
    nodes = {int(tag): tuple(float(value) for value in coordinates[3*i:3*i+3])
             for i, tag in enumerate(node_tags)}
    if len(nodes) != len(node_tags) or any(not all(math.isfinite(value) for value in point) for point in nodes.values()):
        raise ValueError('Node tags or coordinates are invalid.')
    ordered_tags = sorted(nodes)
    index = {tag: offset for offset, tag in enumerate(ordered_tags)}
    elements = sorted((int(tag), tuple(int(value) for value in group[4*i:4*i+4]))
                      for tags, group in zip(element_tags, groups)
                      for i, tag in enumerate(tags))
    if not 6 <= len(elements) <= 400_000 or len({tag for tag, _ in elements}) != len(elements):
        raise ValueError('Tetrahedral element tags are invalid.')
    cells = []
    volume = 0.0
    faces = Counter()
    for _, tagged in elements:
        if len(set(tagged)) != 4 or any(tag not in nodes for tag in tagged):
            raise ValueError('Tetrahedron connectivity is invalid.')
        cell = [index[tag] for tag in tagged]
        points = [nodes[tag] for tag in tagged]
        signed = signed_volume(*points)
        if abs(signed) <= 1e-12:
            raise ValueError('Degenerate tetrahedron.')
        if signed < 0:
            cell[1], cell[2] = cell[2], cell[1]
        volume += abs(signed)
        cells.append(cell)
        for face in ((cell[0], cell[1], cell[2]), (cell[0], cell[1], cell[3]),
                     (cell[0], cell[2], cell[3]), (cell[1], cell[2], cell[3])):
            faces[tuple(sorted(face))] += 1
    if any(count > 2 for count in faces.values()):
        raise ValueError('Nonmanifold tetrahedral face.')
    boundary = [face for face, count in faces.items() if count == 1]
    if abs(volume - 1) > 1e-6 or len(boundary) < 12:
        raise ValueError('Fixed-cube volume or boundary changed.')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream:
        stream.write(struct.pack('<4sIII', b'M3DT', 1, len(ordered_tags), len(cells)))
        for tag in ordered_tags:
            stream.write(struct.pack('<3d', *nodes[tag]))
        for cell in cells:
            stream.write(struct.pack('<4I', *cell))
    expected_length = 16 + 24 * len(ordered_tags) + 16 * len(cells)
    if output.stat().st_size != expected_length:
        raise ValueError('M3DT resource length changed.')
    report = {'schemaVersion': 1, 'format': 'M3DT', 'version': 1,
              'sourceMshSha256': sha(source), 'resourceSha256': sha(output),
              'points': len(ordered_tags), 'tetrahedra': len(cells),
              'boundaryTriangles': len(boundary), 'volume': volume,
              'bytes': expected_length, 'exporterSha256': sha(__file__)}
    report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--result', required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.input, args.output, args.result)))
