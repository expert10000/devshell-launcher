"""Fixed native square-hole fill and refusal evidence."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_quad_hole_repair import check_patch, run, verify


@unittest.skipUnless(os.environ.get('SCIENTIFIC_CGAL_HOLE_REPAIR_WORKER') and
                     os.environ.get('SCIENTIFIC_CGAL_CORPUS_PREFIX'),
                     'Local CGAL hole-repair worker and prefix are required')
class LiveQuadRepairChecks(unittest.TestCase):
    def test_fixed_suite_and_output_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            target, report = run(os.environ['SCIENTIFIC_CGAL_HOLE_REPAIR_WORKER'],
                                 os.environ['SCIENTIFIC_CGAL_CORPUS_PREFIX'], directory)
            self.assertEqual(len(report['cases']), 6)
            self.assertEqual(verify(target)['verdict'], 'passed')
            output = Path(report['cases'][0]['directory']) / 'output.obj'
            self.assertEqual(check_patch(output)['rimEdges'], 4)
            original = output.read_bytes()
            try:
                output.write_bytes(original + b' ')
                with self.assertRaisesRegex(ValueError, 'artifact changed'):
                    verify(target)
            finally:
                output.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
