"""Test-only child process and partial output fixture for supervisor cleanup checks."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time


parser = argparse.ArgumentParser()
parser.add_argument('--request', required=True)
parser.add_argument('--worker', required=True)
args = parser.parse_args()
request = json.loads(Path(args.request).read_text(encoding='utf-8'))
directory = Path(request['workingDirectory'])
if directory != Path(args.request).parent or request['runtimeId'] != 'cgal-win-conda':
    raise ValueError('Diagnostic worker must stay in its broker-owned directory.')
mode = os.environ.get('SCIENTIFIC_BROKER_DIAGNOSTIC_MODE')
if mode not in ('hold', 'orphan'):
    raise ValueError('Diagnostic worker mode must be hold or orphan.')
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], cwd=directory,
                         creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
(directory / 'diagnostic-child.json').write_text(json.dumps({'pid': child.pid, 'mode': mode}))
(directory / 'l5-positive.obj').write_text('partial diagnostic output\n')
if mode == 'orphan':
    time.sleep(0.5)
    sys.exit(1)
time.sleep(30)
