"""Local Gmsh worker, reproduction and consumer verdicts stay evidence-bound."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools' / 'scientific-broker'
sys.path.insert(0, str(TOOL))
spec = importlib.util.spec_from_file_location('gmsh_progression', TOOL / 'gmsh_progression.py')
progression = importlib.util.module_from_spec(spec)
spec.loader.exec_module(progression)


class GmshProgressionTests(unittest.TestCase):
    def test_comparison_requires_orientation_scale_and_topology(self):
        mesh = {'state': 'accepted', 'outputObjSha256': 'a', 'inputObjSha256': 'a',
                'points': 4, 'triangles': 2, 'boundaryEdges': 4, 'nonManifoldEdges': 0,
                'bounds': [0,1,0,1,0,0], 'signedAreaXY': 1}
        self.assertTrue(progression.comparable(mesh, mesh, mesh))
        self.assertFalse(progression.comparable(mesh, mesh, {**mesh, 'signedAreaXY': -1}))
        self.assertFalse(progression.comparable(mesh, mesh, {**mesh, 'bounds': [0,2,0,1,0,0]}))
        self.assertFalse(progression.comparable(mesh, mesh, {**mesh, 'boundaryEdges': 0}))
        self.assertFalse(progression.comparable(mesh, mesh, {**mesh, 'signedAreaXY': float('nan')}))

    def test_saved_local_chain_is_sealed_and_not_release_certified(self):
        root = ROOT / '.scientific' / 'gmsh-progression'
        records = sorted(root.glob('*/DS-SCI-057.json'), key=lambda path: path.stat().st_mtime) if root.exists() else []
        if not records:
            self.skipTest('Local Gmsh progression evidence is unavailable')
        record = progression.verify(records[-1])
        self.assertEqual('passed', record['verdict'])
        self.assertFalse(record['releaseCertified'])
        with tempfile.TemporaryDirectory() as directory:
            copy = Path(directory) / 'DS-SCI-057.json'
            copy.write_bytes(records[-1].read_bytes() + b' ')
            Path(str(copy) + '.sha256').write_text(Path(str(records[-1]) + '.sha256').read_text())
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                progression.verify(copy)


if __name__ == '__main__':
    unittest.main()
