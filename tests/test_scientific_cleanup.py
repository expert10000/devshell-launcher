"""Verify real and controlled broker process-tree cleanup paths."""
import os
from pathlib import Path
import sys
import unittest


TOOL_ROOT = Path(__file__).resolve().parents[1] / 'tools' / 'scientific-broker'
sys.path.insert(0, str(TOOL_ROOT))
from qualify_cleanup import run_suite
from telemetry import psutil


@unittest.skipUnless(os.environ.get('SCIENTIFIC_BROKER_CONFIG'), 'Local broker config is required')
class CleanupQualification(unittest.TestCase):
    def test_cancel_timeout_orphan_and_partial_cleanup(self):
        if psutil is None:
            self.skipTest('psutil is required for orphan verification')
        path, report = run_suite(os.environ['SCIENTIFIC_BROKER_CONFIG'])
        self.assertTrue(path.is_file())
        expected = {'realCancellation': 'cancelled', 'forcedCancellation': 'cancelled',
                    'forcedTimeout': 'timed-out', 'orphanCleanup': 'partial'}
        self.assertEqual({name: case['state'] for name, case in report['cases'].items()}, expected)
        for case in report['cases'].values():
            self.assertEqual(case['cleanup']['state'], 'passed')
            self.assertEqual(case['cleanup']['activePids'], [])
            self.assertEqual(case['promotionDecision'], 'blocked')
            self.assertIn('l5-positive.obj', case['removedPartialArtifacts'])
        self.assertFalse(report['diagnosticWorkerQualified'])
        self.assertIn(report['cases']['orphanCleanup']['childPid'],
                      report['cases']['orphanCleanup']['cleanup']['orphanPids'])


if __name__ == '__main__':
    unittest.main()
