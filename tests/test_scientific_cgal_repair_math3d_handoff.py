"""Reject changed managed evidence before invoking the MATH3D consumer."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
spec = importlib.util.spec_from_file_location('repair_handoff', ROOT / 'tools/scientific-cgal-repair-math3d-handoff.py')
handoff = importlib.util.module_from_spec(spec)
spec.loader.exec_module(handoff)


class RepairHandoffChecks(unittest.TestCase):
    def test_changed_artifact_or_audit_is_rejected_before_import(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset, run = root / 'datasets', root / 'run'
            dataset.mkdir(); run.mkdir()
            source, output = dataset / 'input.obj', run / 'repaired.obj'
            shutil.copyfile(ROOT / 'scientific/fixtures/cgal-repair/tetra-one-hole.obj', source)
            shutil.copyfile(ROOT / 'scientific/fixtures/cgal/closed-tetra.obj', output)
            request = {'runId': 'a' * 32, 'recipeId': 'cgal.fill-one-hole', 'workingDirectory': str(run),
                       'datasetRoot': str(dataset), 'inputArtifacts': [{'path': str(source), 'sha256': handoff.sha(source)}],
                       'outputArtifacts': [{'path': output.name}]}
            result = {'runId': request['runId'], 'recipeId': request['recipeId'], 'state': 'succeeded',
                      'validatedCapabilities': ['mesh.repair'],
                      'artifacts': [{'path': output.name, 'sha256': handoff.sha(output)}],
                      'engineDetails': {'beforeFaces': 3, 'afterFaces': 4, 'boundaryLoopsBefore': 1,
                                        'boundaryEdgesBefore': 3, 'holesFilled': 1, 'patchFaces': 1,
                                        'patchFaceCounts': [1], 'signedVolumeAfter': 1 / 6},
                      'repairAudit': {'retainedFaces': 0}}
            (run / 'request.json').write_text(json.dumps(request), encoding='utf-8')
            result['artifacts'][0]['sha256'] = '0' * 64
            (run / 'results.json').write_text(json.dumps(result), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'artifact changed'):
                handoff.verify(run, ROOT, 'node', root / 'handoff.json')
            result['artifacts'][0]['sha256'] = handoff.sha(output)
            (run / 'results.json').write_text(json.dumps(result), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'audit changed'):
                handoff.verify(run, ROOT, 'node', root / 'handoff.json')


if __name__ == '__main__':
    unittest.main()
