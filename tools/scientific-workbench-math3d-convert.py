"""Convert a hash-verified Workbench OBJ/VTP result to MATH3D's bounded OBJ intake."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from vtkmodules.vtkIOGeometry import vtkOBJReader
from vtkmodules.vtkIOXML import vtkXMLPolyDataReader
from vtkmodules.vtkCommonCore import vtkIdList


def sha(data):
    return hashlib.sha256(data).hexdigest()


def convert(source, expected, output):
    source = Path(source).resolve(strict=True)
    output = Path(output).resolve()
    if source.suffix.lower() not in ('.obj', '.vtp'):
        raise ValueError('Only saved OBJ and VTP Workbench results can enter MATH3D.')
    data = source.read_bytes()
    if not data or len(data) > 32 * 1024 * 1024 or sha(data) != expected:
        raise ValueError('Saved Workbench artifact is empty, oversized, or changed.')
    reader = vtkOBJReader() if source.suffix.lower() == '.obj' else vtkXMLPolyDataReader()
    reader.SetFileName(str(source))
    reader.Update()
    mesh = reader.GetOutput()
    count = mesh.GetNumberOfPoints()
    polys = mesh.GetPolys()
    triangles = polys.GetNumberOfCells()
    if count < 3 or count > 200_000 or triangles < 1 or triangles > 400_000:
        raise ValueError('Saved surface exceeds the MATH3D handoff topology bound.')
    points = [mesh.GetPoint(i) for i in range(count)]
    if any(not all(math.isfinite(value) for value in point) for point in points):
        raise ValueError('Saved surface has non-finite coordinates.')
    ids = vtkIdList()
    polys.InitTraversal()
    faces = []
    while polys.GetNextCell(ids):
        face = [ids.GetId(i) for i in range(ids.GetNumberOfIds())]
        if len(face) != 3 or len(set(face)) != 3 or min(face) < 0 or max(face) >= count:
            raise ValueError('Saved surface has invalid or non-triangular faces.')
        faces.append(face)
    lines = [f'v {point[0]:.17g} {point[1]:.17g} {point[2]:.17g}' for point in points]
    lines += [f'f {a + 1} {b + 1} {c + 1}' for a, b, c in faces]
    encoded = ('\n'.join(lines) + '\n').encode('ascii')
    if len(encoded) > 32 * 1024 * 1024:
        raise ValueError('Converted OBJ exceeds the MATH3D importer budget.')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(encoded)
    report = {'schemaVersion': 1, 'kind': 'scientific.workbench-math3d-conversion',
              'sourceArtifactSha256': expected, 'sourceFormat': source.suffix.lower()[1:],
              'objSha256': sha(encoded), 'points': count, 'triangles': triangles}
    (output.parent / 'conversion.json').write_text(json.dumps(report, sort_keys=True), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--expected-sha', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(convert(args.source, args.expected_sha, args.output)))
