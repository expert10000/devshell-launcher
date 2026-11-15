"""Paired inspection ranking abstains on ties, disagreement and missing resources."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/scientific-broker'))
from inspect_ranking import policy, rank_class  # noqa: E402


def class_evidence(cold_cgal, cold_vtk, warm_cgal, warm_vtk, rss=40 * 1048576):
    runs = {'cgal': [], 'vtk': []}
    for provider, cold, warm in (('cgal', cold_cgal, warm_cgal), ('vtk', cold_vtk, warm_vtk)):
        runs[provider] = [{'coldInvocationMs': c, 'warmExecutionMs': w,
                           'warmExecutionUs': int(w * 1000), 'peakRssBytes': rss}
                          for c, w in zip(cold, warm)]
    return {'runs': runs, 'statistics': {name: {'peakRssBytes': rss} for name in runs}}


class InspectRankingTests(unittest.TestCase):
    def setUp(self):
        self.policy, _ = policy(ROOT)

    def test_clear_paired_winner(self):
        saved = class_evidence([100, 101, 99, 102, 98], [180, 181, 179, 182, 178],
                               [10, 11, 9, 12, 8], [30, 31, 29, 32, 28])
        self.assertEqual(rank_class(saved, 'tetra-uniform-4', self.policy)['recommendation'], 'cgal-win-conda')

    def test_close_or_disagreeing_evidence_abstains(self):
        tied = class_evidence([100, 101, 99, 102, 98], [101, 100, 102, 99, 103],
                              [10, 11, 9, 12, 8], [11, 10, 12, 9, 13])
        split = class_evidence([100] * 5, [200] * 5, [30] * 5, [10] * 5)
        self.assertIsNone(rank_class(tied, 'tetra-uniform-4', self.policy)['recommendation'])
        self.assertIsNone(rank_class(split, 'tetra-uniform-4', self.policy)['recommendation'])

    def test_resource_limit_and_sample_count_abstain(self):
        saved = class_evidence([100] * 5, [200] * 5, [10] * 5, [30] * 5, rss=3 * 1024**3)
        self.assertIsNone(rank_class(saved, 'tetra-uniform-4', self.policy)['recommendation'])
        saved['runs']['cgal'].pop()
        self.assertIsNone(rank_class(saved, 'tetra-uniform-4', self.policy)['recommendation'])

    def test_missing_or_rounded_warm_measurement_abstains(self):
        saved = class_evidence([100] * 5, [200] * 5, [1] * 5, [30] * 5)
        saved['runs']['cgal'][0]['warmExecutionUs'] = 0
        self.assertIsNone(rank_class(saved, 'tetra-uniform-4', self.policy)['recommendation'])


if __name__ == '__main__':
    unittest.main()
