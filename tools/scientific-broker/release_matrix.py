"""Evidence-linked release-to-release coverage and qualification comparison."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import uuid

from broker import sha
from release_certification import verify_release

PROVIDERS = ('cgal-win-conda', 'vtk-win-conda', 'vtkm', 'sage-wsl', 'gmsh-win-conda', 'math3d')


def age_state(inventory, release):
    try:
        observed = datetime.fromisoformat(inventory['generatedAt'].replace('Z', '+00:00'))
        published = datetime.fromisoformat(release['createdAtUtc'].replace('Z', '+00:00'))
        hours = (published - observed).total_seconds() / 3600
        return 'current' if 0 <= hours <= 24 else 'stale'
    except (KeyError, ValueError, TypeError):
        return 'unknown'


def rows(release, inventory, inventory_state):
    available = {item['id']: item for item in inventory.get('runtimes', [])}
    certified = {item['runtimeId']: item for item in release.get('capabilities', [])} if release['verdict'] == 'qualified' else {}
    result = []
    for provider in PROVIDERS:
        consumer = provider == 'math3d'
        evidence = certified.get('cgal-win-conda') if consumer else certified.get(provider)
        runtime = available.get(provider)
        qualified = bool(evidence and not consumer)
        contract_evidence = bool(consumer and evidence and evidence.get('productContractSha256'))
        support = evidence.get('supportingRecords', []) if qualified else []
        linked = evidence.get('supportingRecords', []) if contract_evidence else support
        result.append({'provider': provider,
                       'version': runtime.get('version') if runtime else None,
                       'availability': runtime.get('state', 'not-recorded') if runtime else 'not-recorded',
                       'inventoryState': inventory_state if runtime else 'unavailable',
                       'confidence': 'certified' if qualified else 'contract-evidence' if contract_evidence
                           else 'stale-inventory' if runtime and inventory_state != 'current'
                           else 'inventory-only' if runtime else 'no-evidence',
                       'qualifiedCapabilities': [evidence['capabilityId']] if qualified else [],
                       'coverage': {'currentLevels': len(support), 'expectedLevels': 10 if provider == 'cgal-win-conda' else None},
                       'recordId': evidence.get('recordId') if qualified or contract_evidence else None,
                       'sourceRunId': linked[-1]['runId'] if linked else None,
                       'productContractSha256': evidence.get('productContractSha256') if contract_evidence else None,
                       'reason': None if qualified else 'MATH3D product contract is linked, but no MATH3D release identity is recorded.'
                           if contract_evidence else 'Release report did not certify this provider and capability.'})
    return result


def save(root, name, value):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    path = root / (name + '.json')
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
    Path(str(path) + '.sha256').write_text(sha(path), encoding='utf-8')
    return path


def snapshot(release_path, inventory_path, output_root):
    release_path, inventory_path = Path(release_path).resolve(strict=True), Path(inventory_path).resolve(strict=True)
    release = verify_release(release_path)
    inventory = json.loads(inventory_path.read_text(encoding='utf-8'))
    if inventory.get('schemaVersion') != 1 or not isinstance(inventory.get('runtimes'), list):
        raise ValueError('Unsupported runtime inventory.')
    state = age_state(inventory, release)
    record = {'schemaVersion': 1, 'kind': 'scientific.release-matrix-snapshot',
              'matrixSourceSha256': sha(Path(__file__)),
              'releaseId': release['releaseId'], 'releaseTag': release['releaseTag'],
              'sourceCommit': release['sourceCommit'], 'releaseVerdict': release['verdict'],
              'releaseReasons': release['reasons'], 'releaseReportPath': str(release_path),
              'releaseReportSha256': sha(release_path), 'inventoryPath': str(inventory_path),
              'inventorySha256': sha(inventory_path), 'inventoryState': state,
              'rows': rows(release, inventory, state)}
    return save(output_root, uuid.uuid4().hex, record), record


def verify_snapshot(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text().strip():
        raise ValueError('Release snapshot hash mismatch.')
    record = json.loads(path.read_text(encoding='utf-8'))
    if (record.get('schemaVersion') != 1 or record.get('kind') != 'scientific.release-matrix-snapshot'
            or record.get('matrixSourceSha256') != sha(Path(__file__))
            or [item['provider'] for item in record['rows']] != list(PROVIDERS)):
        raise ValueError('Release snapshot contract changed.')
    release_path, inventory_path = Path(record['releaseReportPath']), Path(record['inventoryPath'])
    if sha(release_path) != record['releaseReportSha256'] or sha(inventory_path) != record['inventorySha256']:
        raise ValueError('Release snapshot source evidence changed.')
    release = verify_release(release_path)
    inventory = json.loads(inventory_path.read_text(encoding='utf-8'))
    state = age_state(inventory, release)
    if (record['releaseId'] != release['releaseId'] or record['releaseTag'] != release['releaseTag']
            or record['sourceCommit'] != release['sourceCommit'] or record['releaseVerdict'] != release['verdict']
            or record['releaseReasons'] != release['reasons'] or record['inventoryState'] != state
            or record['rows'] != rows(release, inventory, state)):
        raise ValueError('Release snapshot does not match verified source evidence.')
    return record


def compare(left, right):
    same_release = left['releaseTag'] == right['releaseTag'] or left['releaseId'] == right['releaseId']
    result = []
    for previous, current in zip(left['rows'], right['rows']):
        if previous['provider'] != current['provider']:
            raise ValueError('Release provider matrix differs.')
        first, second = previous['confidence'] == 'certified', current['confidence'] == 'certified'
        if same_release:
            verdict, confidence = 'inconclusive', 'same-release'
        elif first and second:
            verdict = 'qualified-unchanged' if previous['recordId'] == current['recordId'] else 'qualified-changed'
            confidence = 'certified'
        elif first and not second:
            verdict, confidence = 'qualification-not-current', 'verified-release'
        elif second and not first:
            verdict, confidence = 'newly-qualified', 'certified'
        else:
            verdict = 'version-changed-unqualified' if previous['version'] != current['version'] else 'inconclusive'
            observed = {previous['confidence'], current['confidence']}
            confidence = ('stale-inventory' if 'stale-inventory' in observed else
                          'inventory-only' if 'inventory-only' in observed else
                          'contract-evidence' if 'contract-evidence' in observed else 'no-evidence')
        result.append({'provider': previous['provider'], 'verdict': verdict, 'confidence': confidence,
                       'leftVersion': previous['version'], 'rightVersion': current['version'],
                       'leftCoverage': previous['coverage'], 'rightCoverage': current['coverage'],
                       'leftRecordId': previous['recordId'], 'rightRecordId': current['recordId'],
                       'leftSourceRunId': previous['sourceRunId'], 'rightSourceRunId': current['sourceRunId'],
                       'leftReleaseReportPath': left['releaseReportPath'],
                       'rightReleaseReportPath': right['releaseReportPath']})
    return {'sameRelease': same_release, 'rows': result,
            'verdict': 'inconclusive' if same_release or not any(item['confidence'] == 'certified' for item in result)
            else 'evidence-linked'}


def matrix(left_path, right_path, output_root):
    left, right = verify_snapshot(left_path), verify_snapshot(right_path)
    assessment = compare(left, right)
    record = {'schemaVersion': 1, 'kind': 'scientific.release-qualification-matrix',
              'matrixSourceSha256': sha(Path(__file__)),
              'createdAtUtc': datetime.now(timezone.utc).isoformat(),
              'leftSnapshotPath': str(Path(left_path).resolve()), 'leftSnapshotSha256': sha(left_path),
              'rightSnapshotPath': str(Path(right_path).resolve()), 'rightSnapshotSha256': sha(right_path),
              'leftReleaseTag': left['releaseTag'], 'rightReleaseTag': right['releaseTag'], **assessment}
    return save(output_root, uuid.uuid4().hex, record), record


def verify_matrix(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text().strip():
        raise ValueError('Release matrix hash mismatch.')
    record = json.loads(path.read_text(encoding='utf-8'))
    if (record.get('schemaVersion') != 1 or record.get('kind') != 'scientific.release-qualification-matrix'
            or record.get('matrixSourceSha256') != sha(Path(__file__))):
        raise ValueError('Release matrix contract changed.')
    left_path, right_path = Path(record['leftSnapshotPath']), Path(record['rightSnapshotPath'])
    if sha(left_path) != record['leftSnapshotSha256'] or sha(right_path) != record['rightSnapshotSha256']:
        raise ValueError('Release matrix snapshot changed.')
    left, right = verify_snapshot(left_path), verify_snapshot(right_path)
    assessment = compare(left, right)
    if any(record[key] != assessment[key] for key in assessment):
        raise ValueError('Release matrix verdict changed.')
    return record


def render_markdown(record):
    lines = [f"# Scientific release matrix: {record['leftReleaseTag']} -> {record['rightReleaseTag']}", '',
             f"Overall: **{record['verdict']}**. Verdicts describe qualification evidence, not a measured scientific regression.", '',
             '| Provider | Versions | Evidence coverage | Verdict | Confidence | Supporting evidence |',
             '|---|---|---|---|---|---|']
    for item in record['rows']:
        versions = f"{item['leftVersion'] or 'unknown'} -> {item['rightVersion'] or 'unknown'}"
        coverage = f"{item['leftCoverage']['currentLevels']} -> {item['rightCoverage']['currentLevels']} current levels"
        reports = f"[left report](<{Path(item['leftReleaseReportPath']).as_posix()}>) / [right report](<{Path(item['rightReleaseReportPath']).as_posix()}>)"
        records = ', '.join(value[:12] for value in (item['leftRecordId'], item['rightRecordId']) if value)
        support = reports + (f' / records {records}' if records else '')
        lines.append(f"| {item['provider']} | {versions} | {coverage} | {item['verdict']} | {item['confidence']} | {support} |")
    lines += ['', '## Evidence', '',
              f"- Left release report: `{record['rows'][0]['leftReleaseReportPath']}`",
              f"- Right release report: `{record['rows'][0]['rightReleaseReportPath']}`",
              f"- Left snapshot: `{record['leftSnapshotPath']}`",
              f"- Right snapshot: `{record['rightSnapshotPath']}`", '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['snapshot', 'compare', 'verify', 'render'])
    parser.add_argument('--release-report')
    parser.add_argument('--inventory')
    parser.add_argument('--left')
    parser.add_argument('--right')
    parser.add_argument('--record')
    parser.add_argument('--output-root')
    args = parser.parse_args()
    if args.command == 'snapshot':
        path, record = snapshot(args.release_report, args.inventory, args.output_root)
        output = {'record': str(path), 'releaseTag': record['releaseTag'], 'releaseVerdict': record['releaseVerdict']}
    elif args.command == 'compare':
        path, record = matrix(args.left, args.right, args.output_root)
        output = {'record': str(path), 'verdict': record['verdict'], 'sameRelease': record['sameRelease']}
    elif args.command == 'verify':
        record = verify_matrix(args.record)
        output = {'record': args.record, 'verdict': record['verdict'], 'rows': len(record['rows'])}
    else:
        print(render_markdown(verify_matrix(args.record)))
        return
    print(json.dumps(output))


if __name__ == '__main__':
    main()
