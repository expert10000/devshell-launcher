"""Broker adapter for the one certified fixed Gmsh 2D surface."""
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
    if worker.name != 'scientific-gmsh-worker.py' or request.name != 'request.json':
        raise ValueError('Only the registered Gmsh worker and request are accepted.')
    payload = json.loads(request.read_text(encoding='utf-8'))
    if payload.get('runtimeId') != 'gmsh-win-conda' or payload.get('recipeId') != 'gmsh.mesh2d':
        raise ValueError('The Gmsh broker request is outside the certified recipe.')
    command = [sys.executable, str(worker), '--request', str(request)]
    completed = subprocess.run(command, cwd=request.parent, timeout=payload['timeoutSeconds'],
                               capture_output=True, text=True, encoding='utf-8', errors='replace',
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if completed.stdout:
        print(completed.stdout, end='', flush=True)
    if completed.stderr:
        print(completed.stderr, end='', file=sys.stderr, flush=True)
    if completed.returncode:
        return completed.returncode
    source = request.parent / 'l5-positive.msh'
    converter = worker.with_name('scientific-gmsh-handoff.py')
    if not source.is_file() or not converter.is_file():
        raise ValueError('The Gmsh mesh or registered converter is missing.')
    converted = subprocess.run([sys.executable, str(converter), '--input', str(source),
                                '--output', str(request.parent / 'l5-positive.obj'),
                                '--result', str(request.parent / 'conversion.json')],
                               cwd=request.parent, timeout=60, capture_output=True, text=True,
                               encoding='utf-8', errors='replace',
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if converted.stdout:
        print(converted.stdout, end='', flush=True)
    if converted.stderr:
        print(converted.stderr, end='', file=sys.stderr, flush=True)
    return converted.returncode


if __name__ == '__main__':
    sys.exit(main())
