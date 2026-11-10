"""Sealed numerical diagnostics over a local CGAL fidelity profile."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_remesh_diagnostics import run, verify


@unittest.skipUnless(os.environ.get('SCIENTIFIC_CGAL_FIDELITY_REPORT'),
                     'A sealed local CGAL fidelity profile is required')
class DiagnosticChecks(unittest.TestCase):
    def test_measurements_are_sealed_and_source_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            target, report = run(os.environ['SCIENTIFIC_CGAL_FIDELITY_REPORT'], directory)
            self.assertEqual(len(report['cases']), 6)
            self.assertEqual(verify(target)['verdict'], 'measured')
            self.assertFalse(report['cases'][-1]['volumeEligible'])
            self.assertGreater(report['cases'][-1]['surfaceSamples']
                               ['targetVerticesToSource']['maximumDistance'], 0)
            output = Path(os.environ['SCIENTIFIC_CGAL_FIDELITY_REPORT']).parent / \
                report['cases'][-1]['name'] / 'output.obj'
            original = output.read_bytes()
            try:
                output.write_bytes(original + b' ')
                with self.assertRaisesRegex(ValueError, 'artifact changed'):
                    verify(target)
            finally:
                output.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
