"""Explicit, bounded runtime inventory; no compiler builds or rendering."""
import argparse
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from urllib.parse import urlsplit, urlunsplit

parser = argparse.ArgumentParser()
parser.add_argument('--kind', choices=['cgal', 'vtk', 'gmsh', 'python'], required=True)
args = parser.parse_args()
prefix = Path(sys.prefix)
checks = []
_dll_handles = []
if hasattr(os, 'add_dll_directory'):
    for directory in (prefix, prefix / 'Library' / 'bin'):
        if directory.is_dir():
            _dll_handles.append(os.add_dll_directory(str(directory)))


def check(identifier, name, action):
    start = time.monotonic()
    try:
        detail = str(action())
        state = 'passed'
    except Exception as error:
        detail = f'{type(error).__name__}: {error}'
        state = 'failed'
    checks.append({'id': identifier, 'name': name, 'state': state,
                   'durationMs': round((time.monotonic() - start) * 1000), 'detail': detail[:4000]})


def safe_channel(value):
    value = str(value or '')
    if '://' not in value:
        return value[:256]
    parsed = urlsplit(value)
    return urlunsplit((parsed.scheme, parsed.hostname or '', parsed.path, '', ''))[:256]


packages = []
for item in sorted((prefix / 'conda-meta').glob('*.json')):
    try:
        metadata = json.loads(item.read_text(encoding='utf-8'))
        packages.append({'name': metadata['name'], 'version': metadata['version'],
                         'build': metadata.get('build', ''), 'source': safe_channel(metadata.get('channel'))})
    except (OSError, ValueError, KeyError):
        continue
versions = {package['name']: package['version'] for package in packages}
for distribution in importlib.metadata.distributions():
    name = distribution.metadata.get('Name', '')
    if name and name.lower().replace('_', '-') not in versions:
        packages.append({'name': name, 'version': distribution.version, 'build': '', 'source': 'Python distribution metadata'})

check('python.version', 'Python interpreter', lambda: sys.version.split()[0])
check('python.numpy', 'NumPy import', lambda: importlib.import_module('numpy').__version__)
check('python.scipy', 'SciPy import', lambda: importlib.import_module('scipy').__version__)
if args.kind == 'python':
    def abi_smoke():
        numpy = importlib.import_module('numpy')
        linalg = importlib.import_module('scipy.linalg')
        value = linalg.solve(numpy.array([[2.0, 0.0], [0.0, 4.0]], dtype='float64'),
                             numpy.array([2.0, 8.0], dtype='float64'))
        if value.dtype != numpy.float64 or not numpy.allclose(value, [1.0, 2.0], rtol=0, atol=1e-12):
            raise ValueError('SciPy binary solve returned the wrong result or dtype.')
        return 'float64 SciPy solve [1,2]; ABI smoke only, not capability qualification'
    check('python.scipy-abi', 'NumPy / SciPy binary ABI smoke', abi_smoke)
if args.kind == 'cgal':
    check('cgal.python', 'CGAL Python bindings / Point_3',
          lambda: str(importlib.import_module('CGAL.CGAL_Kernel').Point_3(1, 2, 3)))
    include = prefix / 'Library' / 'include' / 'CGAL' / 'version.h'
    config_candidates = [prefix / 'Library' / 'lib' / 'cmake' / 'CGAL' / 'CGALConfig.cmake']
    sdk_version = versions.get('cgal-cpp')
elif args.kind == 'vtk':
    check('vtk.python', 'VTK Python bindings / version',
          lambda: importlib.import_module('vtkmodules.vtkCommonCore').vtkVersion.GetVTKVersion())
    check('vtk.polydata', 'vtkPolyData construction',
          lambda: f"{importlib.import_module('vtkmodules.vtkCommonDataModel').vtkPolyData().GetNumberOfPoints()} points")
    include_candidates = sorted((prefix / 'Library' / 'include').glob('vtk*/vtkVersion.h'))
    include = include_candidates[0] if include_candidates else prefix / 'Library' / 'include' / 'vtkVersion.h'
    config_candidates = sorted((prefix / 'Library' / 'lib' / 'cmake').glob('vtk*/vtk-config.cmake'))
    sdk_version = versions.get('vtk-base', versions.get('vtk'))
elif args.kind == 'gmsh':
    check('gmsh.python', 'Gmsh Python binding / version',
          lambda: importlib.import_module('gmsh').__version__)
    include = prefix / 'Library' / 'include' / 'gmsh.h'
    config_candidates = []
    sdk_version = versions.get('gmsh')
else:
    include = None
    config_candidates = []
    sdk_version = versions.get('scipy')
config = next((item for item in config_candidates if item.is_file()), None)
sdk_present = bool(include and include.is_file() and (config is not None if args.kind != 'gmsh'
                                      else (prefix / 'Library' / 'lib' / 'gmsh.dll.lib').is_file()))
if args.kind != 'python':
    checks.append({'id': f'{args.kind}.sdk', 'name': 'C++ SDK header and import library' if args.kind == 'gmsh' else 'C++ SDK headers and CMake config',
                   'state': 'passed' if sdk_present else 'missing', 'durationMs': 0,
                   'detail': 'Installed files detected; compilation/linking NOT tested.' if sdk_present else 'SDK header or link dependency missing.'})
tools = {}
for name in ('cmake', 'ninja'):
    executable = prefix / 'Library' / 'bin' / f'{name}.exe'
    if not executable.is_file():
        executable = prefix / 'Scripts' / f'{name}.exe'
    record = {'path': str(executable), 'version': None, 'state': 'missing'}
    if executable.is_file():
        try:
            output = subprocess.run([str(executable), '--version'], capture_output=True, timeout=10,
                                    text=True, encoding='utf-8', errors='replace')
            record.update(version=(output.stdout or output.stderr).splitlines()[0][:512],
                          state='passed' if output.returncode == 0 else 'failed')
        except (OSError, subprocess.TimeoutExpired, IndexError) as error:
            record.update(state='failed', detail=str(error)[:1000])
    tools[name] = record

result = {
    'id': f'{args.kind}-win-conda', 'kind': args.kind, 'name': {'cgal': 'CGAL', 'vtk': 'VTK', 'gmsh': 'Gmsh', 'python': 'Python / SciPy'}[args.kind],
    'execution': 'windows-native', 'environmentRoot': str(prefix), 'executable': sys.executable,
    'version': sdk_version, 'state': 'failed' if any(item['state'] == 'failed' for item in checks) else 'partial',
    'pythonVersion': platform.python_version(), 'architecture': platform.machine(),
    'tools': tools, 'checks': checks, 'packages': sorted(packages, key=lambda package: package['name'].lower()),
    'validatedCapabilities': [],
}
if args.kind != 'python':
    result['sdk'] = {'root': str(prefix / 'Library'), 'include': str(include),
                     'cmakeConfig': str(config) if config else None, 'installed': sdk_present,
                     'compilation': 'not-tested', 'linking': 'not-tested', 'rendering': 'not-tested'}
print(json.dumps(result, ensure_ascii=True))
