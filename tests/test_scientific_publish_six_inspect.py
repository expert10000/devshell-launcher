"""Publication refuses unpaired evidence and consumer checkout drift before running jobs."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/scientific-broker'))
from publish_six_inspect import publish, save_checkpoint, load_checkpoint, sha
from publish_inspection_asset import publish as publish_asset
from six_capability_report import compare


class PublicationGates(unittest.TestCase):
    def test_remote_asset_refuses_unpushed_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            publication = root / 'publication.json'
            publication.write_text('{"kind":"scientific.six-inspect-publication","sourceCommit":"' + 'a' * 40 + '"}')
            from subprocess import CompletedProcess
            with patch('publish_inspection_asset.command', side_effect=[
                    CompletedProcess([], 0, 'a' * 40 + '\n', ''),
                    CompletedProcess([], 0, 'b' * 40 + '\trefs/heads/main\n', '')]):
                with self.assertRaisesRegex(ValueError, 'pushed remote main'):
                    publish_asset(publication, root)

    def test_checkpoint_seal_and_stage_tamper_block_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            release = root / 'release.json'
            release.write_text('{}')
            math3d = root / 'math3d'
            math3d.mkdir()
            run = root / 'publication'
            run.mkdir()
            classes = run / 'classes.json'
            classes.write_text('original')
            checkpoint = run / 'checkpoint.json'
            identity = {'commit': 'a' * 40}
            saved = {'schemaVersion': 1, 'kind': 'scientific.six-inspect-publication-checkpoint',
                     'release': str(release), 'releaseSha256': sha(release),
                     'sourceCommit': 'b' * 40, 'math3dRoot': str(math3d),
                     'math3dIdentity': identity, 'keyId': 'test', 'samples': 7,
                     'stages': {'classes': {'path': 'classes.json', 'sha256': sha(classes)}}}
            save_checkpoint(checkpoint, saved)
            self.assertEqual(load_checkpoint(checkpoint)['stages']['classes']['sha256'], sha(classes))
            classes.write_text('changed')
            with patch('publish_six_inspect.verify_release', return_value={
                    'repo': str(root), 'sourceCommit': 'b' * 40,
                    'math3dRoot': str(math3d), 'math3dIdentity': identity}), \
                 patch('publish_six_inspect.verify_math3d'):
                with self.assertRaisesRegex(ValueError, 'checkpoint artifact changed'):
                    publish(release, math3d, 'key.pem', 'test', root, checkpoint=checkpoint)
            saved['sourceCommit'] = 'c' * 40
            save_checkpoint(checkpoint, saved)
            with patch('publish_six_inspect.verify_release', return_value={
                    'repo': str(root), 'sourceCommit': 'b' * 40,
                    'math3dRoot': str(math3d), 'math3dIdentity': identity}), \
                 patch('publish_six_inspect.verify_math3d'):
                with self.assertRaisesRegex(ValueError, 'source, release, consumer or policy drifted'):
                    publish(release, math3d, 'key.pem', 'test', root, checkpoint=checkpoint)
            checkpoint.write_text(checkpoint.read_text().replace('"samples": 7', '"samples": 8'))
            with self.assertRaisesRegex(ValueError, 'checkpoint seal changed'):
                load_checkpoint(checkpoint)

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
