"""Fixture-specific remesh acceptance policy and sealed evidence."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_remesh_acceptance import assess, run, verify


class AcceptanceChecks(unittest.TestCase):
    def test_surface_failure_blocks_otherwise_valid_case(self):
        case = {'name': 'example', 'outputSha256': 'x', 'volumeEligible': True,
                'quality': {'minimumAngleDegrees': 30, 'minimumShapeScore': 0.8},
                'surfaceSamples': {'sourceFacetSamplesToTarget': {'maximumDistance': 0.02}}}
        decision = assess(case)
        self.assertFalse(decision['eligible'])
        self.assertFalse(decision['checks']['sampledSurface'])
        self.assertTrue(decision['checks']['volume'])


@unittest.skipUnless(os.environ.get('SCIENTIFIC_CGAL_DIAGNOSTICS_REPORT'),
                     'A sealed local CGAL diagnostic profile is required')
class LiveAcceptanceChecks(unittest.TestCase):
    def test_six_fixture_decisions_and_report_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            target, report = run(os.environ['SCIENTIFIC_CGAL_DIAGNOSTICS_REPORT'], directory)
            self.assertEqual(report['eligibleCount'], 5)
            self.assertFalse(report['cases'][-1]['eligible'])
            self.assertEqual(verify(target)['verdict'], 'fixture-scoped')
            original = target.read_bytes()
            try:
                target.write_bytes(original + b' ')
                with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                    verify(target)
            finally:
                target.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
