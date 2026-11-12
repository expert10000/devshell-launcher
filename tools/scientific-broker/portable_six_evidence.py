"""Export and independently verify path-redacted six-capability release evidence."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import struct
import zipfile
import zlib

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

from six_capability_release import TARGETS, verify as verify_live
from comparable_inspect import verify as verify_shared
from six_capability_report import verify as verify_report
from advisor import verify_shared_advice
from math3d_inspect_product import verify as verify_product
from class_inspect_qualification import verify as verify_classes

PATH = re.compile(r'(?i)(?:[a-z]:[\\/]|\\\\)[^\s\"\'<>;,]*')
HASH = re.compile(r'^[0-9a-f]{64}$')
RUN = re.compile(r'^[0-9a-f]{32}$')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def compact(value):
    return json.dumps(value, separators=(',', ':'), ensure_ascii=True).encode('utf-8')


def redact(value):
    if isinstance(value, dict):
        return {redact(key): redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return PATH.sub(lambda match: '<local-path:' + digest(match.group().encode('utf-8'))[:16] + '>', value)
    return value


def path_free(data):
    if PATH.search(data.decode('utf-8')):
        raise ValueError('Portable evidence contains a local absolute path.')


def portable_artifact(path, source):
    """Accept only reviewed data formats; strip local paths and PNG metadata."""
    suffix = Path(path).suffix.lower()
    if len(source) > 64 * 1024 * 1024:
        raise ValueError('Supporting artifact exceeds the portable size limit.')
    if suffix == '.json':
        return compact(redact(json.loads(source))), 'redacted-json'
    if suffix in ('.txt', '.log', '.obj', '.msh', '.vtp'):
        return redact(source.decode('utf-8')).encode('utf-8'), 'redacted-utf8'
    magic = {'.bin': b'MD3M', '.m3dm': b'M3DM', '.m3dt': b'M3DT'}
    if suffix in magic:
        if len(source) < 16 or not source.startswith(magic[suffix]):
            raise ValueError('Native mesh payload has an invalid header.')
        if suffix == '.bin':
            if len(source) < 24:
                raise ValueError('Native mesh payload has an invalid header.')
            _, version, positions, indices, normals, flags = struct.unpack_from('<4sIIIII', source)
            if (version != 1 or flags != 0 or positions % 3 or indices % 3 or normals != positions
                    or len(source) != 24 + 4 * (positions + indices + normals)):
                raise ValueError('Native mesh payload length changed.')
        elif suffix == '.m3dm':
            if len(source) < 32:
                raise ValueError('Native mesh payload has an invalid header.')
            _, version, header, vertices, triangles, positions, indices, total, flags = \
                struct.unpack_from('<4sHHIIIIII', source)
            if (version != 1 or header != 32 or flags != 0 or positions != vertices * 12
                    or indices != triangles * 12 or total != len(source) or total != 32 + positions + indices):
                raise ValueError('Native mesh payload length changed.')
        else:
            _, version, vertices, cells = struct.unpack_from('<4sIII', source)
            if version != 1 or len(source) != 16 + vertices * 24 + cells * 16:
                raise ValueError('Tetrahedral mesh payload length changed.')
        return source, 'native-mesh-v1'
    if suffix == '.png':
        if not source.startswith(b'\x89PNG\r\n\x1a\n'):
            raise ValueError('Invalid PNG payload.')
        output = bytearray(source[:8])
        offset, seen = 8, []
        while offset + 12 <= len(source):
            length = int.from_bytes(source[offset:offset + 4], 'big')
            end = offset + 12 + length
            if end > len(source) or length > 64 * 1024 * 1024:
                raise ValueError('Truncated PNG payload.')
            kind = source[offset + 4:offset + 8]
            payload = source[offset + 8:offset + 8 + length]
            if zlib.crc32(kind + payload) & 0xffffffff != int.from_bytes(source[end - 4:end], 'big'):
                raise ValueError('PNG checksum changed.')
            if kind in (b'IHDR', b'PLTE', b'IDAT', b'IEND', b'tRNS'):
                output.extend(source[offset:end])
                seen.append(kind)
            elif kind[0] & 32 == 0:
                raise ValueError('Unknown critical PNG chunk.')
            offset = end
            if kind == b'IEND':
                break
        if offset != len(source) or not seen or seen[0] != b'IHDR' or b'IDAT' not in seen or seen[-1] != b'IEND':
            raise ValueError('Invalid PNG structure.')
        return bytes(output), 'png-metadata-stripped'
    raise ValueError('Supporting artifact format is outside the portable policy: ' + suffix)


def signing_identity(private_key_path, key_id):
    key = serialization.load_pem_private_key(Path(private_key_path).read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey) or not re.fullmatch(r'[a-z0-9][a-z0-9.-]{2,63}', key_id):
        raise ValueError('Expected an Ed25519 signing key and stable key ID.')
    return key


def verify_signature(body, signature, trust_store):
    if not trust_store:
        raise ValueError('A trusted public-key store is required for signed evidence.')
    trust = json.loads(Path(trust_store).read_text(encoding='utf-8'))
    if trust.get('schemaVersion') != 1 or signature.get('algorithm') != 'Ed25519':
        raise ValueError('Unsupported evidence trust policy.')
    keys = [item for item in trust.get('keys', []) if item.get('keyId') == signature.get('keyId')]
    if len(keys) != 1:
        raise ValueError('Evidence signing key is not trusted.')
    key = keys[0]
    signed = datetime.fromisoformat(signature['signedAtUtc'])
    now = datetime.now(timezone.utc)
    if signed > now or signed < datetime.fromisoformat(key['validFromUtc']) \
            or signed >= datetime.fromisoformat(key['validUntilUtc']):
        raise ValueError('Evidence signing key was not valid at signing time.')
    if key.get('revokedAtUtc') and now >= datetime.fromisoformat(key['revokedAtUtc']):
        raise ValueError('Evidence signing key was revoked.')
    try:
        Ed25519PublicKey.from_public_bytes(base64.b64decode(key['publicKeyBase64'], validate=True)).verify(
            base64.b64decode(signature['signatureBase64'], validate=True), body)
    except (InvalidSignature, ValueError, TypeError) as error:
        raise ValueError('Evidence manifest signature changed.') from error


def add(files, name, data, *, binary=False):
    if name in files or PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts:
        raise ValueError('Unsafe or duplicate bundle path.')
    if not binary:
        path_free(data)
    files[name] = data


def json_file(files, name, path, *, redacted=True):
    source = Path(path).read_bytes()
    value = json.loads(source)
    data = compact(redact(value)) if redacted else source
    add(files, name, data)
    return {'path': name, 'sha256': digest(data), 'sourceSha256': digest(source), 'bytes': len(data)}


def find_runs(repo, needed):
    found = {}
    for directory in (repo / '.scientific/runs').iterdir():
        result = directory / 'results.json'
        if not directory.is_dir() or not result.is_file():
            continue
        try:
            run_id = json.loads(result.read_text(encoding='utf-8'))['runId']
        except (KeyError, ValueError):
            continue
        if run_id in needed:
            if run_id in found:
                raise ValueError('Duplicate support run ID.')
            found[run_id] = directory
    if set(found) != set(needed):
        raise ValueError('A supporting managed run is unavailable.')
    return found


def export(record_path, output, signing_key, key_id, shared_path, report_path,
           advisor_path, product_path, class_path=None):
    record_path = Path(record_path).resolve(strict=True)
    live = verify_live(record_path)
    repo = Path(live['repo']).resolve(strict=True)
    release_root = record_path.parent
    certified = release_root / 'certified.json'
    if digest(certified.read_bytes()) != Path(str(certified) + '.sha256').read_text().strip():
        raise ValueError('Certified capability export changed.')
    source = json.loads(certified.read_text(encoding='utf-8'))
    entries = {(item['runtimeId'], item['capabilityId']): item for item in source['certifiedCapabilities']}
    if set(entries) != set(TARGETS.values()):
        raise ValueError('Six certified capability entries are required.')
    shared = verify_shared(shared_path)
    report = verify_report(report_path)
    advice = verify_shared_advice(advisor_path)
    product = json.loads(Path(product_path).read_text(encoding='utf-8'))
    verify_product(product_path, shared_path, product['inputPath'])
    if (shared['releaseRecordSha256'] != digest(record_path.read_bytes())
            or report['releaseRecordSha256'] != digest(record_path.read_bytes())
            or advice['scopeRecordSha256'] != digest(Path(shared_path).read_bytes())
            or product['scopeRecordSha256'] != digest(Path(shared_path).read_bytes())):
        raise ValueError('Six-capability evidence sources are not linked.')
    classes = verify_classes(class_path) if class_path else None
    if classes and (classes['releaseRecordSha256'] != digest(record_path.read_bytes())
                    or classes['sourceCommit'] != live['sourceCommit']):
        raise ValueError('Bounded class evidence belongs to another release.')
    files, index, payloads = {}, [], []
    index.append(json_file(files, 'release/coexistence.json', record_path))
    index.append(json_file(files, 'release/certified.json', certified))
    support = {item['runId'] for entry in entries.values() for item in entry['supportingRecords']}
    runs = find_runs(repo, support)
    for name, identity in TARGETS.items():
        profile = live['profiles'][name]
        index.append(json_file(files, f'profiles/{name}/config.json', profile['config']))
        index.append(json_file(files, f'profiles/{name}/smoke.json', profile['smoke']))
        index.append(json_file(files, f'profiles/{name}/math3d-link.json', profile['math3dLink']))
    evidence_paths = {'shared': shared_path, 'report': report_path,
                      'matrix': Path(report_path).parent / 'matrix.json',
                      'comparison': Path(report_path).parent / 'comparison.json',
                      'advisor': advisor_path, 'product': product_path}
    if classes:
        evidence_paths.update({'classes': class_path,
                               'classPolicy': repo / 'schemas/scientific-mesh-inspect-classes.v1.json',
                               'rankingPolicy': repo / 'schemas/scientific-inspect-ranking.v1.json'})
    evidence_hashes = {}
    for name, source_path in evidence_paths.items():
        entry = json_file(files, f'evidence/{name}.json', source_path)
        index.append(entry)
        evidence_hashes[name] = entry['sourceSha256']
    benchmark_payloads = []

    def benchmark_file(tier, provider, sample, kind, source_path, source_hash):
        data, format_policy = portable_artifact(source_path, Path(source_path).read_bytes())
        if format_policy.startswith('redacted'):
            path_free(data)
        object_path = 'objects/sha256/' + digest(data)
        if object_path not in files:
            add(files, object_path, data, binary=not format_policy.startswith('redacted'))
            index.append({'path': object_path, 'sha256': digest(data),
                          'sourceSha256': source_hash, 'bytes': len(data),
                          'formatPolicy': format_policy})
        benchmark_payloads.append({'tier': tier, 'provider': provider, 'sample': sample,
                                   'kind': kind, 'sourceSha256': source_hash,
                                   'object': object_path, 'formatPolicy': format_policy})

    for tier, evidence in shared['tiers'].items():
        for provider in ('cgal', 'vtk'):
            gate = evidence['brokerJobs'][provider]
            for kind in ('result', 'promotion'):
                benchmark_file(tier, provider, 'gate', kind, gate[kind + 'Path'], gate[kind + 'Sha256'])
            samples = [('warmup', evidence['warmups'][provider])]
            samples += [(str(index), item) for index, item in
                        enumerate(evidence['measurements'][provider]['runs'])]
            for sample, item in samples:
                for kind in ('request', 'result', 'brokerResult', 'telemetry', 'artifact'):
                    benchmark_file(tier, provider, sample, kind,
                                   item[kind + 'Path'], item[kind + 'Sha256'])
    class_payloads = []
    if classes:
        for class_id, evidence in classes['classes'].items():
            for provider in ('cgal', 'vtk'):
                for sample, run in enumerate(evidence['runs'][provider]):
                    for kind, item in run['files'].items():
                        data, format_policy = portable_artifact(kind, Path(item['path']).read_bytes())
                        object_path = 'objects/sha256/' + digest(data)
                        if object_path not in files:
                            add(files, object_path, data, binary=not format_policy.startswith('redacted'))
                            index.append({'path': object_path, 'sha256': digest(data),
                                          'sourceSha256': item['sha256'], 'bytes': len(data),
                                          'formatPolicy': format_policy})
                        class_payloads.append({'classId': class_id, 'provider': provider,
                                               'sample': sample, 'kind': kind,
                                               'sourceSha256': item['sha256'], 'object': object_path,
                                               'formatPolicy': format_policy})
    product_payloads = []
    for name, source_hash in product['productFiles'].items():
        source_path = Path(product_path).parent / 'product' / name
        data, format_policy = portable_artifact(name, source_path.read_bytes())
        object_path = 'objects/sha256/' + digest(data)
        if object_path not in files:
            add(files, object_path, data, binary=not format_policy.startswith('redacted'))
            index.append({'path': object_path, 'sha256': digest(data),
                          'sourceSha256': source_hash, 'bytes': len(data),
                          'formatPolicy': format_policy})
        product_payloads.append({'name': name, 'sourceSha256': source_hash,
                                 'object': object_path, 'formatPolicy': format_policy})
    for run_id, directory in sorted(runs.items()):
        if not RUN.fullmatch(run_id):
            raise ValueError('Invalid support run ID.')
        result = json.loads((directory / 'results.json').read_text(encoding='utf-8'))
        if result.get('runId') != run_id or result.get('state') != 'succeeded':
            raise ValueError('Supporting run changed.')
        for filename in ('results.json', 'qualifications.json', 'fingerprint.json', 'source-snapshot.json'):
            path = directory / filename
            if path.is_file():
                index.append(json_file(files, f'runs/{run_id}/{filename}', path,
                                       redacted=filename in ('results.json', 'source-snapshot.json')))
        for artifact in result.get('artifacts', []):
            relative = artifact.get('path', '')
            target = (directory / relative).resolve()
            if (not relative or PurePosixPath(relative.replace('\\', '/')).is_absolute()
                    or '..' in PurePosixPath(relative.replace('\\', '/')).parts
                    or not target.is_relative_to(directory.resolve()) or not target.is_file()):
                raise ValueError('Unsafe or missing supporting artifact.')
            source_bytes = target.read_bytes()
            if digest(source_bytes) != artifact.get('sha256'):
                raise ValueError('Supporting artifact hash changed.')
            try:
                data, format_policy = portable_artifact(relative, source_bytes)
            except ValueError as error:
                raise ValueError('Unsafe artifact ' + run_id + '/' + relative + ': ' + str(error)) from error
            if format_policy.startswith('redacted'):
                try:
                    path_free(data)
                except ValueError as error:
                    raise ValueError('Artifact redaction failed for ' + run_id + '/' + relative) from error
            object_path = 'objects/sha256/' + digest(data)
            if object_path not in files:
                add(files, object_path, data, binary=not format_policy.startswith('redacted'))
                index.append({'path': object_path, 'sha256': digest(data),
                              'sourceSha256': digest(source_bytes), 'bytes': len(data),
                              'formatPolicy': format_policy})
            payloads.append({'runId': run_id, 'path': relative.replace('\\', '/'),
                             'sourceSha256': digest(source_bytes), 'object': object_path,
                             'formatPolicy': format_policy})
    manifest = {'schemaVersion': 2, 'kind': 'scientific.portable-six-capability-evidence',
                'sourceCommit': live['sourceCommit'], 'verifiedAtUtc': datetime.now(timezone.utc).isoformat(),
                'liveRecordSha256': digest(record_path.read_bytes()),
                'signingKeyId': key_id,
                'capabilities': [{'name': name, 'runtimeId': identity[0], 'capabilityId': identity[1],
                                  'recordId': live['profiles'][name]['recordId']} for name, identity in TARGETS.items()],
                'artifactPayloads': payloads, 'omittedArtifacts': [],
                'evidenceHashes': evidence_hashes,
                'benchmarkPayloads': benchmark_payloads,
                'classPayloads': class_payloads,
                'productPayloads': product_payloads,
                'files': sorted(index, key=lambda item: item['path'])}
    body = compact(manifest)
    path_free(body)
    key = signing_identity(signing_key, key_id)
    signature = compact({'schemaVersion': 1, 'algorithm': 'Ed25519', 'keyId': key_id,
                         'signedAtUtc': datetime.now(timezone.utc).isoformat(),
                         'signatureBase64': base64.b64encode(key.sign(body)).decode('ascii')})
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, data in sorted(files.items()):
            archive.writestr(name, data)
        archive.writestr('manifest.json', body)
        archive.writestr('manifest.sha256', digest(body))
        archive.writestr('manifest.signature.json', signature)
    return {'bundle': str(output), 'manifestSha256': digest(body), 'supportRuns': len(runs),
            'capabilities': len(TARGETS), 'artifactPayloads': len(payloads), 'omittedArtifacts': 0,
            'signingKeyId': key_id}


def verify(path, trust_store=None):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or any(PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts for name in names):
            raise ValueError('Unsafe or duplicate bundle entries.')
        body = archive.read('manifest.json')
        if digest(body) != archive.read('manifest.sha256').decode('ascii'):
            raise ValueError('Bundle manifest seal changed.')
        manifest = json.loads(body)
        version = manifest.get('schemaVersion')
        if version not in (1, 2) or manifest.get('kind') != 'scientific.portable-six-capability-evidence':
            raise ValueError('Unsupported portable evidence bundle.')
        if version == 2:
            signature = json.loads(archive.read('manifest.signature.json'))
            if signature.get('keyId') != manifest.get('signingKeyId'):
                raise ValueError('Evidence signing key ID changed.')
            verify_signature(body, signature, trust_store)
        files = {item['path']: item for item in manifest['files']}
        metadata = {'manifest.json', 'manifest.sha256'} | ({'manifest.signature.json'} if version == 2 else set())
        if set(names) != set(files) | metadata or len(files) != len(manifest['files']):
            raise ValueError('Bundle inventory changed.')
        for name, item in files.items():
            data = archive.read(name)
            if version == 2 and name.startswith('objects/sha256/'):
                if name != 'objects/sha256/' + digest(data):
                    raise ValueError('Content-addressed object name changed.')
            else:
                path_free(data)
            if len(data) != item['bytes'] or digest(data) != item['sha256'] or not HASH.fullmatch(item['sourceSha256']):
                raise ValueError('Bundle file hash changed: ' + name)
        if version == 2:
            if manifest.get('omittedArtifacts'):
                raise ValueError('Signed bundle omits supporting artifacts.')
            payloads = manifest.get('artifactPayloads')
            if not isinstance(payloads, list):
                raise ValueError('Signed bundle has no artifact payload inventory.')
            by_key = {(item['runId'], item['path']): item for item in payloads}
            if len(by_key) != len(payloads):
                raise ValueError('Duplicate artifact payload identity.')
            referenced = set()
            for item in payloads:
                name = item['object']
                if name not in files or not name.startswith('objects/sha256/'):
                    raise ValueError('Artifact payload object missing.')
                data = archive.read(name)
                if item['formatPolicy'] != files[name]['formatPolicy']:
                    raise ValueError('Artifact format policy changed.')
                checked, policy = portable_artifact(item['path'], data)
                if checked != data or policy != item['formatPolicy']:
                    raise ValueError('Artifact payload violates safe format policy.')
                if policy == 'native-mesh-v1' and item['sourceSha256'] != digest(data):
                    raise ValueError('Native artifact source hash changed.')
                referenced.add(name)
            evidence_names = ('shared', 'report', 'matrix', 'comparison', 'advisor', 'product')
            if 'classes' in manifest.get('evidenceHashes', {}):
                evidence_names += ('classes', 'classPolicy', 'rankingPolicy')
            if set(manifest.get('evidenceHashes', {})) != set(evidence_names):
                raise ValueError('Six-capability evidence inventory changed.')
            for name in evidence_names:
                path = f'evidence/{name}.json'
                if files[path]['sourceSha256'] != manifest['evidenceHashes'][name]:
                    raise ValueError('Six-capability evidence source hash changed.')
            shared = json.loads(archive.read('evidence/shared.json'))
            report = json.loads(archive.read('evidence/report.json'))
            matrix = json.loads(archive.read('evidence/matrix.json'))
            advisor = json.loads(archive.read('evidence/advisor.json'))
            product = json.loads(archive.read('evidence/product.json'))
            if (shared['sourceCommit'] != manifest['sourceCommit']
                    or shared['releaseRecordSha256'] != manifest['liveRecordSha256']
                    or report['releaseRecordSha256'] != manifest['liveRecordSha256']
                    or report['files']['matrix.json'] != manifest['evidenceHashes']['matrix']
                    or report['files']['comparison.json'] != manifest['evidenceHashes']['comparison']
                    or matrix['sharedInspect']['sha256'] != manifest['evidenceHashes']['shared']
                    or matrix['advisor']['sha256'] != manifest['evidenceHashes']['advisor']
                    or matrix['math3dProduct']['sha256'] != manifest['evidenceHashes']['product']
                    or advisor['scopeRecordSha256'] != manifest['evidenceHashes']['shared']
                    or product['scopeRecordSha256'] != manifest['evidenceHashes']['shared']):
                raise ValueError('Offline release, benchmark, matrix or advisor link changed.')
            if 'classes' in manifest['evidenceHashes']:
                classes = json.loads(archive.read('evidence/classes.json'))
                if (classes['sourceCommit'] != manifest['sourceCommit']
                        or classes['releaseRecordSha256'] != manifest['liveRecordSha256']
                        or classes['policySha256'] != manifest['evidenceHashes']['classPolicy']
                        or advisor.get('rankingPolicySha256') != manifest['evidenceHashes']['rankingPolicy']):
                    raise ValueError('Offline bounded class or ranking policy link changed.')
                expected_classes = {}
                for class_id, evidence in classes['classes'].items():
                    for provider in ('cgal', 'vtk'):
                        for sample, run in enumerate(evidence['runs'][provider]):
                            for kind, item in run['files'].items():
                                expected_classes[(class_id, provider, sample, kind)] = item['sha256']
                observed_classes = {}
                for item in manifest.get('classPayloads', []):
                    key = (item['classId'], item['provider'], item['sample'], item['kind'])
                    if key in observed_classes:
                        raise ValueError('Duplicate bounded class payload.')
                    observed_classes[key] = item['sourceSha256']
                    data = archive.read(item['object'])
                    checked, policy = portable_artifact(item['kind'], data)
                    if checked != data or policy != item['formatPolicy']:
                        raise ValueError('Bounded class payload format changed.')
                    referenced.add(item['object'])
                if observed_classes != expected_classes:
                    raise ValueError('Bounded class broker payloads are incomplete or changed.')
            elif manifest.get('classPayloads'):
                raise ValueError('Bounded class payloads lack a signed class record.')
            expected_benchmark = {}
            for tier, evidence in shared['tiers'].items():
                for provider in ('cgal', 'vtk'):
                    gate = evidence['brokerJobs'][provider]
                    for kind in ('result', 'promotion'):
                        expected_benchmark[(tier, provider, 'gate', kind)] = gate[kind + 'Sha256']
                    samples = [('warmup', evidence['warmups'][provider])]
                    samples += [(str(i), item) for i, item in enumerate(evidence['measurements'][provider]['runs'])]
                    for sample, item in samples:
                        for kind in ('request', 'result', 'brokerResult', 'telemetry', 'artifact'):
                            expected_benchmark[(tier, provider, sample, kind)] = item[kind + 'Sha256']
            observed_benchmark = {}
            for item in manifest.get('benchmarkPayloads', []):
                key = (item['tier'], item['provider'], item['sample'], item['kind'])
                if key in observed_benchmark:
                    raise ValueError('Duplicate benchmark payload.')
                observed_benchmark[key] = item['sourceSha256']
                data = archive.read(item['object'])
                checked, policy = portable_artifact(item['kind'] + ('.obj' if item['kind'] == 'artifact'
                    and item['provider'] == 'cgal' else '.vtp' if item['kind'] == 'artifact' else '.json'), data)
                if checked != data or policy != item['formatPolicy']:
                    raise ValueError('Benchmark payload format changed.')
                referenced.add(item['object'])
            if observed_benchmark != expected_benchmark:
                raise ValueError('Benchmark sample payloads are incomplete or changed.')
            observed_product = {}
            for item in manifest.get('productPayloads', []):
                if item['name'] in observed_product:
                    raise ValueError('Duplicate MATH3D product payload.')
                observed_product[item['name']] = item['sourceSha256']
                data = archive.read(item['object'])
                checked, policy = portable_artifact(item['name'], data)
                if checked != data or policy != item['formatPolicy']:
                    raise ValueError('MATH3D product format changed.')
                referenced.add(item['object'])
            if observed_product != product['productFiles']:
                raise ValueError('MATH3D product payloads are incomplete or changed.')
            if referenced != {name for name in files if name.startswith('objects/sha256/')}:
                raise ValueError('Unreferenced artifact object.')
        release = json.loads(archive.read('release/coexistence.json'))
        certified = json.loads(archive.read('release/certified.json'))
        if release['sourceCommit'] != certified.get('sourceCommit', release['sourceCommit']) or release['sourceCommit'] != manifest['sourceCommit']:
            raise ValueError('Source commit changed.')
        capabilities = {(item['runtimeId'], item['capabilityId']): item for item in certified['certifiedCapabilities']}
        if set(capabilities) != set(TARGETS.values()):
            raise ValueError('Capability set changed.')
        for item in manifest['capabilities']:
            if item['recordId'] != release['profiles'][item['name']]['recordId']:
                raise ValueError('Release record ID changed.')
            entry = capabilities[(item['runtimeId'], item['capabilityId'])]
            for label in ('config', 'smoke'):
                profile_file = files[f'profiles/{item["name"]}/{label}.json']
                if profile_file['sourceSha256'] != release['profiles'][item['name']][label + 'Sha256']:
                    raise ValueError('Release profile source hash changed.')
            if version == 2 and release.get('math3dIdentity'):
                link_file = files[f'profiles/{item["name"]}/math3d-link.json']
                if link_file['sourceSha256'] != release['profiles'][item['name']]['math3dLinkSha256']:
                    raise ValueError('MATH3D product smoke link changed.')
                link = json.loads(archive.read(link_file['path']))
                if (link['smokeSha256'] != release['profiles'][item['name']]['smokeSha256']
                        or link['math3dIdentitySha256'] != release['math3dIdentity']['identitySha256']):
                    raise ValueError('MATH3D product smoke identity changed.')
            if entry['recordId'] != item['recordId'] or entry['level'] != 'L9' or len(entry['supportingRecords']) != 10:
                raise ValueError('Certified support changed.')
            for level, support in enumerate(entry['supportingRecords']):
                run_id, record_id = support['runId'], support['recordId']
                result = json.loads(archive.read(f'runs/{run_id}/results.json'))
                if version == 2:
                    for artifact in result.get('artifacts', []):
                        identity = (run_id, artifact['path'].replace('\\', '/'))
                        payload = by_key.get(identity)
                        if payload is None or payload['sourceSha256'] != artifact['sha256']:
                            raise ValueError('Supporting artifact payload changed.')
                qualifications = archive.read(f'runs/{run_id}/qualifications.json')
                fingerprint = archive.read(f'runs/{run_id}/fingerprint.json')
                fingerprint_value = json.loads(fingerprint)
                if (support['level'] != f'L{level}' or result['runId'] != run_id
                        or result['qualificationSha256'] != files[f'runs/{run_id}/qualifications.json']['sourceSha256']
                        or result['runFingerprintSha256'] != fingerprint_value['sha256']
                        or digest(compact(fingerprint_value['components'])) != fingerprint_value['sha256']):
                    raise ValueError('Supporting run reference changed.')
                snapshot_path = f'runs/{run_id}/source-snapshot.json'
                if snapshot_path in files and result.get('sourceSnapshotSha256') != files[snapshot_path]['sourceSha256']:
                    raise ValueError('Supporting source snapshot changed.')
                records = json.loads(qualifications)['records']
                record = next((value for value in records if value['recordId'] == record_id), None)
                if record is None or record['level'] != f'L{level}' or record['capabilityId'] != support['capabilityId']:
                    raise ValueError('Supporting qualification changed.')
                copy = dict(record)
                copy.pop('recordId')
                if digest(compact(copy)) != record_id:
                    raise ValueError('Qualification record hash changed.')
        return {'verdict': 'verified-historical-evidence', 'sourceCommit': manifest['sourceCommit'],
                'manifestSha256': digest(body), 'capabilities': len(capabilities),
                'artifactPayloads': len(manifest.get('artifactPayloads', [])),
                'signature': 'trusted' if version == 2 else 'legacy-unsigned'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('export', 'verify', 'keygen'))
    parser.add_argument('--record')
    parser.add_argument('--shared-record')
    parser.add_argument('--report-record')
    parser.add_argument('--advisor-record')
    parser.add_argument('--product-record')
    parser.add_argument('--class-record')
    parser.add_argument('--output')
    parser.add_argument('--bundle')
    parser.add_argument('--signing-key')
    parser.add_argument('--key-id')
    parser.add_argument('--trust-store')
    parser.add_argument('--private-key')
    parser.add_argument('--public-key')
    options = parser.parse_args()
    if options.command == 'keygen':
        if not options.private_key or not options.public_key:
            parser.error('keygen requires --private-key and --public-key')
        key = Ed25519PrivateKey.generate()
        private = Path(options.private_key)
        private.parent.mkdir(parents=True, exist_ok=True)
        private.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                             serialization.NoEncryption()))
        public = Path(options.public_key)
        public.parent.mkdir(parents=True, exist_ok=True)
        public.write_bytes(key.public_key().public_bytes(serialization.Encoding.Raw,
                                                         serialization.PublicFormat.Raw))
        report = {'privateKey': str(private), 'publicKey': str(public)}
    elif options.command == 'export':
        if not all((options.record, options.output, options.signing_key, options.key_id,
                    options.shared_record, options.report_record, options.advisor_record,
                    options.product_record)):
            parser.error('export requires release, shared, report, advisor and product records plus signing key')
        report = export(options.record, options.output, options.signing_key, options.key_id,
                        options.shared_record, options.report_record, options.advisor_record,
                        options.product_record, options.class_record)
    else:
        if not options.bundle:
            parser.error('verify requires --bundle')
        report = verify(options.bundle, options.trust_store)
    print(json.dumps(report, indent=2))
