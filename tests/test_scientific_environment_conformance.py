"""Environment lock integrity and provider-scoped conformance verdicts."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools' / 'scientific-broker'))
import adapter_conformance
import environment_manifest
from broker import Broker


class ContractVerdicts(unittest.TestCase):
    def test_incomplete_and_failed_are_not_passed(self):
        self.assertEqual('passed', adapter_conformance.verdict({'contract': adapter_conformance.case('passed', '')}))
        self.assertEqual('incomplete', adapter_conformance.verdict({'progress': adapter_conformance.case('unavailable', '')}))
        self.assertEqual('failed', adapter_conformance.verdict({'artifactHashes': adapter_conformance.case('failed', '')}))

    def test_unsafe_package_url_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            meta = Path(directory) / 'conda-meta'
            meta.mkdir()
            record = {'name': 'private', 'version': '1', 'build': '0', 'fn': 'private-1-0.conda',
                      'url': 'https://user:secret@example.com/private-1-0.conda',
                      'sha256': 'a' * 64, 'md5': 'b' * 32}
            (meta / 'private.json').write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError, 'not safe'):
                environment_manifest.package_records(directory)


@unittest.skipUnless(os.environ.get('SCIENTIFIC_BROKER_CONFIG'), 'Local qualified broker config required')
class LiveEnvironmentAndAdapters(unittest.TestCase):
    def setUp(self):
        self.config = Path(os.environ['SCIENTIFIC_BROKER_CONFIG']).resolve()
        self.broker = Broker(self.config)

    def test_exact_lock_hashes_and_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = environment_manifest.capture('cgal-win-conda', self.broker.paths['prefix'], directory)
            record = environment_manifest.verify_manifest(path)
            self.assertEqual('exact-explicit-builds', record['formats']['conda'])
            self.assertGreater(record['packageCount'], 20)
            self.assertTrue((path.parent / 'conda-explicit.txt').read_text().startswith('@EXPLICIT\n'))
            lock = path.parent / 'conda-explicit.txt'
            original = lock.read_bytes()
            lock.write_bytes(original + b'\n')
            with self.assertRaisesRegex(ValueError, 'artifact hash mismatch'):
                environment_manifest.verify_manifest(path)
            lock.write_bytes(original)

    def test_five_provider_matrix_keeps_gmsh_unqualified(self):
        with tempfile.TemporaryDirectory() as directory:
            path, record = adapter_conformance.run(self.config, ROOT / '.scientific' / 'runtime-report.json', directory)
            self.assertTrue(path.is_file())
            self.assertEqual(record, adapter_conformance.verify_record(path))
            self.assertEqual(set(adapter_conformance.PROVIDERS), {item['runtimeId'] for item in record['providers']})
            by_id = {item['runtimeId']: item for item in record['providers']}
            self.assertEqual('passed', by_id['cgal-win-conda']['verdict'])
            self.assertEqual('passed', by_id['vtk-win-conda']['cases']['artifactHashes']['state'])
            self.assertEqual('incomplete', by_id['vtk-win-conda']['verdict'])
            self.assertEqual('incomplete', by_id['gmsh-win-conda']['verdict'])
            self.assertEqual('unavailable', by_id['gmsh-win-conda']['cases']['artifactHashes']['state'])
            self.assertIn('cannot grant L0-L9', record['qualificationImpact'])
            original = path.read_bytes()
            path.write_bytes(original + b'\n')
            with self.assertRaisesRegex(ValueError, 'record hash mismatch'):
                adapter_conformance.verify_record(path)


if __name__ == '__main__':
    unittest.main()
