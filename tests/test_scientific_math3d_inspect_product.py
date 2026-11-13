"""Product selection refuses stale scope and keeps an explicit provider choice."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/scientific-broker'))
from comparable_inspect import policy
from math3d_inspect_product import choose


class ProductSelection(unittest.TestCase):
    def setUp(self):
        self.input = ROOT / 'scientific/fixtures/inspect-shared/sphere-128.obj'
        self.shared = ROOT / 'schemas/scientific-mesh-inspect.v2.json'
        self.contract = policy(ROOT)[0]
        self.scope = {'releaseRecord': 'unused', 'configPaths': {'cgal': 'cgal.json', 'vtk': 'vtk.json'},
            'tiers': {'sphere-128': {'measurements': {
                name: {'statistics': {'medianMs': cold, 'median95PctBootstrapMs': [cold, cold]},
                       'runs': [{'coldInvocationMs': cold, 'warmExecutionMs': warm,
                                 'warmExecutionUs': warm * 1000,
                                 'peakRssBytes': 40 * 1048576}] * 5,
                       'phases': {'peakRssBytes': 40 * 1048576}}
                for name, cold, warm in (('cgal', 100, 10), ('vtk', 200, 30))}}}}

    def test_current_exact_tier_and_manual_choice(self):
        with patch('math3d_inspect_product.verify_shared', return_value=self.scope), \
             patch('math3d_inspect_product.verify_release', return_value={'repo': str(ROOT)}):
            recommended = choose(self.shared, self.input)
            self.assertEqual('cgal-win-conda', recommended['selectedProvider'])
            self.assertEqual('sphere-128', recommended['tier'])
            self.assertIn('Paired cold and warm', recommended['reason'])
            manual = choose(self.shared, self.input, 'vtk-win-conda')
            self.assertEqual('vtk-win-conda', manual['selectedProvider'])
            self.assertEqual('cgal-win-conda', manual['recommendedProvider'])
            self.assertEqual('manual', manual['state'])

    def test_stale_and_out_of_scope_fallback(self):
        with patch('math3d_inspect_product.verify_shared', side_effect=ValueError('drift')):
            stale = choose(self.shared, self.input)
            self.assertEqual('math3d-direct', stale['selectedProvider'])
            self.assertIn('stale', stale['reason'])
        with patch('math3d_inspect_product.verify_shared', return_value=self.scope), \
             patch('math3d_inspect_product.verify_release', return_value={'repo': str(ROOT)}):
            outside = choose(self.shared, ROOT / 'scientific/fixtures/cgal/open-square.obj')
            self.assertEqual('fallback', outside['state'])
            self.assertIn('outside', outside['reason'])

    def test_uncertain_scope_falls_back_unless_manually_selected(self):
        for item in self.scope['tiers']['sphere-128']['measurements']['vtk']['runs']:
            item['coldInvocationMs'] = 101
            item['warmExecutionMs'] = 11
            item['warmExecutionUs'] = 11000
        with patch('math3d_inspect_product.verify_shared', return_value=self.scope), \
             patch('math3d_inspect_product.verify_release', return_value={'repo': str(ROOT)}):
            self.assertEqual('fallback', choose(self.shared, self.input)['state'])
            self.assertEqual('manual', choose(self.shared, self.input, 'vtk-win-conda')['state'])

    def test_bounded_class_requires_current_evidence(self):
        decision = {'state': 'ranked', 'selectedProvider': 'cgal-win-conda',
                    'recommendation': 'cgal-win-conda', 'reason': None, 'classId': 'tetra-uniform-4',
                    'rankingPolicySha256': 'a' * 64, 'evidence': {'phases': {}},
                    'configPaths': {'cgal': 'cgal.json', 'vtk': 'vtk.json'}}
        with patch('math3d_inspect_product.decide_class', return_value=decision):
            selected = choose(None, self.input, class_record=self.shared)
            self.assertEqual('cgal-win-conda', selected['selectedProvider'])
        with patch('math3d_inspect_product.decide_class', side_effect=ValueError('tampered')):
            self.assertEqual('fallback', choose(None, self.input, class_record=self.shared)['state'])


if __name__ == '__main__':
    unittest.main()
