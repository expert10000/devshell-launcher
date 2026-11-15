"""The shared operation permits ranking only after current matched desktop and broker evidence."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/scientific-broker'))
from comparable_inspect import host_fingerprint, policy, summary, verify
from advisor import advise, advise_shared


class SharedInspectPolicy(unittest.TestCase):
    def test_host_identity_uses_stable_windows_build(self):
        with patch('comparable_inspect.platform.release', return_value='10'):
            first = host_fingerprint()
        with patch('comparable_inspect.platform.release', return_value='11'):
            self.assertEqual(first, host_fingerprint())

    def test_versioned_matched_tiers(self):
        contract, digest = policy(ROOT)
        self.assertEqual('mesh.inspect', contract['operation'])
        self.assertEqual(['tetra-4', 'octa-6', 'cube-8', 'sphere-128', 'sphere-512', 'sphere-2048'],
                         [item['id'] for item in contract['tiers']])
        self.assertEqual([128, 512, 2048], [item['triangles'] for item in contract['tiers'][3:]])
        self.assertEqual(64, len(digest))
        self.assertEqual(5, summary([1, 2, 3, 4, 5])['samples'])
        self.assertEqual([1, 5], summary([1, 2, 3, 4, 5])['median95PctBootstrapMs'])

    def test_ranking_requires_verified_scope_and_exact_tier(self):
        with self.assertRaisesRegex(ValueError, 'requires a current comparable-inspection'):
            advise('unused', 'mesh.inspect', 'single', None, 'unused')
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'scope.json'
            source.write_text('{}')
            release = Path(directory) / 'release.json'
            release.write_text(json.dumps({'repo': str(ROOT)}))
            scope = {'contractSha256': 'a' * 64, 'releaseRecord': str(release),
                     'tiers': {'tetra-4': {'measurements': {
                         name: {'statistics': {'medianMs': cold},
                                'runs': [{'coldInvocationMs': cold, 'warmExecutionMs': warm,
                                          'warmExecutionUs': warm * 1000,
                                          'peakRssBytes': 40 * 1048576}] * 5,
                                'phases': {'peakRssBytes': 40 * 1048576}}
                         for name, cold, warm in (('cgal', 100, 10), ('vtk', 200, 30))}}}}
            with patch('advisor.verify_shared_inspect', return_value=scope):
                with self.assertRaisesRegex(ValueError, 'outside the qualified shared scope'):
                    advise_shared(source, 'large', None, directory)
                path, result = advise_shared(source, 'tetra-4', 'vtk-win-conda', directory)
                self.assertEqual('cgal-win-conda', result['recommendation'])
                self.assertEqual('vtk-win-conda', result['selectedProvider'])
                self.assertEqual('ranked-within-qualified-shared-scope', json.loads(path.read_text())['state'])
                close = json.loads(json.dumps(scope))
                close['tiers']['tetra-4']['measurements']['vtk']['runs'] = [
                    {'coldInvocationMs': 101, 'warmExecutionMs': 11, 'warmExecutionUs': 11000,
                     'peakRssBytes': 40 * 1048576}] * 5
                with patch('advisor.verify_shared_inspect', return_value=close):
                    _, abstained = advise_shared(source, 'tetra-4', None, directory)
                self.assertIsNone(abstained['recommendation'])
                self.assertEqual('abstained', abstained['state'])


@unittest.skipUnless(os.environ.get('SCIENTIFIC_SHARED_INSPECT_RECORD'), 'Live comparable scope required')
class LiveSharedInspect(unittest.TestCase):
    def test_current_scope_and_tamper(self):
        path = Path(os.environ['SCIENTIFIC_SHARED_INSPECT_RECORD'])
        record = verify(path)
        self.assertEqual('qualified-shared-scope', record['state'])
        self.assertEqual(6, len(record['tiers']))
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / 'record.json'
            copied.write_bytes(path.read_bytes() + b' ')
            Path(str(copied) + '.sha256').write_text(Path(str(path) + '.sha256').read_text())
            with self.assertRaisesRegex(ValueError, 'seal changed'):
                verify(copied)


if __name__ == '__main__':
    unittest.main()
