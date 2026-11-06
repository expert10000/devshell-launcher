"""The local foundation record remains verifiable and outside release certification."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools' / 'scientific-broker'
sys.path.insert(0, str(TOOL))
spec = importlib.util.spec_from_file_location('gmsh_foundation', TOOL / 'gmsh_foundation.py')
foundation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(foundation)


class GmshFoundationTests(unittest.TestCase):
    def test_local_foundation_evidence_is_sealed_and_not_certified(self):
        root = ROOT / '.scientific' / 'gmsh-foundation'
        records = sorted(root.glob('*/foundation.json'), key=lambda path: path.stat().st_mtime) if root.exists() else []
        if not records:
            self.skipTest('Local Gmsh foundation run is unavailable')
        record = foundation.verify(records[-1])
        self.assertEqual(set(record['levels']), {f'L{i}' for i in range(5)})
        self.assertTrue(all(item['verdict'] == 'passed' for item in record['levels'].values()))
        self.assertFalse(record['releaseCertified'])
        with tempfile.TemporaryDirectory() as directory:
            copy = Path(directory) / 'foundation.json'
            copy.write_bytes(records[-1].read_bytes() + b' ')
            Path(str(copy) + '.sha256').write_text(Path(str(records[-1]) + '.sha256').read_text())
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                foundation.verify(copy)


if __name__ == '__main__':
    unittest.main()
