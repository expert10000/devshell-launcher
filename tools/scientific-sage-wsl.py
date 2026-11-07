"""Windows-to-WSL transport for the version 1 Sage exact worker.

The worker and this adapter are independent of the DevShell desktop process.
All paths passed to WSL are mapped with wslpath and passed as argv, not eval'd.
"""

import argparse
import json
import os
from pathlib import Path
import posixpath
import re
import subprocess
import sys


RUNTIME = 'sage-wsl'
RECIPE = 'sage.exact.v1'
OPERATIONS = ('rational.add', 'polynomial.factor', 'matrix.solve')
DISTRO = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z')
DISCOVER = ('for sage in /usr/bin/sage /usr/local/bin/sage '
            '"$HOME/miniforge3/envs/sage/bin/sage" '
            '"$HOME/mambaforge/envs/sage/bin/sage" '
            '"$HOME/miniconda3/envs/sage/bin/sage"; '
            'do if test -x "$sage"; then printf "%s\\n" "$sage"; exit 0; fi; done; exit 127')


def wsl(distro, *arguments, timeout=60):
    return subprocess.run(['wsl.exe', '-d', distro, '--exec', *arguments],
                          capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)


def wsl_path(distro, path):
    result = wsl(distro, 'wslpath', '-a', str(path.resolve()))
    if result.returncode or not result.stdout.strip().startswith('/'):
        raise RuntimeError('Could not map a Windows path into the selected WSL distribution: ' + result.stderr[-300:])
    return result.stdout.strip()


def discover(distro):
    result = wsl(distro, '/bin/sh', '-c', DISCOVER)
    if result.returncode == 127:
        raise RuntimeError('SageMath is missing from the selected WSL distribution.')
    if result.returncode:
        raise RuntimeError(f'WSL could not start Sage discovery (exit {result.returncode}).')
    sage = result.stdout.strip()
    python = posixpath.join(posixpath.dirname(sage), 'python')
    check = wsl(distro, '/bin/sh', '-c', 'test -x "$1"', 'sage-adapter', python)
    if check.returncode:
        raise RuntimeError('The Sage environment has no sibling Python interpreter: ' + python)
    return sage, python


def handshake(distro):
    sage, python = discover(distro)
    result = wsl(distro, python, '-c', 'from sage.version import version; print(version)', timeout=90)
    if result.returncode:
        raise RuntimeError('Sage Python import failed: ' + result.stderr[-400:])
    return {'schemaVersion': 1, 'runtimeId': RUNTIME, 'backend': 'wsl',
            'distro': distro, 'sageExecutable': sage, 'pythonExecutable': python,
            'sageVersion': result.stdout.strip(), 'recipeId': RECIPE,
            'operations': list(OPERATIONS), 'qualification': 'candidate'}


def transport_failure(request, directory, state, code, message):
    result = {'schemaVersion': 1, 'runId': request.get('runId'), 'runtimeId': RUNTIME,
              'recipeId': RECIPE, 'operation': request.get('operation'), 'state': state,
              'exitCode': None, 'durationMs': None, 'versions': {}, 'validatedCapabilities': [],
              'result': None, 'diagnostics': [{'severity': 'error', 'code': code, 'message': message[:400]}],
              'artifacts': [], 'logReference': 'full.log',
              'scope': 'DS-SCI-016 transport failure; no qualification.'}
    path = directory / 'results.json'
    if not path.exists():
        path.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return json.loads(path.read_text(encoding='utf-8'))


def stop_tree(process):
    if process.poll() is not None:
        return
    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                   capture_output=True, timeout=15)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def run(distro, request_path, timeout):
    request_path = request_path.resolve(strict=True)
    directory = request_path.parent
    if request_path.stat().st_size > 65536 or (directory / 'results.json').exists():
        raise ValueError('Use a fresh run directory with a request no larger than 64 KiB.')
    request = json.loads(request_path.read_text(encoding='utf-8-sig'))
    if not isinstance(request, dict):
        raise ValueError('Request must be a JSON object.')
    declared_timeout = request.get('timeoutSeconds')
    if declared_timeout is not None:
        if isinstance(declared_timeout, bool) or not isinstance(declared_timeout, int) or not 1 <= declared_timeout <= 300:
            raise ValueError('timeoutSeconds must be an integer from 1 to 300.')
        timeout = min(timeout, declared_timeout)
    worker = Path(__file__).with_name('scientific-sage-worker.py')
    if not worker.is_file():
        raise RuntimeError('Sage worker script is missing.')
    try:
        sage, python = discover(distro)
        worker_linux = wsl_path(distro, worker)
        directory_linux = wsl_path(distro, directory)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        return transport_failure(request, directory, 'failed', 'wsl-unavailable', str(error))
    request_linux = directory_linux.rstrip('/') + '/worker-request.json'
    worker_request = dict(request, workingDirectory=directory_linux)
    worker_request_path = directory / 'worker-request.json'
    with worker_request_path.open('x', encoding='utf-8') as stream:
        json.dump(worker_request, stream, indent=2)
        stream.write('\n')
    command = ['wsl.exe', '-d', distro, '--exec', python, worker_linux, '--request', request_linux]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding='utf-8', errors='replace',
                               creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        stop_tree(process)
        stdout, stderr = process.communicate()
        (directory / 'full.log').write_text((stdout + '\n' + stderr)[-65536:], encoding='utf-8')
        return transport_failure(request, directory, 'timed-out', 'transport-timeout',
                                 f'Sage WSL worker exceeded {timeout} seconds.')
    except KeyboardInterrupt:
        stop_tree(process)
        stdout, stderr = process.communicate()
        (directory / 'full.log').write_text((stdout + '\n' + stderr)[-65536:], encoding='utf-8')
        return transport_failure(request, directory, 'cancelled', 'transport-cancelled',
                                 'The owned Sage WSL process was cancelled.')
    (directory / 'full.log').write_text((stdout + '\n' + stderr)[-65536:], encoding='utf-8')
    result_path = directory / 'results.json'
    if not result_path.is_file():
        return transport_failure(request, directory, 'failed', 'transport-error',
                                 f'Sage worker exited {process.returncode} without a typed result: {stderr[-250:]}')
    result = json.loads(result_path.read_text(encoding='utf-8'))
    if result.get('runId') != request.get('runId') or result.get('runtimeId') != RUNTIME:
        raise RuntimeError('Sage worker result does not match its request.')
    if (result.get('state') == 'succeeded') != (process.returncode == 0):
        raise RuntimeError('Sage worker exit status disagrees with its typed result.')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--distro', default=os.environ.get('MATH3D_WSL_DISTRO', 'Ubuntu'))
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('probe')
    execute = commands.add_parser('run')
    execute.add_argument('--request', type=Path, required=True)
    execute.add_argument('--timeout', type=int, default=120)
    args = parser.parse_args()
    if not DISTRO.fullmatch(args.distro):
        parser.error('Invalid WSL distribution name.')
    if args.command == 'probe':
        value = handshake(args.distro)
    else:
        if not 1 <= args.timeout <= 300:
            parser.error('Timeout must be 1 to 300 seconds.')
        value = run(args.distro, args.request, args.timeout)
    print(json.dumps(value, separators=(',', ':'), allow_nan=False))
    return 0 if args.command == 'probe' or value['state'] == 'succeeded' else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        print(f'Sage WSL adapter: {error}', file=sys.stderr)
        sys.exit(1)
