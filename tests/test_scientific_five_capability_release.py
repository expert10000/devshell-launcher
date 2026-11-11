"""A five-capability release refuses stale lower support and source drift."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/scientific-broker'))
from five_capability_release import TARGETS, checked, require_current_support, verifier_sha  # noqa: E402
from math3d_release_identity import PACKAGE, CONSUMER, BUILD, capture as capture_math3d, verify as verify_math3d


class FiveCapabilitySupport(unittest.TestCase):
    def manifest(self):
        expected = {name: (name[0] * 64) for name in TARGETS}
        entries = []
        for name, (runtime, capability) in TARGETS.items():
            support = [{'level': f'L{index}', 'recordId': f'{index:064x}', 'runId': f'{index:032x}'}
                       for index in range(9)]
            support.append({'level': 'L9', 'recordId': expected[name], 'runId': 'f' * 32})
            entries.append({'runtimeId': runtime, 'capabilityId': capability, 'level': 'L9',
                            'recordId': expected[name], 'supportingRecords': support})
        return {'certifiedCapabilities': entries}, expected

    def test_current_five_chain(self):
        manifest, expected = self.manifest()
        self.assertEqual(len(require_current_support(manifest, expected)), 5)

    def test_missing_vtk_refused(self):
        manifest, expected = self.manifest()
        manifest['certifiedCapabilities'].pop()
        with self.assertRaisesRegex(ValueError, 'exactly current'):
            require_current_support(manifest, expected)

    def test_stale_repair_support_refused(self):
        manifest, expected = self.manifest()
        manifest['certifiedCapabilities'][2]['supportingRecords'][7]['level'] = 'L6'
        with self.assertRaisesRegex(ValueError, 'stale or incomplete'):
            require_current_support(manifest, expected)

    def test_changed_volume_record_refused(self):
        manifest, expected = self.manifest()
        manifest['certifiedCapabilities'][3]['recordId'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'stale or incomplete'):
            require_current_support(manifest, expected)

    def test_stale_vtk_l8_refused(self):
        manifest, expected = self.manifest()
        manifest['certifiedCapabilities'][-1]['supportingRecords'][8]['recordId'] = None
        with self.assertRaisesRegex(ValueError, 'stale or incomplete'):
            require_current_support(manifest, expected)

    def test_changed_source_commit_refused_before_export(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('repo', 'installed', 'math3d'):
                (root / name).mkdir()
            record = {'schemaVersion': 1, 'kind': 'scientific.five-capability-release',
                      'verifierSha256': verifier_sha(), 'repo': str(root / 'repo'),
                      'installedRoot': str(root / 'installed'), 'math3dRoot': str(root / 'math3d'),
                      'sourceCommit': 'a' * 40, 'profiles': {name: {} for name in TARGETS}}
            with patch('five_capability_release.commit', return_value='b' * 40):
                with self.assertRaisesRegex(ValueError, 'source commit changed'):
                    checked(record)

    def test_verifier_seal_ignores_checkout_line_endings(self):
        with tempfile.TemporaryDirectory() as directory:
            lf = Path(directory) / 'lf.py'
            crlf = Path(directory) / 'crlf.py'
            lf.write_bytes(b'one\ntwo\n')
            crlf.write_bytes(b'one\r\ntwo\r\n')
            self.assertEqual(verifier_sha(lf), verifier_sha(crlf))

    def test_math3d_identity_rejects_consumer_package_and_build_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
            subprocess.run(['git', 'config', 'user.email', 'test@example.invalid'], cwd=root, check=True)
            subprocess.run(['git', 'config', 'user.name', 'Test'], cwd=root, check=True)
            for name in set(PACKAGE + CONSUMER + BUILD + ('renderer/dist/index.html',)):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('{}' if name.endswith('.json') else 'fixture', encoding='utf-8')
            (root / 'package.json').write_text('{"version":"1.7.0"}')
            subprocess.run(['git', 'add', '.'], cwd=root, check=True)
            subprocess.run(['git', 'commit', '-qm', 'fixture'], cwd=root, check=True)
            commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
            import hashlib
            renderer_hash = hashlib.sha256((root / 'renderer/dist/index.html').read_bytes()).hexdigest()
            (root / 'dist/build-identity.json').write_text(json.dumps({
                'commit': commit, 'version':'1.7.0', 'dirty':False, 'rendererHash':renderer_hash}))
            identity = capture_math3d(root)
            self.assertEqual(identity, verify_math3d(root, identity))
            for name in (CONSUMER[0], PACKAGE[0], BUILD[1]):
                path = root / name
                before = path.read_bytes()
                path.write_bytes(b'{"version":"1.7.1"}' if name == PACKAGE[0] else before + b'changed')
                with self.assertRaisesRegex(ValueError, 'drifted|stale'):
                    verify_math3d(root, identity)
                path.write_bytes(before)


if __name__ == '__main__':
    unittest.main()
