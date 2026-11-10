"""Native reload coverage for the six-setting fidelity profile."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_remesh_profile_reload import run, verify


@unittest.skipUnless(os.environ.get('SCIENTIFIC_CGAL_FIDELITY_REPORT'),
                     'A sealed local CGAL fidelity profile is required')
class ProfileReloadChecks(unittest.TestCase):
    def test_all_six_native_outputs_reopen_and_detect_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            target, report = run(os.environ['SCIENTIFIC_CGAL_FIDELITY_REPORT'], directory)
            self.assertEqual(len(report['cases']), 6)
            self.assertEqual(verify(target)['verdict'], 'passed')
            output = Path(report['cases'][-1]['directory']) / 'output.obj'
            original = output.read_bytes()
            try:
                output.write_bytes(original + b' ')
                with self.assertRaisesRegex(ValueError, 'artifact changed'):
                    verify(target)
            finally:
                output.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
