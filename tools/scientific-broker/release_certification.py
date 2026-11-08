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
from gmsh_volume_smoke import verify as verify_volume_smoke
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
    matching = [item for item in capabilities if item.get('runtimeId') == broker.runtime_id
                and item.get('capabilityId') == broker.capability_id] if isinstance(capabilities, list) else []
    if len(matching) != 1:
        reasons.append('Fresh desktop export has no single current L9 capability for ' + broker.runtime_id + '.')
    else:
        current = matching[0]
        deployed = broker.capabilities[0] if broker.capabilities else None
        if deployed is None or current != deployed:
            reasons.append('Fresh desktop L0-L9 record, fingerprint or contract differs from deployed broker certification.')
        if current.get('capabilityId') != broker.capability_id or current.get('level') != 'L9':
            reasons.append('Release capability is outside the qualified L9 broker profile.')
        support = current.get('supportingRecords', [])
        if len(support) != 10 or any(item.get('level') != f'L{index}' for index, item in enumerate(support)):
            reasons.append('Fresh L0-L9 supporting records are incomplete.')
    return reasons


def inventory_state(inventory, release_time):
    try:
        captured = datetime.fromisoformat(inventory['generatedAt'].replace('Z', '+00:00'))
        age = (release_time - captured).total_seconds()
        return 'current' if 0 <= age <= 24 * 3600 else 'stale'
    except (KeyError, TypeError, ValueError):
        return 'unknown'


def load_inventory(repo, source=None):
    path = Path(source).resolve(strict=True) if source is not None else repo / '.scientific/runtime-report.json'
    content = path.read_bytes()
    if len(content) > 1048576:
        raise ValueError('Runtime inventory exceeds the release budget.')
    inventory = json.loads(content.decode('utf-8'))
    if inventory.get('schemaVersion') != 1 or not isinstance(inventory.get('runtimes'), list):
        raise ValueError('Unsupported release runtime inventory.')
    return content, inventory


def volume_smoke_link(config_path, record_path):
    if record_path is None:
        raise ValueError('A verified broker/MATH3D smoke record is required for volume release.')
    path = Path(record_path).resolve(strict=True)
    record = verify_volume_smoke(path, config_path)
    return {'recordPath': str(path), 'recordSha256': sha(path),
            'sourceJobId': record['sourceJobId'],
            'certificationRecordId': record['certificationRecordId']}


def gate_verdicts(fresh, runtime_id='cgal-win-conda', capability_id=None):
    capabilities = fresh.get('certifiedCapabilities', [])
    matching = [item for item in capabilities if item.get('runtimeId') == runtime_id
                and (capability_id is None or item.get('capabilityId') == capability_id)]
    support = matching[0].get('supportingRecords', []) if len(matching) == 1 else []
    complete = len(support) == 10 and all(item.get('level') == f'L{index}' for index, item in enumerate(support))
    return [dict(level=f'L{index}', state='current', capabilityId=support[index]['capabilityId'],
                 runId=support[index]['runId'], recordId=support[index]['recordId']) if complete
            else dict(level=f'L{index}', state='blocked',
                      reason='Fresh exporter supplied no complete current L0–L9 chain for this level.')
            for index in range(10)]


def certify(config_path, installed_root, profile_id, release_tag, output_root,
            exporter=fresh_export, inventory_source=None, smoke_record=None):
    if not RELEASE_TAG.fullmatch(release_tag):
        raise ValueError('Invalid release tag.')
    broker = Broker(config_path)
    if broker.math3d_root is None:
        raise ValueError('MATH3D consumer checkout is required.')
    smoke = volume_smoke_link(config_path, smoke_record) if broker.volume else None
    repo = broker.source_root
    installed_root = Path(installed_root).resolve(strict=True)
    output_root = Path(output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    release_id = uuid.uuid4().hex
    directory = output_root / release_id
    directory.mkdir()
    inventory_bytes, inventory = load_inventory(repo, inventory_source)
    inventory_path = directory / 'runtime-inventory.json'
    inventory_path.write_bytes(inventory_bytes)
    with tempfile.TemporaryDirectory(prefix='scientific-release-') as scratch:
        fresh_path = Path(scratch) / 'fresh-capabilities.json'
        fresh = exporter(repo, installed_root, broker.math3d_root, profile_id, fresh_path)
        fresh_hash = sha(fresh_path)
        reasons = assess(fresh, broker)
        created_at = datetime.now(timezone.utc)
        state = inventory_state(inventory, created_at)
        if state != 'current':
            reasons.append('Runtime inventory is ' + state + '; capture it within 24 hours before certification.')
        source_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
        report = {'schemaVersion': 1, 'kind': 'scientific.release-qualification-report',
                  'releaseId': release_id, 'releaseTag': release_tag,
                  'runtimeId': broker.runtime_id, 'capabilityId': broker.capability_id,
                  'createdAtUtc': created_at.isoformat(),
                  'sourceCommit': source_commit,
                  'verdict': 'qualified' if not reasons else 'blocked', 'reasons': reasons,
                  'gateVerdicts': gate_verdicts(fresh, broker.runtime_id, broker.capability_id), 'agent': {'kind': 'local', 'hostFingerprintSha256': host_fingerprint()},
                  'inventoryPath': str(inventory_path), 'inventorySha256': sha(inventory_path),
                  'inventoryState': state, 'inventoryCapturedAtUtc': inventory['generatedAt'],
                  'freshManifestSha256': fresh_hash,
                  'deployedManifestSha256': sha(broker.paths['manifest']),
                  'capabilities': []}
        if smoke is not None:
            report['productSmoke'] = smoke
        if not reasons:
            entry = next(item for item in fresh['certifiedCapabilities'] if item['runtimeId'] == broker.runtime_id
                         and item['capabilityId'] == broker.capability_id)
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
                        'inventorySha256': report['inventorySha256'],
                        'hostFingerprintSha256': host_fingerprint(),
                        'capabilities': report['capabilities']}
            if smoke is not None:
                manifest['productSmoke'] = smoke
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
    smoke = report.get('productSmoke')
    if smoke is not None:
        path = Path(smoke['recordPath']).resolve(strict=True)
        if (sha(path) != smoke.get('recordSha256')
                or Path(str(path) + '.sha256').read_text(encoding='utf-8').strip() != smoke['recordSha256']):
            raise ValueError('Volume product smoke record hash mismatch.')
        record = json.loads(path.read_text(encoding='utf-8'))
        if (record.get('sourceJobId') != smoke.get('sourceJobId')
                or record.get('certificationRecordId') != smoke.get('certificationRecordId')):
            raise ValueError('Volume product smoke identity mismatch.')
        if config_path:
            verify_volume_smoke(path, config_path)
    fresh_path = report_path.parent / 'fresh-capabilities.json'
    if 'inventoryPath' in report:
        inventory_path = report_path.parent / 'runtime-inventory.json'
        if (report['inventoryPath'] != str(inventory_path)
                or sha(inventory_path) != report.get('inventorySha256')):
            raise ValueError('Release runtime inventory hash mismatch.')
        inventory = json.loads(inventory_path.read_text(encoding='utf-8'))
        release_time = datetime.fromisoformat(report['createdAtUtc'])
        if (report.get('inventoryCapturedAtUtc') != inventory.get('generatedAt')
                or report.get('inventoryState') != inventory_state(inventory, release_time)
                or len(report.get('gateVerdicts', [])) != 10
                or report['gateVerdicts'] != gate_verdicts(json.loads(fresh_path.read_text(encoding='utf-8')),
                                                           report.get('runtimeId', 'cgal-win-conda'),
                                                           report.get('capabilityId') or next(
                                                               (item.get('capabilityId') for item in report.get('capabilities', [])),
                                                               None))):
            raise ValueError('Release inventory age or gate verdicts changed.')
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
                or manifest.get('productSmoke') != smoke
                or manifest['freshManifestSha256'] != report['freshManifestSha256']
                or manifest['sourceCommit'] != report['sourceCommit']
                or ('inventoryPath' in report and (report['inventoryState'] != 'current'
                    or manifest.get('inventorySha256') != report['inventorySha256']
                    or manifest.get('hostFingerprintSha256') != report['agent']['hostFingerprintSha256']))):
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
    parser.add_argument('--inventory')
    parser.add_argument('--smoke-record')
    parser.add_argument('--report')
    args = parser.parse_args()
    if args.command == 'certify':
        if not all((args.config, args.installed_root, args.profile_id, args.release_tag, args.output_root)):
            parser.error('certify requires config, installed-root, profile-id, release-tag and output-root.')
        path, report = certify(args.config, args.installed_root, args.profile_id, args.release_tag,
                               args.output_root, inventory_source=args.inventory, smoke_record=args.smoke_record)
    else:
        if not args.report:
            parser.error('verify requires --report.')
        path, report = args.report, verify_release(args.report, args.config)
    print(json.dumps({'report': str(path), 'verdict': report['verdict'], 'reasons': report['reasons']}))
    if report['verdict'] != 'qualified':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
