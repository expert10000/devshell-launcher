"""Volume fidelity gate for bounded native CGAL remeshing."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_mesh_metrics import metrics
from scientific_cgal_remesh_fidelity import classify, run, verify


class FidelityPolicyChecks(unittest.TestCase):
    def test_volume_loss_is_ineligible(self):
        original = metrics(ROOT / 'scientific/fixtures/cgal/closed-tetra.obj')
        changed = dict(original, signedVolume=original['signedVolume'] * 0.75)
        self.assertFalse(classify(changed, original)['volumeEligible'])


@unittest.skipUnless(os.environ.get('SCIENTIFIC_CGAL_CORPUS_WORKER') and
                     os.environ.get('SCIENTIFIC_CGAL_CORPUS_PREFIX'),
                     'Local CGAL worker and prefix are required')
class LiveFidelityChecks(unittest.TestCase):
    def test_six_settings_and_artifact_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            target, report = run(os.environ['SCIENTIFIC_CGAL_CORPUS_WORKER'],
                                 os.environ['SCIENTIFIC_CGAL_CORPUS_PREFIX'], directory)
            self.assertEqual(len(report['cases']), 6)
            self.assertEqual(report['eligibleCount'], 5)
            self.assertEqual(verify(target)['verdict'], 'measured')
            last = report['cases'][-1]
            self.assertEqual((last['targetEdge'], last['iterations']), (0.5, 2))
            self.assertFalse(last['fidelity']['volumeEligible'])
            output = Path(last['directory']) / 'output.obj'
            original = output.read_bytes()
            try:
                output.write_bytes(original + b' ')
                with self.assertRaisesRegex(ValueError, 'artifact changed'):
                    verify(target)
            finally:
                output.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
