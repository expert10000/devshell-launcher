"""Authored fixture identity and independent geometry checks."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scientific_cgal_corpus import CORPUS, verify_corpus


class CgalCorpusChecks(unittest.TestCase):
    def test_authored_corpus_has_expected_topology(self):
        report = verify_corpus()
        self.assertEqual(report['verdict'], 'passed')
        self.assertEqual([item['id'] for item in report['fixtures']],
                         ['closed-tetra', 'open-square', 'degenerate-triangle', 'nonmanifold-edge'])
        self.assertEqual(report['fixtures'][0]['geometry']['signedVolume'], 1 / 6)

    def test_changed_bytes_and_rights_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / 'cgal'
            shutil.copytree(CORPUS, destination)
            fixture = destination / 'closed-tetra.obj'
            fixture.write_bytes(fixture.read_bytes() + b' ')
            with self.assertRaisesRegex(ValueError, 'hash or path mismatch'):
                verify_corpus(destination)
            shutil.copy2(CORPUS / fixture.name, fixture)
            manifest = destination / 'manifest.v1.json'
            value = json.loads(manifest.read_text(encoding='utf-8'))
            value['license'] = 'unknown'
            manifest.write_text(json.dumps(value), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'provenance'):
                verify_corpus(destination)


if __name__ == '__main__':
    unittest.main()
