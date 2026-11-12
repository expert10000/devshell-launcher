"""Current six-capability matrix and same-host CGAL/VTK diagnostic comparison."""
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
from six_capability_release import TARGETS, find_worker, verify as verify_release
from reproducibility_report import render_html

TOLERANCE = 1e-6
FIXTURE = 'scientific/fixtures/cgal/closed-tetra.obj'
OPERATIONS = {'cgal': 'cgal.validate', 'vtk': 'mesh.inspect'}


def require_consumer_identity(matrix, release):
    if matrix.get('consumer', {}).get('releaseIdentity') != release.get('math3dIdentity'):
        raise ValueError('Six-capability matrix MATH3D consumer identity drifted.')


def source_run(repo, dataset, root, name, python, worker=None, operation=None):
    directory = root / (name + '-' + uuid.uuid4().hex)
    directory.mkdir(parents=True)
    output = 'mesh.obj' if name == 'cgal' else 'mesh.vtp'
    request = {'schemaVersion': 1, 'runId': uuid.uuid4().hex,
               'runtimeId': 'cgal-win-conda' if name == 'cgal' else 'vtk-win-conda',
               'recipeId': OPERATIONS[name], 'operation': operation or OPERATIONS[name],
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
    if result.get('operation') != (operation or OPERATIONS[name]):
        raise ValueError(name + ' worker operation changed.')
    descriptor = load_saved_mesh(result_path, output)
    return {'resultPath': str(result_path), 'resultSha256': sha(result_path),
            'artifactPath': str(directory / output), 'artifactSha256': sha(directory / output),
            'runId': result['runId'], 'durationMs': result['durationMs'], 'descriptor': descriptor}


def compare(record, output_root, repetitions=5, shared_inspect_record=None,
            advisor_record=None, product_record=None, class_record=None, desktop_journey_record=None):
    if repetitions < 3 or repetitions > 15:
        raise ValueError('Use 3–15 measured repetitions.')
    if not all((shared_inspect_record, advisor_record, product_record, class_record, desktop_journey_record)):
        raise ValueError('Six-capability report requires shared, class, advisor, product and desktop journey evidence.')
    release = verify_release(record)
    repo = Path(release['repo'])
    certified = json.loads((Path(record).parent / 'certified.json').read_text(encoding='utf-8'))
    entries = {(item['runtimeId'], item['capabilityId']): item for item in certified['certifiedCapabilities']}
    if set(entries) != set(TARGETS.values()) or any(item['level'] != 'L9' for item in entries.values()):
        raise ValueError('Six current L9 entries are required.')
    configs = {name: json.loads(Path(release['profiles'][name]['config']).read_text(encoding='utf-8'))
               for name in ('inspect', 'vtk_read')}
    root = Path(output_root).resolve() / uuid.uuid4().hex
    root.mkdir(parents=True)
    dataset = root / 'datasets' / 'closed-tetra.obj'
    dataset.parent.mkdir()
    shutil.copyfile(repo / FIXTURE, dataset)
    cgal_worker = find_worker(repo, 'devshell_cgal_worker.exe',
                              entries[TARGETS['inspect']]['workerBinarySha256'])
    runners = {'cgal': (Path(configs['inspect']['python']), cgal_worker),
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
    comparison = {'schemaVersion': 1, 'kind': 'scientific.six-capability-cross-provider-diagnostic',
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
    matrix = {'schemaVersion': 2, 'kind': 'scientific.six-capability-current-matrix',
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
              'consumer': {'name': 'MATH3D', 'evidence': 'six broker/MATH3D smokes passed',
                           'releaseIdentity': release['math3dIdentity']}}
    shared = None
    if shared_inspect_record:
        from comparable_inspect import verify as verify_shared
        shared = verify_shared(shared_inspect_record)
        if shared['releaseRecordSha256'] != sha(record) or shared['sourceCommit'] != release['sourceCommit']:
            raise ValueError('Shared inspection scope is from another release.')
        matrix['sharedInspect'] = {'record': str(Path(shared_inspect_record).resolve()),
                                   'sha256': sha(shared_inspect_record),
                                   'contractSha256': shared['contractSha256'],
                                   'tiers': list(shared['tiers'])}
    from advisor import verify_shared_advice
    from math3d_inspect_product import verify as verify_product
    advice = verify_shared_advice(advisor_record)
    product = json.loads(Path(product_record).read_text(encoding='utf-8'))
    verify_product(product_record, shared_inspect_record, product['inputPath'])
    if (advice['scopeRecordSha256'] != sha(shared_inspect_record)
            or product['scopeRecordSha256'] != sha(shared_inspect_record)):
        raise ValueError('Advisor or product uses another shared scope.')
    matrix['advisor'] = {'record': str(Path(advisor_record).resolve()),
                         'sha256': sha(advisor_record), 'tier': advice['tier'],
                         'recommendation': advice['recommendation']}
    matrix['math3dProduct'] = {'record': str(Path(product_record).resolve()),
                               'sha256': sha(product_record), 'selectedProvider': product['selectedProvider']}
    from class_inspect_qualification import verify as verify_classes
    from desktop_inspect_journey import verify as verify_journey
    from inspect_ranking import policy as ranking_policy, rank_class
    classes = verify_classes(class_record)
    journey = verify_journey(desktop_journey_record, record, class_record)
    ranking, ranking_hash = ranking_policy(repo)
    if classes['releaseRecordSha256'] != sha(record) or journey['classRecordSha256'] != sha(class_record):
        raise ValueError('Bounded inspection or desktop journey belongs to another release.')
    matrix['boundedInspect'] = {'record': str(Path(class_record).resolve()), 'sha256': sha(class_record),
        'policySha256': classes['policySha256'], 'rankingPolicySha256': ranking_hash,
        'classes': {name: rank_class(saved, name, ranking) for name, saved in classes['classes'].items()}}
    matrix['desktopJourney'] = {'record': str(Path(desktop_journey_record).resolve()),
        'sha256': sha(desktop_journey_record),
        'runIds': {role: saved['runId'] for role, saved in journey['runs'].items()}}
    lines = ['# Six-capability reproducibility report', '',
             f"Source commit: `{release['sourceCommit']}`. Six current L0–L9 chains and broker/MATH3D smokes verified.", '',
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
              '- The six-capability release record verifies each current managed support chain and broker/MATH3D smoke.',
              f"- MATH3D identity `{release['math3dIdentity']['identitySha256']}` pins commit, build, package and consumer contract to every product smoke.",
              '- Requalify after source, environment, worker, contract or consumer drift.', '',
              '## Reproduce', '',
              f"`python tools/scientific-broker/six_capability_release.py verify --record \"{record}\"`",
              f"`python tools/scientific-broker/six_capability_report.py verify --record \"{root / 'report.json'}\"`", '']
    if shared:
        lines += ['## Qualified shared mesh.inspect scope', '',
                  f"Contract SHA-256: `{shared['contractSha256']}`. Current desktop L0–L9 and broker job/promotion gates passed for six matched closed fixtures.",
                  '| Tier | CGAL median ms | VTK median ms | Samples per provider |',
                  '|---|---:|---:|---:|']
        for tier, evidence in shared['tiers'].items():
            left = evidence['measurements']['cgal']['statistics']
            right = evidence['measurements']['vtk']['statistics']
            lines.append(f"| {tier} | {left['medianMs']} | {right['medianMs']} | {left['samples']} |")
        lines += ['', 'Advisor ranking is permitted only for these exact fixture and size tiers while the shared record remains current.', '']
    lines += ['## Bounded independent closed meshes', '',
              f"Class policy SHA-256: `{classes['policySha256']}`. Both desktop L5–L9 chains and "
              f"{len(classes['classes']) * classes['samples'] * 2} accepted broker jobs passed; "
              f"{len(classes['rejections'])} adverse broker jobs rejected.",
              '| Class | CGAL cold / warm median ms | VTK cold / warm median ms | Paired 95% intervals (cold; warm) | Decision |',
              '|---|---:|---:|---|---|']
    for name, saved in classes['classes'].items():
        decision = matrix['boundedInspect']['classes'][name]
        phases = decision.get('phases', {})
        cold, warm = phases.get('coldInvocationMs'), phases.get('warmExecutionMs')
        if not cold or not warm:
            lines.append(f"| {name} | unavailable | unavailable | unavailable | abstain: {decision['reason']} |")
            continue
        left, right = cold['mediansMs'], warm['mediansMs']
        lines.append(f"| {name} | {left['cgal-win-conda']} / {right['cgal-win-conda']} | "
                     f"{left['vtk-win-conda']} / {right['vtk-win-conda']} | "
                     f"{cold['pairedCgalMinusVtk95PctMs']}; {warm['pairedCgalMinusVtk95PctMs']} | "
                     f"{decision['recommendation'] or 'abstain'} |")
    lines += ['', 'A recommendation requires separate cold and warm advantages, paired uncertainty and resource limits. '
              'Inputs outside these verified classes fall back to direct MATH3D import.', '',
              '## Managed desktop product journey', '',
              'Automatic selection, manual override, direct fallback, cancellation and saved-document/viewport reload '
              'are sealed to the release and MATH3D consumer identity.', '']
    markdown = '\n'.join(lines)
    (root / 'comparison.json').write_text(json.dumps(comparison, separators=(',', ':')), encoding='utf-8')
    (root / 'matrix.json').write_text(json.dumps(matrix, separators=(',', ':')), encoding='utf-8')
    (root / 'reproducibility.md').write_text(markdown, encoding='utf-8')
    (root / 'reproducibility.html').write_text(render_html(markdown), encoding='utf-8')
    report = {'schemaVersion': 2, 'kind': 'scientific.six-capability-report',
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
        raise ValueError('Six-capability report seal changed.')
    report = json.loads(path.read_text(encoding='utf-8'))
    if report.get('schemaVersion') != 2 or report.get('kind') != 'scientific.six-capability-report':
        raise ValueError('Report contract changed.')
    release = verify_release(report['releaseRecord'])
    if report['sourceCommit'] != release['sourceCommit'] or report['releaseRecordSha256'] != sha(report['releaseRecord']):
        raise ValueError('Six-capability source release changed.')
    if any(sha(path.parent / name) != expected for name, expected in report['files'].items()):
        raise ValueError('Report artifact changed.')
    matrix = json.loads((path.parent / 'matrix.json').read_text(encoding='utf-8'))
    comparison = json.loads((path.parent / 'comparison.json').read_text(encoding='utf-8'))
    require_consumer_identity(matrix, release)
    from class_inspect_qualification import verify as verify_classes
    from desktop_inspect_journey import verify as verify_journey
    from inspect_ranking import policy as ranking_policy, rank_class
    class_ref, journey_ref = matrix['boundedInspect'], matrix['desktopJourney']
    if sha(class_ref['record']) != class_ref['sha256'] or sha(journey_ref['record']) != journey_ref['sha256']:
        raise ValueError('Bounded inspection or desktop journey matrix hash changed.')
    classes = verify_classes(class_ref['record'])
    journey = verify_journey(journey_ref['record'], report['releaseRecord'], class_ref['record'])
    ranking, ranking_hash = ranking_policy(release['repo'])
    if (class_ref['policySha256'] != classes['policySha256']
            or class_ref['rankingPolicySha256'] != ranking_hash
            or class_ref['classes'] != {name: rank_class(saved, name, ranking)
                                        for name, saved in classes['classes'].items()}
            or journey_ref['runIds'] != {role: saved['runId'] for role, saved in journey['runs'].items()}):
        raise ValueError('Bounded class ranking or desktop journey matrix drifted.')
    if matrix.get('sharedInspect'):
        from comparable_inspect import verify as verify_shared
        shared_ref = matrix['sharedInspect']
        if sha(shared_ref['record']) != shared_ref['sha256']:
            raise ValueError('Shared inspection matrix record changed.')
        shared = verify_shared(shared_ref['record'])
        if (shared['contractSha256'] != shared_ref['contractSha256']
                or shared['releaseRecordSha256'] != sha(report['releaseRecord'])
                or list(shared['tiers']) != shared_ref['tiers']):
            raise ValueError('Shared inspection matrix scope changed.')
    from advisor import verify_shared_advice
    from math3d_inspect_product import verify as verify_product
    advisor_ref, product_ref = matrix['advisor'], matrix['math3dProduct']
    if sha(advisor_ref['record']) != advisor_ref['sha256'] or sha(product_ref['record']) != product_ref['sha256']:
        raise ValueError('Advisor or MATH3D product matrix hash changed.')
    advice = verify_shared_advice(advisor_ref['record'])
    product = json.loads(Path(product_ref['record']).read_text(encoding='utf-8'))
    verify_product(product_ref['record'], matrix['sharedInspect']['record'], product['inputPath'])
    if (advice['tier'] != advisor_ref['tier'] or advice['recommendation'] != advisor_ref['recommendation']
            or product['selectedProvider'] != product_ref['selectedProvider']):
        raise ValueError('Advisor or MATH3D selection changed.')
    if (matrix['sourceCommit'] != release['sourceCommit'] or comparison['sourceCommit'] != release['sourceCommit']
            or len(matrix['rows']) != 6 or set((row['runtimeId'], row['capabilityId']) for row in matrix['rows']) != set(TARGETS.values())
            or comparison['operations'] != OPERATIONS or comparison['semanticVerdict'] != 'distinct-operations-no-backend-ranking'):
        raise ValueError('Matrix or operation semantics changed.')
    if any(row['recordId'] != release['profiles'][row['name']]['recordId']
           or [item['level'] for item in row['supportingRecords']] != [f'L{level}' for level in range(10)]
           for row in matrix['rows']):
        raise ValueError('Six-capability matrix support changed.')
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
    parser.add_argument('--shared-inspect-record')
    parser.add_argument('--advisor-record')
    parser.add_argument('--product-record')
    parser.add_argument('--class-record')
    parser.add_argument('--desktop-journey-record')
    args = parser.parse_args()
    if args.command == 'build':
        if not args.output_root:
            parser.error('build requires --output-root')
        path, report = compare(args.record, args.output_root, args.repetitions,
                               args.shared_inspect_record, args.advisor_record, args.product_record,
                               args.class_record, args.desktop_journey_record)
    else:
        path, report = args.record, verify(args.record)
    print(json.dumps({'record': str(path), 'sourceCommit': report['sourceCommit'], 'verdict': 'verified'}))
