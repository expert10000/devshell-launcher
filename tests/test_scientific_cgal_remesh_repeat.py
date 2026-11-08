"""Byte-stable native remesh replay checks."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_remesh_repeat import run, verify


@unittest.skipUnless(os.environ.get('SCIENTIFIC_CGAL_REMESH_REPORT'),
                     'A sealed local CGAL remesh suite is required')
class LiveRepeatChecks(unittest.TestCase):
    def test_three_fresh_runs_per_mesh_and_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            target, report = run(os.environ['SCIENTIFIC_CGAL_REMESH_REPORT'], directory)
            self.assertEqual(len(report['cases']), 6)
            self.assertEqual(verify(target)['verdict'], 'passed')
            output = Path(report['cases'][0]['directory']) / 'output.obj'
            original = output.read_bytes()
            try:
                output.write_bytes(original + b' ')
                with self.assertRaisesRegex(ValueError, 'byte evidence changed'):
                    verify(target)
            finally:
                output.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
