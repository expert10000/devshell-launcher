"""Contract checks for the desktop CGAL hole-repair adapter."""
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_mesh_metrics import metrics

spec = importlib.util.spec_from_file_location('managed_repair', ROOT / 'tools' / 'scientific-cgal-hole-repair-worker.py')
repair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)


class ManagedRepairEvidenceTests(unittest.TestCase):
    def test_fixture_topologies_match_explicit_operations(self):
        cases = (
            ('cgal.fill-one-hole', 'scientific/fixtures/cgal-repair/tetra-one-hole.obj'),
            ('cgal.fill-quad-hole', 'scientific/fixtures/cgal-repair-quad/cube-one-quad-hole.obj'),
            ('cgal.fill-two-quad-holes', 'scientific/fixtures/cgal-repair-multi/cube-two-square-holes.obj'),
        )
        for recipe, path in cases:
            with self.subTest(recipe=recipe):
                measured = metrics(ROOT / path)
                _, loops, edges, _ = repair.OPERATIONS[recipe]
                self.assertEqual((measured['boundaryLoops'], measured['boundaryEdges']), (loops, edges))
                self.assertEqual(measured['components'], 1)

    def test_evidence_rejects_wrong_face_count_and_volume(self):
        before = {'faces': 3, 'vertices': 4, 'boundaryLoops': 1, 'boundaryEdges': 3,
                  'boundaryLoopEdgeCounts': [3], 'components': 1,
                  'maximumEdgeIncidence': 2, 'degenerateFaces': 0}
        after = {'faces': 4, 'vertices': 4, 'boundaryLoops': 0, 'boundaryEdges': 0,
                 'components': 1, 'maximumEdgeIncidence': 2, 'degenerateFaces': 0,
                 'signedVolume': 1 / 6}
        engine = {'beforeFaces': 3, 'afterFaces': 4, 'boundaryLoopsBefore': 1,
                  'boundaryEdgesBefore': 3, 'holesFilled': 1, 'patchFaces': 1,
                  'patchFaceCounts': [1], 'signedVolumeAfter': 1 / 6}
        repair.check_geometry(before, after, engine, 'cgal.fill-one-hole')
        for key, value in (('afterFaces', 5), ('signedVolumeAfter', -1)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                repair.check_geometry(before, after, {**engine, key: value}, 'cgal.fill-one-hole')

    def test_bounded_boundary_measurement(self):
        path = ROOT / 'scientific/fixtures/cgal-repair-bounded/pentagonal-pyramid-open-base.obj'
        self.assertEqual(repair.boundary_sizes(path), [5])
        path = ROOT / 'scientific/fixtures/cgal-repair-multi/cube-two-square-holes.obj'
        self.assertEqual(repair.boundary_sizes(path), [4, 4])


if __name__ == '__main__':
    unittest.main()
