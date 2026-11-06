"""Qualification and shared-fixture comparison must remain separate verdicts."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools' / 'scientific-broker'
sys.path.insert(0, str(TOOL))
spec = importlib.util.spec_from_file_location('cross_provider', TOOL / 'cross_provider.py')
cross = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cross)


class CrossProviderTests(unittest.TestCase):
    def test_performance_requires_both_current_certifications_and_shared_policy(self):
        fixture = 'f' * 64
        cgal = {'recordId': 'cgal'}
        vtk = {'recordId': 'vtk'}
        a = {'recordId': 'a', 'runtimeId': 'cgal-win-conda', 'certificationRecordId': 'cgal', 'inputSha256': fixture,
             'benchmarkId': 'shared', 'hostFingerprintSha256': 'host', 'policy': {'cold': 'one'},
             'benchmarkRunId': 'a', 'tiers': {'small': {'batchSize': 1, 'medianWorkerDurationMs': 10}}}
        b = {**a, 'recordId': 'b', 'runtimeId': 'vtk-win-conda', 'certificationRecordId': 'vtk', 'benchmarkRunId': 'b',
             'tiers': {'small': {'batchSize': 1, 'medianWorkerDurationMs': 20}}}
        self.assertEqual('comparable', cross.performance(a, b, cgal, vtk, fixture)['verdict'])
        self.assertEqual(2, cross.performance(a, b, cgal, vtk, fixture)['tiers']['small']['vtkToCgalRatio'])
        self.assertEqual('inconclusive', cross.performance(a, None, cgal, None, fixture)['verdict'])
        self.assertEqual('inconclusive', cross.performance(a, {**b, 'hostFingerprintSha256': 'other'}, cgal, vtk, fixture)['verdict'])

    def test_saved_real_meshes_compare_but_vtk_is_not_certified(self):
        scientific = ROOT / '.scientific'
        paths = {
            'cgalRelease': scientific / 'releases' / '7e22f779ad4f4b47837e00c1484ef28e' / 'qualification-report.json',
            'vtkRelease': scientific / 'releases' / '7e22f779ad4f4b47837e00c1484ef28e' / 'qualification-report.json',
            'cgalResult': scientific / 'runs' / 'b5ad9651caf04ccba9dea7ff4605ee94' / 'results.json',
            'vtkResult': scientific / 'runs' / '0328feb6271f49b8a024fe1a2cc576b4' / 'results.json',
            'cgalConfig': scientific / 'release-refresh' / '2026-11-06' / 'broker-config.json',
        }
        if not all(path.is_file() for path in paths.values()):
            self.skipTest('Local saved scientific runs are unavailable')
        with tempfile.TemporaryDirectory() as directory:
            path, record = cross.generate(paths, 1e-6, directory)
            self.assertEqual('blocked', record['verdict'])
            self.assertTrue(all(record['dimensions'].values()))
            self.assertEqual('inconclusive', record['performance']['verdict'])
            self.assertEqual('blocked', record['certifications']['cgal']['state'])
            self.assertEqual('blocked', record['certifications']['vtk']['state'])
            self.assertTrue(any('workerContract hash mismatch' in reason for reason in record['reasons']))
            self.assertEqual(record, cross.verify(path))
            path.write_bytes(path.read_bytes() + b' ')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                cross.verify(path)


if __name__ == '__main__':
    unittest.main()
