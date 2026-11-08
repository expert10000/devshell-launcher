"""Broker adapter for the certified fixed-cube Gmsh volume recipe."""
import argparse
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', required=True)
    parser.add_argument('--worker', required=True)
    args = parser.parse_args()
    request = Path(args.request).resolve(strict=True)
    worker = Path(args.worker).resolve(strict=True)
    if worker.name != 'scientific-gmsh-volume-worker.py' or request.name != 'request.json':
        raise ValueError('Only the registered Gmsh volume worker and request are accepted.')
    payload = json.loads(request.read_text(encoding='utf-8'))
    if (payload.get('runtimeId') != 'gmsh-win-conda'
            or payload.get('recipeId') != 'gmsh.volume3d.cube'
            or payload.get('parameters') != {'meshSize': 0.35}):
        raise ValueError('The Gmsh volume request is outside the certified fixed-cube recipe.')
    completed = subprocess.run([sys.executable, str(worker), '--request', str(request)],
                               cwd=request.parent, timeout=payload['timeoutSeconds'],
                               capture_output=True, text=True, encoding='utf-8', errors='replace',
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if completed.stdout:
        print(completed.stdout, end='', flush=True)
    if completed.stderr:
        print(completed.stderr, end='', file=sys.stderr, flush=True)
    if completed.returncode:
        return completed.returncode
    source = request.parent / 'cube.msh'
    exporter = worker.with_name('scientific-gmsh-tetmesh-export.py')
    if not source.is_file() or not exporter.is_file():
        raise ValueError('The Gmsh tetrahedral mesh or registered exporter is missing.')
    exported = subprocess.run([sys.executable, str(exporter), '--input', str(source),
                               '--output', str(request.parent / 'volume.m3dt'),
                               '--result', str(request.parent / 'exporter.json')],
                              cwd=request.parent, timeout=60, capture_output=True, text=True,
                              encoding='utf-8', errors='replace',
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if exported.stdout:
        print(exported.stdout, end='', flush=True)
    if exported.stderr:
        print(exported.stderr, end='', file=sys.stderr, flush=True)
    return exported.returncode


if __name__ == '__main__':
    sys.exit(main())
