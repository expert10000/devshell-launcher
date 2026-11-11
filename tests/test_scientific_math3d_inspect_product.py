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
                'cgal': {'statistics': {'medianMs': 20, 'median95PctBootstrapMs': [18, 24]}},
                'vtk': {'statistics': {'medianMs': 30, 'median95PctBootstrapMs': [28, 33]}}}}}}

    def test_current_exact_tier_and_manual_choice(self):
        with patch('math3d_inspect_product.verify_shared', return_value=self.scope), \
             patch('math3d_inspect_product.verify_release', return_value={'repo': str(ROOT)}):
            recommended = choose(self.shared, self.input)
            self.assertEqual('cgal-win-conda', recommended['selectedProvider'])
            self.assertEqual('sphere-128', recommended['tier'])
            self.assertIn('startup', recommended['reason'])
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


if __name__ == '__main__':
    unittest.main()
