import importlib.util
from pathlib import Path
import socket
import tempfile

repo = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('service_control', repo / 'BatchLauncher/service_control.py')
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)
opened = []
service.webbrowser.open = opened.append

with tempfile.TemporaryDirectory(prefix='devshell-service-test-') as root:
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen()
        port = listener.getsockname()[1]
        assert service.status(root, port)['state'] == 'blocked'
        assert service.stop(root, port)['state'] == 'blocked'
        assert service.start(root, port)['state'] == 'blocked'
        assert listener.fileno() >= 0
        print('PASS: unrelated listener is blocked and left alone', flush=True)
    try:
        assert service.status(root, port)['state'] == 'stopped'
        assert service.start(root, port)['state'] == 'running'
        first = service.find_server(root, port)
        assert first and first.get('token')
        assert service.start(root, port)['state'] == 'running'
        assert service.find_server(root, port)['pid'] == first['pid']
        assert len(opened) == 2
        notebook = Path(root) / 'example notebook.ipynb'
        notebook.write_text('{}', encoding='utf-8')
        assert service.start(root, port, notebook.name)['state'] == 'running'
        assert '/lab/tree/example%20notebook.ipynb?' in opened[-1]
        assert service.find_server(root, port)['pid'] == first['pid']
        try:
            service.start(root, port, '../outside.ipynb')
        except ValueError:
            pass
        else:
            raise AssertionError('Outside-workspace path accepted')
        print('PASS: authenticated notebook link and workspace path boundary', flush=True)
        print('PASS: authenticated startup and repeated Start reuses server', flush=True)
        other = str(Path(root) / 'other')
        assert service.stop(other, port)['state'] == 'blocked'
        assert service.find_server(root, port)['pid'] == first['pid']
        print('PASS: other workspace cannot stop the server', flush=True)
        assert service.stop(root, port)['state'] == 'stopped'
        assert service.stop(root, port)['state'] == 'stopped'
        assert service.start(root, port)['state'] == 'running'
        assert service.find_server(root, port)['pid'] != first['pid']
        print('PASS: graceful stop, repeated Stop, and restart', flush=True)
    finally:
        service.stop(root, port)
