"""Seal managed DevShell inspection selection, override, fallback and cancellation runs."""
import argparse
import hashlib
import json
from pathlib import Path

from class_inspect_qualification import verify as verify_classes
from math3d_inspect_product import PRODUCT_FILES, verify as verify_product
from six_capability_release import verify as verify_release

ROLES = ('automatic', 'manual', 'fallback', 'cancelled')
RECIPE = 'l9.math3d-inspect-selection'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_run(role, directory, release, class_record):
    directory = Path(directory).resolve(strict=True)
    request_path, result_path = directory / 'request.json', directory / 'results.json'
    request = json.loads(request_path.read_text(encoding='utf-8'))
    result = json.loads(result_path.read_text(encoding='utf-8'))
    snapshot = json.loads((directory / 'source-snapshot.json').read_text(encoding='utf-8'))
    if (directory.name != result.get('runId') or result['runId'] != request.get('runId')
            or result.get('recipeId') != RECIPE or request.get('recipeId') != RECIPE
            or snapshot['repositories']['devshell']['commit'] != release['sourceCommit']
            or snapshot['repositories']['math3d']['commit'] != release['math3dIdentity']['commit']
            or request['parameters'].get('classRecord') != str(Path(class_record).resolve())):
        raise ValueError(role + ' managed selection source, request or release changed.')
    manual = request['parameters'].get('manualProvider')
    selection = result.get('selection')
    if role == 'cancelled':
        if result.get('state') != 'cancelled' or selection or (directory / 'product-selection/selection.json').exists():
            raise ValueError('Cancelled selection produced a promoted product.')
        if result.get('artifacts'):
            raise ValueError('Cancelled selection saved product artifacts.')
    else:
        if result.get('state') != 'succeeded' or not isinstance(selection, dict):
            raise ValueError(role + ' managed selection did not succeed.')
        product_path = directory / 'product-selection/selection.json'
        if sha(product_path) != next((item['sha256'] for item in result.get('artifacts', [])
                                      if item['path'] == 'product-selection/selection.json'), None):
            raise ValueError(role + ' selected product artifact changed.')
        if json.loads(product_path.read_text(encoding='utf-8')) != selection:
            raise ValueError(role + ' managed result and selected product disagree.')
        if selection.get('math3dIdentity') != release['math3dIdentity']:
            raise ValueError(role + ' MATH3D consumer identity changed.')
        input_path = selection['inputPath']
        if sha(input_path) != request['inputArtifacts'][0]['sha256']:
            raise ValueError(role + ' managed selection input changed.')
        verify_product(product_path, request['parameters'].get('sharedRecord'), input_path, class_record)
        if set(selection['productFiles']) != set(PRODUCT_FILES):
            raise ValueError(role + ' saved MATH3D document or viewport is incomplete.')
        if role == 'automatic' and (manual or selection['selectedProvider'] == 'math3d-direct'):
            raise ValueError('Automatic selection was not qualified.')
        if role == 'manual' and (not manual or selection['selectedProvider'] != manual):
            raise ValueError('Manual provider choice was not retained.')
        if role == 'fallback' and (manual or selection['state'] != 'fallback'
                                    or selection['selectedProvider'] != 'math3d-direct'):
            raise ValueError('Fallback did not use the direct MATH3D importer.')
    files = {'request.json': sha(request_path), 'results.json': sha(result_path),
             'source-snapshot.json': sha(directory / 'source-snapshot.json')}
    if role != 'cancelled':
        files['product-selection/selection.json'] = sha(directory / 'product-selection/selection.json')
        for name in PRODUCT_FILES:
            files['product-selection/product/' + name] = sha(directory / 'product-selection/product' / name)
    for artifact in result.get('artifacts', []):
        path = artifact['path'].replace('\\', '/')
        if not path.startswith('product-selection/') or sha(directory / path) != artifact['sha256']:
            raise ValueError(role + ' managed product artifact changed.')
        files[path] = artifact['sha256']
    return {'runId': result['runId'], 'state': result['state'], 'files': files}


def create(release_path, class_path, run_dirs, output):
    release_path, class_path = Path(release_path).resolve(strict=True), Path(class_path).resolve(strict=True)
    release = verify_release(release_path)
    classes = verify_classes(class_path)
    if classes['releaseRecordSha256'] != sha(release_path) or set(run_dirs) != set(ROLES):
        raise ValueError('Desktop journey needs current class evidence and all four roles.')
    runs = {role: check_run(role, run_dirs[role], release, class_path) for role in ROLES}
    if len({item['runId'] for item in runs.values()}) != len(ROLES):
        raise ValueError('Desktop journey reused a managed run.')
    value = {'schemaVersion': 1, 'kind': 'scientific.desktop-inspect-product-journey',
             'sourceCommit': release['sourceCommit'], 'releaseRecordSha256': sha(release_path),
             'classRecordSha256': sha(class_path),
             'math3dIdentitySha256': release['math3dIdentity']['identitySha256'], 'runs': runs}
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, separators=(',', ':')), encoding='utf-8')
    Path(str(output) + '.sha256').write_text(sha(output), encoding='utf-8')
    return output, value


def verify(path, release_path, class_path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text().strip():
        raise ValueError('Desktop journey record seal changed.')
    value = json.loads(path.read_text(encoding='utf-8'))
    release = verify_release(release_path)
    if (value.get('schemaVersion') != 1 or value.get('kind') != 'scientific.desktop-inspect-product-journey'
            or value['sourceCommit'] != release['sourceCommit']
            or value['releaseRecordSha256'] != sha(release_path)
            or value['classRecordSha256'] != sha(class_path)
            or value['math3dIdentitySha256'] != release['math3dIdentity']['identitySha256']
            or set(value['runs']) != set(ROLES)):
        raise ValueError('Desktop journey release or consumer identity drifted.')
    repo = Path(release['repo'])
    for role, saved in value['runs'].items():
        current = check_run(role, repo / '.scientific/runs' / saved['runId'], release, class_path)
        if current != saved:
            raise ValueError(role + ' desktop journey evidence drifted.')
    return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('create', 'verify'))
    parser.add_argument('--release', required=True)
    parser.add_argument('--classes', required=True)
    parser.add_argument('--record')
    parser.add_argument('--output')
    for role in ROLES:
        parser.add_argument('--' + role + '-run')
    args = parser.parse_args()
    if args.command == 'create':
        paths = {role: getattr(args, role + '_run') for role in ROLES}
        if not args.output or not all(paths.values()):
            parser.error('create requires output and all four managed run directories')
        record, value = create(args.release, args.classes, paths, args.output)
    else:
        record = args.record
        value = verify(record, args.release, args.classes)
    print(json.dumps({'record': str(record), 'runs': {role: item['runId'] for role, item in value['runs'].items()},
                      'verdict': 'verified'}))
