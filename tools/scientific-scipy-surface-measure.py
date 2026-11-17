"""Bounded SciPy surface-area candidate for a verified VTK VTP artifact."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re


MAX_REQUEST = 65536
HASH = re.compile(r'^[0-9a-f]{64}$')
RUN = re.compile(r'^[0-9a-f]{32}$')
COMMIT = re.compile(r'^[0-9a-f]{40}$')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_mesh(path):
    source = Path(__file__).with_name('scientific-artifact-roundtrip.py')
    spec = importlib.util.spec_from_file_location('scientific_artifact_roundtrip', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.inspect(path)


def measure(request_path):
    request_path = Path(request_path).resolve(strict=True)
    if request_path.stat().st_size > MAX_REQUEST:
        raise ValueError('Measurement request exceeds 64 KiB.')
    request = json.loads(request_path.read_text(encoding='utf-8'))
    directory = request_path.parent
    if (request.get('schemaVersion') != 1 or request.get('operation') != 'scipy.measure'
            or not RUN.fullmatch(request.get('runId', ''))
            or not RUN.fullmatch(request.get('sourceRunId', ''))
            or not COMMIT.fullmatch(request.get('sourceCommit', ''))
            or not HASH.fullmatch(request.get('sourceSnapshotSha256', ''))
            or request.get('inputId') != 'vtk-analysis'
            or request.get('lengthUnit') not in ('m', 'mm')
            or not isinstance(request.get('frame'), str) or not request['frame']
            or request.get('workingDirectory') != str(directory)):
        raise ValueError('Invalid typed SciPy measurement request.')
    input_record = request.get('inputArtifact')
    if not isinstance(input_record, dict) or not HASH.fullmatch(input_record.get('sha256', '')):
        raise ValueError('Input artifact hash is missing.')
    source = Path(input_record.get('path', '')).resolve(strict=True)
    root = Path(request.get('artifactRoot', '')).resolve(strict=True)
    if (not source.is_relative_to(root) or source.suffix.lower() != '.vtp'
            or not source.is_file() or source.stat().st_size > 32 * 1024 * 1024
            or source.stat().st_size != input_record.get('bytes') or digest(source) != input_record['sha256']):
        raise ValueError('VTK artifact is outside the registered root, too large, or changed.')
    summary, points, faces = read_mesh(source)
    import numpy as np
    from scipy import linalg
    coordinates = np.asarray(points, dtype=np.float64)
    triangles = np.asarray(faces, dtype=np.int64)
    p0, p1, p2 = (coordinates[triangles[:, index]] for index in range(3))
    double_areas = linalg.norm(np.cross(p1 - p0, p2 - p0), axis=1)
    if not np.all(np.isfinite(double_areas)) or np.any(double_areas <= 0):
        raise ValueError('VTK mesh has a degenerate or non-finite triangle.')
    value = math.fsum(float(item) / 2 for item in double_areas)
    if not math.isfinite(value) or value <= 0:
        raise ValueError('Measured surface area is invalid.')
    # Independent parser uses scalar math; this catches array interpretation drift.
    tolerance = max(1e-12, value * 1e-10)
    if abs(value - summary['surfaceArea']) > tolerance:
        raise ValueError('SciPy and independent surface-area measurements differ.')
    result = {'schemaVersion': 1, 'runId': request['runId'], 'operation': 'scipy.measure',
              'state': 'succeeded', 'sourceRunId': request['sourceRunId'], 'sourceCommit': request.get('sourceCommit'),
              'sourceSnapshotSha256': request.get('sourceSnapshotSha256'),
              'inputHashes': {request.get('inputId', 'vtk-analysis'): input_record['sha256']},
              'measurement': {'kind': 'surface-area', 'value': value,
                              'unit': request['lengthUnit'] + '2', 'tolerance': tolerance,
                              'points': len(points), 'triangles': len(faces),
                              'frame': request['frame'], 'sourceArtifactSha256': input_record['sha256'],
                              'independentValue': summary['surfaceArea'],
                              'scipyVersion': __import__('scipy').__version__}}
    output = directory / 'measurement.json'
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, allow_nan=False, sort_keys=True)
        stream.write('\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', required=True)
    arguments = parser.parse_args()
    print(json.dumps(measure(arguments.request), allow_nan=False, sort_keys=True))
