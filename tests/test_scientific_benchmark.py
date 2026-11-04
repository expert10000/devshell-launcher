"""Persistent baseline comparisons and attributed telemetry checks."""
import json
import os
from pathlib import Path
import sys
import unittest


TOOL_ROOT = Path(__file__).resolve().parents[1] / 'tools' / 'scientific-broker'
sys.path.insert(0, str(TOOL_ROOT))
from benchmark import BENCHMARK_ID, TIERS, compare, digest
from broker import Broker, sha
import telemetry


@unittest.skipUnless(os.environ.get('SCIENTIFIC_BROKER_CONFIG'), 'Local broker config is required')
class BenchmarkEvidence(unittest.TestCase):
    def setUp(self):
        self.broker = Broker(os.environ['SCIENTIFIC_BROKER_CONFIG'])
        self.root = self.broker.jobs_root.parent / 'benchmarks' / BENCHMARK_ID
        if not (self.root / 'baseline.json').exists():
            self.skipTest('A local persistent baseline is required')
        pointer = json.loads((self.root / 'baseline.json').read_text())
        path = self.root / (pointer['benchmarkRunId'] + '.json')
        self.assertEqual(sha(path), pointer['sha256'])
        self.baseline = json.loads(path.read_text())

    def test_comparable_and_inconclusive(self):
        self.assertEqual(set(self.baseline['tiers']), set(TIERS))
        self.assertEqual(self.baseline['recordId'], digest({key: value for key, value in self.baseline.items()
                                                            if key != 'recordId'}))
        records = sorted(path for path in self.root.glob('[0-9a-f]*.json') if path.name != 'baseline.json')
        self.assertGreaterEqual(len(records), 2)
        saved = [json.loads(path.read_text()) for path in records]
        pair = next(((left, right) for left in saved for right in saved
                     if left['benchmarkRunId'] != right['benchmarkRunId']
                     and compare(left, right)['verdict'] == 'comparable'), None)
        self.assertIsNotNone(pair)
        baseline, candidate = pair
        self.assertEqual(compare(baseline, candidate)['verdict'], 'comparable')
        changed_host = {**candidate, 'hostFingerprintSha256': '0' * 64}
        self.assertEqual(compare(baseline, changed_host)['verdict'], 'inconclusive')
        self.assertIn('host differs', compare(baseline, changed_host)['reasons'])
        changed_environment = {**candidate, 'environmentFingerprintSha256': '0' * 64}
        self.assertIn('environment fingerprint differs', compare(baseline, changed_environment)['reasons'])

    def test_collector_units_availability_and_attribution(self):
        job_id = self.baseline['tiers']['single']['coldJob']['jobId']
        directory = self.broker.jobs_root / job_id
        result = json.loads((directory / 'broker-result.json').read_text())
        telemetry_path = directory / 'telemetry.json'
        self.assertEqual(result['telemetrySha256'], sha(telemetry_path))
        telemetry = json.loads(telemetry_path.read_text())
        for name, unit in [('cpu', 's'), ('ram', 'byte'), ('gpu', '%'), ('vram', 'MiB')]:
            item = telemetry[name]
            self.assertEqual(item['unit'], unit)
            self.assertTrue(item['collector'])
            self.assertTrue(item['scope'])
            self.assertIn(item['state'], ('recorded', 'unavailable'))
            if item['state'] == 'unavailable':
                self.assertIsNone(item['value'])
                self.assertTrue(item['reason'])
        self.assertIn('not job-attributed', telemetry['gpu']['scope'])
        self.assertIn('not job-attributed', telemetry['vram']['scope'])
        self.assertEqual(result['cleanup']['state'], 'passed')

    def test_unavailable_measurements_are_empty(self):
        saved = telemetry.psutil
        telemetry.psutil = None
        try:
            sampler = telemetry.ResourceSampler(-1)
            sampler.nvidia_smi = None
            result = sampler.finish()
        finally:
            telemetry.psutil = saved
        for name in ('cpu', 'ram', 'gpu', 'vram'):
            self.assertEqual(result[name]['state'], 'unavailable')
            self.assertIsNone(result[name]['value'])
            self.assertTrue(result[name]['reason'])


if __name__ == '__main__':
    unittest.main()
