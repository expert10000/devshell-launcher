"""Fixed orientation contract and optional native tamper replay."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_orientation import CASES, check_case, run, verify


class OrientationContractChecks(unittest.TestCase):
    def test_inward_inspection_retains_negative_signed_volume(self):
        result = {'schemaVersion': 1, 'operation': 'inspect', 'state': 'succeeded',
                  'beforeOrientation': 'inward', 'afterOrientation': 'inward',
                  'orientationChanged': False, 'signedVolumeBefore': -1/6,
                  'signedVolumeAfter': -1/6, 'versions': {'cgal': '6.0.1'}, 'error': ''}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'output.obj'
            check_case(CASES[1], result, 0, output)
            result['signedVolumeAfter'] = 1/6
            with self.assertRaisesRegex(ValueError, 'signed volume changed'):
                check_case(CASES[1], result, 0, output)


@unittest.skipUnless(os.environ.get('SCIENTIFIC_CGAL_ORIENTATION_WORKER') and
                     os.environ.get('SCIENTIFIC_CGAL_CORPUS_PREFIX'),
                     'Local CGAL orientation worker and prefix are required')
class LiveOrientationChecks(unittest.TestCase):
    def test_native_repair_and_output_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            report_path, report = run(os.environ['SCIENTIFIC_CGAL_ORIENTATION_WORKER'],
                                      os.environ['SCIENTIFIC_CGAL_CORPUS_PREFIX'], directory)
            self.assertEqual(len(report['cases']), 8)
            self.assertEqual(verify(report_path)['verdict'], 'passed')
            output = Path(report['cases'][3]['directory']) / 'output.obj'
            original = output.read_bytes()
            try:
                output.write_bytes(original + b' ')
                with self.assertRaisesRegex(ValueError, 'case evidence changed'):
                    verify(report_path)
            finally:
                output.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
