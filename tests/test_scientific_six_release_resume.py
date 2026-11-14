"""Checkpoint integrity, restart and consumer-launch recovery without a desktop host."""
import json
from pathlib import Path
import subprocess
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
            self.assertIsNone(saved['activeStage'])
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

    def test_failed_stage_discards_partially_written_promotion(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'release/checkpoint.json'
            value = state(path.parent)
            resume.save(path, value)

            def incomplete():
                value['broker']['inspect'] = {'smoke': 'unverified'}
                raise ValueError('cancelled after artifact write')

            with self.assertRaisesRegex(ValueError, 'cancelled'):
                resume.stage(path, value, 'broker:inspect', incomplete)
            self.assertEqual({}, resume.load(path)[1]['broker'])

    def test_source_drift_blocks_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'release/checkpoint.json'
            value = state(path.parent)
            resume.save(path, value)
            with patch.object(resume.release, 'commit', side_effect=['b' * 40, 'a' * 40]):
                with self.assertRaisesRegex(ValueError, 'source commit'):
                    resume.validate(path, value)

    def test_restart_marks_unfinished_stage_interrupted_before_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'release/checkpoint.json'
            value = state(path.parent)
            value['activeStage'] = 'build'
            value['attempts'] = [{'stage': 'build', 'result': 'running'}]
            resume.save(path, value)
            with patch.object(resume.release, 'ROOT', Path(folder)), \
                 patch.object(resume, 'validate'), \
                 patch.object(resume, 'stage', side_effect=RuntimeError('stop before retry')):
                with self.assertRaisesRegex(RuntimeError, 'stop before retry'):
                    resume.execute(path)
            saved = resume.load(path)[1]
            self.assertEqual('interrupted', saved['status'])
            self.assertEqual('interrupted', saved['attempts'][-1]['result'])

    def test_failed_stage_checkpoint_can_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'release/checkpoint.json'
            value = state(path.parent)
            resume.save(path, value)
            with self.assertRaisesRegex(ValueError, 'desktop failure'):
                resume.stage(path, value, 'build', lambda: (_ for _ in ()).throw(ValueError('desktop failure')))
            saved = resume.load(path)[1]
            self.assertIsNone(saved['activeStage'])
            with patch.object(resume.release, 'ROOT', Path(folder)), \
                 patch.object(resume, 'validate'), \
                 patch.object(resume, 'stage', side_effect=RuntimeError('retry started')):
                with self.assertRaisesRegex(RuntimeError, 'retry started'):
                    resume.execute(path)

    def test_legacy_failed_stage_checkpoint_can_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'release/checkpoint.json'
            value = state(path.parent)
            value['activeStage'] = 'build'
            value['status'] = 'interrupted'
            value['attempts'] = [{'stage': 'build', 'result': 'interrupted'}]
            resume.save(path, value)
            with patch.object(resume.release, 'ROOT', Path(folder)), \
                 patch.object(resume, 'validate'), \
                 patch.object(resume, 'stage', side_effect=RuntimeError('retry started')):
                with self.assertRaisesRegex(RuntimeError, 'retry started'):
                    resume.execute(path)
            self.assertIsNone(resume.load(path)[1]['activeStage'])

    def test_stale_saved_desktop_support_blocks_resume(self):
        value = state(Path('release'))
        value['desktop']['inspect'] = {'recordId': 'old', 'runIds': [str(i) for i in range(10)]}
        current = {'certifiedCapabilities': [{'runtimeId': 'cgal-win-conda',
            'capabilityId': 'mesh.inspect', 'level': 'L9', 'recordId': 'new',
            'supportingRecords': [{'level': f'L{i}', 'runId': str(i)} for i in range(10)]}]}
        with self.assertRaisesRegex(ValueError, 'stale'):
            resume.support(value, current)

    def test_failed_l9_launch_restarts_scenario_from_l0(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / 'release/checkpoint.json'
            value = state(path.parent)
            resume.save(path, value)
            first = type('Process', (), {'wait': lambda self, timeout: 1})()
            with patch.object(resume.subprocess, 'Popen', return_value=first):
                with self.assertRaisesRegex(ValueError, 'desktop acceptance failed'):
                    resume.desktop(path, value, 'remesh')
            self.assertNotIn('remesh', value['desktop'])
            seen = []

            def second(args, **kwargs):
                seen.extend(args)
                return type('Process', (), {'wait': lambda self, timeout: 0})()

            entry = {'runtimeId': 'cgal-win-conda', 'capabilityId': 'mesh.remesh',
                     'level': 'L9', 'recordId': 'current',
                     'supportingRecords': [{'runId': str(i)} for i in range(10)]}
            with patch.object(resume.subprocess, 'Popen', side_effect=second), \
                 patch.object(resume, 'current_entries', return_value={'certifiedCapabilities': [entry]}), \
                 patch.object(resume, 'sha', return_value='c' * 64):
                resume.desktop(path, value, 'remesh')
            self.assertNotIn('-ResumeFrom', seen)
            self.assertFalse(value['retryL9'])
            self.assertEqual('current', value['desktop']['remesh']['recordId'])

    def test_desktop_timeout_kills_owned_process_tree(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'release/checkpoint.json'
            value = state(path.parent)
            resume.save(path, value)
            class TimedOut:
                pid = 12345
                calls = 0
                def wait(self, timeout):
                    self.calls += 1
                    if self.calls == 1:
                        raise subprocess.TimeoutExpired('powershell', timeout)
                    return 1
                def poll(self):
                    return None
            with patch.object(resume.subprocess, 'Popen', return_value=TimedOut()), \
                 patch.object(resume.subprocess, 'run') as kill:
                with self.assertRaises(subprocess.TimeoutExpired):
                    resume.desktop(path, value, 'inspect')
            self.assertEqual(['taskkill', '/PID', '12345', '/T', '/F'], kill.call_args.args[0])

    def test_missing_inventory_fails_before_worktree_creation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            math3d = root / 'math3d/renderer/src/mesh'
            math3d.mkdir(parents=True)
            (math3d / 'surfaceMesh.ts').write_text('source')
            prefixes = []
            for name in ('cgal', 'vtk', 'scientific'):
                prefix = root / name
                prefix.mkdir()
                (prefix / 'python.exe').write_bytes(b'')
                prefixes.append(prefix)
            with patch.object(resume.release, 'math3d_identity', return_value={}), \
                 patch.object(resume.release, 'command') as command:
                with self.assertRaises(FileNotFoundError):
                    resume.start(root / 'math3d', *prefixes,
                                 runtime_report=root / 'missing.json')
            command.assert_not_called()

    def test_inventory_prefix_mismatch_and_missing_ui_dependency(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            report = root / 'runtime.json'
            prefix = root / 'prefix'
            report.write_text(json.dumps({'runtimes': [
                {'id': name, 'environmentRoot': str(prefix)} for name in
                ('cgal-win-conda', 'vtk-win-conda', 'gmsh-win-conda')]}))
            mapping = {name: str(prefix) for name in resume.SCENARIOS}
            with self.assertRaisesRegex(ValueError, 'mismatches'):
                resume.runtime_inventory(report, {**mapping, 'volume': str(root / 'other')})
            worktree = root / 'worktree'
            worktree.mkdir()
            state_value = state(root / 'release')
            state_value['worktree'] = str(worktree)
            state_value['runtimeReport'] = str(report)
            state_value['runtimeReportSha256'] = resume.sha(report)
            with patch.object(resume.release, 'command') as command:
                with self.assertRaisesRegex(ValueError, 'Playwright dependency'):
                    resume.build(state_value)
            self.assertEqual(resume.sha(report), resume.sha(worktree / '.scientific/runtime-report.json'))
            self.assertEqual(1, command.call_count)
            dependency = worktree / 'DevShell/ui/dev-ui-react/node_modules/playwright-core/package.json'
            dependency.parent.mkdir(parents=True)
            dependency.write_text('{}')
            with patch.object(resume.release, 'command') as command, \
                 patch.object(resume, 'sha', side_effect=lambda path:
                              state_value['runtimeReportSha256'] if Path(path) == report else 'c' * 64):
                resume.build(state_value)
            self.assertEqual(3, command.call_count)
            self.assertEqual(2, len(state_value['build']))

    def test_execution_hands_off_to_sealed_worktree(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            worktree = root / 'checkout'
            worktree.mkdir()
            checkpoint = root / 'release/checkpoint.json'
            value = state(checkpoint.parent)
            value['worktree'] = str(worktree)
            record = checkpoint.parent / 'coexistence.json'
            record.parent.mkdir()
            record.write_text(json.dumps({'sourceCommit': 'a' * 40}))
            value['releaseRecord'] = str(record)
            value['status'] = 'complete'
            resume.save(checkpoint, value)
            with patch.object(resume.release, 'ROOT', root), \
                 patch.object(resume.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as child:
                path, result = resume.execute(checkpoint)
            self.assertEqual(record, path)
            self.assertEqual('a' * 40, result['sourceCommit'])
            self.assertEqual(worktree, Path(child.call_args.kwargs['cwd']))


if __name__ == '__main__':
    unittest.main()
