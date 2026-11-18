"""Require current six-capability support before sealing a typed desktop/broker journey.

This local release gate never promotes a candidate broker job by itself. It seals
the verified coexistence inputs for subsequent signed portable publication.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from six_capability_release import verify as verify_six_release
from typed_journey_broker import ARTIFACTS, TypedJourneyBroker, sha as hash_file
from verify_typed_product import verify as verify_product


HEX = re.compile(r'^[0-9a-f]{64}$')
RUN = re.compile(r'^[0-9a-f]{32}$')
DESKTOP_ARTIFACTS = {'gmsh/volume.msh', 'gmsh/results.json', 'boundary/boundary.obj',
    'boundary/results.json', 'vtk/analysis.vtp', 'vtk/preview.png', 'vtk/results.json',
    'scipy/measurement.json', 'converted.obj', 'conversion.json', 'typed-provenance.json',
    'product/vtk-mesh-document.json', 'product/vtk-mesh-resource.bin', 'product/read.m3dm',
    'product/product.json', 'cold-reopen.json', 'verification.json'}


def read(path, limit=2 * 1024 * 1024):
    path = Path(path).resolve(strict=True)
    if not path.is_file() or path.stat().st_size > limit:
        raise ValueError('Release evidence is missing or oversized.')
    return json.loads(path.read_text(encoding='utf-8'))


def checked_file(root, name, expected, size=None):
    if (not isinstance(name, str) or '\\' in name or name.startswith('/') or ':' in name
            or any(part in ('', '.', '..') for part in name.split('/'))
            or not HEX.fullmatch(expected or '')):
        raise ValueError('Release artifact path or hash is unsafe.')
    root = Path(root).resolve(strict=True)
    path = root / name
    if (not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root)
            or path.stat().st_size > 64 * 1024 * 1024
            or size is not None and path.stat().st_size != size or hash_file(path) != expected):
        raise ValueError('Release artifact changed: ' + name)
    return path


def desktop(path, consumer):
    path = Path(path).resolve(strict=True)
    result = read(path)
    root = path.parent
    if (not RUN.fullmatch(result.get('runId', '')) or result.get('recipeId') != 'scientific.typed-journey'
            or result.get('state') != 'succeeded' or result.get('validatedCapabilities') != []
            or result.get('typedJourney', {}).get('verdict') != 'passed'
            or result['typedJourney'].get('verification', {}).get('verdict') != 'verified-typed-product-relations'):
        raise ValueError('Desktop typed journey has no successful candidate record.')
    snapshot_sha = result.get('sourceSnapshotSha256')
    fingerprint_sha = result.get('runFingerprintSha256')
    snapshot = read(checked_file(root, 'source-snapshot.json', snapshot_sha))
    fingerprint = read(root / 'fingerprint.json')
    component_hash = hashlib.sha256(json.dumps(fingerprint['components'], separators=(',', ':'),
                                             ensure_ascii=True).encode()).hexdigest()
    if fingerprint.get('sha256') != fingerprint_sha or component_hash != fingerprint_sha:
        raise ValueError('Desktop run fingerprint changed.')
    devshell = snapshot['repositories']['devshell']
    math3d = snapshot['repositories']['math3d']
    if (devshell.get('state') != 'captured' or devshell.get('dirty') is not False
            or math3d.get('state') != 'captured' or math3d.get('dirty') is not False
            or math3d.get('commit') != consumer):
        raise ValueError('Desktop source or MATH3D snapshot is stale.')
    artifacts = result.get('artifacts', [])
    if (not isinstance(artifacts, list) or {item.get('path') for item in artifacts} != DESKTOP_ARTIFACTS
            or len(artifacts) != len(DESKTOP_ARTIFACTS)):
        raise ValueError('Desktop journey artifact inventory is incomplete.')
    for item in artifacts:
        checked_file(root, item['path'], item['sha256'], item['bytes'])
    provenance = read(root / 'typed-provenance.json', 65536)
    if (provenance.get('sourceCommit') != devshell['commit'] or provenance.get('math3dCommit') != consumer
            or hash_file(root / 'typed-provenance.json') != result['typedJourney'].get('provenanceSha256')):
        raise ValueError('Desktop typed provenance differs from saved source.')
    verified = verify_product(root / 'product', root / 'typed-provenance.json',
        root / 'scipy/measurement.json', root / 'vtk/analysis.vtp', root / 'converted.obj',
        root / 'cold-reopen.json')
    if verified != result['typedJourney']['verification']:
        raise ValueError('Desktop independent product verdict changed.')
    return {'runId': result['runId'], 'sourceRunId': result.get('sourceRunId'),
            'sourceCommit': devshell['commit'], 'consumerCommit': consumer,
            'resultSha256': hash_file(path), 'sourceSnapshotSha256': snapshot_sha,
            'documentId': verified['documentId'],
            'artifactHashes': {item['path']: item['sha256'] for item in artifacts}}


def broker(path, config_path, consumer):
    path = Path(path).resolve(strict=True)
    result = read(path)
    config = read(config_path)
    profile = TypedJourneyBroker(config)
    root = path.parent
    if (not RUN.fullmatch(result.get('jobId', '')) or result.get('state') != 'succeeded'
            or result.get('capabilityId') != 'scientific.typed-journey-candidate'
            or result.get('consumerCommit') != consumer
            or result.get('sourceRunId') != profile.case['sourceRunId']
            or result.get('verification', {}).get('verdict') != 'verified-typed-product-relations'):
        raise ValueError('Broker typed journey has no successful candidate record.')
    snapshot = read(checked_file(root, 'source-snapshot.json', result.get('sourceSnapshotSha256')))
    source = snapshot['repositories']['devshell']
    math3d = snapshot['repositories']['math3d']
    if (source.get('dirty') is not False or source.get('commit') != result.get('sourceCommit')
            or math3d.get('dirty') is not False or math3d.get('commit') != consumer):
        raise ValueError('Broker source snapshot changed.')
    if (not isinstance(result.get('artifacts'), list) or len(result['artifacts']) != len(ARTIFACTS)
            or {item.get('name') for item in result['artifacts']} != set(ARTIFACTS)):
        raise ValueError('Broker journey artifact inventory is incomplete.')
    for item in result['artifacts']:
        if item.get('path') != ARTIFACTS[item['name']]:
            raise ValueError('Broker transport alias changed.')
        checked_file(root, item['path'], item['sha256'], item['bytes'])
    verified = verify_product(root / 'product', root / 'typed-provenance.json',
        root / 'scipy/measurement.json', root / 'vtk/analysis.vtp', root / 'converted.obj',
        root / 'cold-reopen.json')
    if verified != result['verification']:
        raise ValueError('Broker independent product verdict changed.')
    if (result['sourceCommit'] != profile.verify()[3]['commit']
            or hash_file(Path(config['caseProfile']['resultPath'])) != config['caseProfile']['resultSha256']):
        raise ValueError('Broker case profile or source drifted.')
    return {'jobId': result['jobId'], 'sourceRunId': result['sourceRunId'],
            'sourceCommit': result['sourceCommit'], 'consumerCommit': consumer,
            'resultSha256': hash_file(path), 'sourceSnapshotSha256': result['sourceSnapshotSha256'],
            'documentId': verified['documentId'],
            'artifactHashes': {item['name']: item['sha256'] for item in result['artifacts']},
            'profileSha256': hash_file(config_path)}


def build(release_path, desktop_path, broker_path, config_path):
    release_path = Path(release_path).resolve(strict=True)
    sidecar = Path(str(release_path) + '.sha256')
    if not sidecar.is_file() or sidecar.read_text(encoding='utf-8').strip() != hash_file(release_path):
        raise ValueError('Six-capability release seal changed.')
    declared = read(release_path)
    source = declared['sourceCommit']
    consumer = declared['math3dIdentity']['commit']
    desktop_record = desktop(desktop_path, consumer)
    broker_record = broker(broker_path, config_path, consumer)
    if (desktop_record['sourceCommit'] != source or broker_record['sourceCommit'] != source
            or desktop_record['sourceRunId'] != broker_record['sourceRunId']):
        raise ValueError('Six-capability release is historical or desktop and broker Boolean runs differ.')
    release = verify_six_release(release_path)
    if release['sourceCommit'] != source or release['math3dIdentity']['commit'] != consumer:
        raise ValueError('Verified six-capability release identity changed.')
    return {'schemaVersion': 1, 'kind': 'scientific.typed-journey-release-candidate',
            'state': 'source-and-consumer-current', 'sourceCommit': source, 'math3dCommit': consumer,
            'sixReleaseSha256': hash_file(release_path), 'desktop': desktop_record, 'broker': broker_record}


def save(release_path, desktop_path, broker_path, config_path, output):
    record = build(release_path, desktop_path, broker_path, config_path)
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, separators=(',', ':')), encoding='utf-8')
    Path(str(output) + '.sha256').write_text(hash_file(output), encoding='utf-8')
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('build', 'verify'))
    parser.add_argument('--release', required=True)
    parser.add_argument('--desktop', required=True)
    parser.add_argument('--broker', required=True)
    parser.add_argument('--broker-config', required=True)
    parser.add_argument('--output')
    parser.add_argument('--record')
    options = parser.parse_args()
    if options.command == 'build':
        if not options.output:
            parser.error('build requires --output')
        result = save(options.release, options.desktop, options.broker, options.broker_config, options.output)
    else:
        if not options.record or hash_file(options.record) != Path(str(options.record) + '.sha256').read_text().strip():
            raise ValueError('Typed journey release record seal changed.')
        result = build(options.release, options.desktop, options.broker, options.broker_config)
        if read(options.record) != result:
            raise ValueError('Typed journey release dependencies changed.')
    print(json.dumps({'verdict': result['state'], 'sourceCommit': result['sourceCommit'],
                      'math3dCommit': result['math3dCommit']}))
