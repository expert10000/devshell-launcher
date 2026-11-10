"""Local guarded CGAL remesh: publish only a measured eligible closed mesh."""
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import uuid

from scientific_cgal_corpus import sha
from scientific_cgal_mesh_metrics import metrics
from scientific_cgal_surface_samples import surface_samples
from scientific_cgal_triangle_quality import quality


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scientific/cgal-worker/main.cpp'
METRICS = ROOT / 'tools/scientific_cgal_mesh_metrics.py'
SAMPLES = ROOT / 'tools/scientific_cgal_surface_samples.py'
QUALITY = ROOT / 'tools/scientific_cgal_triangle_quality.py'
POLICY_FILE = ROOT / 'schemas/scientific-remesh-guard.v1.json'
POLICY_DOCUMENT = json.loads(POLICY_FILE.read_text(encoding='utf-8'))
if POLICY_DOCUMENT['schemaVersion'] != 1 or POLICY_DOCUMENT['policyId'] != 'cgal.remesh.closed-genus-zero':
    raise ValueError('Unsupported remesh guard policy.')
POLICY = {name: POLICY_DOCUMENT[name] for name in ('relativeVolumeTolerance',
          'relativeSampleTolerance', 'minimumAngleDegrees', 'minimumShapeScore')}


def closed_input(measured):
    if (measured['components'] != 1 or measured['boundaryEdges'] != 0
            or measured['boundaryLoops'] != 0 or measured['eulerCharacteristic'] != 2
            or measured['maximumEdgeIncidence'] != 2 or measured['degenerateFaces'] != 0
            or measured['signedVolume'] <= 0 or measured['faces'] > 2048
            or measured['vertices'] > 4096):
        raise ValueError('Guard requires a bounded outward closed genus-zero triangle mesh.')


def assess(original, candidate, samples, shape):
    diagonal = math.sqrt(sum((high-low)**2 for low, high in original['bounds']))
    if diagonal <= 0:
        raise ValueError('Guard input has zero spatial extent.')
    volume_drift = abs(candidate['signedVolume']-original['signedVolume']) / original['signedVolume']
    distance = max(value['maximumDistance'] for value in samples.values()) / diagonal
    checks = {'closedTopology': candidate['components'] == 1 and candidate['boundaryEdges'] == 0
              and candidate['boundaryLoops'] == 0 and candidate['eulerCharacteristic'] == 2
              and candidate['maximumEdgeIncidence'] == 2 and candidate['degenerateFaces'] == 0,
              'relativeVolume': volume_drift <= POLICY['relativeVolumeTolerance'],
              'relativeSampledSurface': distance <= POLICY['relativeSampleTolerance'],
              'minimumAngle': shape['minimumAngleDegrees'] >= POLICY['minimumAngleDegrees'],
              'minimumShape': shape['minimumShapeScore'] >= POLICY['minimumShapeScore']}
    return {'relativeVolumeDrift': volume_drift, 'relativeSampledDistance': distance,
            'checks': checks, 'eligible': all(checks.values())}


def measurements(source, candidate):
    original, measured = metrics(source), metrics(candidate)
    closed_input(original)
    samples, shape = surface_samples(source, candidate), quality(candidate)
    return {'inputMetrics': original, 'candidateMetrics': measured,
            'surfaceSamples': samples, 'quality': shape,
            'decision': assess(original, measured, samples, shape)}


def check_artifacts(report, root):
    source, candidate, accepted, result_path = (root / name for name in
                                                ('input.obj', 'candidate.obj', 'accepted.obj', 'results.json'))
    if (sha(source) != report['inputSha256'] or sha(candidate) != report['candidateSha256']
            or sha(result_path) != report['resultSha256']):
        raise ValueError('Guarded remesh artifact changed.')
    result = json.loads(result_path.read_text(encoding='utf-8-sig'))
    measured = measurements(source, candidate)
    if (result.get('schemaVersion') != 1 or result.get('recipeId') != 'cgal.remesh'
            or result.get('state') != 'succeeded' or result.get('exitCode') != 0
            or result.get('after', {}).get('faces') != measured['candidateMetrics']['faces']
            or result['after'].get('boundaryEdges') != measured['candidateMetrics']['boundaryEdges']
            or report['measurements'] != measured):
        raise ValueError('Guarded remesh measurement changed.')
    if measured['decision']['eligible']:
        if (report['state'] != 'accepted' or sha(accepted) != report['acceptedSha256']
                or accepted.read_bytes() != candidate.read_bytes()):
            raise ValueError('Guarded remesh accepted output changed.')
    elif report['state'] != 'rejected' or report['acceptedSha256'] is not None or accepted.exists():
        raise ValueError('Guarded remesh published a rejected output.')


def run(worker, prefix, input_path, target_edge, iterations, preserve_boundary, output_root):
    worker = Path(worker).resolve(strict=True)
    prefix = Path(prefix).resolve(strict=True)
    source_path = Path(input_path).resolve(strict=True)
    if (not math.isfinite(target_edge) or target_edge <= 0 or not 1 <= iterations <= 10
            or preserve_boundary not in (0, 1)):
        raise ValueError('Guarded remesh parameters are invalid.')
    closed_input(metrics(source_path))
    root = Path(output_root).resolve() / uuid.uuid4().hex
    root.mkdir(parents=True)
    source, candidate, accepted = (root / name for name in
                                   ('input.obj', 'candidate.obj', 'accepted.obj'))
    shutil.copyfile(source_path, source)
    environment = os.environ.copy()
    environment['PATH'] = os.pathsep.join((str(prefix), str(prefix / 'Library/bin'),
                                           str(prefix / 'Scripts'), environment.get('PATH', '')))
    process = subprocess.run([str(worker), 'remesh', str(source), str(candidate),
                              format(target_edge, '.12g'), str(iterations), str(preserve_boundary)],
                             cwd=root, env=environment, capture_output=True, text=True,
                             encoding='utf-8', errors='replace', timeout=60)
    (root / 'stdout.log').write_text(process.stdout, encoding='utf-8')
    (root / 'stderr.log').write_text(process.stderr, encoding='utf-8')
    if process.returncode or not candidate.is_file():
        raise ValueError('Native guarded remesh failed: ' + process.stderr[-300:])
    measured = measurements(source, candidate)
    if measured['decision']['eligible']:
        shutil.copyfile(candidate, accepted)
    report = {'schemaVersion': 1, 'kind': 'scientific.cgal-remesh-guarded',
              'createdAtUtc': datetime.now(timezone.utc).isoformat(),
              'workerPath': str(worker), 'workerSha256': sha(worker),
              'workerSourceSha256': sha(SOURCE), 'metricsSourceSha256': sha(METRICS),
              'samplesSourceSha256': sha(SAMPLES), 'qualitySourceSha256': sha(QUALITY),
              'guardSourceSha256': sha(Path(__file__)), 'runtimePrefix': str(prefix),
              'sourcePath': str(source_path), 'sourceSha256': sha(source_path),
              'inputSha256': sha(source), 'candidateSha256': sha(candidate),
              'acceptedSha256': sha(accepted) if accepted.exists() else None,
              'resultSha256': sha(root / 'results.json'),
              'policyId': POLICY_DOCUMENT['policyId'], 'policyVersion': POLICY_DOCUMENT['schemaVersion'],
              'policySha256': sha(POLICY_FILE),
              'parameters': {'targetEdge': target_edge, 'iterations': iterations,
                             'preserveBoundary': preserve_boundary},
              'policy': POLICY, 'measurements': measured,
              'state': 'accepted' if accepted.exists() else 'rejected'}
    target = root / 'guarded.json'
    with target.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, separators=(',', ':'))
    Path(str(target) + '.sha256').write_text(sha(target), encoding='utf-8')
    verify(target)
    return target, report


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('Guarded remesh report hash mismatch.')
    report = json.loads(path.read_text(encoding='utf-8'))
    params = report['parameters']
    source_path = Path(report['sourcePath']).resolve(strict=True)
    if (report.get('schemaVersion') != 1 or report.get('kind') != 'scientific.cgal-remesh-guarded'
            or report.get('policy') != POLICY or report.get('policyId') != POLICY_DOCUMENT['policyId']
            or report.get('policyVersion') != POLICY_DOCUMENT['schemaVersion']
            or report.get('policySha256') != sha(POLICY_FILE)
            or sha(source_path) != report.get('sourceSha256')
            or sha(Path(report['workerPath']).resolve(strict=True)) != report.get('workerSha256')
            or sha(SOURCE) != report.get('workerSourceSha256')
            or sha(METRICS) != report.get('metricsSourceSha256')
            or sha(SAMPLES) != report.get('samplesSourceSha256')
            or sha(QUALITY) != report.get('qualitySourceSha256')
            or sha(Path(__file__)) != report.get('guardSourceSha256')
            or not isinstance(params.get('targetEdge'), (float, int))
            or not math.isfinite(params['targetEdge']) or params['targetEdge'] <= 0
            or params.get('iterations') not in range(1, 11)
            or params.get('preserveBoundary') not in (0, 1)):
        raise ValueError('Guarded remesh identity changed.')
    if report['inputSha256'] != report['sourceSha256']:
        raise ValueError('Guarded remesh input copy changed.')
    check_artifacts(report, path.parent)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('run', 'verify'))
    parser.add_argument('--worker')
    parser.add_argument('--prefix')
    parser.add_argument('--input')
    parser.add_argument('--target-edge', type=float)
    parser.add_argument('--iterations', type=int)
    parser.add_argument('--preserve-boundary', type=int, default=0)
    parser.add_argument('--output-root')
    parser.add_argument('--report')
    options = parser.parse_args()
    if options.command == 'run':
        if not all((options.worker, options.prefix, options.input, options.target_edge,
                    options.iterations, options.output_root)):
            parser.error('run requires worker, prefix, input, target-edge, iterations and output-root')
        target, value = run(options.worker, options.prefix, options.input,
                            options.target_edge, options.iterations, options.preserve_boundary,
                            options.output_root)
    else:
        if not options.report:
            parser.error('verify requires report')
        target, value = Path(options.report).resolve(), verify(options.report)
    print(json.dumps({'report': str(target), 'state': value['state'],
                      'accepted': value['acceptedSha256'] is not None}))
