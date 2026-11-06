"""Local scientific environment locks and disposable offline recreation evidence."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import urlsplit
import uuid

ROOT = Path(__file__).resolve().parents[2]
PROVIDERS = {'cgal-win-conda', 'vtk-win-conda', 'python-win-conda', 'gmsh-win-conda'}
HEX32 = re.compile(r'[0-9a-f]{32}\Z')
HEX64 = re.compile(r'[0-9a-f]{64}\Z')
SAFE_CHANNELS = {'conda.anaconda.org', 'repo.anaconda.com', 'repo.continuum.io'}


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(65536), b''):
            digest.update(block)
    return digest.hexdigest()


def save(path, value):
    path = Path(path)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, separators=(',', ':'))
    Path(str(path) + '.sha256').write_text(sha(path), encoding='utf-8')
    return path


def package_records(prefix):
    files = sorted((Path(prefix) / 'conda-meta').glob('*.json'), key=lambda item: item.name)
    if not files:
        raise ValueError('Conda package records are unavailable.')
    records = []
    for path in files:
        value = json.loads(path.read_text(encoding='utf-8'))
        for field in ('name', 'version', 'build', 'fn', 'url', 'sha256', 'md5'):
            if not isinstance(value.get(field), str) or not value[field]:
                raise ValueError('Incomplete Conda package record: ' + path.name)
        address = urlsplit(value['url'])
        if (address.scheme != 'https' or address.hostname not in SAFE_CHANNELS
                or address.username or address.password or address.query or address.fragment
                or not HEX64.fullmatch(value['sha256']) or not HEX32.fullmatch(value['md5'])):
            raise ValueError('Conda package URL or checksum is not safe for a portable lock: ' + path.name)
        records.append({field: value[field] for field in ('name', 'version', 'build', 'fn', 'url', 'sha256', 'md5')})
    return records


def identity(records):
    return hashlib.sha256(json.dumps(sorted(records, key=lambda item: (item['name'], item['version'], item['build'])),
                                     sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def capture(runtime_id, prefix, output_root):
    if runtime_id not in PROVIDERS:
        raise ValueError('Only registered Windows Conda providers have an exact lock generator.')
    prefix = Path(prefix).resolve(strict=True)
    if not (prefix / 'python.exe').is_file():
        raise ValueError('Dedicated Conda Python is unavailable.')
    records = package_records(prefix)
    directory = Path(output_root).resolve() / uuid.uuid4().hex
    directory.mkdir(parents=True)
    explicit = directory / 'conda-explicit.txt'
    explicit.write_text('@EXPLICIT\n' + '\n'.join(item['url'] + '#' + item['md5'] for item in records) + '\n',
                        encoding='utf-8')
    pip_state = 'unavailable'
    pip_count = 0
    requirements = directory / 'requirements.versions.txt'
    try:
        result = subprocess.run([str(prefix / 'python.exe'), '-I', '-m', 'pip', 'list', '--format=json'],
                                capture_output=True, text=True, timeout=30, check=True)
        packages = json.loads(result.stdout)
        lines = sorted(f"{item['name']}=={item['version']}" for item in packages
                       if re.fullmatch(r'[A-Za-z0-9_.-]+', item['name'])
                       and re.fullmatch(r'[A-Za-z0-9_.+!-]+', item['version']))
        requirements.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        pip_count = len(lines)
        pip_state = 'version-pinned-no-wheel-hashes'
    except (OSError, ValueError, subprocess.SubprocessError, KeyError):
        requirements.write_text('# pip inventory unavailable; no hash-locked venv can be claimed\n', encoding='utf-8')
    cmake = prefix / 'Library' / 'bin' / 'cmake.exe'
    presets = {'version': 4, 'configurePresets': [{'name': runtime_id + '-locked',
                'displayName': runtime_id + ' with SCIENTIFIC_CONDA_PREFIX',
                'generator': 'Visual Studio 17 2022', 'architecture': 'x64',
                'binaryDir': '${sourceDir}/.scientific/cmake/' + runtime_id,
                'cacheVariables': {'CMAKE_PREFIX_PATH': '$env{SCIENTIFIC_CONDA_PREFIX}/Library'}}]}
    (directory / 'CMakePresets.json').write_text(json.dumps(presets, indent=2), encoding='utf-8')
    container = {'schemaVersion': 1, 'targetPlatform': 'win-64', 'baseImageDigest': None,
                 'condaExplicitSha256': sha(explicit), 'state': 'requires-pinned-compatible-windows-base-with-conda',
                 'note': 'A Linux image cannot recreate win-64 CGAL/VTK packages.'}
    (directory / 'container-preset.json').write_text(json.dumps(container, separators=(',', ':')), encoding='utf-8')
    manifest = {'schemaVersion': 1, 'kind': 'scientific.environment-lock',
                'runtimeId': runtime_id, 'capturedAtUtc': datetime.now(timezone.utc).isoformat(),
                'sourceRuntimeManifestSha256': sha(ROOT / 'runtimes' / runtime_id / 'runtime.json'),
                'sourcePythonSha256': sha(prefix / 'python.exe'), 'packageCount': len(records),
                'packageIdentitySha256': identity(records), 'packages': records,
                'artifacts': {name: sha(directory / name) for name in
                              ('conda-explicit.txt', 'requirements.versions.txt', 'CMakePresets.json', 'container-preset.json')},
                'formats': {'conda': 'exact-explicit-builds', 'venv': pip_state,
                            'container': container['state'],
                            'cmake': 'preset-requires-matching-local-compiler-and-prefix' if cmake.is_file() else 'cmake-unavailable'},
                'pipPackageCount': pip_count,
                'exactRecreation': 'not-attempted'}
    return save(directory / 'environment-manifest.json', manifest)


def verify_manifest(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('Environment manifest hash mismatch.')
    manifest = json.loads(path.read_text(encoding='utf-8'))
    if manifest.get('schemaVersion') != 1 or manifest.get('kind') != 'scientific.environment-lock':
        raise ValueError('Environment manifest contract mismatch.')
    for name, expected in manifest['artifacts'].items():
        if name not in ('conda-explicit.txt', 'requirements.versions.txt', 'CMakePresets.json', 'container-preset.json'):
            raise ValueError('Unexpected environment artifact.')
        if sha(path.parent / name) != expected:
            raise ValueError('Environment artifact hash mismatch: ' + name)
    if identity(manifest['packages']) != manifest['packageIdentitySha256']:
        raise ValueError('Environment package identity changed.')
    return manifest


def recreate(manifest_path, conda_exe, output_root, timeout_seconds=600):
    manifest = verify_manifest(manifest_path)
    if not 30 <= timeout_seconds <= 1800:
        raise ValueError('Recreation timeout must be 30–1800 seconds.')
    conda_exe = Path(conda_exe).resolve(strict=True)
    if conda_exe.suffix.lower() != '.exe':
        raise ValueError('Use an absolute conda.exe path for disposable recreation.')
    root = Path(output_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    attempt_id = uuid.uuid4().hex
    sandbox = root / ('sandbox-' + attempt_id)
    log = root / (attempt_id + '.log')
    state, reason, recreated = 'failed', None, None
    try:
        command = [str(conda_exe), 'create', '--yes', '--offline', '--prefix', str(sandbox),
                   '--file', str(Path(manifest_path).parent / 'conda-explicit.txt')]
        with log.open('x', encoding='utf-8') as output:
            completed = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT,
                                       timeout=timeout_seconds, check=False)
        if completed.returncode:
            reason = f'Offline Conda create exited {completed.returncode}; inspect the local log.'
        else:
            recreated = identity(package_records(sandbox))
            state = 'passed' if recreated == manifest['packageIdentitySha256'] else 'failed'
            if state == 'failed':
                reason = 'Recreated package builds differ from the lock.'
    except subprocess.TimeoutExpired:
        reason = 'Offline Conda create exceeded the time budget.'
    except (OSError, ValueError, json.JSONDecodeError) as error:
        reason = str(error)[:400]
    finally:
        # Never remove outside this explicit attempt root, even after malformed output paths.
        target = sandbox.resolve()
        if target.is_relative_to(root) and target.name == 'sandbox-' + attempt_id and target.exists():
            shutil.rmtree(target)
    record = {'schemaVersion': 1, 'kind': 'scientific.environment-recreation',
              'attemptId': attempt_id, 'runtimeId': manifest['runtimeId'],
              'manifestSha256': sha(manifest_path), 'condaExecutableSha256': sha(conda_exe),
              'policy': 'offline-explicit-lock-disposable-prefix', 'state': state, 'reason': reason,
              'expectedPackageIdentitySha256': manifest['packageIdentitySha256'],
              'recreatedPackageIdentitySha256': recreated,
              'logSha256': sha(log) if log.is_file() else None, 'sandboxRemoved': not sandbox.exists()}
    return save(root / (attempt_id + '.json'), record)


def verify_recreation(record_path, manifest_path):
    record_path = Path(record_path).resolve(strict=True)
    if sha(record_path) != Path(str(record_path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('Recreation record hash mismatch.')
    record = json.loads(record_path.read_text(encoding='utf-8'))
    manifest = verify_manifest(manifest_path)
    if (record.get('schemaVersion') != 1 or record.get('kind') != 'scientific.environment-recreation'
            or record.get('manifestSha256') != sha(manifest_path)
            or record.get('runtimeId') != manifest['runtimeId']
            or record.get('expectedPackageIdentitySha256') != manifest['packageIdentitySha256']
            or not record.get('sandboxRemoved')):
        raise ValueError('Recreation evidence does not match the locked environment.')
    log = record_path.parent / (record['attemptId'] + '.log')
    if record.get('logSha256') != (sha(log) if log.is_file() else None):
        raise ValueError('Recreation log hash mismatch.')
    if record['state'] == 'passed' and record.get('recreatedPackageIdentitySha256') != manifest['packageIdentitySha256']:
        raise ValueError('Recreated package builds differ from the lock.')
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['capture', 'verify', 'recreate', 'verify-recreation'])
    parser.add_argument('--runtime-id')
    parser.add_argument('--prefix')
    parser.add_argument('--manifest')
    parser.add_argument('--conda-exe')
    parser.add_argument('--record')
    parser.add_argument('--output-root')
    parser.add_argument('--timeout-seconds', type=int, default=600)
    args = parser.parse_args()
    if args.command == 'capture':
        print(json.dumps({'manifest': str(capture(args.runtime_id, args.prefix, args.output_root))}))
    elif args.command == 'verify':
        print(json.dumps({'runtimeId': verify_manifest(args.manifest)['runtimeId'], 'state': 'verified'}))
    elif args.command == 'verify-recreation':
        record = verify_recreation(args.record, args.manifest)
        print(json.dumps({'state': record['state'], 'sandboxRemoved': record['sandboxRemoved']}))
    else:
        path = recreate(args.manifest, args.conda_exe, args.output_root, args.timeout_seconds)
        record = json.loads(path.read_text(encoding='utf-8'))
        print(json.dumps({'record': str(path), 'state': record['state'], 'reason': record['reason']}))
        if record['state'] != 'passed':
            raise SystemExit(1)


if __name__ == '__main__':
    main()
