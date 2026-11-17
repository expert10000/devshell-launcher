import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from importlib.util import module_from_spec, spec_from_file_location

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'tools/scientific-broker/verify_runtime_review.py'
spec = spec_from_file_location('verify_runtime_review', PATH)
review = module_from_spec(spec)
spec.loader.exec_module(review)


class RuntimeReviewTests(unittest.TestCase):
    def test_archive_digest_rejects_changed_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'changed.zip'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('manifest.json', '{}')
            with self.assertRaisesRegex(ValueError, 'archive hash changed'):
                review.verify(path)

    def test_unsafe_entry_rejected_even_with_matching_archive_digest(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            path = folder / 'unsafe.zip'
            manifest = (ROOT / 'docs/evidence/scientific-runtime-review-2026-11-17.manifest.json').read_bytes()
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('../escape.jpg', b'unsafe')
                archive.writestr('manifest.json', manifest)
            baseline = json.loads(review.BASELINE.read_text(encoding='utf-8'))
            baseline['archiveSha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
            override = folder / 'baseline.json'
            override.write_text(json.dumps(baseline), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'unsafe path'):
                review.verify(path, override)


if __name__ == '__main__':
    unittest.main()
