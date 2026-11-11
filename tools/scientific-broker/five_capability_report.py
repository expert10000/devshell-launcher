"""Current five-capability matrix and same-host CGAL/VTK diagnostic comparison."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import uuid

from broker import sha
from differential import compare_descriptors, load_saved_mesh
from five_capability_release import TARGETS, find_worker, verify as verify_release
from reproducibility_report import render_html

TOLERANCE = 1e-6
FIXTURE = 'scientific/fixtures/cgal/closed-tetra.obj'
OPERATIONS = {'cgal': 'cgal.validate', 'vtk': 'mesh.inspect'}


def source_run(repo, dataset, root, name, python, worker=None):
    directory = root / (name + '-' + uuid.uuid4().hex)
    directory.mkdir(parents=True)
    output = 'mesh.obj' if name == 'cgal' else 'mesh.vtp'
    request = {'schemaVersion': 1, 'runId': uuid.uuid4().hex,
               'runtimeId': 'cgal-win-conda' if name == 'cgal' else 'vtk-win-conda',
               'recipeId': OPERATIONS[name], 'operation': OPERATIONS[name],
               'workingDirectory': str(directory), 'datasetRoot': str(dataset.parent),
               'timeoutSeconds': 120, 'parameters': {},
               'inputArtifacts': [{'path': str(dataset), 'sha256': sha(dataset),
                                   'datasetId': 'comparison/closed-tetra.obj'}],
               'outputArtifacts': [{'path': output}],
               'provenance': {'comparison': 'same tetrahedron; operation semantics differ'}}
    (directory / 'request.json').write_text(json.dumps(request, separators=(',', ':')), encoding='utf-8')
    script = repo / ('tools/scientific-cgal-worker.py' if name == 'cgal' else 'tools/scientific-mesh-worker.py')
    command = [str(python), str(script), '--request', str(directory / 'request.json')]
    if worker:
        command += ['--worker', str(worker)]
    prefix = Path(python).parent
    env = dict(os.environ)
    env['PATH'] = os.pathsep.join(str(prefix / part) for part in ('Library/bin', 'Library/usr/bin', 'Scripts')) + os.pathsep + env.get('PATH', '')
    env['PYTHONNOUSERSITE'] = '1'
    completed = subprocess.run(command, cwd=repo, env=env, capture_output=True, text=True, timeout=150)
    (directory / 'full.log').write_text(completed.stdout + completed.stderr, encoding='utf-8')
    result_path = directory / 'results.json'
    if completed.returncode or not result_path.is_file():
        raise ValueError(name + ' diagnostic worker failed: ' + completed.stderr[-1000:])
    result = json.loads(result_path.read_text(encoding='utf-8'))
    if result.get('state') != 'succeeded' or result['inputArtifacts'][0]['sha256'] != sha(dataset):
        raise ValueError(name + ' diagnostic result changed.')
    descriptor = load_saved_mesh(result_path, output)
    return {'resultPath': str(result_path), 'resultSha256': sha(result_path),
            'artifactPath': str(directory / output), 'artifactSha256': sha(directory / output),
            'runId': result['runId'], 'durationMs': result['durationMs'], 'descriptor': descriptor}


def compare(record, output_root, repetitions=5):
    if repetitions < 3 or repetitions > 15:
        raise ValueError('Use 3–15 measured repetitions.')
    release = verify_release(record)
    repo = Path(release['repo'])
    certified = json.loads((Path(record).parent / 'certified.json').read_text(encoding='utf-8'))
    entries = {(item['runtimeId'], item['capabilityId']): item for item in certified['certifiedCapabilities']}
    if set(entries) != set(TARGETS.values()) or any(item['level'] != 'L9' for item in entries.values()):
        raise ValueError('Five current L9 entries are required.')
    configs = {name: json.loads(Path(release['profiles'][name]['config']).read_text(encoding='utf-8'))
               for name in ('remesh', 'vtk_read')}
    root = Path(output_root).resolve() / uuid.uuid4().hex
    root.mkdir(parents=True)
    dataset = root / 'datasets' / 'closed-tetra.obj'
    dataset.parent.mkdir()
    shutil.copyfile(repo / FIXTURE, dataset)
    cgal_worker = find_worker(repo, 'devshell_cgal_worker.exe',
                              entries[TARGETS['remesh']]['workerBinarySha256'])
    runners = {'cgal': (Path(configs['remesh']['python']), cgal_worker),
               'vtk': (Path(configs['vtk_read']['python']), None)}
    warmups = {name: source_run(repo, dataset, root, name, *args)
               for name, args in runners.items()}
    observations = {name: [] for name in runners}
    for _ in range(repetitions):
        for name, args in runners.items():
            observations[name].append(source_run(repo, dataset, root, name, *args))
    geometry = compare_descriptors(observations['cgal'][0]['descriptor'],
                                   observations['vtk'][0]['descriptor'], TOLERANCE)
    if geometry['verdict'] != 'equivalent':
        raise ValueError('CGAL and VTK outputs differ on the pinned tetrahedron.')
    host = {'node': platform.node(), 'system': platform.system(), 'release': platform.release(),
            'machine': platform.machine()}
    comparison = {'schemaVersion': 1, 'kind': 'scientific.five-capability-cross-provider-diagnostic',
                  'sourceCommit': release['sourceCommit'], 'fixtureSha256': sha(dataset),
                  'host': host, 'operations': OPERATIONS, 'tolerance': TOLERANCE,
                  'semanticVerdict': 'distinct-operations-no-backend-ranking',
                  'geometry': geometry,
                  'measurements': {name: {'warmup': {key: value for key, value in warmups[name].items() if key != 'descriptor'},
                                          'runs': [{key: value for key, value in item.items() if key != 'descriptor'} for item in values],
                                          'medianWorkerMs': statistics.median(item['durationMs'] for item in values)}
                                   for name, values in observations.items()}}
    inventory_path = repo / '.scientific/runtime-report.json'
    inventory = json.loads(inventory_path.read_text(encoding='utf-8')) if inventory_path.is_file() else {}
    runtime_rows = {item['id']: item for item in inventory.get('runtimes', [])}
    try:
        observed = datetime.fromisoformat(inventory['generatedAt'].replace('Z', '+00:00'))
        inventory_state = 'current' if 0 <= (datetime.now(timezone.utc) - observed).total_seconds() <= 86400 else 'stale'
    except (KeyError, ValueError, TypeError):
        inventory_state = 'unavailable'
    matrix = {'schemaVersion': 1, 'kind': 'scientific.five-capability-current-matrix',
              'sourceCommit': release['sourceCommit'], 'releaseRecordSha256': sha(record),
              'certifiedSha256': sha(Path(record).parent / 'certified.json'),
              'inventorySha256': sha(inventory_path) if inventory_path.is_file() else None,
              'inventoryState': inventory_state,
              'rows': [{'name': name, 'runtimeId': identity[0], 'capabilityId': identity[1],
                        'level': 'L9', 'recordId': entries[identity]['recordId'],
                        'version': runtime_rows.get(identity[0], {}).get('version'),
                        'availability': runtime_rows.get(identity[0], {}).get('state', 'not-recorded'),
                        'supportingRecords': entries[identity]['supportingRecords']}
                       for name, identity in TARGETS.items()],
              'consumer': {'name': 'MATH3D', 'evidence': 'five broker/MATH3D smokes passed',
                           'releaseIdentity': 'not-pinned-by-five-capability-record'}}
    lines = ['# Five-capability reproducibility report', '',
             f"Source commit: `{release['sourceCommit']}`. Five current L0–L9 chains and broker/MATH3D smokes verified.", '',
             f"Runtime inventory: **{inventory_state}**; SHA-256 `{matrix['inventorySha256'] or 'unavailable'}`.", '',
             '| Capability | Provider | Level | Record |', '|---|---|---:|---|']
    for row in matrix['rows']:
        lines.append(f"| {row['capabilityId']} | {row['runtimeId']} | {row['level']} | `{row['recordId']}` |")
    lines += ['', '## CGAL and VTK shared tetrahedron', '',
              f"Fixture SHA-256: `{comparison['fixtureSha256']}`. Geometry verdict: **{geometry['verdict']}** at tolerance `{TOLERANCE}`.",
              f"CGAL `{OPERATIONS['cgal']}` median worker time: {comparison['measurements']['cgal']['medianWorkerMs']} ms; "
              f"VTK `{OPERATIONS['vtk']}`: {comparison['measurements']['vtk']['medianWorkerMs']} ms "
              f"({repetitions} measured runs after one warmup each, same host).",
              'These operations have different semantics. Timing is diagnostic and does not rank interchangeable backends.', '',
              '## Release scope', '',
              '- The five-capability release record verifies each current managed support chain and broker/MATH3D smoke.',
              '- MATH3D consumer behavior is pinned by source hashes and product smoke evidence; a separate MATH3D release identity is not yet sealed.',
              '- Requalify after source, environment, worker, contract or consumer drift.', '',
              '## Reproduce', '',
              f"`python tools/scientific-broker/five_capability_release.py verify --record \"{record}\"`",
              f"`python tools/scientific-broker/five_capability_report.py verify --record \"{root / 'report.json'}\"`", '']
    markdown = '\n'.join(lines)
    (root / 'comparison.json').write_text(json.dumps(comparison, separators=(',', ':')), encoding='utf-8')
    (root / 'matrix.json').write_text(json.dumps(matrix, separators=(',', ':')), encoding='utf-8')
    (root / 'reproducibility.md').write_text(markdown, encoding='utf-8')
    (root / 'reproducibility.html').write_text(render_html(markdown), encoding='utf-8')
    report = {'schemaVersion': 1, 'kind': 'scientific.five-capability-report',
              'createdAtUtc': datetime.now(timezone.utc).isoformat(), 'sourceCommit': release['sourceCommit'],
              'releaseRecord': str(Path(record).resolve()), 'releaseRecordSha256': sha(record),
              'files': {name: sha(root / name) for name in ('comparison.json', 'matrix.json', 'reproducibility.md', 'reproducibility.html')}}
    (root / 'report.json').write_text(json.dumps(report, separators=(',', ':')), encoding='utf-8')
    (root / 'report.json.sha256').write_text(sha(root / 'report.json'), encoding='utf-8')
    verify(root / 'report.json')
    return root / 'report.json', report


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text().strip():
        raise ValueError('Five-capability report seal changed.')
    report = json.loads(path.read_text(encoding='utf-8'))
    if report.get('schemaVersion') != 1 or report.get('kind') != 'scientific.five-capability-report':
        raise ValueError('Report contract changed.')
    release = verify_release(report['releaseRecord'])
    if report['sourceCommit'] != release['sourceCommit'] or report['releaseRecordSha256'] != sha(report['releaseRecord']):
        raise ValueError('Five-capability source release changed.')
    if any(sha(path.parent / name) != expected for name, expected in report['files'].items()):
        raise ValueError('Report artifact changed.')
    matrix = json.loads((path.parent / 'matrix.json').read_text(encoding='utf-8'))
    comparison = json.loads((path.parent / 'comparison.json').read_text(encoding='utf-8'))
    if (matrix['sourceCommit'] != release['sourceCommit'] or comparison['sourceCommit'] != release['sourceCommit']
            or len(matrix['rows']) != 5 or set((row['runtimeId'], row['capabilityId']) for row in matrix['rows']) != set(TARGETS.values())
            or comparison['operations'] != OPERATIONS or comparison['semanticVerdict'] != 'distinct-operations-no-backend-ranking'):
        raise ValueError('Matrix or operation semantics changed.')
    if any(row['recordId'] != release['profiles'][row['name']]['recordId']
           or [item['level'] for item in row['supportingRecords']] != [f'L{level}' for level in range(10)]
           for row in matrix['rows']):
        raise ValueError('Five-capability matrix support changed.')
    for name in OPERATIONS:
        for run in comparison['measurements'][name]['runs']:
            result = Path(run['resultPath'])
            artifact = Path(run['artifactPath'])
            if sha(result) != run['resultSha256'] or sha(artifact) != run['artifactSha256']:
                raise ValueError('Measured worker evidence changed.')
        if statistics.median(run['durationMs'] for run in comparison['measurements'][name]['runs']) != comparison['measurements'][name]['medianWorkerMs']:
            raise ValueError('Measured timing summary changed.')
    left = comparison['measurements']['cgal']['runs'][0]
    right = comparison['measurements']['vtk']['runs'][0]
    geometry = compare_descriptors(load_saved_mesh(left['resultPath'], 'mesh.obj'),
                                   load_saved_mesh(right['resultPath'], 'mesh.vtp'), comparison['tolerance'])
    if geometry != comparison['geometry'] or geometry['verdict'] != 'equivalent':
        raise ValueError('Measured geometry changed.')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('build', 'verify'))
    parser.add_argument('--record', required=True)
    parser.add_argument('--output-root')
    parser.add_argument('--repetitions', type=int, default=5)
    args = parser.parse_args()
    if args.command == 'build':
        if not args.output_root:
            parser.error('build requires --output-root')
        path, report = compare(args.record, args.output_root, args.repetitions)
    else:
        path, report = args.record, verify(args.record)
    print(json.dumps({'record': str(path), 'sourceCommit': report['sourceCommit'], 'verdict': 'verified'}))
