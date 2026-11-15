"""Independent, read-only verifier for a saved Workbench-to-MATH3D handoff."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def verify(handoff, runs, math3d):
    handoff, runs, math3d = (Path(item).resolve(strict=True) for item in (handoff, runs, math3d))
    result = load(handoff / 'results.json')
    if result.get('recipeId') != 'workbench.math3d-handoff' or result.get('state') != 'succeeded':
        raise ValueError('Handoff did not finish successfully.')
    evidence = result['math3dWorkbenchHandoff']
    provenance_path = handoff / 'handoff-provenance.json'
    provenance = load(provenance_path)
    if (provenance.get('kind') != 'scientific.workbench-math3d-handoff'
            or evidence['provenanceSha256'] != digest(provenance_path)
            or provenance['operationCatalogVersion'] != 1):
        raise ValueError('Handoff provenance changed.')
    source_matches = []
    for folder in runs.iterdir():
        path = folder / 'results.json'
        if folder.is_dir() and path.is_file():
            candidate = load(path)
            if candidate.get('runId') == provenance['sourceRunId']:
                source_matches.append((folder, candidate))
    if len(source_matches) != 1:
        raise ValueError('Source run identity is missing or ambiguous.')
    source_dir, source = source_matches[0]
    relative = provenance['sourceArtifactPath']
    artifact = (source_dir / relative).resolve(strict=True)
    if (not artifact.is_relative_to(source_dir) or source['state'] != 'succeeded'
            or source['recipeId'] != provenance['sourceRecipeId']
            or source['runtimeId'] != provenance['sourceRuntimeId']
            or digest(source_dir / 'results.json') != provenance['sourceResultSha256']
            or source['sourceSnapshotSha256'] != provenance['sourceSnapshotSha256']
            or not any(item['path'] == relative and item['sha256'] == digest(artifact)
                       for item in source.get('artifacts', []))
            or digest(artifact) != provenance['sourceArtifactSha256']):
        raise ValueError('Saved source result or artifact changed.')
    conversion = load(handoff / 'conversion.json')
    converted = handoff / 'converted.obj'
    if (conversion != evidence['conversion'] or conversion['sourceArtifactSha256'] != digest(artifact)
            or conversion['objSha256'] != digest(converted)
            or provenance['convertedObjSha256'] != digest(converted)):
        raise ValueError('Converted OBJ or conversion record changed.')
    product_dir = handoff / 'product'
    product = load(product_dir / 'product.json')
    if (product != evidence['product'] or product['verdict'] != 'passed' or product['sourceObjSha256'] != digest(converted)
            or product['provenanceSha256'] != digest(provenance_path)
            or any(product[key] != digest(product_dir / filename) for key, filename in (
                ('documentSha256', 'vtk-mesh-document.json'), ('resourceSha256', 'vtk-mesh-resource.bin'),
                ('m3dmSha256', 'read.m3dm')))):
        raise ValueError('MATH3D product artifacts or hashes changed.')
    document = load(product_dir / 'vtk-mesh-document.json')
    if document['source']['origin']['devshell'] != provenance or document['identity']['id'] != product['documentId']:
        raise ValueError('Saved document lost Workbench provenance.')
    commit = subprocess.check_output(['git', '-C', str(math3d), 'rev-parse', 'HEAD'], text=True).strip()
    if (commit != provenance['math3dCommit'] or commit != product['consumerCommit']
            or subprocess.check_output(['git', '-C', str(math3d), 'status', '--porcelain'], text=True).strip()):
        raise ValueError('MATH3D consumer checkout drifted.')
    for relative, expected in product['consumerSources'].items():
        file = (math3d / relative).resolve(strict=True)
        if not file.is_relative_to(math3d) or digest(file) != expected:
            raise ValueError('MATH3D consumer source changed: ' + relative)
    data = (product_dir / 'read.m3dm').read_bytes()
    if len(data) < 32 or len(data) > 32 * 1024 * 1024:
        raise ValueError('M3DM payload size is invalid.')
    magic, version, header, points, faces, position_bytes, index_bytes, total, flags = struct.unpack_from('<4sHHIIIIII', data)
    if (magic != b'M3DM' or version != 1 or header != 32 or flags != 0
            or points != product['points'] or faces != product['triangles']
            or position_bytes != points * 12 or index_bytes != faces * 12
            or total != len(data) or total != 32 + position_bytes + index_bytes):
        raise ValueError('M3DM reload header or geometry identity is invalid.')
    indices = struct.unpack_from('<' + 'I' * (faces * 3), data, 32 + position_bytes)
    if any(index >= points for index in indices):
        raise ValueError('M3DM triangle index is out of range.')
    return {'verdict': 'passed', 'sourceRunId': source['runId'], 'math3dCommit': commit,
            'documentId': product['documentId'], 'points': points, 'triangles': faces}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--handoff', required=True)
    parser.add_argument('--runs', required=True)
    parser.add_argument('--math3d', required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.handoff, args.runs, args.math3d), sort_keys=True))
