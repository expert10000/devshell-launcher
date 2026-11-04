"""Source identities remain attributable after a branch moves."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'tools' / 'scientific-broker' / 'source_snapshot.py'
spec = importlib.util.spec_from_file_location('source_snapshot', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SourceSnapshotTests(unittest.TestCase):
    def test_clean_dirty_and_advanced_commit(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)

            def git(*args):
                return subprocess.check_output(['git', '-C', str(root), *args], text=True).rstrip('\n')

            git('init', '-q')
            git('config', 'user.name', 'Scientific Test')
            git('config', 'user.email', 'scientific@example.invalid')
            tracked = root / 'mesh.txt'
            tracked.write_text('first\n', encoding='utf-8')
            git('add', 'mesh.txt')
            git('commit', '-q', '-m', 'first')
            clean = module.repository_snapshot(root)
            self.assertFalse(clean['dirty'])
            self.assertEqual(clean['commit'], git('rev-parse', 'HEAD'))
            before_status = git('status', '--porcelain')
            tracked.write_text('changed\n', encoding='utf-8')
            (root / 'untracked.txt').write_text('fixture\n', encoding='utf-8')
            dirty = module.repository_snapshot(root)
            self.assertTrue(dirty['dirty'])
            self.assertEqual(dirty['commit'], clean['commit'])
            self.assertNotEqual(dirty['snapshotId'], clean['snapshotId'])
            self.assertEqual(dirty['untracked'][0]['path'], 'untracked.txt')
            self.assertEqual(git('status', '--porcelain').splitlines(),
                             [' M mesh.txt', '?? untracked.txt'])
            git('add', 'mesh.txt', 'untracked.txt')
            git('commit', '-q', '-m', 'second')
            advanced = module.repository_snapshot(root)
            self.assertNotEqual(advanced['commit'], clean['commit'])
            self.assertFalse(advanced['dirty'])
            self.assertEqual(clean['commit'], git('rev-parse', 'HEAD~1'))
            self.assertEqual(before_status, '')


if __name__ == '__main__':
    unittest.main()
