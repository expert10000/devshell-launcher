"""Independent identity verifier for a completed nine-stage scientific journey.

This verifies artifact relations. Live desktop and broker gates must separately prove
that each named operation actually executed; a fabricated record cannot do that.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re


CONTRACT = Path(__file__).resolve().parents[2] / 'schemas' / 'scientific-typed-journey.v1.json'
HEX = re.compile(r'^[0-9a-f]{64}$')
COMMIT = re.compile(r'^[0-9a-f]{40}$')
MAX_FILE = 64 * 1024 * 1024


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def scoped(root, name):
    if not isinstance(name, str) or not name or '\\' in name or '\x00' in name:
        raise ValueError('Invalid artifact path.')
    relative = Path(name)
    if relative.is_absolute() or any(part in ('', '.', '..') for part in name.split('/')):
        raise ValueError('Artifact path escapes the bundle.')
    path = root / relative
    if any(part.is_symlink() for part in (path, *path.parents) if part != root and part.is_relative_to(root)):
        raise ValueError('Artifact symlink is forbidden.')
    if not path.is_file() or not path.resolve().is_relative_to(root):
        raise ValueError('Artifact is missing or escapes the bundle.')
    if path.stat().st_size > MAX_FILE:
        raise ValueError('Artifact exceeds the 64 MiB limit.')
    return path


def checked_file(root, record):
    if not isinstance(record, dict) or not HEX.fullmatch(record.get('sha256', '')):
        raise ValueError('Artifact hash is invalid.')
    path = scoped(root, record.get('path'))
    if path.stat().st_size != record.get('bytes') or sha(path) != record['sha256']:
        raise ValueError('Artifact content or size changed: ' + record['path'])
    return path


def verify(directory):
    root = Path(directory).resolve(strict=True)
    manifest = json.loads(scoped(root, 'journey.json').read_text(encoding='utf-8'))
    contract = json.loads(CONTRACT.read_text(encoding='utf-8'))
    if manifest.get('schemaVersion') != 1 or manifest.get('contractSha256') != sha(CONTRACT):
        raise ValueError('Journey contract version or hash differs.')
    if not COMMIT.fullmatch(manifest.get('sourceCommit', '')) or not COMMIT.fullmatch(manifest.get('math3dCommit', '')):
        raise ValueError('Source or consumer commit is invalid.')
    if not HEX.fullmatch(manifest.get('sourceSnapshotSha256', '')):
        raise ValueError('Source snapshot hash is invalid.')
    frame = manifest.get('frame')
    if not isinstance(frame, dict) or not frame.get('id') or frame.get('handedness') != 'right' or frame.get('axes') != ['x', 'y', 'z']:
        raise ValueError('Coordinate frame is invalid.')
    if manifest.get('lengthUnit') not in ('m', 'mm'):
        raise ValueError('Length unit must be explicit and supported.')
    stages = manifest.get('stages')
    if not isinstance(stages, list) or [stage.get('id') for stage in stages] != contract['stageOrder']:
        raise ValueError('Journey stages are missing or out of order.')
    artifacts = {}
    paths = set()
    run_ids = set()
    for index, stage in enumerate(stages):
        name = stage['id']
        if stage.get('state') != 'succeeded' or stage.get('operation') != contract['operations'][name]:
            raise ValueError(name + ' has no successful typed result.')
        run_id = stage.get('runId')
        if not isinstance(run_id, str) or not re.fullmatch(r'[0-9a-f]{32}', run_id) or run_id in run_ids:
            raise ValueError('Stage run identity is missing or repeated.')
        run_ids.add(run_id)
        inputs = stage.get('inputs')
        outputs = stage.get('outputs')
        if inputs != contract['requiredInputs'][name] or not isinstance(outputs, list) or [item.get('id') for item in outputs] != contract['requiredOutputs'][name]:
            raise ValueError(name + ' input or output roles differ from the contract.')
        if any(item not in artifacts for item in inputs):
            raise ValueError(name + ' references an output that does not exist yet.')
        evidence = stage.get('evidence')
        checked_file(root, evidence)
        result = json.loads(scoped(root, evidence['path']).read_text(encoding='utf-8'))
        expected_inputs = {item: artifacts[item]['sha256'] for item in inputs}
        expected_outputs = {item['id']: item.get('sha256') for item in outputs}
        if (result.get('runId') != run_id or result.get('operation') != stage['operation']
                or result.get('state') != 'succeeded' or result.get('sourceCommit') != manifest['sourceCommit']
                or result.get('sourceSnapshotSha256') != manifest['sourceSnapshotSha256']
                or result.get('inputHashes') != expected_inputs or result.get('outputHashes') != expected_outputs):
            raise ValueError(name + ' saved result does not bind its input and output hashes.')
        if name in ('math3d', 'save', 'cold-reopen') and result.get('consumerCommit') != manifest['math3dCommit']:
            raise ValueError(name + ' saved result has a different MATH3D consumer.')
        if name == 'validate':
            topology = result.get('topology')
            if not isinstance(topology, dict) or any(topology.get(item) != {'closed': True, 'manifold': True, 'positiveVolume': True} for item in inputs):
                raise ValueError('Both Boolean sources need closed manifold positive-volume validation.')
        if name == 'boolean' and artifacts['source-a']['sha256'] == artifacts['source-b']['sha256']:
            raise ValueError('Boolean demonstration requires two distinct source hashes.')
        if name == 'scipy':
            measurement = result.get('measurement')
            expected_unit = manifest['lengthUnit'] + '3'
            if (not isinstance(measurement, dict) or measurement.get('unit') != expected_unit
                    or not isinstance(measurement.get('value'), (float, int)) or not math.isfinite(measurement['value'])
                    or not isinstance(measurement.get('tolerance'), (float, int)) or not math.isfinite(measurement['tolerance'])
                    or measurement['tolerance'] < 0):
                raise ValueError('SciPy measurement lacks a typed value, unit or tolerance.')
        if name == 'cold-reopen' and result.get('newProcess') is not True:
            raise ValueError('Cold reopen did not record a new consumer process.')
        for item in outputs:
            if item['id'] in artifacts or item.get('path') in paths or item.get('producedBy') != run_id:
                raise ValueError('Output identity, path or generation is reused.')
            if (item.get('frame') != frame['id'] or item.get('lengthUnit') != manifest['lengthUnit']
                    or item.get('generation') != index or item.get('parents') != inputs or not item.get('mediaType')):
                raise ValueError('Output unit, frame, generation or provenance differs.')
            checked_file(root, item)
            artifacts[item['id']] = item
            paths.add(item['path'])
    if artifacts['document']['sha256'] != artifacts['reopened-document']['sha256'] or artifacts['export']['sha256'] != artifacts['reopened-export']['sha256']:
        raise ValueError('Cold-reopened document or export differs from the saved bytes.')
    return {'verdict': 'verified-artifact-relations-only', 'sourceCommit': manifest['sourceCommit'],
            'math3dCommit': manifest['math3dCommit'], 'stages': len(stages), 'artifacts': len(artifacts)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.bundle), sort_keys=True))
