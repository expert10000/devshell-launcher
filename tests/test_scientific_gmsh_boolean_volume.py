import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'tools/scientific-gmsh-boolean-volume.py'
BOUNDARY_SCRIPT = ROOT / 'tools/scientific-gmsh-boundary-extract.py'
spec = importlib.util.spec_from_file_location('gmsh_bridge', SCRIPT)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
VERTICES = [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]
FACES = [(1,3,2),(1,4,3),(5,6,7),(5,7,8),(1,2,6),(1,6,5),
         (2,3,7),(2,7,6),(3,4,8),(3,8,7),(4,1,5),(4,5,8)]


def setup(root, faces=FACES, expected=None):
    source = root / 'boolean.obj'
    source.write_text(''.join('v %s %s %s\n' % vertex for vertex in VERTICES)
                      + ''.join('f %s %s %s\n' % face for face in faces), encoding='utf-8')
    data = source.read_bytes()
    request = root / 'request.json'
    request.write_text(json.dumps({
        'schemaVersion': 1, 'operation': 'gmsh.mesh', 'runId': 'a' * 32,
        'sourceRunId': 'b' * 32, 'sourceCommit': 'c' * 40,
        'sourceSnapshotSha256': 'd' * 64, 'inputId': 'boolean-surface',
        'workingDirectory': str(root), 'artifactRoot': str(root), 'lengthUnit': 'mm',
        'frame': 'world', 'meshSize': 0.5,
        'inputArtifact': {'path': str(source), 'sha256': expected or hashlib.sha256(data).hexdigest(),
                          'bytes': len(data)},
    }), encoding='utf-8')
    return request


class GmshBridgeTests(unittest.TestCase):
    def test_changed_and_open_boolean_surface_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request = setup(root, expected='0' * 64)
            with self.assertRaisesRegex(ValueError, 'changed'):
                bridge.mesh(request)
            request = setup(root, faces=FACES[:-1])
            with self.assertRaisesRegex(ValueError, 'closed manifold'):
                bridge.mesh(request)
            self.assertFalse((root / 'volume.msh').exists())

    def test_live_closed_surface_to_tetrahedral_volume(self):
        python = os.environ.get('DEVSHELL_SCIENTIFIC_PYTHON')
        if not python or not Path(python).is_file():
            self.skipTest('DEVSHELL_SCIENTIFIC_PYTHON is required')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request = setup(root)
            result = subprocess.run([python, str(SCRIPT), '--request', str(request)],
                                    check=True, capture_output=True, text=True)
            record = json.loads(result.stdout)
            self.assertEqual(record['dimension'], 3)
            self.assertGreater(record['tetrahedra'], 0)
            self.assertAlmostEqual(record['tetrahedralVolume'], 8, places=4)
            self.assertEqual(record['physicalGroups']['BooleanVolume']['dimension'], 3)
            self.assertEqual(record['outputHashes']['gmsh-mesh'], hashlib.sha256((root / 'volume.msh').read_bytes()).hexdigest())
            reload_script = ("import gmsh,json,sys; gmsh.initialize(); gmsh.option.setNumber('General.Terminal',0); "
                             "gmsh.open(sys.argv[1]); print(json.dumps({'groups':[(d,gmsh.model.getPhysicalName(d,t)) "
                             "for d,t in gmsh.model.getPhysicalGroups()], 'tets':len(gmsh.model.mesh.getElementsByType(4)[0])})); gmsh.finalize()")
            reopened = subprocess.run([python, '-c', reload_script, str(root / 'volume.msh')],
                                      check=True, capture_output=True, text=True)
            payload = json.loads(reopened.stdout)
            self.assertIn([3, 'BooleanVolume'], payload['groups'])
            self.assertIn([2, 'InputBoundary'], payload['groups'])
            self.assertEqual(payload['tets'], record['tetrahedra'])
            boundary = root / 'boundary'
            boundary.mkdir()
            msh = root / 'volume.msh'
            boundary_request = boundary / 'request.json'
            boundary_request.write_text(json.dumps({
                'schemaVersion': 1, 'operation': 'gmsh.extract-boundary',
                'runId': 'e' * 32, 'sourceRunId': 'a' * 32, 'sourceCommit': 'c' * 40,
                'sourceSnapshotSha256': 'd' * 64, 'inputId': 'gmsh-mesh',
                'workingDirectory': str(boundary), 'artifactRoot': str(root),
                'lengthUnit': 'mm', 'frame': 'world',
                'inputArtifact': {'path': str(msh), 'sha256': record['outputHashes']['gmsh-mesh'],
                                  'bytes': msh.stat().st_size},
            }), encoding='utf-8')
            extracted = subprocess.run([python, str(BOUNDARY_SCRIPT), '--request', str(boundary_request)],
                                       check=True, capture_output=True, text=True)
            shell = json.loads(extracted.stdout)
            self.assertEqual(shell['derivedFromDimension'], 3)
            self.assertEqual(shell['dimension'], 2)
            self.assertAlmostEqual(shell['tetrahedralVolume'], 8, places=4)
            self.assertEqual(shell['outputHashes']['gmsh-boundary'],
                             hashlib.sha256((boundary / 'boundary.obj').read_bytes()).hexdigest())
            vtk_python = os.environ.get('DEVSHELL_VTK_PYTHON')
            if vtk_python and Path(vtk_python).is_file():
                vtp = root / 'vtk-analysis.vtp'
                vtk_script = ("import vtk,json,sys; r=vtk.vtkOBJReader(); r.SetFileName(sys.argv[1]); "
                              "t=vtk.vtkTriangleFilter(); t.SetInputConnection(r.GetOutputPort()); t.Update(); "
                              "m=t.GetOutput(); assert m.GetNumberOfPolys()>0; "
                              "w=vtk.vtkXMLPolyDataWriter(); w.SetFileName(sys.argv[2]); "
                              "w.SetInputData(m); assert w.Write()==1; "
                              "print(json.dumps({'points':m.GetNumberOfPoints(),'triangles':m.GetNumberOfPolys()}))")
                viewed = subprocess.run([vtk_python, '-c', vtk_script, str(boundary / 'boundary.obj'), str(vtp)],
                                        check=True, capture_output=True, text=True)
                self.assertGreater(json.loads(viewed.stdout)['triangles'], 12)
                scipy_dir = root / 'scipy'
                scipy_dir.mkdir()
                scipy_request = scipy_dir / 'request.json'
                scipy_request.write_text(json.dumps({
                    'schemaVersion': 1, 'operation': 'scipy.measure', 'runId': 'f' * 32,
                    'sourceRunId': 'e' * 32, 'sourceCommit': 'c' * 40,
                    'sourceSnapshotSha256': 'd' * 64, 'inputId': 'vtk-analysis',
                    'workingDirectory': str(scipy_dir), 'artifactRoot': str(root),
                    'lengthUnit': 'mm', 'frame': 'world',
                    'inputArtifact': {'path': str(vtp), 'sha256': hashlib.sha256(vtp.read_bytes()).hexdigest(),
                                      'bytes': vtp.stat().st_size},
                }), encoding='utf-8')
                measured = subprocess.run([python, str(ROOT / 'tools/scientific-scipy-surface-measure.py'),
                                            '--request', str(scipy_request)],
                                          check=True, capture_output=True, text=True)
                self.assertAlmostEqual(json.loads(measured.stdout)['measurement']['value'], 24, places=4)


if __name__ == '__main__':
    unittest.main()
