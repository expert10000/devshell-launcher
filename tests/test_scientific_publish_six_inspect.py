"""Publication refuses unpaired evidence and consumer checkout drift before running jobs."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/scientific-broker'))
from publish_six_inspect import publish
from six_capability_report import compare


class PublicationGates(unittest.TestCase):
    def test_report_requires_class_and_desktop_journey(self):
        with self.assertRaisesRegex(ValueError, 'desktop journey'):
            compare('missing.json', 'unused', shared_inspect_record='shared.json',
                    advisor_record='advice.json', product_record='product.json')

    def test_pulled_math3d_checkout_must_match_release(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            release = root / 'release.json'
            release.write_text('{}')
            other = root / 'other'
            other.mkdir()
            with patch('publish_six_inspect.verify_release', return_value={
                    'repo': str(root), 'math3dRoot': str(root),
                    'math3dIdentity': {'commit': 'a' * 40}}):
                with self.assertRaisesRegex(ValueError, 'differs from the release'):
                    publish(release, other, 'key.pem', 'devshell-six', root)


if __name__ == '__main__':
    unittest.main()
