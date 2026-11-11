"""Selective planning, typed preflight and authenticated transport checks."""
import copy
import hashlib
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools' / 'scientific-broker'))
import pipeline
import remote_agent
import retest
from broker import Broker


class PlanningTests(unittest.TestCase):
    def test_selective_and_conservative_changes(self):
        selected = [item['id'] for item in retest.plan(['tools/scientific-cgal-worker.py'])['suites']]
        self.assertIn('cgal.l9', selected)
        self.assertIn('broker.tests', selected)
        self.assertNotIn('sage.l0-l3', selected)
        self.assertNotIn('gmsh.probes', selected)
        consumer = [item['id'] for item in retest.plan(['math3d/packages/core/src/meshDocument.ts'])['suites']]
        self.assertIn('cgal.l7', consumer)
        self.assertIn('vtk.l7', consumer)
        self.assertNotIn('sage.l0-l3', consumer)
        shared = [item['id'] for item in retest.plan(['schemas/scientific-capabilities.v1.json'])['suites']]
        self.assertIn('sage.l0-l3', shared)
        self.assertIn('gmsh.probes', shared)
        self.assertEqual([], retest.plan(['docs/notes.md'])['suites'])
        self.assertEqual(len(retest.load_graph()[1]), len(retest.plan(['unmapped-code.py'])['suites']))

    def test_environment_and_graph_cycle(self):
        selected = [item['id'] for item in retest.plan([], ['cgal.packages'])['suites']]
        self.assertIn('cgal.l9', selected)
        self.assertNotIn('vtk.l0-l3', selected)
        with tempfile.TemporaryDirectory() as directory:
            graph = copy.deepcopy(retest.load_graph()[0])
            graph['suites'][0]['dependsOn'] = ['cgal.l9']
            path = Path(directory) / 'graph.json'
            path.write_text(json.dumps(graph), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Cyclic'):
                retest.load_graph(path)

    def test_scoped_managed_chains_and_unaffected_records(self):
        cases = {
            'BatchLauncher/Form1.Scientific.CgalOrientation.cs': ('cgal.orient', 'l5-cgal-orient'),
            'BatchLauncher/Form1.Scientific.CgalRemesh.cs': ('cgal.remesh', 'l5-cgal-remesh'),
            'BatchLauncher/Form1.Scientific.CgalRepairL5.cs': ('cgal.repair', 'l5-cgal-repair'),
            'BatchLauncher/Form1.Scientific.VtkRead.cs': ('vtk.read', 'l5-vtk-read'),
            'tools/scientific-gmsh-volume-worker.py': ('gmsh.volume', 'l5-gmsh-volume'),
        }
        for path, (prefix, action) in cases.items():
            with self.subTest(path=path):
                selected = retest.plan([path])['suites']
                scoped = [item for item in selected if item['id'] in {f'{prefix}.l{level}' for level in range(5, 10)}]
                self.assertEqual([f'{prefix}.l{level}' for level in range(5, 10)],
                                 [item['id'] for item in scoped])
                self.assertEqual(action, scoped[0]['managedAction'])
                self.assertNotIn('sage.l0-l3', [item['id'] for item in selected])
        for path, suite in (('tools/scientific_cgal_orientation_l9.py', 'cgal.orient.l9'),
                            ('tools/scientific_cgal_remesh.py', 'cgal.remesh.l5'),
                            ('tools/scientific-cgal-hole-repair-worker.py', 'cgal.repair.l5')):
            self.assertIn(suite, [item['id'] for item in retest.plan([path])['suites']])
            self.assertNotIn('sage.l0-l3', [item['id'] for item in retest.plan([path])['suites']])


@unittest.skipUnless(os.environ.get('SCIENTIFIC_BROKER_CONFIG'), 'Local qualified broker config required')
class QualifiedTests(unittest.TestCase):
    def setUp(self):
        self.broker = Broker(os.environ['SCIENTIFIC_BROKER_CONFIG'])
        self.spec = json.loads((ROOT / 'schemas' / 'scientific-pipeline-example.v1.json').read_text())

    def test_pipeline_preflight_and_replay(self):
        malformed = copy.deepcopy(self.spec)
        malformed['nodes'][1]['inputs']['mesh'] = 'worker.handoff'
        before = len(self.broker.jobs)
        with self.assertRaisesRegex(ValueError, 'Incompatible artifact type'):
            pipeline.preflight(malformed, self.broker)
        self.assertEqual(before, len(self.broker.jobs))
        malformed = copy.deepcopy(self.spec)
        malformed['nodes'][0]['kind'] = 'gmsh.mesh'
        with self.assertRaisesRegex(ValueError, 'Unqualified'):
            pipeline.preflight(malformed, self.broker)
        with tempfile.TemporaryDirectory() as directory:
            first, record = pipeline.execute(self.spec, self.broker, directory)
            self.assertEqual('succeeded', record['state'], record['error'])
            self.assertEqual(3, len(record['nodes']))
            self.assertEqual('allowed', json.loads(Path(record['nodes'][2]['outputs']['decision']['path']).read_text())['decision'])
            self.assertEqual('succeeded', pipeline.verify(first)['state'])
            second, replay = pipeline.execute(self.spec, self.broker, directory)
            self.assertEqual('succeeded', replay['state'], replay['error'])
            self.assertTrue(replay['nodes'][1]['cacheHit'])
            self.assertEqual(record['nodes'][0]['outputs']['mesh']['sha256'],
                             replay['nodes'][0]['outputs']['mesh']['sha256'])
            changed = Path(replay['nodes'][1]['outputs']['metrics']['path'])
            changed.write_bytes(changed.read_bytes() + b' ')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                pipeline.verify(second)

    @unittest.skipUnless(shutil.which('openssl'), 'OpenSSL test certificate generator required')
    def test_remote_https_identity_policy_and_integrity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            key, cert = root / 'key.pem', root / 'cert.pem'
            subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                            '-keyout', str(key), '-out', str(cert), '-days', '1',
                            '-subj', '/CN=localhost', '-addext', 'subjectAltName=DNS:localhost'],
                           check=True, capture_output=True)
            token_file = root / 'token.txt'
            token_file.write_text('a' * 48)
            server_config = {'agentId': 'lab-agent-1', 'hostId': 'lab-host-1', 'maxTimeoutSeconds': 30}
            server = ThreadingHTTPServer(('127.0.0.1', 0), remote_agent.handler_for(server_config, 'a' * 48, self.broker))
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(cert, key)
            server.socket = context.wrap_socket(server.socket, server_side=True)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                config = {'url': f'https://localhost:{server.server_port}', 'agentId': 'lab-agent-1',
                          'hostId': 'lab-host-1', 'manifestSha256': remote_agent.sha(self.broker.paths['manifest']),
                          'caFile': str(cert), 'tokenFile': str(token_file)}
                path = root / 'client.json'
                path.write_text(json.dumps(config))
                client = remote_agent.RemoteClient(path)
                identity = client.profile()
                self.assertEqual('remote', identity['executionLocation'])
                config['hostId'] = 'wrong-host'
                path.write_text(json.dumps(config))
                with self.assertRaisesRegex(ValueError, 'identity mismatch'):
                    remote_agent.RemoteClient(path).profile()
                config['hostId'] = 'lab-host-1'
                config['url'] = f'https://127.0.0.1:{server.server_port}'
                path.write_text(json.dumps(config))
                with self.assertRaises(urllib.error.URLError):
                    remote_agent.RemoteClient(path).profile()
                config['url'] = f'https://localhost:{server.server_port}'
                path.write_text(json.dumps(config))
                with self.assertRaises(urllib.error.HTTPError):
                    client.request('/v1/jobs', {'schemaVersion': 1, 'runtimeId': 'gmsh-win-conda',
                        'capabilityId': identity['capabilityId'], 'referenceInputSha256': identity['referenceInputSha256'],
                        'timeoutSeconds': 20})
                record_path = client.run(root / 'results', 20)
                evidence = json.loads(record_path.read_text())
                self.assertEqual('remote', evidence['executionLocation'])
                self.assertEqual('succeeded', evidence['jobState'])
                self.assertEqual(evidence['sourceJobId'], remote_agent.verify_record(record_path)['sourceJobId'])
                for artifact in evidence['artifacts']:
                    self.assertEqual(artifact['sha256'], hashlib.sha256(Path(artifact['path']).read_bytes()).hexdigest())
                first_artifact = Path(evidence['artifacts'][0]['path'])
                original_bytes = first_artifact.read_bytes()
                first_artifact.write_bytes(original_bytes + b' ')
                with self.assertRaisesRegex(ValueError, 'saved artifact hash mismatch'):
                    remote_agent.verify_record(record_path)
                first_artifact.write_bytes(original_bytes)
                original_artifact = self.broker.artifact
                self.broker.artifact = lambda job_id, name: (b'tampered' if name == 'l5-positive.obj'
                                                              else original_artifact(job_id, name))
                try:
                    with self.assertRaisesRegex(ValueError, 'transport hash mismatch'):
                        client.run(root / 'tamper-results', 20)
                finally:
                    self.broker.artifact = original_artifact
                token_file.write_text('wrong' * 10)
                with self.assertRaises(urllib.error.HTTPError) as error:
                    remote_agent.RemoteClient(path).profile()
                self.assertEqual(401, error.exception.code)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == '__main__':
    unittest.main()
