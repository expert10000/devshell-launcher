"""A three-capability record cannot accept missing or changed lower-level support."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/scientific-broker'))
from three_capability_release import TARGETS, require_current_support  # noqa: E402


class ThreeCapabilitySupport(unittest.TestCase):
    def manifest(self):
        expected = {name: (name[0] * 64) for name in TARGETS}
        entries = []
        for name, (runtime, capability) in TARGETS.items():
            support = [{'level': f'L{index}', 'recordId': f'{index:064x}', 'runId': f'{index:032x}'}
                       for index in range(9)]
            support.append({'level': 'L9', 'recordId': expected[name], 'runId': 'f' * 32})
            entries.append({'runtimeId': runtime, 'capabilityId': capability, 'level': 'L9',
                            'recordId': expected[name], 'supportingRecords': support})
        return {'certifiedCapabilities': entries}, expected

    def test_current_three_chain(self):
        manifest, expected = self.manifest()
        self.assertEqual(len(require_current_support(manifest, expected)), 3)

    def test_missing_remesh_refused(self):
        manifest, expected = self.manifest()
        manifest['certifiedCapabilities'].pop(0)
        with self.assertRaisesRegex(ValueError, 'exactly current'):
            require_current_support(manifest, expected)

    def test_stale_repair_support_refused(self):
        manifest, expected = self.manifest()
        manifest['certifiedCapabilities'][1]['supportingRecords'][7]['level'] = 'L6'
        with self.assertRaisesRegex(ValueError, 'stale or incomplete'):
            require_current_support(manifest, expected)

    def test_changed_volume_record_refused(self):
        manifest, expected = self.manifest()
        manifest['certifiedCapabilities'][2]['recordId'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'stale or incomplete'):
            require_current_support(manifest, expected)


if __name__ == '__main__':
    unittest.main()
