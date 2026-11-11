"""Portable release evidence checks survive a move and reject changed content."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools' / 'scientific-broker'))
from portable_evidence import digest, path_free, redact, verify


class RedactionTests(unittest.TestCase):
    def test_nested_paths_are_redacted(self):
        source = {'command': 'open C:\\private\\workspace\\run.json',
                  'items': ['G:\\master\\Math3D\\mesh.obj', {'path': 'C:/isolated/release.json'}]}
        value = redact(source)
        self.assertEqual(source['items'][0], 'G:\\master\\Math3D\\mesh.obj')
        self.assertNotIn('private', json.dumps(value))
        self.assertNotIn('Math3D', json.dumps(value))
        path_free(json.dumps(value).encode())


@unittest.skipUnless(os.environ.get('SCIENTIFIC_PORTABLE_BUNDLE'), 'A live portable bundle is required')
class LivePortableEvidence(unittest.TestCase):
    def test_moved_bundle_and_rehashed_content_tamper(self):
        source = Path(os.environ['SCIENTIFIC_PORTABLE_BUNDLE'])
        self.assertEqual('verified-historical-evidence', verify(source)['verdict'])
        with tempfile.TemporaryDirectory() as directory:
            moved = Path(directory) / 'moved.zip'
            moved.write_bytes(source.read_bytes())
            self.assertEqual(verify(source)['manifestSha256'], verify(moved)['manifestSha256'])
            with zipfile.ZipFile(source) as archive:
                files = {name: archive.read(name) for name in archive.namelist()}
            certified = json.loads(files['release/certified.json'])
            run_id = certified['certifiedCapabilities'][0]['supportingRecords'][0]['runId']
            name = f'runs/{run_id}/qualifications.json'
            altered = json.loads(files[name])
            altered['records'][0]['capabilityId'] = 'mesh.tampered'
            files[name] = json.dumps(altered, separators=(',', ':')).encode()
            manifest = json.loads(files['manifest.json'])
            entry = next(item for item in manifest['files'] if item['path'] == name)
            entry['sha256'] = digest(files[name])
            entry['bytes'] = len(files[name])
            files['manifest.json'] = json.dumps(manifest, separators=(',', ':')).encode()
            files['manifest.sha256'] = digest(files['manifest.json']).encode()
            with zipfile.ZipFile(moved, 'w') as archive:
                for path, content in files.items():
                    archive.writestr(path, content)
            with self.assertRaisesRegex(ValueError, 'Supporting qualification changed|Qualification record hash changed'):
                verify(moved)


if __name__ == '__main__':
    unittest.main()
