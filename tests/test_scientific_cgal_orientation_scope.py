"""The versioned orientation scope accepts only its pinned, live case evidence."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import scientific_cgal_orientation_scope as scope  # noqa: E402


class OrientationScope(unittest.TestCase):
    def test_pinned_shape_and_adverse_inputs(self):
        cases = scope.manifest()['cases']
        self.assertEqual(len([case for case in cases if case['expected'] == 'accepted']), 8)
        self.assertEqual(len([case for case in cases if case['expected'] == 'rejected']), 4)

    def test_changed_fixture_hash_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'manifest.json'
            value = scope.manifest()
            value['cases'][0]['sha256'] = '0' * 64
            path.write_text(json.dumps(value), encoding='utf-8')
            with patch.object(scope, 'MANIFEST', path):
                with self.assertRaisesRegex(ValueError, 'fixture hash changed'):
                    scope.manifest()


@unittest.skipUnless(os.environ.get('SCIENTIFIC_CGAL_ORIENTATION_WORKER') and
                     os.environ.get('SCIENTIFIC_CGAL_CORPUS_PREFIX'),
                     'Local CGAL orientation worker and prefix are required')
class LiveOrientationScope(unittest.TestCase):
    def test_each_case_and_tampered_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path, report = scope.run(os.environ['SCIENTIFIC_CGAL_ORIENTATION_WORKER'],
                                     os.environ['SCIENTIFIC_CGAL_CORPUS_PREFIX'], directory)
            self.assertEqual(len(report['cases']), 12)
            self.assertEqual(scope.verify(path)['verdict'], 'passed')
            output = Path(report['cases'][0]['directory']) / 'oriented.obj'
            original = output.read_bytes()
            try:
                output.write_bytes(original + b' ')
                with self.assertRaisesRegex(ValueError, 'output hash changed|case publication changed|saved case evidence changed'):
                    scope.verify(path)
            finally:
                output.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
