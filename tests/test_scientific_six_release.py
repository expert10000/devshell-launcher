"""Six-capability support and portable release regression gates."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/scientific-broker'))
from six_capability_release import TARGETS, require_current_support, verify as verify_release
from portable_six_evidence import verify as verify_bundle


class SixSupport(unittest.TestCase):
    def test_missing_or_stale_support_is_rejected(self):
        fresh = {'certifiedCapabilities': []}
        ids = {}
        for name, (runtime, capability) in TARGETS.items():
            records = [{'level': f'L{level}', 'runId': f'{name}-{level}',
                        'recordId': f'{name}-record-{level}'} for level in range(10)]
            ids[name] = records[-1]['recordId']
            fresh['certifiedCapabilities'].append({'runtimeId': runtime,
                'capabilityId': capability, 'level': 'L9', 'recordId': ids[name],
                'supportingRecords': records})
        require_current_support(fresh, ids)
        stale = json.loads(json.dumps(fresh))
        stale['certifiedCapabilities'][0]['supportingRecords'][-1]['recordId'] = 'drifted'
        with self.assertRaisesRegex(ValueError, 'stale or incomplete'):
            require_current_support(stale, ids)
        missing = json.loads(json.dumps(fresh))
        missing['certifiedCapabilities'].pop()
        with self.assertRaisesRegex(ValueError, 'exactly current'):
            require_current_support(missing, ids)


@unittest.skipUnless(os.environ.get('SCIENTIFIC_SIX_RELEASE_RECORD') and
                     os.environ.get('SCIENTIFIC_SIX_BUNDLE'), 'Live release evidence required')
class LiveSixRelease(unittest.TestCase):
    def test_current_release_and_offline_tamper(self):
        release = verify_release(os.environ['SCIENTIFIC_SIX_RELEASE_RECORD'])
        self.assertEqual(set(TARGETS), set(release['profiles']))
        trust = ROOT / 'schemas/scientific-evidence-trust.v1.json'
        bundle = Path(os.environ['SCIENTIFIC_SIX_BUNDLE'])
        self.assertEqual(6, verify_bundle(bundle, trust)['capabilities'])
        with tempfile.TemporaryDirectory() as folder:
            changed = Path(folder) / 'tampered.zip'
            with zipfile.ZipFile(bundle) as source, zipfile.ZipFile(changed, 'w') as target:
                for item in source.infolist():
                    data = source.read(item.filename)
                    if item.filename == 'manifest.json':
                        data += b' '
                    target.writestr(item, data)
            with self.assertRaisesRegex(ValueError, 'seal changed'):
                verify_bundle(changed, trust)


if __name__ == '__main__':
    unittest.main()
