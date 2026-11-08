"""Optional local C++ replay and artifact tamper gate."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_corpus_replay import run, verify


@unittest.skipUnless(os.environ.get('SCIENTIFIC_CGAL_CORPUS_WORKER') and
                     os.environ.get('SCIENTIFIC_CGAL_CORPUS_PREFIX'),
                     'Local CGAL worker and prefix are required')
class CgalCorpusReplayChecks(unittest.TestCase):
    def test_worker_replay_and_changed_output_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            report_path, report = run(os.environ['SCIENTIFIC_CGAL_CORPUS_WORKER'],
                                      os.environ['SCIENTIFIC_CGAL_CORPUS_PREFIX'], directory)
            self.assertEqual([case['state'] for case in report['cases']],
                             ['succeeded', 'succeeded', 'failed', 'failed'])
            self.assertEqual(verify(report_path)['verdict'], 'passed')
            output = Path(report['cases'][0]['directory']) / 'output.obj'
            original = output.read_bytes()
            try:
                output.write_bytes(original + b' ')
                with self.assertRaisesRegex(ValueError, 'output hash mismatch'):
                    verify(report_path)
            finally:
                output.write_bytes(original)
            self.assertEqual(verify(report_path)['verdict'], 'passed')


if __name__ == '__main__':
    unittest.main()
