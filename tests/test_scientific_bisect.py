"""Bisect classification never calls build or infrastructure failures scientific regressions."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1] / 'tools' / 'scientific-broker'
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('scientific_bisect', ROOT / 'bisect_commits.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class BisectTests(unittest.TestCase):
    def test_exact_boundary_and_skipped_ambiguity(self):
        commits = ['a', 'b', 'c', 'd', 'e']
        first = {'a': 'good', 'b': 'good', 'c': 'bad', 'd': 'bad', 'e': 'bad'}
        result = module.search(commits, first.__getitem__)
        self.assertEqual((result['verdict'], result['firstBad']), ('first-bad', 'c'))
        ambiguous = {'a': 'good', 'b': 'skip', 'c': 'bad', 'd': 'bad', 'e': 'bad'}
        result = module.search(commits, ambiguous.__getitem__)
        self.assertEqual(result['verdict'], 'inconclusive')
        self.assertIsNone(result['firstBad'])
        invalid = {'a': 'good', 'b': 'good', 'c': 'good', 'd': 'good', 'e': 'skip'}
        self.assertEqual(module.search(commits, invalid.__getitem__)['verdict'], 'invalid-endpoints')

    def test_build_error_and_test_setup_are_skip(self):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / 'tests.log'
            log.write_text('Ran 2 tests in 0.1s\nFAILED (failures=1)\n')
            case = {'build': {'state': 'failed'}, 'tests': {'state': 'passed', 'log': str(log), 'testCount': 2},
                    'mesh': {'state': 'passed'}}
            self.assertEqual(module.classify(case)[0], 'skip')
            case['build']['state'] = 'passed'
            case['tests']['state'] = 'failed'
            self.assertEqual(module.classify(case)[0], 'bad')
            log.write_text('ImportError: missing package\nFAILED (errors=1)\n')
            self.assertEqual(module.classify(case)[0], 'skip')
            case['tests']['state'] = 'passed'
            case['mesh'] = {'state': 'failed', 'diagnosticTail': 'The fixed tetrahedron geometry contract failed.'}
            self.assertEqual(module.classify(case)[0], 'bad')
            case['mesh']['diagnosticTail'] = 'Parser did not start.'
            self.assertEqual(module.classify(case)[0], 'skip')

    def test_isolated_worktrees_find_first_bad(self):
        if not module.shutil.which('dotnet'):
            self.skipTest('dotnet SDK is required for the repository matrix')
        with tempfile.TemporaryDirectory() as folder:
            repo = Path(folder) / 'repo'
            repo.mkdir()

            def git(*args):
                return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()

            git('init', '-q')
            git('config', 'user.name', 'Scientific Test')
            git('config', 'user.email', 'scientific@example.invalid')
            commits = []
            for index, verdict in enumerate(['good', 'good', 'bad', 'bad']):
                (repo / 'classification.txt').write_text(verdict)
                (repo / 'revision.txt').write_text(str(index))
                git('add', '.')
                git('commit', '-q', '-m', str(index))
                commits.append(git('rev-parse', 'HEAD'))

            def evaluate(worktree, destination, python, dotnet):
                bad = (worktree / 'classification.txt').read_text() == 'bad'
                return {'build': {'state': 'passed'}, 'tests': {'state': 'passed', 'testCount': 1},
                        'mesh': {'state': 'failed' if bad else 'passed',
                                 'diagnosticTail': 'The fixed tetrahedron geometry contract failed.' if bad else None}}

            with mock.patch.object(module, 'evaluate', side_effect=evaluate):
                path, report = module.run_bisect(repo, commits[0], commits[-1], Path(folder) / 'evidence')
            self.assertEqual(report['verdict'], 'first-bad')
            self.assertEqual(report['firstBadCommit'], commits[2])
            self.assertTrue(path.is_file())
            self.assertEqual(git('worktree', 'list', '--porcelain').count('worktree '), 1)


if __name__ == '__main__':
    unittest.main()
