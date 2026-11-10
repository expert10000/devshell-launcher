"""Verify CGAL repair and Gmsh volume releases from one source checkout."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

from broker import Broker, sha
from release_certification import assess, fresh_export, verify_release

EXPECTED = {('cgal-win-conda', 'mesh.repair'), ('gmsh-win-conda', 'mesh.generate3d')}


def checked(record):
    if record.get('verifierSha256') != sha(Path(__file__)):
        raise ValueError('Combined release verifier changed.')
    repo = Path(record['repo']).resolve(strict=True)
    installed = Path(record['installedRoot']).resolve(strict=True)
    math3d = Path(record['math3dRoot']).resolve(strict=True)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    if commit != record['sourceCommit']:
        raise ValueError('Combined release source commit changed.')
    configs = record['profiles']
    if set(configs) != {'repair', 'volume'}:
        raise ValueError('Both release profiles are required.')
    with tempfile.TemporaryDirectory() as temporary:
        fresh = fresh_export(repo, installed, math3d, record['profileId'],
                             Path(temporary) / 'fresh-manifest.json')
    entries = {(item['runtimeId'], item['capabilityId']): item
               for item in fresh['certifiedCapabilities']}
    if set(entries) != EXPECTED or len(fresh['certifiedCapabilities']) != 2:
        raise ValueError('Fresh export must contain exactly repair and fixed-cube volume L9.')
    results = {}
    for name, identity in (('repair', ('cgal-win-conda', 'mesh.repair')),
                           ('volume', ('gmsh-win-conda', 'mesh.generate3d'))):
        item = configs[name]
        config, report = Path(item['config']).resolve(strict=True), Path(item['report']).resolve(strict=True)
        if sha(config) != item['configSha256'] or sha(report) != item['reportSha256']:
            raise ValueError(name + ' release input changed.')
        broker = Broker(config)
        verified = verify_release(report, config)
        if (verified['verdict'] != 'qualified' or verified['sourceCommit'] != commit
                or (broker.runtime_id, broker.capability_id) != identity
                or assess(fresh, broker)):
            raise ValueError(name + ' release differs from the current combined export.')
        entry = entries[identity]
        if (entry['recordId'] != item['recordId'] or len(entry['supportingRecords']) != 10
                or any(support['level'] != f'L{index}'
                       for index, support in enumerate(entry['supportingRecords']))):
            raise ValueError(name + ' L0-L9 support changed.')
        results[name] = entry['recordId']
    return results


def certify(args):
    repo = Path(args.repo).resolve(strict=True)
    record = {'schemaVersion': 1, 'kind': 'scientific.combined-repair-volume-release',
              'verifierSha256': sha(Path(__file__)),
              'repo': str(repo), 'installedRoot': str(Path(args.installed_root).resolve(strict=True)),
              'math3dRoot': str(Path(args.math3d_root).resolve(strict=True)),
              'profileId': args.profile_id,
              'sourceCommit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
              'profiles': {}}
    for name in ('repair', 'volume'):
        config, report = Path(getattr(args, name + '_config')).resolve(strict=True), \
                         Path(getattr(args, name + '_report')).resolve(strict=True)
        value = json.loads(report.read_text(encoding='utf-8'))
        record['profiles'][name] = {'config': str(config), 'configSha256': sha(config),
                                    'report': str(report), 'reportSha256': sha(report),
                                    'recordId': value['capabilities'][0]['recordId']}
    checked(record)
    output = Path(args.output).resolve()
    with output.open('x', encoding='utf-8') as stream:
        json.dump(record, stream, separators=(',', ':'))
    Path(str(output) + '.sha256').write_text(sha(output), encoding='utf-8')
    return output, record


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('Combined release record hash changed.')
    record = json.loads(path.read_text(encoding='utf-8'))
    if record.get('schemaVersion') != 1 or record.get('kind') != 'scientific.combined-repair-volume-release':
        raise ValueError('Combined release record type changed.')
    checked(record)
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('certify', 'verify'))
    for name in ('repo', 'installed-root', 'math3d-root', 'repair-config', 'repair-report',
                 'volume-config', 'volume-report', 'profile-id', 'output', 'record'):
        parser.add_argument('--' + name)
    args = parser.parse_args()
    if args.command == 'certify':
        if any(getattr(args, name) is None for name in ('repo', 'installed_root', 'math3d_root',
                'repair_config', 'repair_report', 'volume_config', 'volume_report', 'output')):
            parser.error('certify requires both profiles, reports, roots and output')
        args.profile_id = args.profile_id or 'desktop-five'
        path, value = certify(args)
    else:
        if not args.record:
            parser.error('verify requires --record')
        path, value = args.record, verify(args.record)
    print(json.dumps({'record': str(path), 'verdict': 'qualified',
                      'sourceCommit': value['sourceCommit']}))
