"""Evidence and rendering checks for DS-SCI-050."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools' / 'scientific-broker'
sys.path.insert(0, str(TOOL))
spec = importlib.util.spec_from_file_location('reproducibility_report', TOOL / 'reproducibility_report.py')
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


class ReproducibilityReportTests(unittest.TestCase):
    def test_html_escapes_untrusted_evidence(self):
        rendered = report.render_html('# Title\n\n- <script>alert(1)</script>\n\n| A | B |\n|---|---|\n| x | y |\n')
        self.assertIn('<h1>Title</h1>', rendered)
        self.assertIn('<table>', rendered)
        self.assertIn('&lt;script&gt;', rendered)
        self.assertNotIn('<script>', rendered)

    def test_real_sources_are_verified_and_blocked_gate_is_preserved(self):
        scientific = ROOT / '.scientific'
        paths = {
            'matrix': scientific / 'release-matrix' / 'a22944f370044a52bd313a28c6625adf.json',
            'conformance': scientific / 'conformance' / '65bb5c360a0e4afb885b9d1ada69ba4b' / 'conformance.json',
            'contract': scientific / 'contract-migrations' / 'd273581668e44c5d951c5a6444585739.json',
            'environment': scientific / 'environment-locks' / 'e19be0f9a8d24bf38f66f5b22c994d4a' / 'environment-manifest.json',
            'recreation': scientific / 'environment-recreation' / '7c16d0501ba2478394bb5b423dee8226.json',
            'provenance': scientific / 'provenance' / 'e37b72b8d70f40b59f3de401e4094a3f' / 'provenance.json',
            'differential': scientific / 'differentials' / 'a45bf36ae44643bfbe04d9f352e96d54.json',
            'config': scientific / 'broker' / 'config.json',
            'policy': report.DEFAULT_POLICY,
        }
        if not all(path.is_file() for path in paths.values()):
            self.skipTest('Local scientific evidence is unavailable')
        with tempfile.TemporaryDirectory() as directory:
            path, record = report.generate(paths, directory)
            self.assertEqual(record['releaseVerdict'], 'inconclusive')
            self.assertEqual(report.verify(path), record)
            markdown = path.with_suffix('.md')
            body = markdown.read_text(encoding='utf-8')
            for heading in ('Capabilities and release gates', 'Fixtures and artifacts',
                            'Fingerprints and tolerances', 'Regressions and scope', 'Reproduce and verify'):
                self.assertIn(heading, body)
            self.assertIn('Fresh desktop export has no single current L9', body)
            self.assertIn('Gmsh remains unqualified', body)
            markdown.write_text(body + '\ntampered', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Rendered report changed'):
                report.verify(path)
            markdown.write_text(body, encoding='utf-8')
            html = path.with_suffix('.html')
            html.write_text(html.read_text(encoding='utf-8') + 'tampered', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Rendered report changed'):
                report.verify(path)
            html.write_text(report.render_html(body), encoding='utf-8')
            record['sources']['matrix']['sha256'] = '0' * 64
            path.write_text(json.dumps(record), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'record hash mismatch'):
                report.verify(path)


if __name__ == '__main__':
    unittest.main()
