"""Live broker contract checks; set SCIENTIFIC_BROKER_CONFIG to a local config."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
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
        self.assertEqual(job['cleanup']['state'], 'passed')
        telemetry = self.broker.telemetry(job['jobId'])
        self.assertEqual(telemetry['sourceJobId'], job['jobId'])
        self.assertEqual(telemetry['cpu']['unit'], 's')
        self.assertEqual(telemetry['ram']['unit'], 'byte')
        handoff = json.loads(self.broker.artifact(job['jobId'], 'handoff.json'))
        self.assertEqual(handoff['contract'], module.CONTRACT)
        self.assertEqual(handoff['artifact']['sha256'],
                         hashlib.sha256(self.broker.artifact(job['jobId'], 'l5-positive.obj')).hexdigest())
        if self.broker.math3d_root is not None:
            allowed = self.broker.promote(job['jobId'])
            self.assertEqual(allowed['decision'], 'allowed', allowed['reasons'])
            self.assertEqual(allowed['contractVersion'], 1)
            with tempfile.TemporaryDirectory() as directory:
                original = self.broker.math3d_root
                changed_root = Path(directory)
                entry = self.broker.capabilities[0]
                for name in entry['consumerSources']:
                    target = changed_root / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(original / name, target)
                changed = changed_root / 'renderer' / 'src' / 'mesh' / 'surfaceMesh.ts'
                changed.write_bytes(changed.read_bytes() + b'\n// changed\n')
                self.broker.math3d_root = changed_root
                try:
                    stale = self.broker.promote(job['jobId'])
                    self.assertEqual(stale['decision'], 'blocked')
                    self.assertTrue(any('consumer' in reason for reason in stale['reasons']))
                finally:
                    self.broker.math3d_root = original
            with tempfile.TemporaryDirectory() as directory:
                original_manifest = self.broker.paths['manifest']
                empty = json.loads(original_manifest.read_text(encoding='utf-8'))
                empty['certifiedCapabilities'] = []
                path = Path(directory) / 'manifest.json'
                path.write_text(json.dumps(empty, separators=(',', ':')))
                Path(str(path) + '.sha256').write_text(module.sha(path))
                self.broker.paths['manifest'] = path
                try:
                    stale = self.broker.promote(job['jobId'])
                    self.assertEqual(stale['decision'], 'blocked')
                    self.assertTrue(any('no longer current' in reason for reason in stale['reasons']))
                finally:
                    self.broker.paths['manifest'] = original_manifest
        output = Path(job['directory']) / 'l5-positive.obj'
        changed = bytearray(output.read_bytes())
        changed[0] ^= 1
        output.write_bytes(changed)
        with self.assertRaisesRegex(ValueError, 'Output artifact hash mismatch'):
            self.broker.artifact(job['jobId'], 'l5-positive.obj')
        blocked = self.broker.promote(job['jobId'])
        self.assertEqual(blocked['decision'], 'blocked')
        self.assertTrue(any('handoff' in reason for reason in blocked['reasons']))
        self.broker.jobs[job['jobId']]['state'] = 'failed'
        failed = self.broker.promote(job['jobId'])
        self.assertEqual(failed['decision'], 'blocked')
        self.assertTrue(any('failed' in reason for reason in failed['reasons']))

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

    def test_smoke_failure_links_source_job(self):
        if self.broker.math3d_root is None:
            self.skipTest('MATH3D checkout is required')
        config = json.loads(self.config.read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            consumer = root / 'changed-math3d'
            for name in self.broker.capabilities[0]['consumerSources']:
                target = consumer / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(self.broker.math3d_root / name, target)
            changed = consumer / 'renderer' / 'src' / 'mesh' / 'surfaceMesh.ts'
            changed.write_bytes(changed.read_bytes() + b'\n// stale\n')
            config['math3dRoot'] = str(consumer)
            config['jobsRoot'] = str(root / 'jobs')
            config_path = root / 'config.json'
            config_path.write_text(json.dumps(config))
            smoke = BROKER_PATH.with_name('smoke.py')
            result = subprocess.run([sys.executable, str(smoke), '--config', str(config_path)],
                                    capture_output=True, text=True, timeout=30)
            self.assertNotEqual(result.returncode, 0)
            records = list((root / 'jobs').glob('*/smoke-result.json'))
            self.assertEqual(len(records), 1)
            report = json.loads(records[0].read_text())
            self.assertEqual(report['state'], 'failed')
            self.assertEqual(report['stage'], 'promotion')
            self.assertEqual(report['sourceJobId'], records[0].parent.name)


if __name__ == '__main__':
    unittest.main()
