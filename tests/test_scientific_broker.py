"""Live broker contract checks; set SCIENTIFIC_BROKER_CONFIG to a local config."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import unittest


BROKER_PATH = Path(__file__).resolve().parents[1] / 'tools' / 'scientific-broker' / 'broker.py'
spec = importlib.util.spec_from_file_location('scientific_broker', BROKER_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@unittest.skipUnless(os.environ.get('SCIENTIFIC_BROKER_CONFIG'), 'Local broker config is required')
class BrokerIntegration(unittest.TestCase):
    def setUp(self):
        self.config = Path(os.environ['SCIENTIFIC_BROKER_CONFIG']).resolve()
        self.broker = module.Broker(self.config)

    def test_certification_and_verified_transport(self):
        providers = self.broker.discover()['providers']
        self.assertEqual([item['runtimeId'] for item in providers], ['cgal-win-conda'])
        source = self.broker.paths['datasetRoot'] / 'math3d' / 'basic' / '01_tetrahedron.obj'
        request = {'schemaVersion': 1, 'runtimeId': 'cgal-win-conda',
                   'capabilityId': 'mesh.interop.vtk-math3d',
                   'input': {'path': str(source), 'sha256': module.sha(source)}}
        with self.assertRaisesRegex(ValueError, 'Unsupported broker job contract'):
            self.broker.submit({**request, 'runtimeId': 'gmsh-win-conda'})
        with self.assertRaisesRegex(ValueError, 'Input artifact hash mismatch'):
            self.broker.submit({**request, 'input': {**request['input'], 'sha256': '0' * 64}})
        cube = self.broker.paths['datasetRoot'] / 'math3d' / 'basic' / '02_cube.obj'
        with self.assertRaisesRegex(ValueError, 'outside the fixed L9 qualification fixture'):
            self.broker.submit({**request, 'input': {'path': str(cube), 'sha256': module.sha(cube)}})
        job = self.broker.submit(request)
        deadline = time.monotonic() + 30
        while job['state'] == 'running' and time.monotonic() < deadline:
            time.sleep(0.1)
            job = self.broker.snapshot(self.broker.jobs[job['jobId']])
        self.assertEqual(job['state'], 'succeeded', job['diagnostics'])
        self.assertEqual(job['progress'], 100)
        handoff = json.loads(self.broker.artifact(job['jobId'], 'handoff.json'))
        self.assertEqual(handoff['contract'], module.CONTRACT)
        self.assertEqual(handoff['artifact']['sha256'],
                         hashlib.sha256(self.broker.artifact(job['jobId'], 'l5-positive.obj')).hexdigest())
        output = Path(job['directory']) / 'l5-positive.obj'
        changed = bytearray(output.read_bytes())
        changed[0] ^= 1
        output.write_bytes(changed)
        with self.assertRaisesRegex(ValueError, 'Output artifact hash mismatch'):
            self.broker.artifact(job['jobId'], 'l5-positive.obj')

    def test_manifest_hash_mismatch(self):
        config = json.loads(self.config.read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as directory:
            original = Path(config['manifest'])
            tampered = Path(directory) / 'certified-capabilities.json'
            tampered.write_bytes(original.read_bytes() + b' ')
            Path(str(tampered) + '.sha256').write_text(Path(str(original) + '.sha256').read_text())
            config['manifest'] = str(tampered)
            config_path = Path(directory) / 'config.json'
            config_path.write_text(json.dumps(config))
            with self.assertRaisesRegex(ValueError, 'Certified manifest hash mismatch'):
                module.Broker(config_path)

    def test_worker_hash_mismatch(self):
        config = json.loads(self.config.read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as directory:
            changed = Path(directory) / 'devshell_cgal_worker.exe'
            changed.write_bytes(Path(config['worker']).read_bytes() + b'changed')
            config['worker'] = str(changed)
            config_path = Path(directory) / 'config.json'
            config_path.write_text(json.dumps(config))
            with self.assertRaisesRegex(ValueError, 'worker hash mismatch'):
                module.Broker(config_path)


if __name__ == '__main__':
    unittest.main()
