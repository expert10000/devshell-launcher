"""Live candidate cube volume worker, reproduction and consumer checks."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/scientific-broker'))
from gmsh_volume import read, run, verify


@unittest.skipUnless(all(os.environ.get(key) for key in
                         ('SCIENTIFIC_GMSH_VOLUME_PYTHON','SCIENTIFIC_VTK_PYTHON','MATH3D_ROOT')),
                     'Local Gmsh, VTK and MATH3D installations are required')
class VolumeCandidate(unittest.TestCase):
    def test_worker_repeat_boundary_and_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            records = run(os.environ['SCIENTIFIC_GMSH_VOLUME_PYTHON'],
                          os.environ['SCIENTIFIC_VTK_PYTHON'],os.environ['MATH3D_ROOT'],directory)
            self.assertEqual([verify(path)['ticket'] for path in records],
                             ['DS-SCI-067','DS-SCI-068','DS-SCI-069'])
            self.assertTrue(all(verify(path)['releaseCertified'] is False for path in records))
            repeat = read(verify(records[1])['reloadResult'])
            self.assertGreaterEqual(repeat['tetrahedra'],6)
            self.assertGreaterEqual(repeat['boundaryTriangles'],12)
            self.assertAlmostEqual(repeat['volume'],1)
            handoff = verify(records[2])
            self.assertEqual(read(handoff['vtkResult'])['state'],'accepted')
            self.assertEqual(read(handoff['math3dResult'])['state'],'accepted')
            self.assertEqual(read(handoff['vtkRejection'])['state'],'rejected')
            self.assertEqual(read(handoff['math3dRejection'])['state'],'rejected')
            artifact = Path(handoff['boundaryObj'])
            original = artifact.read_bytes()
            try:
                artifact.write_bytes(original + b' ')
                with self.assertRaisesRegex(ValueError,'evidence hash mismatch'):
                    verify(records[2])
            finally:
                artifact.write_bytes(original)
            self.assertEqual(verify(records[2])['verdict'],'passed')


if __name__ == '__main__':
    unittest.main()
