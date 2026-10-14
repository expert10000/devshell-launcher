"""JSON adapter for the shipped CGAL C++ worker; no command shell."""
import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
from scientific_worker_contract import ScientificContract

parser = argparse.ArgumentParser()
parser.add_argument('--request', required=True)
parser.add_argument('--worker', required=True)
args = parser.parse_args()
contract = ScientificContract(args.request, 'cgal-win-conda', ('cgal.validate', 'cgal.remesh'))
worker = Path(args.worker).resolve(strict=True)
if worker.name.lower() != 'devshell_cgal_worker.exe':
    raise ValueError('Expected the dedicated CGAL worker executable')
if contract.input.suffix.lower() not in ('.obj', '.stl', '.ply', '.off'):
    raise ValueError('Only OBJ/STL/PLY/OFF inputs supported')
parameters = contract.request.get('parameters', {})
remesh = contract.recipe == 'cgal.remesh'
edge = parameters.get('targetEdge', 0.1) if remesh else 0.1
iterations = parameters.get('iterations', 1) if remesh else 1
boundary = parameters.get('preserveBoundary', False) if remesh else False
if isinstance(edge, bool) or not isinstance(edge, (int, float)) or not math.isfinite(edge) or not 0 < edge <= 1000000:
    raise ValueError('Invalid target edge length')
if isinstance(iterations, bool) or not isinstance(iterations, int) or not 1 <= iterations <= 10 or not isinstance(boundary, bool):
    raise ValueError('Invalid iterations or boundary option')
timeout = contract.request.get('timeoutSeconds', 120)
if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 1 <= timeout <= 120:
    raise ValueError('Invalid worker timeout')
command = [str(worker), 'remesh' if remesh else 'validate', str(contract.input), str(contract.output),
           str(edge), str(iterations), '1' if boundary else '0']
process = subprocess.run(command, cwd=contract.directory, timeout=timeout, capture_output=True,
                         text=True, encoding='utf-8', errors='replace', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
if process.stdout:
    print(process.stdout, end='', flush=True)
if process.stderr:
    print(process.stderr, end='', file=sys.stderr, flush=True)
result_file = contract.directory / 'results.json'
engine = json.loads(result_file.read_text(encoding='utf-8-sig')) if result_file.is_file() else {}
contract.versions = engine.get('versions', {})
diagnostics = [] if process.returncode == 0 else [{'severity': 'error', 'message': engine.get('error') or f'CGAL worker exited {process.returncode}'}]
contract.finish(state='succeeded' if process.returncode == 0 else 'failed', exit_code=process.returncode,
                before=engine.get('before'), after=engine.get('after'), diagnostics=diagnostics,
                capabilities=['mesh.read', 'mesh.write', 'mesh.validate'] + (['mesh.remesh'] if remesh else []) if process.returncode == 0 else [],
                scope=engine.get('scope', ''), extra={'engine': 'CGAL C++', 'engineDetails': engine})
sys.exit(process.returncode)
