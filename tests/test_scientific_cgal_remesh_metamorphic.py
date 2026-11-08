"""Scale covariance and optional native CGAL remesh replay."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_mesh_metrics import metrics
from scientific_cgal_remesh_metamorphic import check_metrics, run, verify


class RemeshScalingChecks(unittest.TestCase):
    def test_volume_must_scale_cubically(self):
        source = metrics(ROOT / 'scientific/fixtures/cgal/closed-tetra.obj')
        scaled = dict(source, area=source['area']*4, signedVolume=source['signedVolume']*8,
                      minimumEdgeLength=source['minimumEdgeLength']*2,
                      maximumEdgeLength=source['maximumEdgeLength']*2)
        check_metrics(source, scaled, 2)
        scaled['signedVolume'] = source['signedVolume']*4
        with self.assertRaisesRegex(ValueError, 'scaling changed: signedVolume'):
            check_metrics(source, scaled, 2)


@unittest.skipUnless(os.environ.get('SCIENTIFIC_CGAL_CORPUS_WORKER') and
                     os.environ.get('SCIENTIFIC_CGAL_CORPUS_PREFIX'),
                     'Local CGAL worker and prefix are required')
class LiveRemeshScalingChecks(unittest.TestCase):
    def test_seeded_native_remesh_and_input_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            target, report = run(os.environ['SCIENTIFIC_CGAL_CORPUS_WORKER'],
                                 os.environ['SCIENTIFIC_CGAL_CORPUS_PREFIX'], directory, 20261108)
            self.assertEqual(len(report['cases']), 4)
            self.assertEqual(verify(target)['verdict'], 'passed')
            source = Path(report['cases'][0]['directory']) / 'input.obj'
            original = source.read_bytes()
            try:
                source.write_bytes(original + b' ')
                with self.assertRaisesRegex(ValueError, 'evidence changed'):
                    verify(target)
            finally:
                source.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
