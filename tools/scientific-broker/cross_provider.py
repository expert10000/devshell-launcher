"""Shared-fixture CGAL/VTK comparison with independent certification and benchmark gates."""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import uuid

from benchmark import digest as benchmark_digest
from broker import Broker, sha
from differential import compare_descriptors, load_saved_mesh
from release_certification import verify_release

SUITE = 'scientific.cross-provider.mesh.v1'
ARTIFACTS = {'cgal': 'positive/l5-positive.obj', 'vtk': 'positive/l5-positive.vtp'}


def benchmark_record(path):
    if path is None:
        return None
    record = json.loads(Path(path).read_text(encoding='utf-8'))
    identity = {key: value for key, value in record.items() if key != 'recordId'}
    if record.get('schemaVersion') != 1 or record.get('recordId') != benchmark_digest(identity):
        raise ValueError('Benchmark identity changed.')
    return record


def certification(report, runtime_id, config_path):
    if report['verdict'] != 'qualified':
        return None, 'Release gate is ' + report['verdict'] + ': ' + '; '.join(report['reasons'])
    entry = next((item for item in report['capabilities'] if item['runtimeId'] == runtime_id
                  and item['level'] == 'L9' and len(item.get('supportingRecords', [])) == 10), None)
    if entry is None:
        return None, runtime_id + ' has no L9 capability in the verified release report.'
    if config_path is None:
        return None, runtime_id + ' has no live broker configuration for current certification verification.'
    try:
        broker = Broker(config_path)
        if not any(item.get('recordId') == entry['recordId'] for item in broker.capabilities):
            raise ValueError('Deployed broker qualification differs from the release report.')
    except (ValueError, OSError, KeyError) as error:
        return None, runtime_id + ' current broker evidence is stale: ' + str(error)
    return entry, None


def performance(left, right, cgal_entry, vtk_entry, fixture):
    reasons = []
    for name, record, entry in (('CGAL', left, cgal_entry), ('VTK', right, vtk_entry)):
        if record is None:
            reasons.append(name + ' benchmark is missing.')
            continue
        runtime = 'cgal-win-conda' if name == 'CGAL' else 'vtk-win-conda'
        if record.get('runtimeId') != runtime:
            reasons.append(name + ' benchmark provider differs from its source run.')
        if entry is None or record.get('certificationRecordId') != entry['recordId']:
            reasons.append(name + ' benchmark is not tied to current L9 certification.')
        if record.get('inputSha256') != fixture:
            reasons.append(name + ' benchmark fixture differs from the shared mesh.')
    if left is not None and right is not None:
        for key in ('benchmarkId', 'hostFingerprintSha256', 'policy'):
            if left.get(key) != right.get(key):
                reasons.append(key + ' differs between benchmarks.')
        if set(left.get('tiers', {})) != set(right.get('tiers', {})):
            reasons.append('Benchmark tiers differ.')
        else:
            for tier in left['tiers']:
                if left['tiers'][tier].get('batchSize') != right['tiers'][tier].get('batchSize'):
                    reasons.append(tier + ' batch size differs.')
    if reasons:
        return {'verdict': 'inconclusive', 'reasons': reasons, 'cgalBenchmarkRunId': left.get('benchmarkRunId') if left else None,
                'vtkBenchmarkRunId': right.get('benchmarkRunId') if right else None, 'tiers': {}}
    tiers = {}
    for name in left['tiers']:
        cgal_ms, vtk_ms = left['tiers'][name]['medianWorkerDurationMs'], right['tiers'][name]['medianWorkerDurationMs']
        tiers[name] = {'cgalMedianWorkerMs': cgal_ms, 'vtkMedianWorkerMs': vtk_ms,
                       'vtkToCgalRatio': round(vtk_ms / cgal_ms, 6) if cgal_ms > 0 else None}
    return {'verdict': 'comparable', 'reasons': [], 'cgalBenchmarkRunId': left['benchmarkRunId'],
            'vtkBenchmarkRunId': right['benchmarkRunId'], 'tiers': tiers}


def assess(paths, tolerance):
    if not math.isfinite(tolerance) or not 0 < tolerance <= 0.01:
        raise ValueError('Tolerance must be finite and between zero and 0.01.')
    releases = {name: verify_release(paths[name]) for name in ('cgalRelease', 'vtkRelease')}
    entries = {name: certification(releases[name + 'Release'], runtime, paths.get(name + 'Config'))[0]
               for name, runtime in (('cgal', 'cgal-win-conda'), ('vtk', 'vtk-win-conda'))}
    reasons = [reason for name, runtime in (('cgal', 'cgal-win-conda'), ('vtk', 'vtk-win-conda'))
               if (reason := certification(releases[name + 'Release'], runtime, paths.get(name + 'Config'))[1])]
    descriptors = {name: load_saved_mesh(paths[name + 'Result'], ARTIFACTS[name]) for name in ('cgal', 'vtk')}
    for name, runtime in (('cgal', 'cgal-win-conda'), ('vtk', 'vtk-win-conda')):
        if descriptors[name]['runtimeId'] != runtime:
            raise ValueError(name.upper() + ' source run has the wrong provider identity.')
    inputs = {}
    for name in ('cgal', 'vtk'):
        result = json.loads(Path(paths[name + 'Result']).read_text(encoding='utf-8'))
        inputs[name] = next((item['sha256'] for item in result.get('inputArtifacts', [])
                             if item.get('datasetId') == 'math3d/basic/01_tetrahedron.obj'), None)
    if not inputs['cgal'] or inputs['cgal'] != inputs['vtk']:
        raise ValueError('CGAL and VTK source runs do not use the same registered tetrahedron fixture.')
    geometry = compare_descriptors(descriptors['cgal'], descriptors['vtk'], tolerance)
    checks = geometry.get('checks', {})
    dimensions = {'geometry': bool(checks.get('surface') and checks.get('area')),
                  'topology': bool(checks.get('topology')),
                  'orientation': bool(checks.get('orientation') and checks.get('signedVolume')),
                  'scale': bool(checks.get('bounds') and checks.get('area'))}
    metrics = performance(benchmark_record(paths.get('cgalBenchmark')), benchmark_record(paths.get('vtkBenchmark')),
                          entries['cgal'], entries['vtk'], inputs['cgal'])
    if geometry.get('verdict') != 'equivalent':
        verdict = 'failed'
        reasons.append('The saved meshes differ under the declared tolerance.')
    elif not all(entries.values()):
        verdict = 'blocked'
    elif metrics['verdict'] != 'comparable':
        verdict = 'inconclusive'
    else:
        verdict = 'passed'
    return {'schemaVersion': 1, 'suiteId': SUITE, 'verdict': verdict, 'reasons': reasons,
            'tolerance': tolerance, 'fixtureSha256': inputs['cgal'],
            'certifications': {name: {'releaseId': releases[name + 'Release']['releaseId'],
                                      'recordId': entries[name]['recordId'] if entries[name] else None,
                                      'state': 'current' if entries[name] else 'blocked'} for name in ('cgal', 'vtk')},
            'sourceRuns': {name: {'runId': descriptors[name]['runId'], 'resultPath': paths[name + 'Result'],
                                  'artifactPath': descriptors[name]['artifactPath'],
                                  'artifactSha256': descriptors[name]['artifactSha256'],
                                  'runFingerprintSha256': descriptors[name].get('runFingerprintSha256'),
                                  'contractFingerprintSha256': descriptors[name].get('contractFingerprintSha256')}
                           for name in ('cgal', 'vtk')},
            'dimensions': dimensions, 'meshComparison': geometry, 'performance': metrics}


def generate(paths, tolerance, output_root):
    paths = {key: str(Path(value).resolve(strict=True)) for key, value in paths.items() if value is not None}
    result = assess(paths, tolerance)
    result['createdAtUtc'] = datetime.now(timezone.utc).isoformat()
    result['sourceSha256'] = sha(Path(__file__))
    result['sources'] = {key: {'path': value, 'sha256': sha(value)} for key, value in paths.items()}
    root = Path(output_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    path = root / (uuid.uuid4().hex + '.json')
    with path.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    Path(str(path) + '.sha256').write_text(sha(path), encoding='utf-8')
    return path, result


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('Cross-provider record hash mismatch.')
    saved = json.loads(path.read_text(encoding='utf-8'))
    if saved.get('suiteId') != SUITE or saved.get('sourceSha256') != sha(Path(__file__)):
        raise ValueError('Cross-provider suite changed.')
    paths = {key: item['path'] for key, item in saved['sources'].items()}
    if any(sha(item['path']) != item['sha256'] for item in saved['sources'].values()):
        raise ValueError('Cross-provider source evidence changed.')
    assessed = assess(paths, saved['tolerance'])
    if any(saved.get(key) != value for key, value in assessed.items()):
        raise ValueError('Cross-provider verdict changed.')
    return saved


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('compare', 'verify'))
    for name in ('cgal-release', 'vtk-release', 'cgal-result', 'vtk-result', 'cgal-benchmark', 'vtk-benchmark',
                 'cgal-config', 'vtk-config'):
        parser.add_argument('--' + name)
    parser.add_argument('--tolerance', type=float, default=1e-6)
    parser.add_argument('--output-root')
    parser.add_argument('--record')
    args = parser.parse_args()
    if args.command == 'compare':
        if not all((args.cgal_release, args.cgal_result, args.vtk_result, args.output_root)):
            parser.error('compare requires a CGAL release, both source runs and an output root')
        if not math.isfinite(args.tolerance) or not 0 < args.tolerance <= 0.01:
            parser.error('tolerance must be between zero and 0.01')
        paths = {'cgalRelease': args.cgal_release, 'vtkRelease': args.vtk_release or args.cgal_release,
                 'cgalResult': args.cgal_result, 'vtkResult': args.vtk_result,
                 'cgalBenchmark': args.cgal_benchmark, 'vtkBenchmark': args.vtk_benchmark,
                 'cgalConfig': args.cgal_config, 'vtkConfig': args.vtk_config}
        path, saved = generate(paths, args.tolerance, args.output_root)
    else:
        if not args.record:
            parser.error('verify requires --record')
        path, saved = args.record, verify(args.record)
    print(json.dumps({'record': str(path), 'verdict': saved['verdict'], 'dimensions': saved['dimensions'],
                      'performance': saved['performance']['verdict'], 'reasons': saved['reasons']}))


if __name__ == '__main__':
    main()
