"""Five-capability matrix and diagnostic comparison must stay evidence-linked."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools' / 'scientific-broker'))
from five_capability_report import OPERATIONS, compare, verify


class ReportPolicyTests(unittest.TestCase):
    def test_distinct_operation_contract(self):
        self.assertEqual({'cgal': 'cgal.validate', 'vtk': 'mesh.inspect'}, OPERATIONS)
        with self.assertRaisesRegex(ValueError, '3–15'):
            compare('missing.json', 'missing', repetitions=2)


@unittest.skipUnless(os.environ.get('SCIENTIFIC_FIVE_RELEASE_RECORD'), 'A live five-capability release is required')
class LiveReportTests(unittest.TestCase):
    def test_matrix_and_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _ = compare(os.environ['SCIENTIFIC_FIVE_RELEASE_RECORD'], directory, repetitions=3)
            self.assertEqual('scientific.five-capability-report', verify(path)['kind'])
            matrix = json.loads((path.parent / 'matrix.json').read_text())
            self.assertEqual(5, len(matrix['rows']))
            self.assertTrue(all(len(row['supportingRecords']) == 10 for row in matrix['rows']))
            self.assertIn('distinct-operations-no-backend-ranking',
                          (path.parent / 'comparison.json').read_text())
            (path.parent / 'reproducibility.md').write_text('changed', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Report artifact changed'):
                verify(path)


if __name__ == '__main__':
    unittest.main()
