"""Read a saved CGAL OBJ with VTK and report bounded semantic mesh evidence."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from vtkmodules.vtkIOGeometry import vtkOBJReader
from vtkmodules.vtkCommonCore import vtkVersion


def inspect(path):
    data = path.read_bytes()
    if not data or len(data) > 32 * 1024 * 1024:
        raise ValueError("OBJ is empty or exceeds the VTK handoff budget")
    reader = vtkOBJReader()
    reader.SetFileName(str(path))
    reader.Update()
    mesh = reader.GetOutput()
    count = mesh.GetNumberOfPoints()
    cells = mesh.GetPolys()
    if count < 1 or count > 200_000 or cells.GetNumberOfCells() < 1 or cells.GetNumberOfCells() > 400_000:
        raise ValueError("VTK rejected empty or oversized mesh topology")
    points = [mesh.GetPoint(index) for index in range(count)]
    faces = []
    cells.InitTraversal()
    from vtkmodules.vtkCommonCore import vtkIdList
    ids = vtkIdList()
    while cells.GetNextCell(ids):
        if ids.GetNumberOfIds() != 3:
            raise ValueError("VTK mesh contains a non-triangular face")
        faces.append(tuple(ids.GetId(index) for index in range(3)))
    edges = {}
    signed_volume = 0.0
    surface_area = 0.0
    for a, b, c in faces:
        if min(a, b, c) < 0 or max(a, b, c) >= count or len({a, b, c}) != 3:
            raise ValueError("VTK mesh contains invalid face indices")
        pa, pb, pc = points[a], points[b], points[c]
        ab = [pb[index] - pa[index] for index in range(3)]
        ac = [pc[index] - pa[index] for index in range(3)]
        cross = (ab[1] * ac[2] - ab[2] * ac[1], ab[2] * ac[0] - ab[0] * ac[2], ab[0] * ac[1] - ab[1] * ac[0])
        area = math.sqrt(sum(value * value for value in cross)) / 2
        if not math.isfinite(area) or area <= 1e-12:
            raise ValueError("VTK mesh has a degenerate face")
        surface_area += area
        signed_volume += sum(pa[index] * cross[index] for index in range(3)) / 6
        for left, right in ((a, b), (b, c), (c, a)):
            key = tuple(sorted((left, right)))
            edges[key] = edges.get(key, 0) + 1
    bounds = [value for axis in range(3) for value in
              (min(point[axis] for point in points), max(point[axis] for point in points))]
    if any(not math.isfinite(value) for value in bounds):
        raise ValueError("VTK mesh contains non-finite coordinates")
    return {"consumer": "VTK vtkOBJReader", "consumerVersion": 1,
            "vtkVersion": vtkVersion.GetVTKVersion(), "format": "obj",
            "readerSourceSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "inputObjSha256": hashlib.sha256(data).hexdigest(),
            "points": count, "triangles": len(faces), "bounds": bounds,
            "boundaryEdges": sum(value == 1 for value in edges.values()),
            "nonManifoldEdges": sum(value > 2 for value in edges.values()),
            "closed": all(value == 2 for value in edges.values()),
            "signedVolume": signed_volume, "surfaceArea": surface_area}


def main():
    arguments = argparse.ArgumentParser()
    arguments.add_argument("--input", required=True)
    arguments.add_argument("--result", required=True)
    arguments.add_argument("--expect-reject", action="store_true")
    options = arguments.parse_args()
    path = Path(options.input).resolve(strict=True)
    try:
        report = inspect(path)
    except ValueError as error:
        if not options.expect_reject:
            raise
        report = {"consumer": "VTK vtkOBJReader", "consumerVersion": 1,
                  "readerSourceSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  "inputObjSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                  "state": "rejected", "reason": str(error)}
    else:
        if options.expect_reject:
            raise ValueError("Malformed OBJ was unexpectedly accepted by VTK")
    output = Path(options.result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    main()
