"""Opt-in live HTTP test for the certified guarded-remesh broker profile."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/scientific-broker'))
from broker import Broker, handler_for  # noqa: E402
from http.server import ThreadingHTTPServer  # noqa: E402


def run(config_path):
    broker = Broker(config_path)
    assert broker.capabilities and broker.capabilities[0]['capabilityId'] == 'mesh.remesh'
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(broker))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'

    def call(method, path, body=None):
        payload = json.dumps(body).encode() if body is not None else None
        request = Request(base + path, data=payload, method=method,
                          headers={'Content-Type': 'application/json'} if payload else {})
        try:
            with urlopen(request, timeout=180) as response:
                raw = response.read()
                return json.loads(raw) if response.headers.get_content_type() == 'application/json' else raw
        except HTTPError as error:
            raise AssertionError(f'{method} {path}: {error.code} {error.read().decode()}') from error

    def submit(case_id):
        case = next(item for item in broker.capabilities[0]['referenceCases'] if item['caseId'] == case_id)
        fixture = next(item for item in json.loads((broker.source_root / 'scientific/fixtures/cgal-remesh-qualification/manifest.json').read_text())['cases']
                       if item['caseId'] == case_id)
        source = broker.paths['datasetRoot'] / f'{case_id}.obj'
        shutil.copyfile(broker.source_root / fixture['path'], source)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        assert digest == case['inputSha256']
        return call('POST', '/v1/jobs', {'schemaVersion': 1, 'runtimeId': 'cgal-win-conda',
                    'capabilityId': 'mesh.remesh', 'caseId': case_id,
                    'input': {'path': str(source), 'sha256': digest}, 'timeoutSeconds': 120})['jobId']

    def wait(job_id):
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            job = call('GET', '/v1/jobs/' + job_id)
            if job['state'] != 'running':
                return job
            time.sleep(.1)
        raise AssertionError('Broker job timed out: ' + job_id)

    try:
        providers = call('GET', '/v1/providers')
        assert providers['providers'][0]['capabilities'][0]['capabilityId'] == 'mesh.remesh'
        accepted_id = submit('accepted')
        accepted = wait(accepted_id)
        assert accepted['state'] == 'succeeded', accepted
        output = call('GET', f'/v1/jobs/{accepted_id}/artifacts/remeshed.obj')
        assert hashlib.sha256(output).hexdigest() == broker.capabilities[0]['referenceCases'][0]['outputSha256']
        guard = call('GET', f'/v1/jobs/{accepted_id}/artifacts/guarded.json')
        assert guard['state'] == 'accepted'
        assert call('POST', f'/v1/jobs/{accepted_id}/promote')['decision'] == 'allowed'

        rejected_id = submit('volume-loss')
        rejected = wait(rejected_id)
        assert rejected['state'] == 'rejected', rejected
        assert not (Path(rejected['directory']) / 'remeshed.obj').exists()
        assert call('POST', f'/v1/jobs/{rejected_id}/promote')['decision'] == 'blocked'

        output_path = Path(accepted['directory']) / 'remeshed.obj'
        output_path.write_bytes(output_path.read_bytes() + b'\n# tampered\n')
        assert call('POST', f'/v1/jobs/{accepted_id}/promote')['decision'] == 'blocked'

        broker.batch_release_gate = Path(broker.jobs_root) / 'held-worker.gate'
        cancelled_id = submit('cube-accepted')
        call('POST', f'/v1/jobs/{cancelled_id}/cancel')
        cancelled = wait(cancelled_id)
        assert cancelled['state'] == 'cancelled', cancelled
        assert call('POST', f'/v1/jobs/{cancelled_id}/promote')['decision'] == 'blocked'
        print('PASS: accepted, rejected, tampered, and cancelled HTTP remesh jobs')
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    run(os.environ['DEVSHELL_REMESH_BROKER_CONFIG'])
