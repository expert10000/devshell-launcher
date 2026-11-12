"""Managed product journey refuses missing roles, changed consumers and cancellation artifacts."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/scientific-broker'))
import desktop_inspect_journey as journey


class DesktopJourney(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.release = {'sourceCommit': 'a' * 40,
                        'math3dIdentity': {'commit': 'b' * 40, 'identitySha256': 'c' * 64}}
        self.class_path = self.root / 'classes.json'
        self.class_path.write_text('{}')
        self.input = self.root / 'accepted.obj'
        self.input.write_text('v 0 0 0\n')

    def run_folder(self, role):
        directory = self.root / ({'automatic': '1', 'manual': '2',
                                  'fallback': '3', 'cancelled': '4'}[role] * 32)
        directory.mkdir()
        selection = {'state': 'manual' if role == 'manual' else 'ranked',
                     'selectedProvider': 'vtk-win-conda' if role == 'manual' else 'cgal-win-conda',
                     'inputPath': str(self.input), 'math3dIdentity': self.release['math3dIdentity'],
                     'productFiles': {name: journey.sha(self._product(directory, name))
                                      for name in journey.PRODUCT_FILES}} if role != 'cancelled' else None
        if selection:
            product = directory / 'product-selection'
            product.mkdir(exist_ok=True)
            (product / 'selection.json').write_text(json.dumps(selection))
        result = {'runId': directory.name, 'recipeId': journey.RECIPE,
                  'state': 'cancelled' if role == 'cancelled' else 'succeeded',
                  'selection': selection, 'artifacts': []}
        if selection:
            path = directory / 'product-selection/selection.json'
            result['artifacts'].append({'path': 'product-selection/selection.json', 'sha256': journey.sha(path)})
        (directory / 'results.json').write_text(json.dumps(result))
        (directory / 'request.json').write_text(json.dumps({'runId': directory.name,
            'recipeId': journey.RECIPE, 'parameters': {'classRecord': str(self.class_path),
            'manualProvider': 'vtk-win-conda' if role == 'manual' else None},
            'inputArtifacts': [{'sha256': journey.sha(self.input)}]}))
        (directory / 'source-snapshot.json').write_text(json.dumps({'repositories': {
            'devshell': {'commit': self.release['sourceCommit']},
            'math3d': {'commit': self.release['math3dIdentity']['commit']}}}))
        return directory

    def _product(self, directory, name):
        path = directory / 'product-selection/product' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(name.encode())
        return path

    def test_selection_and_manual_override_are_managed(self):
        for role in ('automatic', 'manual'):
            directory = self.run_folder(role)
            with patch.object(journey, 'verify_product'):
                evidence = journey.check_run(role, directory, self.release, self.class_path)
            self.assertEqual('succeeded', evidence['state'])
            self.assertIn('product-selection/product/read.m3dm', evidence['files'])

    def test_cancelled_run_must_have_no_promoted_artifact(self):
        directory = self.run_folder('cancelled')
        self.assertEqual('cancelled', journey.check_run('cancelled', directory, self.release,
                                                       self.class_path)['state'])
        result_path = directory / 'results.json'
        result = json.loads(result_path.read_text())
        result['artifacts'] = [{'path': 'product-selection/selection.json'}]
        result_path.write_text(json.dumps(result))
        with self.assertRaisesRegex(ValueError, 'product artifacts'):
            journey.check_run('cancelled', directory, self.release, self.class_path)

    def test_changed_math3d_identity_is_rejected(self):
        directory = self.run_folder('automatic')
        result_path = directory / 'results.json'
        result = json.loads(result_path.read_text())
        result['selection']['math3dIdentity']['commit'] = 'd' * 40
        product_path = directory / 'product-selection/selection.json'
        product_path.write_text(json.dumps(result['selection']))
        result['artifacts'][0]['sha256'] = journey.sha(product_path)
        result_path.write_text(json.dumps(result))
        with self.assertRaisesRegex(ValueError, 'consumer identity changed'):
            journey.check_run('automatic', directory, self.release, self.class_path)


if __name__ == '__main__':
    unittest.main()
