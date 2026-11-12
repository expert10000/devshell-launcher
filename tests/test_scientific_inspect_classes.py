"""Bounded inspection classes admit holdouts and reject nearby unsafe inputs."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/scientific-broker'))
from inspect_classes import classify, equivalent, policy  # noqa: E402


class InspectClassesTests(unittest.TestCase):
    def test_live_holdouts_and_rejections(self):
        value, digest = policy(ROOT)
        self.assertEqual(len(digest), 64)
        for entry in value['classes']:
            scope = classify(ROOT / entry['holdoutFixture'], ROOT)
            self.assertEqual(scope['classId'], entry['id'])
            self.assertEqual(scope['inputSha256'], entry['holdoutSha256'])
            self.assertTrue(equivalent(ROOT / entry['holdoutFixture'],
                                       ROOT / entry['holdoutFixture']))
        for entry in value['rejectedFixtures']:
            with self.assertRaises(ValueError):
                classify(ROOT / entry['path'], ROOT)

    def test_class_is_bounded_beyond_pinned_hash(self):
        value, _ = policy(ROOT)
        source = ROOT / value['classes'][0]['holdoutFixture']
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'translated.obj'
            lines = []
            for line in source.read_text(encoding='utf-8').splitlines():
                if line.startswith('v '):
                    point = [float(item) for item in line.split()[1:]]
                    line = 'v ' + ' '.join(str(point[index] + (.125 if index == 0 else 0))
                                         for index in range(3))
                lines.append(line)
            path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
            self.assertNotEqual(classify(path, ROOT)['inputSha256'], value['classes'][0]['holdoutSha256'])
            self.assertEqual(classify(path, ROOT)['classId'], value['classes'][0]['id'])

    def test_policy_hash_and_geometry_tamper(self):
        value, _ = policy(ROOT)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'tampered.obj'
            source = ROOT / value['classes'][0]['holdoutFixture']
            path.write_bytes(source.read_bytes() + b'\nf 1 2 3\n')
            with self.assertRaises(ValueError):
                classify(path, ROOT)
            self.assertFalse(equivalent(source, path))


if __name__ == '__main__':
    unittest.main()
