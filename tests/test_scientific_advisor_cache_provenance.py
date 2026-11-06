"""Evidence-gated advice, artifact retention and exact-to-document provenance."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools' / 'scientific-broker'))
import advisor
import artifact_cache
import provenance


class CacheLifecycle(unittest.TestCase):
    def test_advisor_never_ranks_incomparable_policies(self):
        common = {'policySha256': 'a' * 64, 'inputSha256': 'b' * 64,
                  'hostFingerprintSha256': 'c' * 64, 'tier': 'single', 'batchSize': 1}
        first = {'runtimeId': 'one', 'cost': {**common, 'medianWorkerDurationMs': 100}}
        second = {'runtimeId': 'two', 'cost': {**common, 'medianWorkerDurationMs': 90}}
        self.assertEqual('two', advisor.rank([first, second]))
        self.assertIsNone(advisor.rank([first, {'runtimeId': 'two', 'cost': {**second['cost'], 'policySha256': 'd' * 64}}]))

    def test_dedup_references_pins_retention_and_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source.obj'
            source.write_bytes(b'v 0 0 0\n')
            cache = artifact_cache.Cache(root / 'cache')
            first = cache.put(source, 'job:one')
            second = cache.put(source, 'job:two')
            self.assertEqual(first['sha256'], second['sha256'])
            self.assertEqual(2, len(cache.inspect(first['sha256'])['references']))
            cache.reference(first['sha256'], 'release:one', pin=True)
            cache.reference(first['sha256'], 'job:one', remove=True)
            cache.reference(first['sha256'], 'job:two', remove=True)
            self.assertEqual([], cache.gc(0, dry_run=True)['eligible'])
            cache.reference(first['sha256'], 'release:one', pin=True, remove=True)
            self.assertEqual([first['sha256']], cache.gc(0, dry_run=True)['eligible'])
            self.assertTrue(Path(first['path']).exists())
            Path(first['path']).write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError, 'missing or changed'):
                cache.gc(0, dry_run=False)
            Path(first['path']).write_bytes(source.read_bytes())
            self.assertEqual([first['sha256']], cache.gc(0, dry_run=False)['eligible'])
            self.assertFalse(Path(first['path']).exists())
            cache.close()

    def test_exact_sample_rejects_changed_roots(self):
        exact = {'roots': ['-1', '1'], 'verified': True}
        sample, points = provenance.sample_obj(exact)
        self.assertEqual(4, len(points))
        self.assertTrue(sample.endswith(b'f 2 3 4\r\n'))
        with self.assertRaisesRegex(ValueError, 'Unverified'):
            provenance.sample_obj({'roots': ['-2', '2'], 'verified': True})


@unittest.skipUnless(os.environ.get('SCIENTIFIC_BROKER_CONFIG'), 'Qualified local broker config required')
class LiveEvidence(unittest.TestCase):
    def test_advice_requires_cross_provider_comparison(self):
        config = os.environ['SCIENTIFIC_BROKER_CONFIG']
        with tempfile.TemporaryDirectory() as directory:
            path, record = advisor.advise(config, 'mesh.interop.vtk-math3d', 'single', 'cgal-win-conda', directory)
            self.assertEqual(record, advisor.verify(path, config))
            self.assertEqual('insufficient-comparison', record['state'])
            self.assertIsNone(record['recommendation'])
            self.assertEqual('cgal-win-conda', record['selectedProvider'])
            with self.assertRaisesRegex(ValueError, 'not currently certified'):
                advisor.advise(config, 'mesh.interop.vtk-math3d', 'single', 'gmsh-win-conda', directory)

    def test_exact_sage_to_verified_document_and_cache(self):
        config = os.environ['SCIENTIFIC_BROKER_CONFIG']
        with tempfile.TemporaryDirectory() as directory:
            path, record = provenance.build(config, Path(directory) / 'provenance',
                                            os.environ.get('MATH3D_WSL_DISTRO', 'Ubuntu'))
            self.assertEqual(record, provenance.verify(path, config))
            self.assertEqual(7, len(record['nodes']))
            cache = artifact_cache.Cache(Path(directory) / 'cache')
            mesh = artifact_cache.ingest_broker(cache, config, record['sourceJobId'], 'l5-positive.obj')
            duplicate = artifact_cache.ingest_broker(cache, config, record['sourceJobId'], 'l5-positive.obj')
            document = artifact_cache.ingest_document(cache, config, record['sourceJobId'])
            self.assertEqual(mesh['sha256'], duplicate['sha256'])
            self.assertEqual(record['nodes'][-1]['sha256'], document['sha256'])
            self.assertEqual([], cache.gc(0, dry_run=True)['eligible'])
            cache.close()
            original = path.read_bytes()
            path.write_bytes(original + b'\n')
            with self.assertRaisesRegex(ValueError, 'record hash mismatch'):
                provenance.verify(path, config)


if __name__ == '__main__':
    unittest.main()
