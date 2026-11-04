"""Check that independently reloading the real MATH3D artifact rejects corruption."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'tools' / 'scientific-broker' / 'check_m3dm_roundtrip.py'
spec = importlib.util.spec_from_file_location('check_m3dm_roundtrip', SCRIPT)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)
sys.path.insert(0, str(SCRIPT.parent))
from smoke import verify_saved_smoke


@unittest.skipUnless(os.environ.get('SCIENTIFIC_M3DM_PRODUCT'), 'A fresh broker smoke product is required')
class M3DMRoundTrip(unittest.TestCase):
    def setUp(self):
        self.product = Path(os.environ['SCIENTIFIC_M3DM_PRODUCT']).resolve()
        self.obj = self.product.parent / 'l5-positive.obj'
        self.m3dm = self.product / 'qualified-mesh.m3dm'
        self.writer = self.product / 'm3dm-write.json'

    def changed(self, transform):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'changed.m3dm'
            data = bytearray(self.m3dm.read_bytes())
            transform(data)
            path.write_bytes(data)
            report = json.loads(self.writer.read_text())
            report['m3dmSha256'] = hashlib.sha256(data).hexdigest()
            writer = Path(directory) / 'writer.json'
            writer.write_text(json.dumps(report))
            with self.assertRaises(ValueError):
                checker.check(self.obj, path, writer)

    def test_real_roundtrip_and_corruption(self):
        result = checker.check(self.obj, self.m3dm, self.writer)
        self.assertEqual(result['verdict'], 'passed')
        self.changed(lambda data: data.__setitem__(slice(0, 4), b'FAIL'))
        self.changed(lambda data: struct.pack_into('<I', data, 32 + 4 * 12, 99))
        self.changed(lambda data: struct.pack_into('<f', data, 32, 2.0))

    def test_saved_evidence_detects_changed_viewer(self):
        self.assertEqual(verify_saved_smoke(self.product.parent)['state'], 'passed')
        with tempfile.TemporaryDirectory() as directory:
            copy = Path(directory) / self.product.parent.name
            shutil.copytree(self.product.parent, copy)
            screenshot = copy / 'product' / 'viewer.png'
            changed = bytearray(screenshot.read_bytes())
            changed[0] ^= 1
            screenshot.write_bytes(changed)
            with self.assertRaisesRegex(ValueError, 'viewerSha256 hash mismatch'):
                verify_saved_smoke(copy)


if __name__ == '__main__':
    unittest.main()
