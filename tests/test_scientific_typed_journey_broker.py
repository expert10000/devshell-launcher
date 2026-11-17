"""Opt-in accepted/rejected/tampered/cancelled HTTP candidate journey check."""
import hashlib
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/scientific-broker'))
from broker import handler_for  # noqa: E402
from typed_journey_broker import CAPABILITY, TypedJourneyBroker  # noqa: E402


def sha(data):
    return hashlib.sha256(data).hexdigest()


def exchange(url, method='GET', body=None, expected=200):
    request = Request(url, data=json.dumps(body).encode() if body is not None else None,
                      headers={'Content-Type': 'application/json'} if body is not None else {}, method=method)
    try:
        with urlopen(request, timeout=20) as response:
            status, data, headers = response.status, response.read(), response.headers
    except HTTPError as error:
        status, data, headers = error.code, error.read(), error.headers
    assert status == expected, (url, status, data[:500])
    return data if '/artifacts/' in url and status == 200 else json.loads(data), headers


def complete(base, job_id, timeout=600):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job, _ = exchange(f'{base}/v1/jobs/{job_id}')
        if job['state'] != 'running':
            return job
        time.sleep(0.2)
    raise AssertionError('Broker typed journey did not finish.')


def main():
    config_path = os.environ.get('DEVSHELL_TYPED_BROKER_CONFIG')
    assert config_path, 'Set DEVSHELL_TYPED_BROKER_CONFIG to a pinned local profile.'
    config = json.loads(Path(config_path).read_text(encoding='utf-8'))
    broker = TypedJourneyBroker(config)
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(broker))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        discovery, _ = exchange(base + '/v1/providers')
        assert discovery['providers'][0]['capabilities'][0]['level'] == 'candidate'
        request = {'schemaVersion': 1, 'runtimeId': 'cgal-win-conda', 'capabilityId': CAPABILITY,
                   'caseId': config['caseProfile']['caseId'], 'input': {
                       'path': config['caseProfile']['resultPath'],
                       'sha256': config['caseProfile']['resultSha256']}, 'timeoutSeconds': 300}
        job, _ = exchange(base + '/v1/jobs', 'POST', request, 202)
        accepted = complete(base, job['jobId'])
        assert accepted['state'] == 'succeeded', accepted['diagnostics']
        assert len(accepted['artifacts']) == 13
        assert accepted['verification']['verdict'] == 'verified-typed-product-relations'
        snapshot, _ = exchange(f"{base}/v1/jobs/{job['jobId']}/source")
        assert snapshot['repositories']['devshell']['commit'] == accepted['sourceCommit']
        for artifact in accepted['artifacts']:
            raw, headers = exchange(f"{base}/v1/jobs/{job['jobId']}/artifacts/{artifact['name']}")
            assert len(raw) == artifact['bytes'] and sha(raw) == artifact['sha256']
            if artifact['name'] == 'preview.png':
                assert headers['Content-Type'] == 'image/png' and raw.startswith(b'\x89PNG\r\n\x1a\n')
        promotion, _ = exchange(f"{base}/v1/jobs/{job['jobId']}/promote", 'POST', {})
        assert promotion['decision'] == 'blocked' and 'signed journey bundle' in promotion['reasons'][-1]
        for patch in ({'caseId': 'not-allowlisted'}, {'input': {**request['input'], 'sha256': '0' * 64}},
                      {'unexpected': True}):
            rejected, _ = exchange(base + '/v1/jobs', 'POST', {**request, **patch}, 400)
            assert 'error' in rejected
        target = Path(accepted['directory']) / 'vtk/analysis.vtp'
        original = target.read_bytes()
        try:
            target.write_bytes(original + b'changed')
            tampered, _ = exchange(f"{base}/v1/jobs/{job['jobId']}/artifacts/analysis.vtp", expected=409)
            assert 'changed' in tampered['error']
            blocked, _ = exchange(f"{base}/v1/jobs/{job['jobId']}/promote", 'POST', {})
            assert blocked['decision'] == 'blocked' and any('changed' in reason for reason in blocked['reasons'])
        finally:
            target.write_bytes(original)
        running, _ = exchange(base + '/v1/jobs', 'POST', request, 202)
        exchange(f"{base}/v1/jobs/{running['jobId']}/cancel", 'POST', {})
        cancelled = complete(base, running['jobId'])
        assert cancelled['state'] == 'cancelled' and cancelled['artifacts'] == []
        denied, _ = exchange(f"{base}/v1/jobs/{running['jobId']}/promote", 'POST', {})
        assert denied['decision'] == 'blocked'
        print(json.dumps({'verdict': 'typed-broker-http-passed', 'acceptedJobId': job['jobId'],
                          'cancelledJobId': running['jobId'], 'sourceCommit': accepted['sourceCommit'],
                          'consumerCommit': accepted['consumerCommit']}))
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)


if __name__ == '__main__':
    main()
