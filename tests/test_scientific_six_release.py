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
from portable_six_evidence import verify as verify_bundle, verify_desktop


class SixSupport(unittest.TestCase):
    def test_desktop_selection_and_cancellation_are_bound_to_results(self):
        import hashlib
        def sha(path):
            return hashlib.sha256(Path(path).read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            release = root / 'release.json'
            classes = root / 'classes.json'
            release.write_text(json.dumps({'sourceCommit': 'a' * 40}), encoding='utf-8')
            classes.write_text('{}', encoding='utf-8')
            selection_path = root / ('a' * 32) / 'product-selection' / 'selection.json'
            selection_path.parent.mkdir(parents=True)
            selection = {'classRecordSha256': sha(classes), 'inputSha256': 'b' * 64,
                         'classId': 'tetra-uniform-4', 'state': 'qualified',
                         'productFiles': {'read.m3dm': 'c' * 64, 'viewer.png': 'd' * 64}}
            selection_path.write_text(json.dumps(selection), encoding='utf-8')
            success = selection_path.parent.parent / 'results.json'
            success.write_text(json.dumps({'runId': 'a' * 32, 'recipeId': 'l9.math3d-inspect-selection',
                                           'state': 'succeeded', 'selection': selection}), encoding='utf-8')
            cancel = root / ('e' * 32) / 'results.json'
            cancel.parent.mkdir()
            cancel.write_text(json.dumps({'runId': 'e' * 32, 'recipeId': 'l9.math3d-inspect-selection',
                                          'state': 'cancelled', 'artifacts': [],
                                          'validatedCapabilities': []}), encoding='utf-8')
            record = root / 'desktop.json'
            record.write_text(json.dumps({'schemaVersion': 1,
                'kind': 'scientific.live-desktop-inspect-selection', 'sourceCommit': 'a' * 40,
                'releaseRecordSha256': sha(release), 'classRecordSha256': sha(classes),
                'inputSha256': 'b' * 64, 'automaticText': 'qualified / selected cgal-win-conda',
                'manualText': 'manual / selected vtk-win-conda',
                'success': {'runId': 'a' * 32, 'resultPath': str(success),
                            'resultSha256': sha(success), 'selectionPath': str(selection_path),
                            'selectionSha256': sha(selection_path)},
                'cancellation': {'runId': 'e' * 32, 'resultPath': str(cancel),
                                 'resultSha256': sha(cancel)}}), encoding='utf-8')
            Path(str(record) + '.sha256').write_text(sha(record), encoding='utf-8')
            self.assertEqual('cancelled', json.loads(cancel.read_text())['state'])
            verify_desktop(record, release, classes)
            cancel.write_text(cancel.read_text().replace('cancelled', 'succeeded'), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'managed result changed'):
                verify_desktop(record, release, classes)

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
