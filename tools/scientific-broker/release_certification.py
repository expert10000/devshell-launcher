"""Fresh L0-L9 evidence gate and immutable scientific release manifest."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark import environment_fingerprint
from broker import Broker, sha
from telemetry import host_fingerprint

ROOT = Path(__file__).resolve().parents[2]
RELEASE_TAG = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def fresh_export(repo, installed_root, math3d_root, profile_id, output):
    completed = subprocess.run(['dotnet', 'run', '--project', str(repo / 'tools' / 'scientific-broker' / 'ScientificBroker.csproj'),
                                '--', 'export', str(repo), str(installed_root), str(math3d_root), profile_id, str(output)],
                               cwd=repo, capture_output=True, text=True, timeout=180)
    if completed.returncode:
        raise ValueError('Fresh desktop qualification export failed: ' + (completed.stderr or completed.stdout)[-1500:])
    if sha(output) != Path(str(output) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('Fresh desktop qualification export hash mismatch.')
    value = json.loads(output.read_text(encoding='utf-8'))
    if value.get('schemaVersion') != 1 or value.get('kind') != 'scientific.certified-capabilities':
        raise ValueError('Fresh desktop qualification contract mismatch.')
    return value


def assess(fresh, broker):
    reasons = []
    capabilities = fresh.get('certifiedCapabilities')
    if not isinstance(capabilities, list) or len(capabilities) != 1:
        reasons.append('Fresh desktop export has no single current L9 CGAL mesh capability.')
    else:
        current = capabilities[0]
        deployed = broker.capabilities[0] if broker.capabilities else None
        if deployed is None or current != deployed:
            reasons.append('Fresh desktop L0-L9 record, fingerprint or contract differs from deployed broker certification.')
        if current.get('runtimeId') != 'cgal-win-conda' or current.get('level') != 'L9':
            reasons.append('Release capability is not the qualified CGAL L9 path.')
        support = current.get('supportingRecords', [])
        if len(support) != 10 or any(item.get('level') != f'L{index}' for index, item in enumerate(support)):
            reasons.append('Fresh L0-L9 supporting records are incomplete.')
    return reasons


def certify(config_path, installed_root, profile_id, release_tag, output_root, exporter=fresh_export):
    if not RELEASE_TAG.fullmatch(release_tag):
        raise ValueError('Invalid release tag.')
    broker = Broker(config_path)
    if broker.math3d_root is None:
        raise ValueError('MATH3D consumer checkout is required.')
    repo = broker.source_root
    installed_root = Path(installed_root).resolve(strict=True)
    output_root = Path(output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    release_id = uuid.uuid4().hex
    directory = output_root / release_id
    directory.mkdir()
    with tempfile.TemporaryDirectory(prefix='scientific-release-') as scratch:
        fresh_path = Path(scratch) / 'fresh-capabilities.json'
        fresh = exporter(repo, installed_root, broker.math3d_root, profile_id, fresh_path)
        fresh_hash = sha(fresh_path)
        reasons = assess(fresh, broker)
        source_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
        report = {'schemaVersion': 1, 'kind': 'scientific.release-qualification-report',
                  'releaseId': release_id, 'releaseTag': release_tag,
                  'createdAtUtc': datetime.now(timezone.utc).isoformat(),
                  'sourceCommit': source_commit,
                  'verdict': 'qualified' if not reasons else 'blocked', 'reasons': reasons,
                  'freshManifestSha256': fresh_hash,
                  'deployedManifestSha256': sha(broker.paths['manifest']),
                  'capabilities': []}
        if not reasons:
            entry = fresh['certifiedCapabilities'][0]
            report['capabilities'].append({'runtimeId': entry['runtimeId'], 'capabilityId': entry['capabilityId'],
                                           'level': entry['level'], 'recordId': entry['recordId'],
                                           'suiteRevisionSha256': entry['suiteRevisionSha256'],
                                           'runFingerprintSha256': entry['runFingerprintSha256'],
                                           'environmentFingerprintSha256': environment_fingerprint(entry),
                                           'productContractSha256': entry['productContractSha256'],
                                           'supportingRecords': entry['supportingRecords']})
            manifest = {'schemaVersion': 1, 'kind': 'scientific.release-capabilities',
                        'releaseId': release_id, 'releaseTag': release_tag, 'sourceCommit': source_commit,
                        'freshManifestSha256': fresh_hash, 'deployedManifestSha256': sha(broker.paths['manifest']),
                        'hostFingerprintSha256': host_fingerprint(),
                        'capabilities': report['capabilities']}
            manifest['recordId'] = digest(manifest)
            manifest_path = directory / 'release-capabilities.json'
            with manifest_path.open('x', encoding='utf-8') as stream:
                json.dump(manifest, stream, separators=(',', ':'))
            Path(str(manifest_path) + '.sha256').write_text(sha(manifest_path), encoding='utf-8')
            report['releaseManifestSha256'] = sha(manifest_path)
            report['releaseManifestRecordId'] = manifest['recordId']
        # Keep the fresh export for both allowed and blocked decisions.
        (directory / 'fresh-capabilities.json').write_bytes(fresh_path.read_bytes())
        Path(str(directory / 'fresh-capabilities.json') + '.sha256').write_text(fresh_hash, encoding='utf-8')
        report_path = directory / 'qualification-report.json'
        with report_path.open('x', encoding='utf-8') as stream:
            json.dump(report, stream, separators=(',', ':'))
        Path(str(report_path) + '.sha256').write_text(sha(report_path), encoding='utf-8')
    return report_path, report


def verify_release(report_path, config_path=None):
    report_path = Path(report_path).resolve(strict=True)
    if sha(report_path) != Path(str(report_path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('Release qualification report hash mismatch.')
    report = json.loads(report_path.read_text(encoding='utf-8'))
    if report.get('schemaVersion') != 1 or report.get('kind') != 'scientific.release-qualification-report':
        raise ValueError('Release report contract mismatch.')
    fresh_path = report_path.parent / 'fresh-capabilities.json'
    if (sha(fresh_path) != report['freshManifestSha256']
            or sha(fresh_path) != Path(str(fresh_path) + '.sha256').read_text(encoding='utf-8').strip()):
        raise ValueError('Fresh desktop export hash mismatch.')
    if report['verdict'] == 'qualified':
        directory = report_path.parent
        manifest_path = directory / 'release-capabilities.json'
        if (sha(manifest_path) != report['releaseManifestSha256']
                or sha(manifest_path) != Path(str(manifest_path) + '.sha256').read_text(encoding='utf-8').strip()):
            raise ValueError('Release manifest or fresh evidence hash mismatch.')
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        identity = dict(manifest)
        record_id = identity.pop('recordId', None)
        if (record_id != digest(identity) or record_id != report['releaseManifestRecordId']
                or manifest['capabilities'] != report['capabilities']
                or manifest['freshManifestSha256'] != report['freshManifestSha256']):
            raise ValueError('Release manifest identity or current qualification mismatch.')
        if config_path and assess(json.loads(fresh_path.read_text(encoding='utf-8')), Broker(config_path)):
            raise ValueError('Release qualification no longer matches the deployed broker.')
    elif report['verdict'] != 'blocked' or (report_path.parent / 'release-capabilities.json').exists():
        raise ValueError('Blocked release has an invalid published manifest.')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['certify', 'verify'])
    parser.add_argument('--config')
    parser.add_argument('--installed-root')
    parser.add_argument('--profile-id')
    parser.add_argument('--release-tag')
    parser.add_argument('--output-root')
    parser.add_argument('--report')
    args = parser.parse_args()
    if args.command == 'certify':
        if not all((args.config, args.installed_root, args.profile_id, args.release_tag, args.output_root)):
            parser.error('certify requires config, installed-root, profile-id, release-tag and output-root.')
        path, report = certify(args.config, args.installed_root, args.profile_id, args.release_tag, args.output_root)
    else:
        if not args.report:
            parser.error('verify requires --report.')
        path, report = args.report, verify_release(args.report, args.config)
    print(json.dumps({'report': str(path), 'verdict': report['verdict'], 'reasons': report['reasons']}))
    if report['verdict'] != 'qualified':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
