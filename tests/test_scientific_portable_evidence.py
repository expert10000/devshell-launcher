"""Portable release evidence checks survive a move and reject changed content."""
import json
import base64
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sys
import struct
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools' / 'scientific-broker'))
from portable_evidence import digest, path_free, redact, verify, verify_signature, portable_artifact
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization


class RedactionTests(unittest.TestCase):
    def test_nested_paths_are_redacted(self):
        source = {'command': 'open C:\\private\\workspace\\run.json',
                  'items': ['G:\\master\\Math3D\\mesh.obj', {'path': 'C:/isolated/release.json'}]}
        value = redact(source)
        self.assertEqual(source['items'][0], 'G:\\master\\Math3D\\mesh.obj')
        self.assertNotIn('private', json.dumps(value))
        self.assertNotIn('Math3D', json.dumps(value))
        path_free(json.dumps(value).encode())

    def test_safe_native_format_and_path_bearing_json(self):
        sample = struct.pack('<4sIII', b'M3DT', 1, 0, 0)
        data, policy = portable_artifact('product/volume.m3dt', sample)
        self.assertEqual('native-mesh-v1', policy)
        self.assertEqual(sample, data)
        with self.assertRaisesRegex(ValueError, 'invalid header'):
            portable_artifact('product/volume.m3dt', b'MZ' + bytes(30))
        source = json.dumps({'C:/private/run': {'path': 'C:/private/file'}}).encode()
        redacted, policy = portable_artifact('volume/DS-SCI-067.json', source)
        self.assertEqual('redacted-json', policy)
        path_free(redacted)

    def test_signature_trust_rotation_and_revocation(self):
        private = Ed25519PrivateKey.generate()
        now = datetime.now(timezone.utc)
        body = b'{"signed":true}'
        signature = {'algorithm':'Ed25519', 'keyId':'release-2026', 'signedAtUtc':now.isoformat(),
                     'signatureBase64':base64.b64encode(private.sign(body)).decode()}
        key = {'keyId':'release-2026',
               'publicKeyBase64':base64.b64encode(private.public_key().public_bytes(
                   serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode(),
               'validFromUtc':(now-timedelta(days=1)).isoformat(),
               'validUntilUtc':(now+timedelta(days=1)).isoformat()}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'trust.json'
            path.write_text(json.dumps({'schemaVersion':1,'keys':[key]}))
            verify_signature(body, signature, path)
            with self.assertRaisesRegex(ValueError, 'signature changed'):
                verify_signature(body+b' ', signature, path)
            key['revokedAtUtc'] = (now-timedelta(seconds=1)).isoformat()
            path.write_text(json.dumps({'schemaVersion':1,'keys':[key]}))
            with self.assertRaisesRegex(ValueError, 'revoked'):
                verify_signature(body, signature, path)
            del key['revokedAtUtc']
            key['validFromUtc'] = (now+timedelta(seconds=1)).isoformat()
            path.write_text(json.dumps({'schemaVersion':1,'keys':[key]}))
            with self.assertRaisesRegex(ValueError, 'not valid'):
                verify_signature(body, signature, path)


@unittest.skipUnless(os.environ.get('SCIENTIFIC_PORTABLE_BUNDLE'), 'A live portable bundle is required')
class LivePortableEvidence(unittest.TestCase):
    def test_moved_bundle_and_rehashed_content_tamper(self):
        source = Path(os.environ['SCIENTIFIC_PORTABLE_BUNDLE'])
        trust = os.environ.get('SCIENTIFIC_PORTABLE_TRUST_STORE')
        self.assertEqual('verified-historical-evidence', verify(source, trust)['verdict'])
        with tempfile.TemporaryDirectory() as directory:
            moved = Path(directory) / 'moved.zip'
            moved.write_bytes(source.read_bytes())
            self.assertEqual(verify(source, trust)['manifestSha256'], verify(moved, trust)['manifestSha256'])
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
            with self.assertRaisesRegex(ValueError, 'Supporting qualification changed|Qualification record hash changed|signature changed'):
                verify(moved, trust)


if __name__ == '__main__':
    unittest.main()
