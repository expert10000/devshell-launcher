"""Jupyter lifecycle control. Only control a server matching this workspace and port."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import psutil


def same_path(left, right):
    return os.path.normcase(os.path.realpath(left)) == os.path.normcase(os.path.realpath(right))


def request(server, endpoint, method='GET'):
    url = server['url'].rstrip('/') + endpoint
    headers = {'Authorization': 'token ' + server.get('token', '')}
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers, method=method), timeout=2)


def find_server(root, port):
    from jupyter_server.serverapp import list_running_servers
    for server in list_running_servers():
        if server.get('port') == port and same_path(server.get('root_dir', ''), root):
            try:
                with request(server, '/api/status') as response:
                    if response.status == 200:
                        return server
            except (OSError, urllib.error.URLError):
                pass
    return None


def port_busy(port):
    with socket.socket() as connection:
        connection.settimeout(0.3)
        return connection.connect_ex(('127.0.0.1', port)) == 0


def status(root, port):
    if find_server(root, port):
        return {'state': 'running', 'message': 'Ready'}
    if port_busy(port):
        return {'state': 'blocked', 'message': 'Port is in use by another server or application.'}
    return {'state': 'stopped', 'message': 'Stopped'}


def stop(root, port):
    server = find_server(root, port)
    if not server:
        return status(root, port)
    try:
        process = psutil.Process(server['pid'])
    except psutil.NoSuchProcess:
        process = None
    try:
        with request(server, '/api/shutdown', 'POST'):
            pass
    except (ConnectionError, urllib.error.URLError):
        pass  # A shutdown can close the HTTP connection before returning a response.
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if not port_busy(port) and (process is None or not process.is_running()):
            return {'state': 'stopped', 'message': 'Stopped'}
        time.sleep(0.25)
    raise RuntimeError('Jupyter has not released its port yet. Check its terminals and retry.')


def start(root, port, lab_path=None):
    target_path = None
    if lab_path:
        target = (Path(root) / lab_path).resolve()
        target_path = target.relative_to(Path(root).resolve()).as_posix()
        if not target.exists():
            raise RuntimeError('The requested Lab file or folder does not exist.')
    server = find_server(root, port)
    if not server:
        if port_busy(port):
            return {'state': 'blocked', 'message': 'Port is in use by another server or application.'}
        log_dir = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'DevShellLauncher' / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f'jupyter-{port}.log'
        with log_path.open('a', encoding='utf-8') as log:
            process = subprocess.Popen(
                [sys.executable, '-m', 'jupyterlab', '--no-browser', '--ip=127.0.0.1',
                 f'--port={port}', '--ServerApp.port_retries=0', f'--ServerApp.root_dir={root}'],
                cwd=root, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            )
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            server = find_server(root, port)
            if server:
                break
            if process.poll() is not None:
                raise RuntimeError(f'Jupyter exited during startup. See {log_path}')
            time.sleep(0.4)
        if not server:
            raise RuntimeError(f'Jupyter is taking longer to start. Refresh status; see {log_path}')
    # Use the discovered token, including when reusing an existing authenticated server.
    route = '/lab/tree/' + urllib.parse.quote(target_path, safe='/') if target_path else '/lab'
    url = server['url'].rstrip('/') + route + '?' + urllib.parse.urlencode({'token': server.get('token', '')})
    webbrowser.open(url)
    return {'state': 'running', 'message': 'Ready — opened Jupyter Lab'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['status', 'start', 'stop', 'restart', 'open'])
    parser.add_argument('--root', required=True)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--path', help='File or folder to open, relative to the workspace root')
    args = parser.parse_args()
    try:
        if not Path(args.root).is_dir():
            raise RuntimeError('Workspace directory does not exist.')
        if args.action == 'status':
            result = status(args.root, args.port)
        elif args.action == 'stop':
            result = stop(args.root, args.port)
        else:
            if args.action == 'restart':
                result = stop(args.root, args.port)
                if result['state'] != 'stopped':
                    print(json.dumps(result))
                    return
            result = start(args.root, args.port, args.path)
        print(json.dumps(result))
    except Exception as error:
        print(json.dumps({'state': 'error', 'message': str(error)}))


if __name__ == '__main__':
    main()
