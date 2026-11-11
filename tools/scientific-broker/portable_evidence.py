"""Export and independently verify path-redacted five-capability release evidence."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import zipfile

from five_capability_release import TARGETS, verify as verify_live

PATH = re.compile(r'(?i)(?:[a-z]:[\\/]|\\\\)[^\s\"\'<>;,]*')
HASH = re.compile(r'^[0-9a-f]{64}$')
RUN = re.compile(r'^[0-9a-f]{32}$')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def compact(value):
    return json.dumps(value, separators=(',', ':'), ensure_ascii=True).encode('utf-8')


def redact(value):
    if isinstance(value, dict):
        return {key: redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return PATH.sub(lambda match: '<local-path:' + digest(match.group().encode('utf-8'))[:16] + '>', value)
    return value


def path_free(data):
    if PATH.search(data.decode('utf-8')):
        raise ValueError('Portable evidence contains a local absolute path.')


def add(files, name, data):
    if name in files or PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts:
        raise ValueError('Unsafe or duplicate bundle path.')
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


def export(record_path, output):
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
        raise ValueError('Five certified capability entries are required.')
    files, index, omitted = {}, [], []
    index.append(json_file(files, 'release/coexistence.json', record_path))
    index.append(json_file(files, 'release/certified.json', certified))
    support = {item['runId'] for entry in entries.values() for item in entry['supportingRecords']}
    runs = find_runs(repo, support)
    for name, identity in TARGETS.items():
        profile = live['profiles'][name]
        index.append(json_file(files, f'profiles/{name}/config.json', profile['config']))
        index.append(json_file(files, f'profiles/{name}/smoke.json', profile['smoke']))
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
            if target.suffix.lower() in ('.json', '.log', '.txt'):
                try:
                    data = compact(redact(json.loads(source_bytes))) if target.suffix.lower() == '.json' else \
                        redact(source_bytes.decode('utf-8')).encode('utf-8')
                except (UnicodeError, ValueError):
                    data = None
            else:
                data = source_bytes
            try:
                safe_text = data.decode('utf-8') if data is not None else None
            except UnicodeDecodeError:
                safe_text = None
            if safe_text is not None and not PATH.search(safe_text):
                name_in_bundle = f'runs/{run_id}/artifacts/{relative.replace(chr(92), "/")}'
                add(files, name_in_bundle, data)
                index.append({'path': name_in_bundle, 'sha256': digest(data),
                              'sourceSha256': digest(source_bytes), 'bytes': len(data)})
            else:
                omitted.append({'runId': run_id, 'path': relative.replace('\\', '/'),
                                'sha256': artifact['sha256'], 'reason': 'binary or embedded local path'})
    manifest = {'schemaVersion': 1, 'kind': 'scientific.portable-five-capability-evidence',
                'sourceCommit': live['sourceCommit'], 'verifiedAtUtc': datetime.now(timezone.utc).isoformat(),
                'liveRecordSha256': digest(record_path.read_bytes()),
                'capabilities': [{'name': name, 'runtimeId': identity[0], 'capabilityId': identity[1],
                                  'recordId': live['profiles'][name]['recordId']} for name, identity in TARGETS.items()],
                'omittedArtifacts': omitted,
                'files': sorted(index, key=lambda item: item['path'])}
    body = compact(manifest)
    path_free(body)
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, data in sorted(files.items()):
            archive.writestr(name, data)
        archive.writestr('manifest.json', body)
        archive.writestr('manifest.sha256', digest(body))
    return {'bundle': str(output), 'manifestSha256': digest(body), 'supportRuns': len(runs),
            'capabilities': len(TARGETS), 'omittedArtifacts': len(omitted)}


def verify(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or any(PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts for name in names):
            raise ValueError('Unsafe or duplicate bundle entries.')
        body = archive.read('manifest.json')
        if digest(body) != archive.read('manifest.sha256').decode('ascii'):
            raise ValueError('Bundle manifest seal changed.')
        manifest = json.loads(body)
        if manifest.get('schemaVersion') != 1 or manifest.get('kind') != 'scientific.portable-five-capability-evidence':
            raise ValueError('Unsupported portable evidence bundle.')
        files = {item['path']: item for item in manifest['files']}
        if set(names) != set(files) | {'manifest.json', 'manifest.sha256'} or len(files) != len(manifest['files']):
            raise ValueError('Bundle inventory changed.')
        for name, item in files.items():
            data = archive.read(name)
            path_free(data)
            if len(data) != item['bytes'] or digest(data) != item['sha256'] or not HASH.fullmatch(item['sourceSha256']):
                raise ValueError('Bundle file hash changed: ' + name)
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
            if entry['recordId'] != item['recordId'] or entry['level'] != 'L9' or len(entry['supportingRecords']) != 10:
                raise ValueError('Certified support changed.')
            for level, support in enumerate(entry['supportingRecords']):
                run_id, record_id = support['runId'], support['recordId']
                result = json.loads(archive.read(f'runs/{run_id}/results.json'))
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
                'manifestSha256': digest(body), 'capabilities': len(capabilities)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('export', 'verify'))
    parser.add_argument('--record')
    parser.add_argument('--output')
    parser.add_argument('--bundle')
    options = parser.parse_args()
    if options.command == 'export':
        if not options.record or not options.output:
            parser.error('export requires --record and --output')
        report = export(options.record, options.output)
    else:
        if not options.bundle:
            parser.error('verify requires --bundle')
        report = verify(options.bundle)
    print(json.dumps(report, indent=2))
