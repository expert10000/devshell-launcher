"""Requalification planning must retain stale lower-level dependencies."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/scientific-broker'))
from gmsh_volume_requalify import FULL, RESUME, mode_for, require_desktop


class VolumeRequalificationPlanChecks(unittest.TestCase):
    def test_current_certificate_needs_no_managed_runs(self):
        self.assertEqual(mode_for({'eligible': True}), ('current', ()))

    def test_changed_early_support_requires_the_full_chain(self):
        support = [{'level': f'L{index}', 'status': 'current'} for index in range(9)]
        support[3]['status'] = 'stale'
        self.assertEqual(mode_for({'eligible': False, 'candidates': [{'support': support}]}),
                         ('full', FULL))

    def test_late_consumer_drift_repeats_product_gates(self):
        support = [{'level': f'L{index}', 'status': 'current'} for index in range(9)]
        support[7]['status'] = 'stale'
        self.assertEqual(mode_for({'eligible': False, 'candidates': [{'support': support}]}),
                         ('resume', RESUME))

    def test_missing_evidence_requires_the_full_chain(self):
        self.assertEqual(mode_for({'eligible': False, 'candidates': []}), ('full', FULL))

    def test_misordered_support_cannot_authorize_a_shortened_chain(self):
        support = [{'level': f'L{index}', 'status': 'current'} for index in range(9)]
        support[0], support[8] = support[8], support[0]
        self.assertEqual(mode_for({'eligible': False, 'candidates': [{'support': support}]}),
                         ('full', FULL))

    def test_cdp_preflight_rejects_misleading_loopback_urls(self):
        for url in ('http://127.0.0.1:9244@other.example',
                    'http://127.0.0.1:9244/redirect',
                    'http://127.0.0.1:9244?url=other.example'):
            with self.subTest(url=url), self.assertRaisesRegex(ValueError, 'localhost'):
                require_desktop(url)

    def test_cdp_preflight_requires_an_app_page(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                pass

            def read(self):
                return b'[{"url":"http://other.example/?next=app.local"}]'

        with patch('gmsh_volume_requalify.urlopen', return_value=Response()):
            with self.assertRaisesRegex(ValueError, 'no DevShell app page'):
                require_desktop('http://127.0.0.1:9244')


if __name__ == '__main__':
    unittest.main()
