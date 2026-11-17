import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'tools/scientific-vtk-boundary-inspect.py'
spec = importlib.util.spec_from_file_location('vtk_boundary', SCRIPT)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


class VtkBoundaryTests(unittest.TestCase):
    def test_changed_boundary_rejected_before_vtk_import(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'boundary.obj'
            source.write_text('v 0 0 0\n', encoding='utf-8')
            request = root / 'request.json'
            request.write_text(json.dumps({
                'schemaVersion': 1, 'operation': 'mesh.inspect', 'runId': 'a' * 32,
                'sourceRunId': 'b' * 32, 'sourceCommit': 'c' * 40,
                'sourceSnapshotSha256': 'd' * 64, 'inputId': 'gmsh-boundary',
                'workingDirectory': str(root), 'artifactRoot': str(root),
                'lengthUnit': 'mm', 'frame': 'world',
                'inputArtifact': {'path': str(source), 'sha256': '0' * 64,
                                  'bytes': source.stat().st_size},
            }), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'changed'):
                worker.inspect(request)
            self.assertFalse((root / 'analysis.vtp').exists())
            self.assertFalse((root / 'preview.png').exists())


if __name__ == '__main__':
    unittest.main()
