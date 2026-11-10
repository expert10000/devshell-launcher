"""Live managed remesh must withhold an adverse candidate."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import uuid
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_corpus import sha
from scientific_cgal_remesh_guard import verify as verify_guard


@unittest.skipUnless(os.environ.get('SCIENTIFIC_CGAL_WORKER') and
                     os.environ.get('SCIENTIFIC_CGAL_PREFIX'), 'A built CGAL worker and prefix are required')
class ManagedRemeshGuard(unittest.TestCase):
    def test_accepted_mesh_and_rejected_candidate(self):
        worker = Path(os.environ['SCIENTIFIC_CGAL_WORKER'])
        prefix = Path(os.environ['SCIENTIFIC_CGAL_PREFIX'])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset = root / 'datasets'
            dataset.mkdir()
            source = dataset / 'closed-tetra.obj'
            shutil.copyfile(ROOT / 'scientific/fixtures/cgal/closed-tetra.obj', source)
            for iterations, state in ((1, 'succeeded'), (2, 'failed')):
                run = root / f'run-{iterations}'
                run.mkdir()
                request = {'schemaVersion': 1, 'runId': uuid.uuid4().hex,
                           'runtimeId': 'cgal-win-conda', 'recipeId': 'cgal.remesh',
                           'workingDirectory': str(run), 'datasetRoot': str(dataset),
                           'inputArtifacts': [{'path': str(source), 'sha256': sha(source)}],
                           'outputArtifacts': [{'path': 'accepted.obj'}],
                           'parameters': {'targetEdge': 0.5, 'iterations': iterations,
                                          'preserveBoundary': False}}
                path = run / 'request.json'
                path.write_text(json.dumps(request), encoding='utf-8')
                process = subprocess.run([str(prefix / 'python.exe'),
                    str(ROOT / 'tools/scientific-cgal-worker.py'), '--request', str(path),
                    '--worker', str(worker), '--prefix', str(prefix)],
                    capture_output=True, text=True, timeout=120)
                result = json.loads((run / 'results.json').read_text(encoding='utf-8'))
                self.assertEqual(result['state'], state, process.stderr[-800:])
                self.assertEqual((run / 'accepted.obj').exists(), state == 'succeeded')
                self.assertEqual(len(result['artifacts']), int(state == 'succeeded'))
                self.assertEqual('mesh.remesh' in result['validatedCapabilities'], state == 'succeeded')
                evidence = result['guardEvidence']
                report_path = run / evidence['path']
                self.assertEqual(verify_guard(report_path)['state'], evidence['state'])
                self.assertTrue((report_path.parent / 'candidate.obj').is_file())


if __name__ == '__main__':
    unittest.main()
