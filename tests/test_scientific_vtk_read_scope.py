"""VTK read scope accepts only its pinned, live worker evidence."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_vtk_read_scope import CASES, manifest, run, verify  # noqa: E402


class VtkReadScopeChecks(unittest.TestCase):
    def test_pinned_case_set(self):
        cases = manifest()['cases']
        self.assertEqual(tuple(item['caseId'] for item in cases), CASES)
        self.assertEqual(sum(item['expected'] == 'accepted' for item in cases), 6)
        self.assertEqual(sum(item['expected'] == 'rejected' for item in cases), 3)

    @unittest.skipUnless(os.environ.get('DEVSHELL_VTK_PYTHON'), 'Set DEVSHELL_VTK_PYTHON for live worker test')
    def test_live_replay_and_tamper(self):
        with tempfile.TemporaryDirectory() as temporary:
            path, report = run(os.environ['DEVSHELL_VTK_PYTHON'], temporary)
            self.assertEqual(verify(path), report)
            output = path.parent / 'tetra' / 'mesh.vtp'
            output.write_bytes(output.read_bytes() + b'changed')
            with self.assertRaisesRegex(ValueError, 'output changed'):
                verify(path)


if __name__ == '__main__':
    unittest.main()
