"""Invoke only the configured VTK mesh worker through the broker's typed request."""
import argparse
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', required=True)
    parser.add_argument('--worker', required=True)
    options = parser.parse_args()
    request = Path(options.request).resolve(strict=True)
    worker = Path(options.worker).resolve(strict=True)
    if request.name != 'request.json' or worker.name != 'scientific-mesh-worker.py':
        raise ValueError('The VTK broker adapter requires its registered request and worker.')
    return subprocess.run([sys.executable, str(worker), '--request', str(request)],
                          cwd=request.parent, check=False).returncode


if __name__ == '__main__':
    sys.exit(main())
