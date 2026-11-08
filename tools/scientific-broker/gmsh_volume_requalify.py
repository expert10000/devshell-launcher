"""Plan or execute the managed fixed-cube Gmsh requalification chain."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
from urllib.parse import urlsplit
from urllib.request import urlopen

from broker import sha
from release_certification import verify_release

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / 'tools/scientific-broker/ScientificBroker.csproj'
DLL = ROOT / 'tools/scientific-broker/bin/Release/net8.0/ScientificBroker.dll'
FULL = ('lab.probe', 'compile-link', 'l5.gmsh-volume', 'l6.gmsh-volume',
        'l7.gmsh-volume', 'l8.gmsh-volume', 'product-readiness.gmsh-volume', 'l9.gmsh-volume')
RESUME = ('l7.gmsh-volume', 'l8.gmsh-volume', 'product-readiness.gmsh-volume', 'l9.gmsh-volume')


def command(args, timeout=300, env=None, log=None):
    result = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, text=True,
                            encoding='utf-8', errors='replace', timeout=timeout)
    if log is not None:
        log.write_text(result.stdout + result.stderr, encoding='utf-8')
    if result.returncode:
        raise ValueError(f'{Path(args[0]).name} exited {result.returncode}: '
                         + (result.stderr or result.stdout)[-1600:])
    return result.stdout


def audit(installed, math3d, profile):
    command(['dotnet', 'build', str(PROJECT), '-c', 'Release', '--no-restore'], timeout=120)
    return json.loads(command(['dotnet', str(DLL), 'audit-volume', str(ROOT),
                               str(installed), str(math3d), profile], timeout=120))


def mode_for(audited):
    if audited.get('eligible'):
        return 'current', ()
    candidates = audited.get('candidates') or []
    if not candidates:
        return 'full', FULL
    support = candidates[0].get('support') or []
    if len(support) != 9 or any(item.get('level') != f'L{index}'
                                for index, item in enumerate(support)):
        return 'full', FULL
    earliest = next((index for index, item in enumerate(support)
                     if item.get('status') != 'current'), 9)
    return ('full', FULL) if earliest <= 6 else ('resume', RESUME)


def require_desktop(url):
    parsed = urlsplit(url or '')
    if (parsed.scheme != 'http' or parsed.hostname != '127.0.0.1'
            or parsed.username or parsed.password or parsed.path not in ('', '/')
            or parsed.query or parsed.fragment or parsed.port is None):
        raise ValueError('A localhost DevShell CDP URL is required for managed runs.')
    with urlopen(url.rstrip('/') + '/json/list', timeout=3) as response:
        targets = json.load(response)
    if not isinstance(targets, list) or not any(
            urlsplit(item.get('url', '')).hostname == 'app.local'
            for item in targets if isinstance(item, dict)):
        raise ValueError('The CDP endpoint has no DevShell app page.')


def save(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, separators=(',', ':'))
    Path(str(path) + '.sha256').write_text(sha(path), encoding='utf-8')


def publish_manifest(candidate, deployed, expected_sha, verify=None):
    sidecar = Path(str(deployed) + '.sha256')
    if sha(deployed) != expected_sha or sidecar.read_text(encoding='utf-8').strip() != expected_sha:
        raise ValueError('The deployed broker manifest changed during requalification.')
    previous = deployed.read_bytes(), sidecar.read_bytes()
    replacement = candidate.read_bytes(), Path(str(candidate) + '.sha256').read_bytes()
    if sha(candidate) != replacement[1].decode('utf-8').strip():
        raise ValueError('The staged broker manifest hash changed.')
    temporary = deployed.with_name(deployed.name + '.' + uuid.uuid4().hex + '.next')
    temporary_sidecar = Path(str(temporary) + '.sha256')
    try:
        temporary.write_bytes(replacement[0])
        temporary_sidecar.write_bytes(replacement[1])
        os.replace(temporary, deployed)
        os.replace(temporary_sidecar, sidecar)
        if verify is not None:
            verify()
    except Exception:
        deployed.write_bytes(previous[0])
        sidecar.write_bytes(previous[1])
        raise
    finally:
        temporary.unlink(missing_ok=True)
        temporary_sidecar.unlink(missing_ok=True)


def verified_file(path, expected):
    target = Path(path).resolve(strict=True)
    if sha(target) != expected:
        raise ValueError('Requalification evidence hash mismatch: ' + str(target))
    return target


def verify_result(path, config_path=None):
    path = Path(path).resolve(strict=True)
    verified_file(path, Path(str(path) + '.sha256').read_text(encoding='utf-8').strip())
    result = json.loads(path.read_text(encoding='utf-8'))
    if result.get('schemaVersion') != 1 or result.get('kind') != 'scientific.gmsh-volume-requalification-run':
        raise ValueError('Unsupported volume requalification result.')
    plan_path = verified_file(result['planPath'], result['planSha256'])
    verified_file(plan_path, Path(str(plan_path) + '.sha256').read_text(encoding='utf-8').strip())
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    if (plan.get('schemaVersion') != 1 or plan.get('kind') != 'scientific.gmsh-volume-requalification-plan'
            or plan.get('profileId') != result.get('profileId')
            or (plan.get('mode'), tuple(plan.get('recipes', []))) != mode_for(plan.get('before', {}))):
        raise ValueError('Volume requalification plan identity is invalid.')
    expected = (['managed-qualification'] if plan['recipes'] else []) + [
        'broker-export', 'product-smoke', 'runtime-inventory', 'release', 'deployed-manifest']
    steps = result.get('steps', [])
    if not isinstance(steps, list) or any(not isinstance(step, dict) for step in steps):
        raise ValueError('Volume requalification steps or verdict are invalid.')
    ids = [step.get('id') for step in steps]
    if (ids != expected[:len(ids)]
            or result.get('verdict') not in ('passed', 'failed')
            or (result['verdict'] == 'passed' and (ids != expected or not result.get('after', {}).get('eligible')))
            or (result['verdict'] == 'failed' and not result.get('reason'))):
        raise ValueError('Volume requalification steps or verdict are invalid.')
    evidence = {'managed-qualification': ('logPath', 'logSha256'),
                'broker-export': ('manifestPath', 'manifestSha256'),
                'product-smoke': ('recordPath', 'recordSha256'),
                'runtime-inventory': ('inventoryPath', 'inventorySha256'),
                'release': ('reportPath', 'reportSha256')}
    for step in steps:
        if step.get('state') not in ('passed', 'qualified'):
            raise ValueError('A recorded requalification step did not pass.')
        if step['id'] in evidence:
            path_key, hash_key = evidence[step['id']]
            verified_file(step[path_key], step[hash_key])
    release = next((step for step in steps if step['id'] == 'release'), None)
    if release:
        report = verify_release(release['reportPath'], config_path if result['verdict'] == 'passed' else None)
        smoke = next(step for step in steps if step['id'] == 'product-smoke')
        if (report.get('verdict') != 'qualified' or report.get('productSmoke', {}).get('recordSha256')
                != smoke['recordSha256']):
            raise ValueError('Volume release is not linked to its product smoke.')
    if result['verdict'] == 'passed' and config_path:
        deployed = next(step for step in steps if step['id'] == 'deployed-manifest')
        configured = json.loads(Path(config_path).read_text(encoding='utf-8'))
        if Path(configured['manifest']).resolve() != Path(deployed['manifestPath']).resolve():
            raise ValueError('Volume deployment path changed after requalification.')
        verified_file(deployed['manifestPath'], deployed['manifestSha256'])
    return result


def run(args):
    config_path = Path(args.config).resolve(strict=True)
    config = json.loads(config_path.read_text(encoding='utf-8'))
    installed = Path(args.installed_root).resolve(strict=True)
    math3d = Path(args.math3d_root).resolve(strict=True)
    if (config.get('runtimeId') != 'gmsh-win-conda'
            or config.get('capabilityId') != 'mesh.generate3d'
            or Path(config.get('math3dRoot', '')).resolve() != math3d
            or Path(config.get('sourceRoot', str(ROOT))).resolve() != ROOT
            or Path(config.get('runtimeManifest', '')).resolve()
               != (installed / 'runtimes/gmsh-win-conda/runtime.json').resolve()):
        raise ValueError('Broker config does not match the fixed-cube volume deployment paths.')
    output = Path(args.output_root).resolve()
    output.mkdir(parents=True, exist_ok=True)
    deployed = Path(config['manifest']).resolve(strict=True)
    deployed_sha = sha(deployed)
    started = datetime.now(timezone.utc).isoformat()
    before = audit(installed, math3d, args.profile_id)
    mode, recipes = mode_for(before)
    plan = {'schemaVersion': 1, 'kind': 'scientific.gmsh-volume-requalification-plan',
            'createdAtUtc': started, 'profileId': args.profile_id, 'mode': mode,
            'recipes': recipes, 'before': before}
    plan_path = output / (uuid.uuid4().hex + '-plan.json')
    save(plan_path, plan)
    if args.command == 'plan':
        return {'plan': str(plan_path), 'mode': mode, 'recipes': recipes,
                'reason': before.get('exportReason')}
    execution = {'schemaVersion': 1, 'kind': 'scientific.gmsh-volume-requalification-run',
                 'planPath': str(plan_path), 'planSha256': sha(plan_path),
                 'startedAtUtc': started, 'profileId': args.profile_id, 'steps': []}
    result_path = output / (uuid.uuid4().hex + '-result.json')
    try:
        if recipes:
            require_desktop(args.cdp_url)
            env = os.environ.copy()
            env['DEVSHELL_CDP_URL'] = args.cdp_url
            env['DEVSHELL_GMSH_VOLUME_ONLY'] = '1' if mode == 'full' else ''
            env['DEVSHELL_GMSH_VOLUME_RESUME'] = '1' if mode == 'resume' else ''
            log = output / (uuid.uuid4().hex + '-managed.log')
            command(['node', str(ROOT / 'tests/scientific-gmsh-managed-ui-checks.mjs')],
                    timeout=1800, env=env, log=log)
            execution['steps'].append({'id': 'managed-qualification', 'state': 'passed',
                                       'logPath': str(log), 'logSha256': sha(log)})
        after = audit(installed, math3d, args.profile_id)
        execution['after'] = after
        if not after.get('eligible'):
            raise ValueError('The managed volume L0-L9 chain is still not current: '
                             + str(after.get('exportReason')))
        manifest = output / (uuid.uuid4().hex + '-candidate.json')
        command(['dotnet', str(DLL), 'export', str(ROOT), str(installed), str(math3d),
                 args.profile_id, str(manifest)], timeout=120)
        candidate_config = output / (uuid.uuid4().hex + '-candidate-config.json')
        save(candidate_config, {**config, 'manifest': str(manifest)})
        command([sys.executable, str(ROOT / 'tools/scientific-broker/broker.py'),
                 'verify', '--config', str(candidate_config)], timeout=30)
        execution['steps'].append({'id': 'broker-export', 'state': 'passed',
                                   'manifestPath': str(manifest), 'manifestSha256': sha(manifest)})
        smoke = json.loads(command([sys.executable, str(ROOT / 'tools/scientific-broker/gmsh_volume_smoke.py'),
                                    'run', '--config', str(candidate_config)], timeout=300).splitlines()[-1])
        execution['steps'].append({'id': 'product-smoke', 'state': smoke['verdict'],
                                   'recordPath': smoke['record'], 'recordSha256': sha(smoke['record'])})
        prefix_root = Path(config['prefix']).resolve().parent
        inventory = output / (uuid.uuid4().hex + '-runtime-inventory.json')
        command(['pwsh', '-NoProfile', '-File', str(ROOT / 'tools/Inspect-ScientificRuntimes.ps1'),
                 '-RuntimeRoot', str(prefix_root), '-OutputPath', str(inventory)],
                timeout=180)
        execution['steps'].append({'id': 'runtime-inventory', 'state': 'passed',
                                   'inventoryPath': str(inventory), 'inventorySha256': sha(inventory)})
        release = json.loads(command([sys.executable, str(ROOT / 'tools/scientific-broker/release_certification.py'),
                                      'certify', '--config', str(candidate_config), '--installed-root', str(installed),
                                      '--profile-id', args.profile_id, '--release-tag', args.release_tag,
                                      '--inventory', str(inventory),
                                      '--smoke-record', smoke['record'],
                                      '--output-root', str(output / 'releases')], timeout=300).splitlines()[-1])
        if release['verdict'] != 'qualified':
            raise ValueError('Volume release certification was blocked: ' + str(release.get('reasons')))
        execution['steps'].append({'id': 'release', 'state': release['verdict'],
                                   'reportPath': release['report'], 'reportSha256': sha(release['report'])})
        publish_manifest(manifest, deployed, deployed_sha, lambda: command([
            sys.executable, str(ROOT / 'tools/scientific-broker/release_certification.py'),
            'verify', '--config', str(config_path), '--report', release['report']], timeout=120))
        execution['steps'].append({'id': 'deployed-manifest', 'state': 'passed',
                                   'manifestPath': str(deployed), 'manifestSha256': sha(deployed)})
        execution['verdict'] = 'passed'
    except Exception as error:
        execution['verdict'] = 'failed'
        execution['reason'] = str(error)[:2000]
    execution['finishedAtUtc'] = datetime.now(timezone.utc).isoformat()
    save(result_path, execution)
    return {'result': str(result_path), 'verdict': execution['verdict'],
            'reason': execution.get('reason'), 'steps': execution['steps']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('plan', 'run', 'verify'))
    parser.add_argument('--config')
    parser.add_argument('--installed-root')
    parser.add_argument('--math3d-root')
    parser.add_argument('--profile-id', default='desktop-five')
    parser.add_argument('--output-root')
    parser.add_argument('--cdp-url')
    parser.add_argument('--release-tag', default='gmsh-fixed-cube-volume-v1')
    parser.add_argument('--record')
    options = parser.parse_args()
    if options.command == 'verify':
        if not options.record:
            parser.error('verify requires --record')
        verified = verify_result(options.record, options.config)
        value = {'result': str(Path(options.record).resolve()), 'verdict': verified['verdict']}
    else:
        if not all((options.config, options.installed_root, options.math3d_root, options.output_root)):
            parser.error('plan/run require config, installed-root, math3d-root and output-root')
        value = run(options)
    print(json.dumps(value, separators=(',', ':')))
    if options.command != 'verify' and value.get('verdict') == 'failed':
        raise SystemExit(1)
