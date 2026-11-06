"""Independently reload the fixed Gmsh surface for the managed L6 gate."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy

convert = runpy.run_path(str(Path(__file__).with_name("scientific-gmsh-handoff.py")))["convert"]


def inspect(source: Path, scratch: Path) -> dict:
    try:
        metrics = convert(source, scratch)
        return {
            "parserVersion": 1,
            "format": "msh",
            "artifactSha256": metrics["sourceMshSha256"],
            "parserSourceSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "points": metrics["points"],
            "triangles": metrics["triangles"],
            "bounds": metrics["bounds"],
            "boundaryEdges": metrics["boundaryEdges"],
            "nonManifoldEdges": metrics["nonManifoldEdges"],
            "signedAreaXY": metrics["signedAreaXY"],
            "gmshVersion": metrics["gmshVersion"],
        }
    finally:
        scratch.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    args = parser.parse_args()
    report = inspect(args.input, args.result.with_suffix(".scratch.obj"))
    args.result.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
