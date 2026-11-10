"""Guarded local remeshing only publishes independently accepted geometry."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_mesh_metrics import metrics
from scientific_cgal_remesh_guard import assess, run, verify


class GuardPolicyChecks(unittest.TestCase):
    def test_relative_volume_loss_rejects_candidate(self):
        original = metrics(ROOT / 'scientific/fixtures/cgal/closed-tetra.obj')
        candidate = dict(original, signedVolume=original['signedVolume'] * 0.75)
        samples = {'test': {'maximumDistance': 0}}
        shape = {'minimumAngleDegrees': 30, 'minimumShapeScore': 0.8}
        result = assess(original, candidate, samples, shape)
        self.assertFalse(result['eligible'])
        self.assertFalse(result['checks']['relativeVolume'])


@unittest.skipUnless(os.environ.get('SCIENTIFIC_CGAL_CORPUS_WORKER') and
                     os.environ.get('SCIENTIFIC_CGAL_CORPUS_PREFIX'),
                     'Local CGAL worker and prefix are required')
class LiveGuardChecks(unittest.TestCase):
    def test_accepted_and_rejected_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            args = (os.environ['SCIENTIFIC_CGAL_CORPUS_WORKER'],
                    os.environ['SCIENTIFIC_CGAL_CORPUS_PREFIX'],
                    ROOT / 'scientific/fixtures/cgal/closed-tetra.obj')
            passed, accepted = run(*args, 0.75, 1, 0, directory)
            failed, rejected = run(*args, 0.5, 2, 0, directory)
            self.assertEqual(verify(passed)['state'], 'accepted')
            self.assertEqual(verify(failed)['state'], 'rejected')
            self.assertTrue((passed.parent / 'accepted.obj').is_file())
            self.assertFalse((failed.parent / 'accepted.obj').exists())
            self.assertIsNone(rejected['acceptedSha256'])
            self.assertTrue(accepted['measurements']['decision']['eligible'])


if __name__ == '__main__':
    unittest.main()
