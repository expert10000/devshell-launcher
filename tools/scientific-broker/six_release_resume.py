"""Checkpointed, restartable six-capability desktop and broker release run."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid

import six_capability_release as release
from broker import Broker, sha

SCENARIOS = {'inspect': 'CgalInspect', 'orientation': 'Orientation',
             'remesh': 'Remesh', 'repair': 'Repair', 'volume': 'GmshVolume',
             'vtk_read': 'VtkRead'}
SMOKES = {'inspect': (release.inspect_smoke, release.verify_inspect),
          'orientation': (release.orientation_smoke, release.verify_orientation),
          'remesh': (release.remesh_smoke, release.verify_remesh),
          'repair': (release.repair_smoke, release.verify_repair),
          'volume': (release.volume_smoke, release.verify_volume),
          'vtk_read': (release.vtk_read_smoke, release.verify_vtk_read)}


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def save(path, state):
    """Replace one self-sealed file atomically so an interrupted write is rejected."""
    path = Path(path)
    value = {key: item for key, item in state.items() if key != 'checkpointSha256'}
    value['checkpointSha256'] = digest(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temp.write_text(json.dumps(value, separators=(',', ':')), encoding='utf-8')
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
    state.clear()
    state.update(value)


def load(path):
    path = Path(path).resolve(strict=True)
    state = json.loads(path.read_text(encoding='utf-8'))
    seal = state.pop('checkpointSha256', None)
    if (state.get('schemaVersion') != 1 or state.get('kind') != 'scientific.six-release-checkpoint'
            or seal != digest(state) or set(state.get('desktop', {})) - set(release.TARGETS)
            or set(state.get('broker', {})) - set(release.TARGETS)):
        raise ValueError('Six-capability release checkpoint is tampered or unsupported.')
    state['checkpointSha256'] = seal
    if Path(state['releaseRoot']).resolve() != path.parent:
        raise ValueError('Six-capability release checkpoint location changed.')
    return path, state


def prefixes(cgal, vtk, scientific):
    values = {'inspect': cgal, 'orientation': cgal, 'remesh': cgal,
              'repair': cgal, 'volume': scientific, 'vtk_read': vtk}
    values = {name: str(Path(value).resolve(strict=True)) for name, value in values.items()}
    if any(not (Path(value) / 'python.exe').is_file() for value in values.values()):
        raise ValueError('Each scientific prefix must contain python.exe.')
    return values


def start(math3d, cgal, vtk, scientific, output_root=None, profile='desktop-five', port=9270):
    math3d = Path(math3d).resolve(strict=True)
    if not (math3d / 'renderer/src/mesh/surfaceMesh.ts').is_file():
        raise ValueError('MATH3D consumer checkout is unavailable.')
    runtime_prefixes = prefixes(cgal, vtk, scientific)
    identity = release.math3d_identity(math3d)
    worktree = Path(os.environ.get('SystemDrive', 'C:') + '\\ds6-' + uuid.uuid4().hex[:12])
    release.command(['git', 'worktree', 'add', '--detach', worktree, 'HEAD'])
    root = Path(output_root).resolve() if output_root else worktree / '.scientific/six-capability-release'
    state = {'schemaVersion': 1, 'kind': 'scientific.six-release-checkpoint',
             'sourceCommit': release.commit(worktree), 'worktree': str(worktree),
             'releaseRoot': str(root), 'math3dRoot': str(math3d),
             'math3dIdentity': identity, 'prefixes': runtime_prefixes,
             'profileId': profile, 'port': port, 'build': None,
             'desktop': {}, 'broker': {}, 'manifestSha256': None,
             'releaseRecord': None, 'attempts': [], 'activeStage': None,
             'retryL9': False, 'status': 'running', 'createdAtUtc': now()}
    checkpoint = root / 'checkpoint.json'
    save(checkpoint, state)
    print('WORKTREE=' + str(worktree), flush=True)
    print('CHECKPOINT=' + str(checkpoint), flush=True)
    return execute(checkpoint, state)


def current_entries(state, output):
    worktree = Path(state['worktree'])
    installed = worktree / 'BatchLauncher/bin/Release/net8.0-windows'
    return release.fresh_export(worktree, installed, Path(state['math3dRoot']),
                                state['profileId'], output)


def support(state, fresh):
    entries = {(item['runtimeId'], item['capabilityId']): item
               for item in fresh.get('certifiedCapabilities', [])}
    for name, saved in state['desktop'].items():
        item = entries.get(release.TARGETS[name])
        if (not item or item.get('level') != 'L9' or item.get('recordId') != saved['recordId']
                or len(item.get('supportingRecords', [])) != 10
                or [part.get('level') for part in item['supportingRecords']] !=
                   [f'L{level}' for level in range(10)]
                or [part.get('runId') for part in item['supportingRecords']] != saved['runIds']):
            raise ValueError(name + ' checkpoint desktop support became stale.')
    return entries


def validate(checkpoint, state):
    worktree = Path(state['worktree']).resolve(strict=True)
    if (release.commit(worktree) != state['sourceCommit']
            or release.commit(release.ROOT) != state['sourceCommit']
            or Path(state['releaseRoot']).resolve() != checkpoint.parent):
        raise ValueError('Six-capability checkpoint source commit or worktree changed.')
    release.verify_math3d_identity(state['math3dRoot'], state['math3dIdentity'])
    for path in state['prefixes'].values():
        if not (Path(path) / 'python.exe').is_file():
            raise ValueError('Six-capability runtime prefix disappeared.')
    if state['build']:
        for name, expected in state['build'].items():
            if sha(worktree / name) != expected:
                raise ValueError('Checkpointed desktop build changed: ' + name)
    if state['desktop']:
        probe = checkpoint.parent / ('resume-support-' + uuid.uuid4().hex + '.json')
        try:
            support(state, current_entries(state, probe))
        finally:
            probe.unlink(missing_ok=True)
            Path(str(probe) + '.sha256').unlink(missing_ok=True)
    manifest = checkpoint.parent / 'certified.json'
    if state['manifestSha256']:
        if sha(manifest) != state['manifestSha256']:
            raise ValueError('Checkpointed certified manifest changed.')
        if len(state['desktop']) != 6:
            raise ValueError('Broker checkpoint has incomplete desktop support.')
    for name, item in state['broker'].items():
        if (sha(item['config']) != item['configSha256']
                or sha(item['smoke']) != item['smokeSha256']
                or sha(item['math3dLink']) != item['math3dLinkSha256']):
            raise ValueError(name + ' broker checkpoint artifact changed.')
        broker = Broker(item['config'])
        if (broker.runtime_id, broker.capability_id) != release.TARGETS[name]:
            raise ValueError(name + ' broker checkpoint identity changed.')
        SMOKES[name][1](item['smoke'], item['config'])
    if state['releaseRecord']:
        release.verify(state['releaseRecord'])


def stage(checkpoint, state, name, callback):
    state['activeStage'] = name
    state['status'] = 'running'
    state['attempts'].append({'stage': name, 'startedAtUtc': now(), 'result': 'running'})
    save(checkpoint, state)
    # A callback may fill a release field before a later verification fails.
    # Never checkpoint that partial promotion as a completed gate.
    promotion = {key: deepcopy(state[key]) for key in
                 ('build', 'desktop', 'broker', 'manifestSha256', 'releaseRecord')}
    try:
        result = callback()
    except BaseException as error:
        state.update(promotion)
        state['status'] = 'interrupted'
        state['attempts'][-1].update(result='interrupted', endedAtUtc=now(),
                                     error=str(error)[-500:])
        state['activeStage'] = None
        save(checkpoint, state)
        raise
    state['attempts'][-1].update(result='passed', endedAtUtc=now())
    state['activeStage'] = None
    save(checkpoint, state)
    return result


def build(state):
    worktree = Path(state['worktree'])
    scientific = worktree / '.scientific'
    scientific.mkdir(exist_ok=True)
    inventory = release.ROOT / '.scientific/runtime-report.json'
    if inventory.is_file():
        shutil.copyfile(inventory, scientific / 'runtime-report.json')
    frontend = worktree / 'DevShell/ui/dev-ui-react'
    release.command(['npm', 'ci', '--ignore-scripts'], cwd=frontend, timeout=240)
    release.command(['npm', 'run', 'build'], cwd=frontend, timeout=240)
    release.command(['dotnet', 'build', worktree / 'BatchLauncher/BatchLauncher.csproj', '-c', 'Release'],
                    cwd=worktree, timeout=240)
    assets = ('BatchLauncher/bin/Release/net8.0-windows/BatchLauncher.exe',
              'BatchLauncher/bin/Release/net8.0-windows/runtime-lab.exe')
    state['build'] = {name: sha(worktree / name) for name in assets}


def desktop(checkpoint, state, name):
    worktree = Path(state['worktree'])
    attempt = sum(item['stage'] == 'desktop:' + name for item in state['attempts'])
    log = checkpoint.parent / f'desktop-{name}-{attempt}.log'
    args = ['powershell', '-NoProfile', '-File',
            str(worktree / 'tools/Run-Scientific-Desktop-Acceptance.ps1'),
            '-Scenario', SCENARIOS[name], '-ExistingWorktree', str(worktree), '-SkipBuild',
            '-Math3DCheckout', state['math3dRoot'], '-CdpPort', str(state['port'] + list(release.TARGETS).index(name))]
    with log.open('w', encoding='utf-8') as stream:
        process = subprocess.Popen(args, cwd=worktree, stdout=stream, stderr=subprocess.STDOUT,
                                   text=True)
        try:
            result_code = process.wait(timeout=2400)
        except BaseException:
            if process.poll() is None:
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                process.wait(timeout=10)
            raise
    if result_code:
        raise ValueError(f'{name} desktop acceptance failed; see {log}')
    probe = checkpoint.parent / ('desktop-' + name + '-support.json')
    fresh = current_entries(state, probe)
    item = next((entry for entry in fresh.get('certifiedCapabilities', [])
                 if (entry['runtimeId'], entry['capabilityId']) == release.TARGETS[name]), None)
    if not item or item.get('level') != 'L9' or len(item.get('supportingRecords', [])) != 10:
        raise ValueError(name + ' desktop action did not produce current L0-L9 support.')
    state['desktop'][name] = {'recordId': item['recordId'],
                              'runIds': [part['runId'] for part in item['supportingRecords']],
                              'exportSha256': sha(probe), 'log': str(log)}
    state['retryL9'] = False


def broker_stage(state, name, entries):
    worktree = Path(state['worktree'])
    root = Path(state['releaseRoot'])
    manifest = root / 'certified.json'
    config = release.config_for(worktree, Path(state['math3dRoot']), manifest, name,
                                entries[release.TARGETS[name]], Path(state['prefixes'][name]))
    smoke, _ = SMOKES[name][0](config)
    release.verify_math3d_identity(state['math3dRoot'], state['math3dIdentity'])
    link = root / (name + '-math3d-link.json')
    link.write_text(json.dumps({'schemaVersion': 1, 'kind': 'scientific.product-smoke-math3d-link',
                                'name': name, 'smokeSha256': sha(smoke),
                                'math3dIdentitySha256': state['math3dIdentity']['identitySha256']},
                               separators=(',', ':')), encoding='utf-8')
    state['broker'][name] = {'recordId': entries[release.TARGETS[name]]['recordId'],
                             'config': str(config), 'configSha256': sha(config),
                             'smoke': str(smoke), 'smokeSha256': sha(smoke),
                             'math3dIdentitySha256': state['math3dIdentity']['identitySha256'],
                             'math3dLink': str(link), 'math3dLinkSha256': sha(link)}


def finalize(state):
    worktree = Path(state['worktree'])
    root = Path(state['releaseRoot'])
    record = {'schemaVersion': 1, 'kind': 'scientific.six-capability-release',
              'verifierSha256': release.verifier_sha(), 'sourceCommit': state['sourceCommit'],
              'createdAtUtc': now(), 'repo': str(worktree),
              'installedRoot': str(worktree / 'BatchLauncher/bin/Release/net8.0-windows'),
              'math3dRoot': state['math3dRoot'], 'profileId': state['profileId'],
              'math3dIdentity': state['math3dIdentity'], 'profiles': state['broker']}
    release.checked(record)
    path = root / ('coexistence-' + uuid.uuid4().hex + '.json')
    path.write_text(json.dumps(record, separators=(',', ':')), encoding='utf-8')
    Path(str(path) + '.sha256').write_text(sha(path), encoding='utf-8')
    state['releaseRecord'] = str(path)


def execute(checkpoint, state=None):
    checkpoint = Path(checkpoint).resolve(strict=True)
    if state is None:
        checkpoint, state = load(checkpoint)
    validate(checkpoint, state)
    if state['activeStage']:
        if not state['attempts'] or state['attempts'][-1]['stage'] != state['activeStage']:
            raise ValueError('Incomplete stage checkpoint is inconsistent.')
        if state['attempts'][-1]['result'] == 'running':
            state['attempts'][-1].update(result='interrupted', endedAtUtc=now(),
                                         error='Process ended before stage completion')
        elif state['attempts'][-1]['result'] != 'interrupted' or state['status'] != 'interrupted':
            raise ValueError('Incomplete stage checkpoint is inconsistent.')
        state['activeStage'] = None
        state['status'] = 'interrupted'
        save(checkpoint, state)
    if state['status'] == 'complete':
        return Path(state['releaseRecord']), release.verify(state['releaseRecord'])
    if not state['build']:
        stage(checkpoint, state, 'build', lambda: build(state))
    for name in release.TARGETS:
        if name not in state['desktop']:
            stage(checkpoint, state, 'desktop:' + name,
                  lambda name=name: desktop(checkpoint, state, name))
    root = Path(state['releaseRoot'])
    manifest = root / 'certified.json'
    if not state['manifestSha256']:
        def export():
            fresh = current_entries(state, manifest)
            entries = release.require_current_support(fresh, {
                name: state['desktop'][name]['recordId'] for name in release.TARGETS})
            support(state, fresh)
            state['manifestSha256'] = sha(manifest)
            return entries
        entries = stage(checkpoint, state, 'certified-export', export)
    else:
        fresh = json.loads(manifest.read_text(encoding='utf-8'))
        entries = release.require_current_support(fresh, {
            name: state['desktop'][name]['recordId'] for name in release.TARGETS})
    for name in release.TARGETS:
        if name not in state['broker']:
            stage(checkpoint, state, 'broker:' + name,
                  lambda name=name: broker_stage(state, name, entries))
    if not state['releaseRecord']:
        stage(checkpoint, state, 'finalize', lambda: finalize(state))
    state['status'] = 'complete'
    save(checkpoint, state)
    return Path(state['releaseRecord']), release.verify(state['releaseRecord'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('run', 'resume'))
    parser.add_argument('--checkpoint')
    parser.add_argument('--math3d-root')
    parser.add_argument('--cgal-prefix', default=os.environ.get('DEVSHELL_CGAL_PREFIX'))
    parser.add_argument('--vtk-prefix', default=os.environ.get('DEVSHELL_VTK_PREFIX'))
    parser.add_argument('--scientific-prefix', default=os.environ.get('DEVSHELL_SCIENTIFIC_PREFIX'))
    parser.add_argument('--output-root')
    parser.add_argument('--profile-id', default='desktop-five')
    parser.add_argument('--port', type=int, default=9270)
    options = parser.parse_args()
    if options.command == 'resume':
        if not options.checkpoint:
            parser.error('resume requires --checkpoint')
        path, record = execute(options.checkpoint)
    else:
        if not all((options.math3d_root, options.cgal_prefix, options.vtk_prefix, options.scientific_prefix)):
            parser.error('run requires the MATH3D checkout and three scientific prefixes')
        path, record = start(options.math3d_root, options.cgal_prefix, options.vtk_prefix,
                             options.scientific_prefix, options.output_root,
                             options.profile_id, options.port)
    print(json.dumps({'record': str(path), 'sourceCommit': record['sourceCommit'], 'verdict': 'qualified'}))
