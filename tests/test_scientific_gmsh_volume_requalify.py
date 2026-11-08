"""Requalification planning must retain stale lower-level dependencies."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/scientific-broker'))
from broker import sha
from gmsh_volume_requalify import FULL, RESUME, mode_for, publish_manifest, require_desktop, save, verify_result


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

    def test_manifest_publication_waits_for_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            deployed, candidate = root / 'deployed.json', root / 'candidate.json'
            deployed.write_text('old', encoding='utf-8')
            candidate.write_text('new', encoding='utf-8')
            Path(str(deployed) + '.sha256').write_text(sha(deployed), encoding='utf-8')
            Path(str(candidate) + '.sha256').write_text(sha(candidate), encoding='utf-8')
            original = sha(deployed)

            def reject():
                raise ValueError('verification failed')

            with self.assertRaisesRegex(ValueError, 'verification failed'):
                publish_manifest(candidate, deployed, original, reject)
            self.assertEqual(deployed.read_text(encoding='utf-8'), 'old')
            self.assertEqual(Path(str(deployed) + '.sha256').read_text(encoding='utf-8'), original)
            deployed.write_text('concurrent', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'changed during'):
                publish_manifest(candidate, deployed, original)
            deployed.write_text('old', encoding='utf-8')
            publish_manifest(candidate, deployed, original)
            self.assertEqual(deployed.read_text(encoding='utf-8'), 'new')
            self.assertEqual(Path(str(deployed) + '.sha256').read_text(encoding='utf-8'), sha(deployed))

    def test_failed_run_remains_verifiable_without_desktop(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan_path = root / 'plan.json'
            save(plan_path, {'schemaVersion': 1, 'kind': 'scientific.gmsh-volume-requalification-plan',
                             'profileId': 'desktop-five', 'mode': 'full', 'recipes': FULL,
                             'before': {'eligible': False, 'candidates': []}})
            result_path = root / 'result.json'
            result = {'schemaVersion': 1, 'kind': 'scientific.gmsh-volume-requalification-run',
                      'planPath': str(plan_path), 'planSha256': sha(plan_path),
                      'profileId': 'desktop-five', 'steps': [], 'verdict': 'failed',
                      'reason': 'Desktop session unavailable'}
            save(result_path, result)
            self.assertEqual(verify_result(result_path)['verdict'], 'failed')
            log = root / 'managed.log'
            log.write_text('managed evidence', encoding='utf-8')
            result['steps'] = [{'id': 'managed-qualification', 'state': 'passed',
                                'logPath': str(log), 'logSha256': sha(log)}]
            result_path.write_text(json.dumps(result), encoding='utf-8')
            Path(str(result_path) + '.sha256').write_text(sha(result_path), encoding='utf-8')
            self.assertEqual(verify_result(result_path)['verdict'], 'failed')
            log.write_text('changed', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'evidence hash mismatch'):
                verify_result(result_path)
            result['verdict'], result['reason'] = 'passed', None
            result_path.write_text(json.dumps(result), encoding='utf-8')
            Path(str(result_path) + '.sha256').write_text(sha(result_path), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'steps or verdict'):
                verify_result(result_path)
            plan_path.write_text('{}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'evidence hash mismatch'):
                verify_result(result_path)


if __name__ == '__main__':
    unittest.main()
