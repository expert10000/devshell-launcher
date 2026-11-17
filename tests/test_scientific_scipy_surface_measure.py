import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'tools/scientific-scipy-surface-measure.py'
spec = importlib.util.spec_from_file_location('scipy_measure', SCRIPT)
measure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measure)


def request(directory, source, expected=None):
    path = Path(directory) / 'request.json'
    data = source.read_bytes()
    path.write_text(json.dumps({
        'schemaVersion': 1, 'runId': 'a' * 32, 'sourceRunId': 'd' * 32, 'operation': 'scipy.measure',
        'workingDirectory': str(Path(directory).resolve()), 'artifactRoot': str(source.parent),
        'lengthUnit': 'mm', 'frame': 'world', 'sourceCommit': 'b' * 40,
        'sourceSnapshotSha256': 'c' * 64, 'inputId': 'vtk-analysis',
        'inputArtifact': {'path': str(source), 'bytes': len(data),
                          'sha256': expected or hashlib.sha256(data).hexdigest()},
    }), encoding='utf-8')
    return path


class SciPySurfaceTests(unittest.TestCase):
    def test_changed_input_rejected_before_parse(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'mesh.vtp'
            source.write_bytes(b'changed')
            path = request(directory, source, '0' * 64)
            with self.assertRaisesRegex(ValueError, 'changed'):
                measure.measure(path)
            self.assertFalse((Path(directory) / 'measurement.json').exists())

    def test_live_vtk_to_scipy_area(self):
        vtk_python = os.environ.get('DEVSHELL_VTK_PYTHON')
        scipy_python = os.environ.get('DEVSHELL_SCIENTIFIC_PYTHON')
        if not vtk_python or not scipy_python or not Path(vtk_python).is_file() or not Path(scipy_python).is_file():
            self.skipTest('DEVSHELL_VTK_PYTHON and DEVSHELL_SCIENTIFIC_PYTHON are required')
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'mesh.vtp'
            script = ("import vtk,sys; c=vtk.vtkCubeSource(); c.SetXLength(2); c.SetYLength(2); c.SetZLength(2); "
                      "t=vtk.vtkTriangleFilter(); t.SetInputConnection(c.GetOutputPort()); t.Update(); "
                      "w=vtk.vtkXMLPolyDataWriter(); w.SetFileName(sys.argv[1]); "
                      "w.SetInputConnection(t.GetOutputPort()); assert w.Write()==1")
            subprocess.run([vtk_python, '-c', script, str(source)], check=True, capture_output=True, text=True)
            path = request(directory, source)
            result = subprocess.run([scipy_python, str(SCRIPT), '--request', str(path)],
                                    check=True, capture_output=True, text=True)
            measurement = json.loads(result.stdout)['measurement']
            self.assertAlmostEqual(measurement['value'], 24.0, places=8)
            self.assertEqual(measurement['unit'], 'mm2')
            self.assertEqual(measurement['sourceArtifactSha256'], hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertEqual(json.loads((Path(directory) / 'measurement.json').read_text())['measurement'], measurement)


if __name__ == '__main__':
    unittest.main()
