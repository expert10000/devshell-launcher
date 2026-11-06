"""Live fixed 2D Gmsh broker and MATH3D document checks."""
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools' / 'scientific-broker'))
from broker import Broker, sha
from gmsh_smoke import run, verify


@unittest.skipUnless(os.environ.get('SCIENTIFIC_GMSH_BROKER_CONFIG'), 'Local Gmsh broker config is required')
class GmshBrokerIntegration(unittest.TestCase):
    def test_certified_job_document_and_tamper_rejection(self):
        config = Path(os.environ['SCIENTIFIC_GMSH_BROKER_CONFIG']).resolve(strict=True)
        broker = Broker(config)
        self.assertEqual([(item['runtimeId'], item['capabilities'][0]['capabilityId'])
                          for item in broker.discover()['providers']],
                         [('gmsh-win-conda', 'mesh.generate')])
        fixture = broker.paths['datasetRoot'] / 'gmsh' / 'fixed-square.geo'
        request = {'schemaVersion': 1, 'runtimeId': 'gmsh-win-conda', 'capabilityId': 'mesh.generate',
                   'input': {'path': str(fixture), 'sha256': '0' * 64}}
        with self.assertRaisesRegex(ValueError, 'Input artifact hash mismatch'):
            broker.submit(request)
        with self.assertRaisesRegex(ValueError, 'bounded registered .geo dataset'):
            broker.submit({**request, 'input': {'path': str(ROOT / 'scientific/fixtures/gmsh/tampered-square.geo'),
                                               'sha256': sha(ROOT / 'scientific/fixtures/gmsh/tampered-square.geo')}})
        record_path, record = run(config)
        self.assertEqual(record['verdict'], 'passed')
        self.assertEqual(verify(record_path, config)['sourceJobId'], record['sourceJobId'])
        broker = Broker(config)
        job_dir = record_path.parent
        snapshot = job_dir / 'source-snapshot.json'
        original = snapshot.read_bytes()
        try:
            snapshot.write_bytes(original + b' ')
            self.assertEqual(broker.promote(record['sourceJobId'])['decision'], 'blocked')
            with self.assertRaisesRegex(ValueError, 'Source snapshot hash mismatch'):
                verify(record_path, config)
        finally:
            snapshot.write_bytes(original)
        for target in (job_dir / 'l5-positive.obj', job_dir / 'product/qualified-mesh.m3dm'):
            original = target.read_bytes()
            try:
                target.write_bytes(original + b' ')
                with self.assertRaisesRegex(ValueError, 'changed'):
                    verify(record_path, config)
            finally:
                target.write_bytes(original)
        self.assertEqual(verify(record_path, config)['verdict'], 'passed')


if __name__ == '__main__':
    unittest.main()
