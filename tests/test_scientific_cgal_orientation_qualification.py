"""Orientation levels depend on the exact v2 case chain and current consumer tools."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import scientific_cgal_orientation_qualification as qualification  # noqa: E402
import scientific_cgal_orientation_l9 as product  # noqa: E402


class OrientationQualification(unittest.TestCase):
    def test_replay_refuses_changed_publication(self):
        original = [{'caseId': name, 'state': 'succeeded', 'outputSha256': 'a' * 64}
                    for name in qualification.CASES]
        replay = [dict(item) for item in original]
        qualification.compare_cases(original, replay)
        replay[0]['outputSha256'] = 'b' * 64
        with self.assertRaisesRegex(ValueError, 'replay differs'):
            qualification.compare_cases(original, replay)


@unittest.skipUnless(os.environ.get('SCIENTIFIC_CGAL_ORIENTATION_L9_RECORD'),
                     'Live orientation L9 report is required')
class LiveOrientationQualification(unittest.TestCase):
    def test_sealed_l9_and_source_drift(self):
        record = Path(os.environ['SCIENTIFIC_CGAL_ORIENTATION_L9_RECORD'])
        self.assertEqual(product.verify(record)['verdict'], 'passed')
        with tempfile.TemporaryDirectory() as directory:
            changed = Path(directory) / 'changed.py'
            changed.write_text('changed', encoding='utf-8')
            with patch.object(product, 'SOURCE', changed):
                with self.assertRaisesRegex(ValueError, 'tool or lower evidence changed'):
                    product.verify(record)


if __name__ == '__main__':
    unittest.main()
