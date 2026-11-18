"""Portable broker policy checks; the live HTTP gate uses local scientific runtimes."""
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/scientific-broker'))
from typed_journey_broker import CAPABILITY, TypedJourneyBroker, sha  # noqa: E402


class BrokerPolicyTests(unittest.TestCase):
    def broker(self):
        broker = TypedJourneyBroker.__new__(TypedJourneyBroker)
        broker.runtime_id = 'cgal-win-conda'
        broker.case = {'caseId': 'pinned', 'resultPath': 'saved/results.json',
                       'resultSha256': 'a' * 64}
        broker.lock = threading.RLock()
        broker.jobs = {}
        return broker

    def test_only_exact_pinned_request_reaches_source_verification(self):
        broker = self.broker()
        request = {'schemaVersion': 1, 'runtimeId': broker.runtime_id,
                   'capabilityId': CAPABILITY, 'caseId': 'pinned',
                   'input': {'path': broker.case['resultPath'],
                             'sha256': broker.case['resultSha256']}, 'timeoutSeconds': 300}
        with patch.object(broker, 'verify', side_effect=AssertionError('should not verify')):
            for change in ({'extra': True}, {'caseId': 'other'},
                           {'input': {**request['input'], 'sha256': 'b' * 64}},
                           {'timeoutSeconds': True}, {'timeoutSeconds': 601}):
                with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'allowlisted'):
                    broker.submit({**request, **change})

    def test_transport_rehashes_and_promotion_stays_blocked(self):
        broker = self.broker()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'vtk/analysis.vtp'
            path.parent.mkdir()
            path.write_bytes(b'<VTKFile/>')
            record = {'name': 'analysis.vtp', 'path': 'vtk/analysis.vtp',
                      'bytes': path.stat().st_size, 'sha256': sha(path)}
            broker.jobs['job'] = {'state': 'succeeded', 'directory': str(root),
                                  'artifacts': [record]}
            self.assertEqual(broker.artifact('job', 'analysis.vtp'), path.read_bytes())
            with patch.object(broker, 'verify', return_value=None):
                decision = broker.promote('job')
            self.assertEqual(decision['decision'], 'blocked')
            self.assertTrue(any('signed journey bundle' in reason for reason in decision['reasons']))
            path.write_bytes(b'<changed/>')
            with self.assertRaisesRegex(ValueError, 'changed'):
                broker.artifact('job', 'analysis.vtp')
            with patch.object(broker, 'verify', return_value=None):
                decision = broker.promote('job')
            self.assertTrue(any('changed' in reason for reason in decision['reasons']))


if __name__ == '__main__':
    unittest.main()
