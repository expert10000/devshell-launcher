"""Typed DAG execution for the fixed certified CGAL mesh capability."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
from broker import Broker, sha
from check_m3dm_roundtrip import read_obj, metrics

PORTS = {
    'qualified.cgal.mesh.validate': {'inputs': {}, 'outputs': {'mesh': 'mesh.obj.v1', 'handoff': 'math3d.handoff.v1'}},
    'mesh.inspect': {'inputs': {'mesh': 'mesh.obj.v1'}, 'outputs': {'metrics': 'mesh.metrics.v1'}},
    'math3d.promote': {'inputs': {'mesh': 'mesh.obj.v1', 'handoff': 'math3d.handoff.v1'},
                       'outputs': {'decision': 'math3d.promotion.v1'}},
}


def preflight(spec, broker):
    if spec.get('schemaVersion') != 1 or not isinstance(spec.get('nodes'), list) or not spec['nodes']:
        raise ValueError('Unsupported pipeline specification.')
    broker.discover()
    nodes = {}
    for node in spec['nodes']:
        name, kind = node.get('id'), node.get('kind')
        if not isinstance(name, str) or not re.fullmatch('[a-z][a-z0-9_-]{0,63}', name) or name in nodes:
            raise ValueError('Invalid or duplicate pipeline node ID.')
        if kind not in PORTS:
            raise ValueError('Unqualified or unknown pipeline capability: ' + str(kind))
        if set(node) != {'id', 'kind', 'inputs'} or not isinstance(node['inputs'], dict):
            raise ValueError('Unexpected node contract.')
        nodes[name] = node
    order, visiting, visited = [], set(), set()

    def visit(name):
        if name in visiting:
            raise ValueError('Cyclic pipeline.')
        if name in visited:
            return
        visiting.add(name)
        node = nodes[name]
        required = PORTS[node['kind']]['inputs']
        if set(node['inputs']) != set(required):
            raise ValueError('Missing or extra typed input port.')
        for port, reference in node['inputs'].items():
            if not isinstance(reference, str) or '.' not in reference:
                raise ValueError('Input must reference a node output.')
            source, output = reference.split('.', 1)
            if source not in nodes:
                raise ValueError('Unknown pipeline source node.')
            actual = PORTS[nodes[source]['kind']]['outputs'].get(output)
            if actual != required[port]:
                raise ValueError(f'Incompatible artifact type at {name}.{port}: {actual} != {required[port]}')
            visit(source)
        visiting.remove(name)
        visited.add(name)
        order.append(name)

    for name in nodes:
        visit(name)
    workers = [name for name in order if nodes[name]['kind'] == 'qualified.cgal.mesh.validate']
    if len(workers) != 1:
        raise ValueError('Exactly one qualified CGAL worker node is required.')
    for name in order:
        node = nodes[name]
        if node['kind'] == 'math3d.promote':
            if {value.split('.')[0] for value in node['inputs'].values()} != set(workers):
                raise ValueError('Promotion inputs must share the same verified worker job.')
    return nodes, order


def execute(spec, broker, output_root, wait_seconds=130):
    nodes, order = preflight(spec, broker)  # No worker starts before all ports and edges validate.
    output_root = Path(output_root).resolve()
    directory = output_root / uuid.uuid4().hex
    directory.mkdir(parents=True)
    cache_root = output_root / 'cache'
    cache_root.mkdir(exist_ok=True)
    outputs, records = {}, []
    entry = broker.capabilities[0]
    source = broker.paths['datasetRoot'] / 'math3d' / 'basic' / '01_tetrahedron.obj'
    if sha(source) != entry['referenceInputSha256']:
        raise ValueError('Qualified pipeline fixture changed.')
    try:
        for name in order:
            node = nodes[name]
            kind = node['kind']
            inputs = {port: outputs[reference] for port, reference in node['inputs'].items()}
            result = {'id': name, 'kind': kind, 'inputs': {port: {'type': item['type'], 'sha256': item['sha256']}
                                                         for port, item in inputs.items()},
                      'certificationRecordId': entry['recordId'], 'location': 'local'}
            if kind == 'qualified.cgal.mesh.validate':
                job = broker.submit({'schemaVersion': 1, 'runtimeId': 'cgal-win-conda',
                                     'capabilityId': 'mesh.interop.vtk-math3d',
                                     'input': {'path': str(source), 'sha256': sha(source)}})
                deadline = time.monotonic() + wait_seconds
                while job['state'] == 'running' and time.monotonic() < deadline:
                    time.sleep(0.1)
                    job = broker.snapshot(broker.jobs[job['jobId']])
                if job['state'] == 'running':
                    broker.cancel(job['jobId'])
                    raise TimeoutError('Pipeline worker exceeded its wait budget.')
                if job['state'] != 'succeeded':
                    raise ValueError('Pipeline worker ended ' + job['state'])
                result['sourceJobId'] = job['jobId']
                result['contractVersion'] = job['contractVersion']
                result['outputs'] = {}
                for port, filename in [('mesh', 'l5-positive.obj'), ('handoff', 'handoff.json')]:
                    raw = broker.artifact(job['jobId'], filename)
                    target = directory / f'{name}-{filename}'
                    target.write_bytes(raw)
                    result['outputs'][port] = {'type': PORTS[kind]['outputs'][port], 'path': str(target),
                                               'sha256': sha(target), 'sourceJobId': job['jobId']}
            elif kind == 'mesh.inspect':
                mesh = inputs['mesh']
                raw = Path(mesh['path']).read_bytes()
                if hashlib.sha256(raw).hexdigest() != mesh['sha256']:
                    raise ValueError('Pipeline input hash mismatch.')
                cache_key = hashlib.sha256((mesh['sha256'] + sha(Path(__file__).with_name('check_m3dm_roundtrip.py'))).encode()).hexdigest()
                cached = cache_root / (cache_key + '.json')
                if cached.is_file():
                    seal = cache_root / (cache_key + '.sha256')
                    if not seal.is_file() or seal.read_text(encoding='utf-8').strip() != sha(cached):
                        raise ValueError('Pipeline cache artifact hash mismatch.')
                    data = json.loads(cached.read_text(encoding='utf-8'))
                    if data.get('inputSha256') != mesh['sha256'] or data.get('cacheKey') != cache_key:
                        raise ValueError('Pipeline cache identity mismatch.')
                    result['cacheHit'] = True
                else:
                    vertices, faces = read_obj(Path(mesh['path']))
                    data = {'schemaVersion': 1, 'inputSha256': mesh['sha256'], 'cacheKey': cache_key,
                            'metrics': metrics(vertices, faces)}
                    with cached.open('x', encoding='utf-8') as stream:
                        json.dump(data, stream, separators=(',', ':'))
                    (cache_root / (cache_key + '.sha256')).write_text(sha(cached), encoding='utf-8')
                    result['cacheHit'] = False
                target = directory / f'{name}-metrics.json'
                target.write_bytes(cached.read_bytes())
                result['cacheKey'] = cache_key
                result['outputs'] = {'metrics': {'type': 'mesh.metrics.v1', 'path': str(target),
                                                'sha256': sha(target), 'sourceJobId': mesh['sourceJobId']}}
            else:
                source_job = inputs['mesh']['sourceJobId']
                for item in inputs.values():
                    if item['sourceJobId'] != source_job or sha(item['path']) != item['sha256']:
                        raise ValueError('Promotion input identity changed.')
                decision = broker.promote(source_job)
                if decision['decision'] != 'allowed':
                    raise ValueError('Promotion blocked: ' + '; '.join(decision['reasons']))
                target = directory / f'{name}-decision.json'
                target.write_text(json.dumps(decision, separators=(',', ':')), encoding='utf-8')
                result['sourceJobId'] = source_job
                result['contractVersion'] = decision['contractVersion']
                result['outputs'] = {'decision': {'type': 'math3d.promotion.v1', 'path': str(target),
                                                 'sha256': sha(target), 'sourceJobId': source_job}}
            for port, item in result['outputs'].items():
                outputs[name + '.' + port] = item
            records.append(result)
        state, error = 'succeeded', None
    except Exception as exc:
        state, error = 'failed', str(exc)
    record = {'schemaVersion': 1, 'kind': 'scientific.typed-pipeline', 'state': state,
              'error': error, 'spec': spec, 'specSha256': hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest(),
              'manifestSha256': sha(broker.paths['manifest']), 'nodes': records}
    with (directory / 'pipeline-result.json').open('x', encoding='utf-8') as stream:
        json.dump(record, stream, indent=2)
    (directory / 'pipeline-result.json.sha256').write_text(sha(directory / 'pipeline-result.json'), encoding='utf-8')
    return directory / 'pipeline-result.json', record


def verify(record_path):
    seal = Path(str(record_path) + '.sha256')
    if not seal.is_file() or seal.read_text(encoding='utf-8').strip() != sha(record_path):
        raise ValueError('Pipeline record hash mismatch.')
    record = json.loads(Path(record_path).read_text(encoding='utf-8'))
    if hashlib.sha256(json.dumps(record['spec'], sort_keys=True).encode()).hexdigest() != record['specSha256']:
        raise ValueError('Pipeline specification hash mismatch.')
    for node in record['nodes']:
        for output in node['outputs'].values():
            if sha(output['path']) != output['sha256']:
                raise ValueError('Pipeline output artifact hash mismatch.')
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['run', 'verify', 'replay'])
    parser.add_argument('--config')
    parser.add_argument('--spec', type=Path)
    parser.add_argument('--record', type=Path)
    parser.add_argument('--output-root', type=Path)
    args = parser.parse_args()
    if args.command == 'verify':
        print(json.dumps({'state': verify(args.record)['state']}))
        return
    broker = Broker(args.config)
    original = verify(args.record) if args.command == 'replay' else None
    spec = original['spec'] if original else json.loads(args.spec.read_text(encoding='utf-8'))
    path, result = execute(spec, broker, args.output_root or broker.jobs_root.parent / 'pipelines')
    if original and result['state'] == 'succeeded':
        before = [(n['id'], p, o['sha256']) for n in original['nodes'] for p, o in n['outputs'].items()
                  if p != 'decision']
        after = [(n['id'], p, o['sha256']) for n in result['nodes'] for p, o in n['outputs'].items()
                 if p != 'decision']
        if before != after:
            raise ValueError('Pipeline replay artifact hashes differ.')
    print(json.dumps({'record': str(path), 'state': result['state'], 'error': result['error']}))
    if result['state'] != 'succeeded':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
