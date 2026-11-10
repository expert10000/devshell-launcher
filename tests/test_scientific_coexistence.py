"""A combined repair/volume certificate must reject changed live evidence."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/scientific-broker'))
from broker import sha
from coexistence import verify


@unittest.skipUnless(os.environ.get('SCIENTIFIC_COMBINED_RELEASE_RECORD'),
                     'A live combined repair and volume release record is required')
class CombinedReleaseEvidence(unittest.TestCase):
    def test_both_current_releases_and_rehashed_record_tamper(self):
        source = Path(os.environ['SCIENTIFIC_COMBINED_RELEASE_RECORD'])
        record = verify(source)
        self.assertEqual(set(record['profiles']), {'repair', 'volume'})
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'combined.json'
            changed = json.loads(source.read_text(encoding='utf-8'))
            changed['profiles']['volume']['recordId'] = '0' * 64
            path.write_text(json.dumps(changed, separators=(',', ':')), encoding='utf-8')
            Path(str(path) + '.sha256').write_text(sha(path), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'L0-L9 support changed'):
                verify(path)


if __name__ == '__main__':
    unittest.main()
