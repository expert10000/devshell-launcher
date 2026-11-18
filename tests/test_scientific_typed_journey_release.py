"""The typed journey must not inherit a historical six-capability release."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/scientific-broker'))
import typed_journey_release as gate  # noqa: E402


class TypedJourneyReleaseGate(unittest.TestCase):
    def test_stale_release_stops_before_expensive_verification(self):
        with tempfile.TemporaryDirectory() as temporary:
            release = Path(temporary) / 'release.json'
            release.write_text(json.dumps({'sourceCommit': 'a' * 40,
                'math3dIdentity': {'commit': 'b' * 40}}), encoding='utf-8')
            Path(str(release) + '.sha256').write_text(
                hashlib.sha256(release.read_bytes()).hexdigest(), encoding='utf-8')
            desktop = {'sourceCommit': 'c' * 40, 'sourceRunId': 'd' * 32}
            broker = {'sourceCommit': 'c' * 40, 'sourceRunId': 'd' * 32}
            with patch.object(gate, 'desktop', return_value=desktop), \
                 patch.object(gate, 'broker', return_value=broker), \
                 patch.object(gate, 'verify_six_release') as verify:
                with self.assertRaisesRegex(ValueError, 'historical'):
                    gate.build(release, 'desktop', 'broker', 'profile')
                verify.assert_not_called()

            release.write_text(release.read_text(encoding='utf-8') + ' ', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'seal changed'):
                gate.build(release, 'desktop', 'broker', 'profile')


if __name__ == '__main__':
    unittest.main()
