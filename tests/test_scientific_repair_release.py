"""Repair release must retain a verified four-case broker/MATH3D smoke."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/scientific-broker'))
spec = importlib.util.spec_from_file_location('release_certification',
    ROOT / 'tools/scientific-broker/release_certification.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class RepairReleaseGate(unittest.TestCase):
    def test_qualified_repair_report_without_smoke_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'qualification-report.json'
            path.write_text(json.dumps({'schemaVersion': 1,
                'kind': 'scientific.release-qualification-report', 'verdict': 'qualified',
                'capabilityId': 'mesh.repair'}), encoding='utf-8')
            Path(str(path) + '.sha256').write_text(release.sha(path), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'missing its product smoke'):
                release.verify_release(path)

    def test_repair_certification_requires_smoke_record(self):
        with self.assertRaisesRegex(ValueError, 'four-case broker/MATH3D smoke'):
            release.repair_smoke_link('unused-config.json', None)


if __name__ == '__main__':
    unittest.main()
