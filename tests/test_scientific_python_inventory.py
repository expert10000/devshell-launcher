import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform == 'win32' and shutil.which('pwsh'), 'Windows PowerShell 7 required')
class PythonInventoryTests(unittest.TestCase):
    def test_missing_environment_has_actionable_record(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / 'report.json'
            root = Path(directory) / 'missing'
            subprocess.run([
                'pwsh', '-NoProfile', '-File', str(ROOT / 'tools' / 'Inspect-ScientificRuntimes.ps1'),
                '-RuntimeRoot', str(root), '-OutputPath', str(report),
            ], check=True, capture_output=True, text=True)
            payload = json.loads(report.read_text(encoding='utf-8'))
            runtimes = {runtime['id']: runtime for runtime in payload['runtimes']}
            self.assertEqual(set(runtimes), {'cgal-win-conda', 'vtk-win-conda', 'gmsh-win-conda', 'python-win-conda'})
            python = runtimes['python-win-conda']
            self.assertEqual(python['state'], 'missing')
            self.assertEqual(python['checks'][0]['id'], 'python.environment')
            self.assertEqual(python['validatedCapabilities'], [])

    def test_live_scipy_abi_smoke_is_inventory_only(self):
        configured = os.environ.get('DEVSHELL_SCIENTIFIC_PYTHON')
        if not configured or not Path(configured).is_file():
            self.skipTest('DEVSHELL_SCIENTIFIC_PYTHON is not an installed interpreter')
        executable = Path(configured)
        result = subprocess.run([
            str(executable), str(ROOT / 'tools' / 'scientific-runtime-probe.py'), '--kind', 'python',
        ], check=True, capture_output=True, text=True)
        payload = json.loads(result.stdout)
        checks = {check['id']: check for check in payload['checks']}
        self.assertEqual(checks['python.scipy-abi']['state'], 'passed')
        self.assertNotIn('sdk', payload)
        self.assertEqual(payload['validatedCapabilities'], [])


if __name__ == '__main__':
    unittest.main()
