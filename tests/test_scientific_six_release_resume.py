"""Checkpoint integrity, restart and consumer-launch recovery without a desktop host."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/scientific-broker'))
import six_release_resume as resume


def state(root):
    return {'schemaVersion': 1, 'kind': 'scientific.six-release-checkpoint',
            'releaseRoot': str(root), 'worktree': str(root.parent),
            'sourceCommit': 'a' * 40, 'math3dRoot': str(root.parent),
            'math3dIdentity': {}, 'prefixes': {}, 'profileId': 'desktop-five',
            'port': 9270, 'build': None, 'desktop': {}, 'broker': {},
            'manifestSha256': None, 'releaseRecord': None, 'attempts': [],
            'activeStage': None, 'retryL9': False, 'status': 'running'}


class ReleaseResume(unittest.TestCase):
    def test_checkpoint_tamper_and_location(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'release/checkpoint.json'
            value = state(path.parent)
            resume.save(path, value)
            self.assertEqual(value, resume.load(path)[1])
            altered = json.loads(path.read_text())
            altered['sourceCommit'] = 'b' * 40
            path.write_text(json.dumps(altered))
            with self.assertRaisesRegex(ValueError, 'tampered'):
                resume.load(path)
            resume.save(path, value)
            moved = path.parent.parent / 'checkpoint.json'
            moved.write_bytes(path.read_bytes())
            with self.assertRaisesRegex(ValueError, 'location changed'):
                resume.load(moved)

    def test_interruption_is_restartable_and_prior_stage_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'release/checkpoint.json'
            value = state(path.parent)
            value['desktop']['inspect'] = {'recordId': 'current'}
            resume.save(path, value)
            with self.assertRaises(KeyboardInterrupt):
                resume.stage(path, value, 'desktop:remesh', lambda: (_ for _ in ()).throw(KeyboardInterrupt()))
            saved = resume.load(path)[1]
            self.assertEqual('interrupted', saved['status'])
            self.assertEqual('current', saved['desktop']['inspect']['recordId'])
            self.assertEqual('interrupted', saved['attempts'][0]['result'])
            resume.stage(path, saved, 'desktop:remesh', lambda: saved['desktop'].update(remesh={'recordId': 'new'}))
            verified = resume.load(path)[1]
            self.assertEqual(['interrupted', 'passed'], [item['result'] for item in verified['attempts']])
            self.assertEqual('new', verified['desktop']['remesh']['recordId'])

    def test_cancelled_stage_does_not_advance(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'release/checkpoint.json'
            value = state(path.parent)
            resume.save(path, value)
            with self.assertRaisesRegex(ValueError, 'cancelled'):
                resume.stage(path, value, 'broker:inspect',
                             lambda: (_ for _ in ()).throw(ValueError('cancelled')))
            saved = resume.load(path)[1]
            self.assertEqual({}, saved['broker'])
            self.assertEqual('interrupted', saved['status'])
            self.assertIn('cancelled', saved['attempts'][0]['error'])

    def test_source_drift_blocks_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'release/checkpoint.json'
            value = state(path.parent)
            resume.save(path, value)
            with patch.object(resume.release, 'commit', side_effect=['b' * 40, 'a' * 40]):
                with self.assertRaisesRegex(ValueError, 'source commit'):
                    resume.validate(path, value)

    def test_stale_saved_desktop_support_blocks_resume(self):
        value = state(Path('release'))
        value['desktop']['inspect'] = {'recordId': 'old', 'runIds': [str(i) for i in range(10)]}
        current = {'certifiedCapabilities': [{'runtimeId': 'cgal-win-conda',
            'capabilityId': 'mesh.inspect', 'level': 'L9', 'recordId': 'new',
            'supportingRecords': [{'level': f'L{i}', 'runId': str(i)} for i in range(10)]}]}
        with self.assertRaisesRegex(ValueError, 'stale'):
            resume.support(value, current)

    def test_failed_l9_launch_retries_only_l9(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / 'release/checkpoint.json'
            value = state(path.parent)
            resume.save(path, value)
            failed = 'Error: l9.cgal-remesh: failed / Cannot process request because the process has exited.'

            def first(args, **kwargs):
                kwargs['stdout'].write(failed)
                return type('Completed', (), {'returncode': 1})()

            with patch.object(resume.subprocess, 'run', side_effect=first):
                with self.assertRaisesRegex(ValueError, 'desktop acceptance failed'):
                    resume.desktop(path, value, 'remesh')
            self.assertTrue(value['retryL9'])
            seen = []

            def second(args, **kwargs):
                seen.extend(args)
                return type('Completed', (), {'returncode': 0})()

            entry = {'runtimeId': 'cgal-win-conda', 'capabilityId': 'mesh.remesh',
                     'level': 'L9', 'recordId': 'current',
                     'supportingRecords': [{'runId': str(i)} for i in range(10)]}
            with patch.object(resume.subprocess, 'run', side_effect=second), \
                 patch.object(resume, 'current_entries', return_value={'certifiedCapabilities': [entry]}), \
                 patch.object(resume, 'sha', return_value='c' * 64):
                resume.desktop(path, value, 'remesh')
            self.assertEqual(['-ResumeFrom', 'L9'], seen[-2:])
            self.assertFalse(value['retryL9'])
            self.assertEqual('current', value['desktop']['remesh']['recordId'])


if __name__ == '__main__':
    unittest.main()
