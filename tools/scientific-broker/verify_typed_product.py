"""Read-only verifier for typed VTK/SciPy to MATH3D product and cold reopen."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess


HEX = re.compile(r'^[0-9a-f]{64}$')
COMMIT = re.compile(r'^[0-9a-f]{40}$')


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path, limit=1024 * 1024):
    path = Path(path).resolve(strict=True)
    if not path.is_file() or path.stat().st_size > limit:
        raise ValueError('Typed evidence file is missing or oversized: ' + str(path))
    return json.loads(path.read_text(encoding='utf-8'))


def checked(root, name, expected, limit=32 * 1024 * 1024):
    if not HEX.fullmatch(expected or ''):
        raise ValueError('Artifact SHA-256 is invalid: ' + name)
    path = (root / name).resolve(strict=True)
    if not path.is_relative_to(root) or path.stat().st_size > limit or sha(path) != expected:
        raise ValueError('Saved artifact changed: ' + name)
    return path


def verify(product_directory, provenance_path, measurement_path, vtk_path, obj_path,
           cold_path, math3d_checkout=None):
    root = Path(product_directory).resolve(strict=True)
    product = read(root / 'product.json')
    provenance_path, measurement_path, vtk_path, obj_path, cold_path = (
        Path(item).resolve(strict=True) for item in
        (provenance_path, measurement_path, vtk_path, obj_path, cold_path))
    provenance = read(provenance_path, 65536)
    measurement = read(measurement_path, 65536)
    cold = read(cold_path, 65536)
    if (product.get('verdict') != 'passed' or product.get('provenanceSha256') != sha(provenance_path)
            or provenance.get('kind') != 'scientific.typed-journey'
            or provenance.get('schemaVersion') != 1 or product.get('consumerCommit') != provenance.get('math3dCommit')
            or not COMMIT.fullmatch(provenance.get('sourceCommit', ''))
            or not HEX.fullmatch(provenance.get('sourceSnapshotSha256', ''))):
        raise ValueError('Typed product source, consumer or provenance identity differs.')
    lineage = ('booleanSourceASha256', 'booleanSourceBSha256', 'booleanSurfaceSha256',
               'gmshMeshSha256', 'gmshBoundarySha256', 'vtkArtifactSha256', 'measurementSha256',
               'convertedObjSha256')
    if (any(not HEX.fullmatch(provenance.get(key, '')) for key in lineage)
            or provenance['booleanSourceASha256'] == provenance['booleanSourceBSha256']
            or provenance.get('geometryGeneration') != 4 or provenance.get('measurementGeneration') != 5
            or provenance.get('consumerGeneration') != 6
            or provenance.get('lengthUnit') not in ('m', 'mm') or not provenance.get('frame')):
        raise ValueError('Typed artifact lineage, unit, frame or generation differs.')
    if (sha(vtk_path) != provenance['vtkArtifactSha256'] or sha(obj_path) != provenance['convertedObjSha256']
            or sha(measurement_path) != provenance['measurementSha256']
            or product.get('sourceObjSha256') != provenance['convertedObjSha256']):
        raise ValueError('VTK, conversion or SciPy source bytes changed.')
    value = measurement.get('measurement')
    if (measurement.get('schemaVersion') != 1 or measurement.get('operation') != 'scipy.measure'
            or measurement.get('state') != 'succeeded'
            or measurement.get('sourceCommit') != provenance['sourceCommit']
            or measurement.get('sourceSnapshotSha256') != provenance['sourceSnapshotSha256']
            or measurement.get('inputHashes', {}).get('vtk-analysis') != provenance['vtkArtifactSha256']
            or value != provenance.get('measurement') or not isinstance(value, dict)
            or value.get('unit') != provenance['lengthUnit'] + '2'
            or value.get('frame') != provenance['frame']
            or value.get('sourceArtifactSha256') != provenance['vtkArtifactSha256']
            or product.get('typedMeasurement', {}).get('sha256') != provenance['measurementSha256']
            or product['typedMeasurement'].get('value') != value.get('value')):
        raise ValueError('Typed SciPy measurement differs from product provenance.')
    document_path = checked(root, 'vtk-mesh-document.json', product.get('documentSha256'))
    checked(root, 'vtk-mesh-resource.bin', product.get('resourceSha256'))
    mesh_path = checked(root, 'read.m3dm', product.get('m3dmSha256'))
    document = read(document_path, 32 * 1024 * 1024)
    if (document.get('source', {}).get('origin', {}).get('devshell') != provenance
            or document.get('identity', {}).get('id') != product.get('documentId')
            or document['identity'].get('structuralHash') != product.get('structuralHash')):
        raise ValueError('Saved MATH3D document lost typed provenance or identity.')
    data = mesh_path.read_bytes()
    if len(data) < 32:
        raise ValueError('M3DM export header is incomplete.')
    magic, version, header, points, faces, positions, indices, total, flags = struct.unpack_from('<4sHHIIIIII', data)
    if (magic != b'M3DM' or version != 1 or header != 32 or flags != 0
            or points != product.get('points') or faces != product.get('triangles')
            or positions != points * 12 or indices != faces * 12 or total != len(data)
            or total != 32 + positions + indices):
        raise ValueError('M3DM export geometry or length differs.')
    if any(index >= points for (index,) in struct.iter_unpack('<I', data[32 + positions:])):
        raise ValueError('M3DM export triangle index is out of range.')
    if (cold.get('kind') != 'scientific.typed-journey-cold-reopen' or cold.get('verdict') != 'passed'
            or cold.get('newProcess') is not True or cold.get('producerPid') != product.get('producerPid')
            or cold.get('reopenPid') == cold.get('producerPid')
            or cold.get('sourceCommit') != provenance['sourceCommit']
            or cold.get('sourceSnapshotSha256') != provenance['sourceSnapshotSha256']
            or cold.get('consumerCommit') != provenance['math3dCommit']
            or cold.get('documentId') != product['documentId']
            or cold.get('structuralHash') != product['structuralHash']
            or cold.get('documentSha256') != product['documentSha256']
            or cold.get('resourceSha256') != product['resourceSha256']
            or cold.get('exportSha256') != product['m3dmSha256']
            or cold.get('measurementSha256') != provenance['measurementSha256']
            or cold.get('lengthUnit') != provenance['lengthUnit'] or cold.get('frame') != provenance['frame']
            or cold.get('generation') != 8 or cold.get('points') != points or cold.get('triangles') != faces):
        raise ValueError('Cold-reopen evidence differs from the saved product.')
    if math3d_checkout:
        checkout = Path(math3d_checkout).resolve(strict=True)
        commit = subprocess.check_output(['git', '-C', str(checkout), 'rev-parse', 'HEAD'], text=True).strip()
        if commit != provenance['math3dCommit'] or subprocess.check_output(
                ['git', '-C', str(checkout), 'status', '--porcelain'], text=True).strip():
            raise ValueError('Pulled MATH3D checkout is stale or dirty.')
        for relative, expected in product.get('consumerSources', {}).items():
            if not isinstance(relative, str) or '..' in Path(relative).parts:
                raise ValueError('Consumer source path is unsafe.')
            checked(checkout, relative, expected)
    return {'verdict': 'verified-typed-product-relations', 'sourceCommit': provenance['sourceCommit'],
            'math3dCommit': provenance['math3dCommit'], 'documentId': product['documentId'],
            'points': points, 'triangles': faces, 'measurementSha256': provenance['measurementSha256']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--product', required=True)
    parser.add_argument('--provenance', required=True)
    parser.add_argument('--measurement', required=True)
    parser.add_argument('--vtk', required=True)
    parser.add_argument('--obj', required=True)
    parser.add_argument('--cold', required=True)
    parser.add_argument('--math3d')
    args = parser.parse_args()
    print(json.dumps(verify(args.product, args.provenance, args.measurement,
                            args.vtk, args.obj, args.cold, args.math3d), sort_keys=True))
