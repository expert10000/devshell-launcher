"""Authenticated HTTPS transport for the fixed qualified CGAL broker job."""
import argparse
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parent))
from broker import Broker, sha, MAX_INPUT

JOB_ID = re.compile(r'[0-9a-f]{32}\Z')


def profile(config, broker):
    broker.verify()
    entry = broker.capabilities[0]
    return {'schemaVersion': 1, 'kind': 'scientific.remote-agent', 'executionLocation': 'remote',
            'agentId': config['agentId'], 'hostId': config['hostId'],
            'manifestSha256': sha(broker.paths['manifest']), 'certificationRecordId': entry['recordId'],
            'runtimeId': entry['runtimeId'], 'capabilityId': entry['capabilityId'],
            'referenceInputSha256': entry['referenceInputSha256'],
            'referenceArtifactSha256': entry['referenceArtifactSha256'],
            'resourcePolicy': {'maxConcurrentJobs': broker.max_concurrent_jobs,
                               'maxTimeoutSeconds': config['maxTimeoutSeconds'],
                               'memoryLimitMiB': broker.memory_limit_mib,
                               'maxArtifactBytes': MAX_INPUT}}


def load_config(path):
    config = json.loads(Path(path).read_text(encoding='utf-8'))
    if (config.get('schemaVersion') != 1 or not isinstance(config.get('agentId'), str)
            or not re.fullmatch('[a-zA-Z0-9_.-]{3,64}', config['agentId'])
            or not isinstance(config.get('hostId'), str) or not re.fullmatch('[a-zA-Z0-9_.-]{3,64}', config['hostId'])
            or type(config.get('maxTimeoutSeconds')) is not int
            or not 1 <= config['maxTimeoutSeconds'] <= 120):
        raise ValueError('Invalid remote agent profile.')
    token = Path(config['tokenFile']).read_text(encoding='utf-8').strip()
    if len(token) < 32:
        raise ValueError('Remote agent token must contain at least 32 characters.')
    return config, token


def handler_for(config, token, broker):
    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, value):
            raw = json.dumps(value, separators=(',', ':')).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def authorized(self):
            received = self.headers.get('Authorization', '')
            if not hmac.compare_digest(received, 'Bearer ' + token):
                self.reply(401, {'error': 'Authentication required.'})
                return False
            return True

        def do_GET(self):
            if not self.authorized():
                return
            parts = urllib.parse.urlsplit(self.path).path.strip('/').split('/')
            try:
                if parts == ['v1', 'profile']:
                    return self.reply(200, profile(config, broker))
                if len(parts) == 3 and parts[:2] == ['v1', 'jobs'] and JOB_ID.fullmatch(parts[2]):
                    with broker.lock:
                        job = broker.jobs[parts[2]]
                        snapshot = broker.snapshot(job)
                    snapshot.pop('directory', None)
                    snapshot['executionLocation'] = 'remote'
                    snapshot['agentId'] = config['agentId']
                    return self.reply(200, snapshot)
                if (len(parts) == 5 and parts[:2] == ['v1', 'jobs'] and JOB_ID.fullmatch(parts[2])
                        and parts[3] == 'artifacts' and parts[4] in ('l5-positive.obj', 'handoff.json')):
                    raw = broker.artifact(parts[2], parts[4])
                    self.send_response(200)
                    self.send_header('Content-Type', 'model/obj' if parts[4].endswith('.obj') else 'application/json')
                    self.send_header('Content-Length', str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                    return
                self.reply(404, {'error': 'Unknown route.'})
            except KeyError:
                self.reply(404, {'error': 'Job not found.'})
            except (ValueError, OSError) as error:
                self.reply(400, {'error': str(error)})

        def do_POST(self):
            if not self.authorized():
                return
            parts = urllib.parse.urlsplit(self.path).path.strip('/').split('/')
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if size < 0 or size > 4096:
                    raise ValueError('Request exceeds 4 KiB.')
                body = json.loads(self.rfile.read(size)) if size else {}
                if parts == ['v1', 'jobs']:
                    if set(body) != {'schemaVersion', 'runtimeId', 'capabilityId', 'referenceInputSha256', 'timeoutSeconds'}:
                        raise ValueError('Unsupported remote job request.')
                    expected = profile(config, broker)
                    if (body['schemaVersion'] != 1 or body['runtimeId'] != expected['runtimeId']
                            or body['capabilityId'] != expected['capabilityId']
                            or body['referenceInputSha256'] != expected['referenceInputSha256']
                            or type(body['timeoutSeconds']) is not int
                            or not 1 <= body['timeoutSeconds'] <= config['maxTimeoutSeconds']):
                        raise ValueError('Remote capability, fixture or resource policy mismatch.')
                    source = broker.paths['datasetRoot'] / 'math3d' / 'basic' / '01_tetrahedron.obj'
                    if sha(source) != expected['referenceInputSha256']:
                        raise ValueError('Registered remote fixture changed.')
                    job = broker.submit({'schemaVersion': 1, 'runtimeId': expected['runtimeId'],
                                         'capabilityId': expected['capabilityId'],
                                         'input': {'path': str(source), 'sha256': expected['referenceInputSha256']},
                                         'timeoutSeconds': body['timeoutSeconds']})
                    return self.reply(202, {'jobId': job['jobId'], 'state': job['state'],
                                            'executionLocation': 'remote', 'agentId': config['agentId']})
                if len(parts) == 4 and parts[:2] == ['v1', 'jobs'] and JOB_ID.fullmatch(parts[2]) and parts[3] == 'cancel':
                    job = broker.cancel(parts[2])
                    return self.reply(200, {'jobId': job['jobId'], 'state': job['state'],
                                            'executionLocation': 'remote'})
                self.reply(404, {'error': 'Unknown route.'})
            except KeyError:
                self.reply(404, {'error': 'Job not found.'})
            except (ValueError, OSError, json.JSONDecodeError) as error:
                self.reply(400, {'error': str(error)})

        def log_message(self, format, *args):
            pass

    return Handler


class RemoteClient:
    def __init__(self, config_path):
        config = json.loads(Path(config_path).read_text(encoding='utf-8'))
        url = config['url'].rstrip('/')
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.path or parsed.query:
            raise ValueError('Remote agent requires an HTTPS origin.')
        for name in ('agentId', 'hostId', 'manifestSha256', 'caFile', 'tokenFile'):
            if not config.get(name):
                raise ValueError('Missing remote client pin: ' + name)
        self.config = config
        self.url = url
        self.token = Path(config['tokenFile']).read_text(encoding='utf-8').strip()
        self.context = ssl.create_default_context(cafile=config['caFile'])
        self.context.check_hostname = True
        self.context.verify_mode = ssl.CERT_REQUIRED

    def request(self, route, body=None, raw=False):
        data = None if body is None else json.dumps(body, separators=(',', ':')).encode()
        request = urllib.request.Request(self.url + route, data=data,
                                         headers={'Authorization': 'Bearer ' + self.token,
                                                  'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, context=self.context, timeout=15) as response:
            limit = MAX_INPUT if raw else 1024 * 1024
            value = response.read(limit + 1)
            if len(value) > limit:
                raise ValueError('Remote response exceeds transport budget.')
            return value if raw else json.loads(value)

    def profile(self):
        value = self.request('/v1/profile')
        for key in ('agentId', 'hostId', 'manifestSha256'):
            if value.get(key) != self.config[key]:
                raise ValueError('Remote agent identity mismatch: ' + key)
        if value.get('executionLocation') != 'remote' or value.get('schemaVersion') != 1:
            raise ValueError('Remote agent profile contract mismatch.')
        return value

    def run(self, output_root, timeout=120):
        identity = self.profile()
        if type(timeout) is not int or not 1 <= timeout <= identity['resourcePolicy']['maxTimeoutSeconds']:
            raise ValueError('Remote timeout exceeds agent policy.')
        job = self.request('/v1/jobs', {'schemaVersion': 1, 'runtimeId': identity['runtimeId'],
                         'capabilityId': identity['capabilityId'],
                         'referenceInputSha256': identity['referenceInputSha256'],
                         'timeoutSeconds': timeout})
        job_id = job['jobId']
        if not JOB_ID.fullmatch(job_id):
            raise ValueError('Remote job identity is invalid.')
        deadline = time.monotonic() + timeout + 10
        while job['state'] == 'running' and time.monotonic() < deadline:
            time.sleep(0.1)
            job = self.request('/v1/jobs/' + job_id)
        if job['state'] == 'running':
            self.request('/v1/jobs/' + job_id + '/cancel', {})
            raise TimeoutError('Remote job exceeded client wait budget.')
        if job['state'] != 'succeeded' or job.get('certificationRecordId') != identity['certificationRecordId']:
            raise ValueError('Remote job failed or certification changed: ' + job['state'])
        if self.profile() != identity:
            raise ValueError('Remote agent profile changed during job execution.')
        directory = Path(output_root).resolve() / job_id
        directory.mkdir(parents=True, exist_ok=False)
        artifacts = []
        for name in ('l5-positive.obj', 'handoff.json'):
            expected = next((item for item in job['artifacts'] if item['path'] == name), None)
            if expected is None:
                raise ValueError('Remote artifact registration is missing.')
            data = self.request(f'/v1/jobs/{job_id}/artifacts/{name}', raw=True)
            if len(data) != expected['bytes'] or hashlib.sha256(data).hexdigest() != expected['sha256']:
                raise ValueError('Remote artifact transport hash mismatch.')
            path = directory / name
            path.write_bytes(data)
            artifacts.append({'name': name, 'path': str(path), 'sha256': sha(path), 'bytes': len(data)})
        if artifacts[0]['sha256'] != identity['referenceArtifactSha256']:
            raise ValueError('Remote artifact differs from certified reference.')
        handoff = json.loads((directory / 'handoff.json').read_text(encoding='utf-8'))
        if (handoff.get('artifact', {}).get('sha256') != artifacts[0]['sha256']
                or handoff.get('runtimeId') != identity['runtimeId']
                or handoff.get('capabilityId') != identity['capabilityId']
                or handoff.get('contract', {}).get('version') != 1):
            raise ValueError('Remote handoff artifact identity mismatch.')
        evidence = {'schemaVersion': 1, 'kind': 'scientific.remote-transport', 'executionLocation': 'remote',
                    'agentId': identity['agentId'], 'hostId': identity['hostId'],
                    'manifestSha256': identity['manifestSha256'], 'certificationRecordId': identity['certificationRecordId'],
                    'sourceJobId': job_id, 'jobState': job['state'], 'artifacts': artifacts}
        with (directory / 'remote-evidence.json').open('x', encoding='utf-8') as stream:
            json.dump(evidence, stream, indent=2)
        (directory / 'remote-evidence.json.sha256').write_text(sha(directory / 'remote-evidence.json'), encoding='utf-8')
        return directory / 'remote-evidence.json'


def verify_record(path):
    path = Path(path)
    seal = Path(str(path) + '.sha256')
    if not seal.is_file() or seal.read_text(encoding='utf-8').strip() != sha(path):
        raise ValueError('Remote evidence record hash mismatch.')
    evidence = json.loads(path.read_text(encoding='utf-8'))
    if evidence.get('executionLocation') != 'remote' or evidence.get('jobState') != 'succeeded':
        raise ValueError('Remote evidence is not a successful run.')
    for artifact in evidence['artifacts']:
        target = Path(artifact['path'])
        if not target.is_file() or target.stat().st_size != artifact['bytes'] or sha(target) != artifact['sha256']:
            raise ValueError('Remote saved artifact hash mismatch.')
    return evidence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['serve', 'profile', 'run', 'verify'])
    parser.add_argument('--config')
    parser.add_argument('--record', type=Path)
    parser.add_argument('--output-root', type=Path)
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--timeout', type=int, default=120)
    args = parser.parse_args()
    if args.command == 'verify':
        print(json.dumps({'sourceJobId': verify_record(args.record)['sourceJobId'], 'state': 'verified'}))
        return
    if not args.config:
        parser.error('--config is required.')
    if args.command == 'serve':
        config, token = load_config(args.config)
        broker = Broker(config['brokerConfig'])
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(config['certFile'], config['keyFile'])
        with ThreadingHTTPServer((config.get('bindHost', '127.0.0.1'), args.port), handler_for(config, token, broker)) as server:
            server.socket = context.wrap_socket(server.socket, server_side=True)
            print(json.dumps({'agentId': config['agentId'], 'port': server.server_port}), flush=True)
            server.serve_forever()
    else:
        client = RemoteClient(args.config)
        if args.command == 'run' and not args.output_root:
            parser.error('--output-root is required for run.')
        print(json.dumps(client.profile() if args.command == 'profile' else
                         {'record': str(client.run(args.output_root, args.timeout))}, indent=2))


if __name__ == '__main__':
    main()
