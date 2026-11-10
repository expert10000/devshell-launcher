"""Native two-square-hole repair, dual patch coverage and refusal evidence."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_multi_hole_repair import check_two_patches, run, verify


class MultiPatchChecks(unittest.TestCase):
    def test_authored_closed_cube_has_two_complete_caps(self):
        patches = check_two_patches(ROOT / 'scientific/fixtures/cgal-repair-quad/cube-closed.obj')
        self.assertEqual([item['rimEdges'] for item in patches], [4, 4])


@unittest.skipUnless(os.environ.get('SCIENTIFIC_CGAL_HOLE_REPAIR_WORKER') and
                     os.environ.get('SCIENTIFIC_CGAL_CORPUS_PREFIX'),
                     'Local CGAL hole-repair worker and prefix are required')
class LiveMultiRepairChecks(unittest.TestCase):
    def test_seven_cases_and_output_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            target, report = run(os.environ['SCIENTIFIC_CGAL_HOLE_REPAIR_WORKER'],
                                 os.environ['SCIENTIFIC_CGAL_CORPUS_PREFIX'], directory)
            self.assertEqual(len(report['cases']), 7)
            self.assertEqual(verify(target)['verdict'], 'passed')
            output = Path(report['cases'][0]['directory']) / 'output.obj'
            original = output.read_bytes()
            try:
                output.write_bytes(original + b' ')
                with self.assertRaisesRegex(ValueError, 'artifact changed'):
                    verify(target)
            finally:
                output.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
