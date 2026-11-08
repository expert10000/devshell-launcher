"""Live fixed-cube broker certification, product handoff and tamper gates."""
import os
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
import threading
import unittest
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools' / 'scientific-broker'))
from broker import Broker, handler_for, sha
from gmsh_volume_smoke import run, verify
from release_certification import verify_release


@unittest.skipUnless(os.environ.get('SCIENTIFIC_GMSH_VOLUME_BROKER_CONFIG'),
                     'Local Gmsh volume broker config is required')
class GmshVolumeBrokerIntegration(unittest.TestCase):
    def test_fixed_cube_document_release_and_tamper_rejection(self):
        config = Path(os.environ['SCIENTIFIC_GMSH_VOLUME_BROKER_CONFIG']).resolve(strict=True)
        broker = Broker(config)
        self.assertEqual([(item['runtimeId'], item['capabilities'][0]['capabilityId'])
                          for item in broker.discover()['providers']],
                         [('gmsh-win-conda', 'mesh.generate3d')])
        fixture = broker.paths['datasetRoot'] / 'gmsh' / 'fixed-cube.geo'
        request = {'schemaVersion': 1, 'runtimeId': 'gmsh-win-conda', 'capabilityId': 'mesh.generate3d',
                   'input': {'path': str(fixture), 'sha256': '0' * 64}}
        with self.assertRaisesRegex(ValueError, 'Input artifact hash mismatch'):
            broker.submit(request)
        with self.assertRaisesRegex(ValueError, 'Unsupported broker job contract'):
            broker.submit({**request, 'capabilityId': 'mesh.generate'})
        altered = ROOT / 'scientific/fixtures/gmsh/tampered-cube.geo'
        with self.assertRaisesRegex(ValueError, 'bounded registered .geo dataset'):
            broker.submit({**request, 'input': {'path': str(altered), 'sha256': sha(altered)}})
        record_path, record = run(config)
        self.assertEqual(record['verdict'], 'passed')
        self.assertEqual(verify(record_path, config)['sourceJobId'], record['sourceJobId'])
        with ThreadingHTTPServer(('127.0.0.1', 0), handler_for(Broker(config))) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f'http://127.0.0.1:{server.server_port}'
                with urlopen(base + '/v1/providers') as response:
                    self.assertIn(b'mesh.generate3d', response.read())
                with urlopen(base + f"/v1/jobs/{record['sourceJobId']}/artifacts/volume.m3dt") as response:
                    self.assertEqual(response.headers['Content-Type'], 'application/octet-stream')
                    self.assertEqual(response.read(), (record_path.parent / 'volume.m3dt').read_bytes())
            finally:
                server.shutdown()
                thread.join(timeout=5)
        directory = record_path.parent
        snapshot = directory / 'source-snapshot.json'
        original = snapshot.read_bytes()
        try:
            snapshot.write_bytes(original + b' ')
            self.assertEqual(Broker(config).promote(record['sourceJobId'])['decision'], 'blocked')
            with self.assertRaisesRegex(ValueError, 'Source snapshot hash mismatch'):
                verify(record_path, config)
        finally:
            snapshot.write_bytes(original)
        for target in (directory / 'cube.msh', directory / 'volume.m3dt',
                       directory / 'product/tetra-resource.m3dt'):
            original = target.read_bytes()
            try:
                target.write_bytes(original + b' ')
                if target.name in ('cube.msh', 'volume.m3dt'):
                    self.assertEqual(Broker(config).promote(record['sourceJobId'])['decision'], 'blocked')
                with self.assertRaisesRegex(ValueError, 'changed|hash mismatch'):
                    verify(record_path, config)
            finally:
                target.write_bytes(original)
        self.assertEqual(verify(record_path, config)['verdict'], 'passed')
        report = os.environ.get('SCIENTIFIC_GMSH_VOLUME_RELEASE_REPORT')
        if report:
            self.assertEqual(verify_release(report, config)['verdict'], 'qualified')


if __name__ == '__main__':
    unittest.main()
