"""A semantic verification is reused only while every witnessed byte is fixed."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/scientific-broker'))
from verified_evidence_cache import VerifiedEvidenceCache


class VerifiedEvidenceCacheTests(unittest.TestCase):
    def test_reuses_one_check_and_rejects_artifact_tamper_or_new_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            record = root / 'record.json'
            artifact = root / 'artifact.obj'
            record.write_text('{}')
            artifact.write_text('v 0 0 0\n')
            calls = []
            def verify():
                calls.append(1)
                return {'qualified': True}
            cache = VerifiedEvidenceCache()
            cache.add('classes', record, verify())
            self.assertEqual(cache.get('classes', record), cache.get('classes', record))
            self.assertEqual(len(calls), 1)
            artifact.write_text('v 1 0 0\n')
            with self.assertRaisesRegex(ValueError, 'changed'):
                cache.get('classes', record)
            artifact.write_text('v 0 0 0\n')
            (root / 'new.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'changed'):
                cache.get('classes', record)

    def test_source_witness_rejects_drift_even_with_same_commit(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = Path(folder)
            subprocess.run(['git', 'init', '-q', str(repo)], check=True)
            subprocess.run(['git', '-C', str(repo), 'config', 'user.email', 'test@example.invalid'], check=True)
            subprocess.run(['git', '-C', str(repo), 'config', 'user.name', 'Test'], check=True)
            source = repo / 'source.txt'
            source.write_text('original')
            subprocess.run(['git', '-C', str(repo), 'add', 'source.txt'], check=True)
            subprocess.run(['git', '-C', str(repo), 'commit', '-qm', 'initial'], check=True)
            head = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
            cache = VerifiedEvidenceCache()
            cache.bind_source(repo, head)
            cache.check_source(repo, head)
            source.write_text('changed')
            with self.assertRaisesRegex(ValueError, 'drifted'):
                cache.check_source(repo, head)


if __name__ == '__main__':
    unittest.main()
