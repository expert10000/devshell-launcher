"""Requalification planning must retain stale lower-level dependencies."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/scientific-broker'))
from gmsh_volume_requalify import FULL, RESUME, mode_for


class VolumeRequalificationPlanChecks(unittest.TestCase):
    def test_current_certificate_needs_no_managed_runs(self):
        self.assertEqual(mode_for({'eligible': True}), ('current', ()))

    def test_changed_early_support_requires_the_full_chain(self):
        support = [{'status': 'current'} for _ in range(9)]
        support[3]['status'] = 'stale'
        self.assertEqual(mode_for({'eligible': False, 'candidates': [{'support': support}]}),
                         ('full', FULL))

    def test_late_consumer_drift_repeats_product_gates(self):
        support = [{'status': 'current'} for _ in range(9)]
        support[7]['status'] = 'stale'
        self.assertEqual(mode_for({'eligible': False, 'candidates': [{'support': support}]}),
                         ('resume', RESUME))

    def test_missing_evidence_requires_the_full_chain(self):
        self.assertEqual(mode_for({'eligible': False, 'candidates': []}), ('full', FULL))


if __name__ == '__main__':
    unittest.main()
