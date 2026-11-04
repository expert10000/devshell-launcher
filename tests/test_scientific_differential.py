"""Canonical scientific equivalence and meaningful rejection cases."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'tools' / 'scientific-broker' / 'differential.py'
spec = importlib.util.spec_from_file_location('scientific_differential', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def obj(points, faces):
    return ''.join('v ' + ' '.join(map(str, point)) + '\n' for point in points) + \
        ''.join('f ' + ' '.join(str(index + 1) for index in face) + '\n' for face in faces)


class DifferentialTests(unittest.TestCase):
    def test_equivalent_square_with_opposite_diagonals(self):
        points = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
        with tempfile.TemporaryDirectory() as folder:
            left, right = Path(folder) / 'left.obj', Path(folder) / 'right.obj'
            left.write_text(obj(points, [(0, 1, 2), (0, 2, 3)]))
            right.write_text(obj(points, [(0, 1, 3), (1, 2, 3)]))
            result = module.compare_mesh(left, right)
            self.assertEqual(result['verdict'], 'equivalent')
            self.assertNotEqual(left.read_bytes(), right.read_bytes())
            self.assertEqual((result['leftTopology']['eulerCharacteristic'], result['rightTopology']['eulerCharacteristic']), (1, 1))
            right.write_text(obj(points, [(0, 3, 1), (1, 3, 2)]))
            self.assertFalse(module.compare_mesh(left, right)['checks']['orientation'])
            scaled = [(2 * x, 2 * y, z) for x, y, z in points]
            right.write_text(obj(scaled, [(0, 1, 3), (1, 2, 3)]))
            self.assertEqual(module.compare_mesh(left, right)['verdict'], 'different')

    def test_field_ids_units_and_exact_fractions(self):
        field = {'unit': 'm', 'components': 1, 'samples': {'b': 2.0, 'a': 1.0}}
        same = {'unit': 'm', 'components': 1, 'samples': {'a': 1 + 1e-10, 'b': 2}}
        self.assertEqual(module.compare_field(field, same)['verdict'], 'equivalent')
        self.assertEqual(module.compare_field(field, {**same, 'unit': 'cm'})['verdict'], 'incompatible')
        self.assertEqual(module.compare_field(field, {**same, 'samples': {'a': 1.5, 'b': 2}})['verdict'], 'different')
        self.assertEqual(module.compare_exact({'type': 'rational', 'unit': '1', 'value': '2/4'},
                                              {'type': 'rational', 'unit': '1', 'value': '1/2'})['verdict'], 'equivalent')
        self.assertEqual(module.compare_exact({'type': 'polynomial', 'unit': '1', 'terms': {'x^2': '2/4', 'x': '0'}},
                                              {'type': 'polynomial', 'unit': '1', 'terms': {'x^2': '1/2'}})['verdict'], 'equivalent')

    def test_saved_run_artifact_hash_is_required(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            artifact = root / 'mesh.obj'
            artifact.write_text(obj([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)]))
            result = root / 'results.json'
            result.write_text(json.dumps({'runId': 'a' * 32, 'runtimeId': 'cgal-win-conda',
                'state': 'succeeded', 'artifacts': [{'path': 'mesh.obj', 'sha256': module.digest(artifact.read_bytes())}]}))
            self.assertEqual(module.load_saved_mesh(result, 'mesh.obj')['artifactSha256'], module.digest(artifact.read_bytes()))
            artifact.write_bytes(artifact.read_bytes() + b'changed')
            with self.assertRaisesRegex(ValueError, 'artifact hash'):
                module.load_saved_mesh(result, 'mesh.obj')


if __name__ == '__main__':
    unittest.main()
