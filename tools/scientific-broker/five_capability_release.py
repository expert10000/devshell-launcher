"""Requalify orientation, remesh, repair, volume and VTK read in one isolated DevShell worktree."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

from broker import Broker, sha
from release_certification import fresh_export
from repair_smoke import run as repair_smoke, verify as verify_repair
from gmsh_volume_smoke import run as volume_smoke, verify as verify_volume
from remesh_broker_smoke import run as remesh_smoke, verify as verify_remesh
from orientation_broker_smoke import run as orientation_smoke, verify as verify_orientation
from vtk_read_broker_smoke import run as vtk_read_smoke, verify as verify_vtk_read
from math3d_release_identity import capture as math3d_identity, verify as verify_math3d_identity

SOURCE = Path(__file__).resolve()
ROOT = SOURCE.parents[2]
TARGETS = {'orientation': ('cgal-win-conda', 'mesh.orient'),
           'remesh': ('cgal-win-conda', 'mesh.remesh'),
           'repair': ('cgal-win-conda', 'mesh.repair'),
           'volume': ('gmsh-win-conda', 'mesh.generate3d'),
           'vtk_read': ('vtk-win-conda', 'mesh.read')}


def verifier_sha(path=SOURCE):
    """Seal source content consistently across LF and CRLF Git checkouts."""
    return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def command(args, cwd=None, timeout=2400):
    argv = [str(item) for item in args]
    if not any(separator in argv[0] for separator in ('/', '\\', ':')):
        argv[0] = shutil.which(argv[0]) or argv[0]
    completed = subprocess.run(argv, cwd=cwd or ROOT, timeout=timeout)
    if completed.returncode:
        raise ValueError(f'Command exited {completed.returncode}: {args[0]}')


def commit(repo):
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()


def require_current_support(fresh, expected_ids):
    entries = {(item['runtimeId'], item['capabilityId']): item
               for item in fresh.get('certifiedCapabilities', [])}
    if set(entries) != set(TARGETS.values()) or len(fresh['certifiedCapabilities']) != 5:
        raise ValueError('Fresh export must contain exactly current orientation, remesh, repair, volume and VTK read L9.')
    for name, identity in TARGETS.items():
        entry = entries[identity]
        support = entry.get('supportingRecords')
        if (entry.get('level') != 'L9' or entry.get('recordId') != expected_ids[name]
                or not isinstance(support, list) or len(support) != 10
                or any(item.get('level') != f'L{index}' or not item.get('recordId')
                       or not item.get('runId') for index, item in enumerate(support))
                or support[-1]['recordId'] != expected_ids[name]):
            raise ValueError(name + ' L0-L9 support is stale or incomplete.')
    return entries


def find_worker(worktree, name, expected):
    for path in (worktree / '.scientific/builds').rglob(name):
        if sha(path) == expected:
            return path
    raise ValueError('Qualified worker binary is unavailable: ' + name)


def config_for(worktree, math3d, manifest, name, entry, prefix):
    broker_root = worktree / '.scientific/five-capability-release'
    runtime = entry['runtimeId']
    if name == 'orientation':
        adapter = worktree / 'tools/scientific-cgal-worker.py'
        worker = find_worker(worktree, 'devshell_cgal_orientation.exe', entry['workerBinarySha256'])
    elif name == 'volume':
        adapter = worktree / 'tools/scientific-broker/gmsh_volume_adapter.py'
        worker = worktree / 'tools/scientific-gmsh-volume-worker.py'
    elif name == 'repair':
        adapter = worktree / 'tools/scientific-cgal-hole-repair-worker.py'
        worker = find_worker(worktree, 'devshell_cgal_hole_repair.exe', entry['workerBinarySha256'])
    elif name == 'vtk_read':
        adapter = worktree / 'tools/scientific-broker/vtk_read_adapter.py'
        worker = worktree / 'tools/scientific-mesh-worker.py'
    else:
        adapter = worktree / 'tools/scientific-cgal-worker.py'
        worker = find_worker(worktree, 'devshell_cgal_worker.exe', entry['workerBinarySha256'])
    if sha(adapter) != entry['adapterSha256'] or sha(worker) != entry['workerBinarySha256']:
        raise ValueError(name + ' broker adapter or worker changed.')
    jobs = broker_root / (name + '-jobs')
    jobs.mkdir(parents=True, exist_ok=True)
    value = {'schemaVersion': 1, 'runtimeId': runtime, 'capabilityId': entry['capabilityId'],
             'manifest': str(manifest),
             'runtimeManifest': str(worktree / 'BatchLauncher/bin/Release/net8.0-windows/runtimes' / runtime / 'runtime.json'),
             'adapter': str(adapter), 'workerContract': str(worktree / 'tools/scientific_worker_contract.py'),
             'python': str(prefix / 'python.exe'), 'worker': str(worker), 'prefix': str(prefix),
             'datasetRoot': str(worktree / '.scientific/datasets'), 'jobsRoot': str(jobs),
             'math3dRoot': str(math3d), 'sourceRoot': str(worktree)}
    path = broker_root / (name + '-config.json')
    path.write_text(json.dumps(value, separators=(',', ':')), encoding='utf-8')
    Broker(path)
    return path


def checked(record):
    if record.get('verifierSha256') != verifier_sha() or record.get('schemaVersion') != 1 or record.get('kind') != 'scientific.five-capability-release':
        raise ValueError('Five-capability release verifier changed.')
    if set(record.get('profiles', {})) != set(TARGETS):
        raise ValueError('Five-capability release profile set changed.')
    repo = Path(record['repo']).resolve(strict=True)
    installed = Path(record['installedRoot']).resolve(strict=True)
    math3d = Path(record['math3dRoot']).resolve(strict=True)
    if commit(repo) != record['sourceCommit']:
        raise ValueError('Five-capability release source commit changed.')
    if not isinstance(record.get('math3dIdentity'), dict):
        raise ValueError('Five-capability release has no MATH3D identity.')
    verify_math3d_identity(math3d, record['math3dIdentity'])
    fresh_path = repo / '.scientific/five-capability-release' / ('fresh-verify-' + uuid.uuid4().hex + '.json')
    try:
        fresh = fresh_export(repo, installed, math3d, record['profileId'], fresh_path)
    finally:
        fresh_path.unlink(missing_ok=True)
        Path(str(fresh_path) + '.sha256').unlink(missing_ok=True)
    entries = require_current_support(fresh, {name: item['recordId'] for name, item in record['profiles'].items()})
    for name, identity in TARGETS.items():
        item = record['profiles'][name]
        config = Path(item['config']).resolve(strict=True)
        smoke = Path(item['smoke']).resolve(strict=True)
        if sha(config) != item['configSha256'] or sha(smoke) != item['smokeSha256']:
            raise ValueError(name + ' config or smoke seal changed.')
        link_path = Path(item['math3dLink']).resolve(strict=True)
        if sha(link_path) != item['math3dLinkSha256']:
            raise ValueError(name + ' MATH3D identity link changed.')
        link = json.loads(link_path.read_text(encoding='utf-8'))
        if (link.get('name') != name or link.get('smokeSha256') != item['smokeSha256']
                or link.get('math3dIdentitySha256') != record['math3dIdentity']['identitySha256']
                or item['math3dIdentitySha256'] != record['math3dIdentity']['identitySha256']):
            raise ValueError(name + ' product smoke MATH3D identity drifted.')
        broker = Broker(config)
        if (broker.runtime_id, broker.capability_id) != identity or len(broker.capabilities) != 1 or broker.capabilities[0] != entries[identity]:
            raise ValueError(name + ' broker profile differs from fresh support.')
        (verify_orientation if name == 'orientation' else verify_remesh if name == 'remesh' else
         verify_repair if name == 'repair' else verify_volume if name == 'volume' else verify_vtk_read)(smoke, config)
    return record


def run(math3d, cgal_prefix, vtk_prefix, scientific_prefix, output_root=None, profile='desktop-five', port=9270):
    math3d = Path(math3d).resolve(strict=True)
    if not (math3d / 'renderer/src/mesh/surfaceMesh.ts').is_file():
        raise ValueError('MATH3D consumer checkout is unavailable.')
    prefixes = {'orientation': Path(cgal_prefix).resolve(strict=True),
                'remesh': Path(cgal_prefix).resolve(strict=True),
                'repair': Path(cgal_prefix).resolve(strict=True),
                'volume': Path(scientific_prefix).resolve(strict=True),
                'vtk_read': Path(vtk_prefix).resolve(strict=True)}
    if any(not (prefix / 'python.exe').is_file() for prefix in prefixes.values()):
        raise ValueError('Each configured runtime prefix must contain python.exe.')
    consumer_identity = math3d_identity(math3d)
    worktree = Path(os.environ.get('SystemDrive', 'C:') + '\\ds5-' + uuid.uuid4().hex[:12])
    command(['git', 'worktree', 'add', '--detach', worktree, 'HEAD'])
    if commit(worktree) != commit(ROOT):
        raise ValueError('Isolated worktree source commit changed.')
    scientific = worktree / '.scientific'
    scientific.mkdir(exist_ok=True)
    inventory = ROOT / '.scientific/runtime-report.json'
    if inventory.is_file():
        shutil.copyfile(inventory, scientific / 'runtime-report.json')
    frontend = worktree / 'DevShell/ui/dev-ui-react'
    command(['npm', 'ci', '--ignore-scripts'], cwd=frontend, timeout=240)
    command(['npm', 'run', 'build'], cwd=frontend, timeout=240)
    command(['dotnet', 'build', worktree / 'BatchLauncher/BatchLauncher.csproj', '-c', 'Release'], cwd=worktree, timeout=240)
    for offset, name in enumerate(TARGETS):
        scenario = 'Orientation' if name == 'orientation' else 'Remesh' if name == 'remesh' else 'Repair' if name == 'repair' else 'GmshVolume' if name == 'volume' else 'VtkRead'
        command(['powershell', '-NoProfile', '-File', worktree / 'tools/Run-Scientific-Desktop-Acceptance.ps1',
                 '-Scenario', scenario, '-ExistingWorktree', worktree, '-SkipBuild',
                 '-Math3DCheckout', math3d, '-CdpPort', str(port + offset)], cwd=worktree)
    installed = worktree / 'BatchLauncher/bin/Release/net8.0-windows'
    release_root = Path(output_root).resolve() if output_root else scientific / 'five-capability-release'
    release_root.mkdir(parents=True, exist_ok=True)
    manifest = release_root / 'certified.json'
    fresh = fresh_export(worktree, installed, math3d, profile, manifest)
    entries = require_current_support(fresh, {name: next(item['recordId'] for item in fresh['certifiedCapabilities']
        if (item['runtimeId'], item['capabilityId']) == identity) for name, identity in TARGETS.items()})
    profiles = {}
    for name, identity in TARGETS.items():
        config = config_for(worktree, math3d, manifest, name, entries[identity], prefixes[name])
        smoke, _ = (orientation_smoke if name == 'orientation' else remesh_smoke if name == 'remesh' else
                    repair_smoke if name == 'repair' else volume_smoke if name == 'volume' else vtk_read_smoke)(config)
        verify_math3d_identity(math3d, consumer_identity)
        link_path = release_root / (name + '-math3d-link.json')
        link_path.write_text(json.dumps({'schemaVersion': 1, 'kind': 'scientific.product-smoke-math3d-link',
                                         'name': name, 'smokeSha256': sha(smoke),
                                         'math3dIdentitySha256': consumer_identity['identitySha256']},
                                        separators=(',', ':')), encoding='utf-8')
        profiles[name] = {'recordId': entries[identity]['recordId'], 'config': str(config),
                          'configSha256': sha(config), 'smoke': str(smoke), 'smokeSha256': sha(smoke),
                          'math3dIdentitySha256': consumer_identity['identitySha256'],
                          'math3dLink': str(link_path), 'math3dLinkSha256': sha(link_path)}
    record = {'schemaVersion': 1, 'kind': 'scientific.five-capability-release',
              'verifierSha256': verifier_sha(), 'sourceCommit': commit(worktree),
              'createdAtUtc': datetime.now(timezone.utc).isoformat(), 'repo': str(worktree),
              'installedRoot': str(installed), 'math3dRoot': str(math3d), 'profileId': profile,
              'math3dIdentity': consumer_identity, 'profiles': profiles}
    checked(record)
    path = release_root / ('coexistence-' + uuid.uuid4().hex + '.json')
    path.write_text(json.dumps(record, separators=(',', ':')), encoding='utf-8')
    Path(str(path) + '.sha256').write_text(sha(path), encoding='utf-8')
    return path, record


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('Five-capability release seal changed.')
    return checked(json.loads(path.read_text(encoding='utf-8')))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('run', 'verify'))
    parser.add_argument('--math3d-root')
    parser.add_argument('--cgal-prefix', default=os.environ.get('DEVSHELL_CGAL_PREFIX'))
    parser.add_argument('--vtk-prefix', default=os.environ.get('DEVSHELL_VTK_PREFIX'))
    parser.add_argument('--scientific-prefix', default=os.environ.get('DEVSHELL_SCIENTIFIC_PREFIX'))
    parser.add_argument('--output-root')
    parser.add_argument('--profile-id', default='desktop-five')
    parser.add_argument('--port', type=int, default=9270)
    parser.add_argument('--record')
    options = parser.parse_args()
    if options.command == 'run':
        if not all((options.math3d_root, options.cgal_prefix, options.vtk_prefix, options.scientific_prefix)):
            parser.error('run requires --math3d-root, --cgal-prefix, --vtk-prefix and --scientific-prefix')
        path, result = run(options.math3d_root, options.cgal_prefix, options.vtk_prefix,
                           options.scientific_prefix, options.output_root, options.profile_id, options.port)
    else:
        if not options.record:
            parser.error('verify requires --record')
        path, result = options.record, verify(options.record)
    print(json.dumps({'record': str(path), 'sourceCommit': result['sourceCommit'], 'verdict': 'qualified'}))
