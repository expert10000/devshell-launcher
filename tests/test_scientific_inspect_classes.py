"""Bounded inspection classes admit holdouts and reject nearby unsafe inputs."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/scientific-broker'))
from inspect_classes import classify, equivalent, mesh, policy  # noqa: E402
from generate_inspect_holdouts import render, sphere  # noqa: E402


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

    def test_independent_closed_topology_and_size_tiers(self):
        value, _ = policy(ROOT)
        self.assertEqual(2, value['schemaVersion'])
        tiers = [item for item in value['classes'] if item['mode'] == 'star-closed']
        self.assertEqual([(64, 128), (256, 512), (1024, 2048)],
                         [(item['minimumTriangles'], item['maximumTriangles']) for item in tiers])
        for item in tiers:
            base, holdout = ROOT / item['baseFixture'], ROOT / item['holdoutFixture']
            self.assertNotEqual(mesh(base)[1], mesh(holdout)[1])
            self.assertEqual(item['id'], classify(holdout, ROOT)['classId'])
        for level, triangles in ((1, 80), (2, 320), (3, 1280)):
            committed = ROOT / f'scientific/fixtures/inspect-classes/ico-{triangles}-holdout.obj'
            self.assertEqual(committed.read_text(), render(*sphere(level)))

    def test_large_class_accepts_new_geometry_but_rejects_broken_topology(self):
        value, _ = policy(ROOT)
        item = next(entry for entry in value['classes'] if entry['id'] == 'star-closed-1024-2048')
        source = ROOT / item['holdoutFixture']
        with tempfile.TemporaryDirectory() as folder:
            translated = Path(folder) / 'independent.obj'
            lines = source.read_text().splitlines()
            for index, line in enumerate(lines):
                if line.startswith('v '):
                    point = [float(number) for number in line.split()[1:]]
                    lines[index] = 'v ' + ' '.join(str(axis + (.05 if number == 0 else 0))
                                                     for number, axis in enumerate(point))
            translated.write_text('\n'.join(lines) + '\n')
            self.assertNotEqual(item['holdoutSha256'], classify(translated, ROOT)['inputSha256'])
            self.assertEqual(item['id'], classify(translated, ROOT)['classId'])
            broken = Path(folder) / 'broken.obj'
            broken.write_text('\n'.join(lines[:-1]) + '\n')
            with self.assertRaises(ValueError):
                classify(broken, ROOT)


if __name__ == '__main__':
    unittest.main()
