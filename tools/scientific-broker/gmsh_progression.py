"""Local Gmsh DS-SCI-055/056/057 evidence, gated below release certification."""
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid

from broker import sha
from gmsh_foundation import verify as verify_foundation, mesh_inspection


ROOT = Path(__file__).resolve().parents[2]
SUITE = 'scientific.gmsh.local-progression.v1'
SOURCES = [
    ROOT / 'tools' / 'scientific-gmsh-worker.py',
    ROOT / 'tools' / 'scientific_worker_contract.py',
    ROOT / 'tools' / 'scientific-gmsh-handoff.py',
    ROOT / 'tools' / 'scientific-gmsh-vtk-consumer.py',
    ROOT / 'tools' / 'math3d-gmsh-import-handoff.mjs',
    Path(__file__),
]


def call(argv, *, timeout=90, cwd=ROOT, env=None, allowed=(0,)):
    process = subprocess.run([str(value) for value in argv], cwd=cwd, env=env,
                             capture_output=True, text=True, timeout=timeout, errors='replace')
    if process.returncode not in allowed:
        raise RuntimeError(f'{argv[0]} exited {process.returncode}: {process.stdout[-1200:]} {process.stderr[-1200:]}')
    return process


def worker_case(directory, python, dataset, *, parameters, mutate=False, expected='succeeded'):
    directory.mkdir()
    fixture = dataset / 'square.geo'
    if mutate:
        fixture = dataset / 'tampered.geo'
        fixture.write_text((dataset / 'square.geo').read_text() + '\n// changed\n', encoding='utf-8')
    request = {'schemaVersion': 1, 'runId': uuid.uuid4().hex, 'runtimeId': 'gmsh-win-conda',
               'recipeId': 'gmsh.mesh2d', 'workingDirectory': str(directory), 'datasetRoot': str(dataset),
               'inputArtifacts': [{'path': str(fixture), 'sha256': sha(fixture)}],
               'outputArtifacts': [{'path': 'square.msh'}], 'parameters': parameters}
    (directory / 'request.json').write_text(json.dumps(request, indent=2), encoding='utf-8')
    env = dict(os.environ)
    env['PATH'] = str(Path(python).parent / 'Library' / 'bin') + os.pathsep + env.get('PATH', '')
    process = call([python, ROOT / 'tools' / 'scientific-gmsh-worker.py', '--request', directory / 'request.json'],
                   cwd=ROOT / 'tools', env=env, allowed=(0, 1))
    (directory / 'full.log').write_text(process.stdout + process.stderr, encoding='utf-8')
    result = json.loads((directory / 'results.json').read_text(encoding='utf-8'))
    artifact = directory / 'square.msh'
    if result['state'] != expected or (process.returncode == 0) != (expected == 'succeeded'):
        raise RuntimeError('Gmsh worker case ended in the wrong state.')
    if expected == 'succeeded':
        if len(result['artifacts']) != 1 or result['artifacts'][0]['sha256'] != sha(artifact):
            raise RuntimeError('Gmsh worker artifact hash differs.')
    elif artifact.exists() or result['artifacts'] or not result['diagnostics']:
        raise RuntimeError('Rejected Gmsh request has an artifact or no diagnostic.')
    return {'runId': request['runId'], 'state': expected, 'request': str(directory / 'request.json'),
            'result': str(directory / 'results.json'), 'log': str(directory / 'full.log'),
            'artifact': str(artifact) if expected == 'succeeded' else None}


def seal(directory, ticket, body, sources, files):
    record = {'schemaVersion': 1, 'suiteId': SUITE, 'ticket': ticket,
              'createdAtUtc': datetime.now(timezone.utc).isoformat(),
              'releaseCertified': False, 'sources': sources,
              'fileHashes': {str(path): sha(path) for path in files}, **body}
    path = directory / (ticket + '.json')
    path.write_text(json.dumps(record, indent=2), encoding='utf-8')
    Path(str(path) + '.sha256').write_text(sha(path), encoding='utf-8')
    return path


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('Gmsh progression record hash mismatch.')
    record = json.loads(path.read_text(encoding='utf-8'))
    if record.get('suiteId') != SUITE or record.get('releaseCertified') is not False:
        raise ValueError('Invalid Gmsh progression identity.')
    if any(sha(source) != digest for source, digest in record['sources'].items()):
        raise ValueError('Gmsh progression source drift.')
    if any(sha(file) != digest for file, digest in record['fileHashes'].items()):
        raise ValueError('Gmsh progression evidence hash mismatch.')
    foundation = verify_foundation(record['foundation'])
    if record['foundationSha256'] != sha(record['foundation']) or foundation['releaseCertified'] is not False:
        raise ValueError('Gmsh foundation changed.')
    ticket = record['ticket']
    if ticket == 'DS-SCI-055':
        for case in record['rejections'].values():
            child = json.loads(Path(case['result']).read_text(encoding='utf-8'))
            if child['state'] != 'failed' or child['artifacts'] or not child['diagnostics']:
                raise ValueError('Gmsh rejection evidence changed.')
        if record['verdict'] != 'passed':
            raise ValueError('Gmsh worker conformance verdict changed.')
    elif ticket == 'DS-SCI-056':
        if sha(record['sourceL5']) != record['sourceL5Sha256'] or verify(record['sourceL5'])['ticket'] != 'DS-SCI-055':
            raise ValueError('Gmsh L5 worker evidence changed.')
        cases = record['runs']
        if len(cases) != 2 or any(json.loads(Path(case['result']).read_text())['state'] != 'succeeded' for case in cases):
            raise ValueError('Gmsh repeat run is missing.')
        if any(sha(case['artifact']) != record['artifactSha256'] for case in cases):
            raise ValueError('Gmsh artifact did not reproduce byte-for-byte.')
        if any(json.loads(Path(case['result']).read_text())['artifacts'][0]['sha256'] != record['artifactSha256']
               for case in cases):
            raise ValueError('Gmsh worker artifact registration changed.')
        if any(mesh_inspection(record['python'], case['artifact']) != record['reload'] for case in cases):
            raise ValueError('Gmsh independent reload changed.')
    elif ticket == 'DS-SCI-057':
        source = verify(record['sourceL6'])
        if source['ticket'] != 'DS-SCI-056' or sha(record['sourceL6']) != record['sourceL6Sha256']:
            raise ValueError('Gmsh L6 source evidence changed.')
        handoff = json.loads(Path(record['handoffReport']).read_text(encoding='utf-8'))
        vtk = json.loads(Path(record['vtkResult']).read_text(encoding='utf-8'))
        math3d = json.loads(Path(record['math3dResult']).read_text(encoding='utf-8'))
        output = Path(record['handoffReport']).with_name('handoff.obj')
        if (handoff['sourceMshSha256'] != source['artifactSha256']
                or handoff['outputObjSha256'] != sha(output)
                or not comparable(handoff, vtk, math3d)) or any(
                json.loads(Path(record[key]).read_text())['state'] != 'rejected'
                for key in ('vtkRejection', 'math3dRejection')):
            raise ValueError('Gmsh handoff consumer verdict changed.')
    else:
        raise ValueError('Unknown Gmsh progression ticket.')
    return record


def comparable(handoff, vtk, math3d):
    if vtk.get('state') != 'accepted' or math3d.get('state') != 'accepted':
        return False
    if not handoff['outputObjSha256'] == vtk['inputObjSha256'] == math3d['inputObjSha256']:
        return False
    for key in ('points', 'triangles', 'boundaryEdges', 'nonManifoldEdges'):
        if not handoff[key] == vtk[key] == math3d[key]:
            return False
    for key in ('bounds',):
        if any(not math.isfinite(value) for item in (handoff, vtk, math3d) for value in item[key]):
            return False
        if any(abs(a-b) > 1e-6 for a,b in zip(handoff[key], vtk[key])) or any(
                abs(a-b) > 1e-6 for a,b in zip(handoff[key], math3d[key])):
            return False
    return all(math.isfinite(item['signedAreaXY']) and abs(item['signedAreaXY'] - 1) <= 1e-6
               for item in (handoff, vtk, math3d))


def run(foundation_path, vtk_python, checkout, output_root):
    foundation_path = Path(foundation_path).resolve(strict=True)
    foundation = verify_foundation(foundation_path)
    python = foundation['sources']['python']['path']
    vtk_python = str(Path(vtk_python).resolve(strict=True))
    checkout = Path(checkout).resolve(strict=True)
    importer = checkout / 'renderer' / 'src' / 'mesh' / 'surfaceMesh.ts'
    node = shutil.which('node')
    if node is None:
        raise ValueError('Node is required for the MATH3D consumer check.')
    sources = {str(path): sha(path) for path in SOURCES + [importer, Path(vtk_python), Path(python), Path(node)]}
    directory = Path(output_root).resolve() / uuid.uuid4().hex
    directory.mkdir(parents=True, exist_ok=False)
    dataset = directory / 'dataset'
    dataset.mkdir()
    shutil.copyfile(foundation['sources']['fixture']['path'], dataset / 'square.geo')
    foundation_fields = {'foundation': str(foundation_path), 'foundationSha256': sha(foundation_path),
                         'python': python, 'vtkPython': vtk_python, 'math3dCheckout': str(checkout)}
    rejections = {
        'tamperedFixture': worker_case(directory / 'tampered', python, dataset,
                                       parameters={'meshSize': 0.2}, mutate=True, expected='failed'),
        'unknownParameter': worker_case(directory / 'unknown', python, dataset,
                                        parameters={'meshSize': 0.2, 'unregistered': 1}, expected='failed')}
    files55 = [dataset / 'square.geo', dataset / 'tampered.geo'] + [
        Path(case[key]) for case in rejections.values() for key in ('request', 'result', 'log')]
    l5 = seal(directory, 'DS-SCI-055', {**foundation_fields, 'verdict': 'passed',
              'positiveSourceRunId': foundation['evidence']['cases']['positive']['runId'],
              'rejections': rejections}, sources, files55)
    verify(l5)
    repeats = [worker_case(directory / f'repeat-{i}', python, dataset, parameters={'meshSize': 0.2}) for i in range(2)]
    hashes = [sha(case['artifact']) for case in repeats]
    reloads = [mesh_inspection(python, case['artifact']) for case in repeats]
    if hashes[0] != hashes[1] or reloads[0] != reloads[1]:
        raise RuntimeError('Gmsh repeated output or independent reload differs.')
    files56 = [Path(case[key]) for case in repeats for key in ('request', 'result', 'log', 'artifact')]
    l6 = seal(directory, 'DS-SCI-056', {**foundation_fields, 'sourceL5': str(l5),
              'sourceL5Sha256': sha(l5), 'verdict': 'passed', 'runs': repeats,
              'artifactSha256': hashes[0], 'reload': reloads[0]}, sources, files56)
    verify(l6)
    output = directory / 'handoff.obj'
    handoff_report = directory / 'handoff.json'
    call([python, ROOT / 'tools' / 'scientific-gmsh-handoff.py', '--input', repeats[0]['artifact'],
          '--output', output, '--result', handoff_report])
    vtk_result = directory / 'vtk-result.json'
    call([vtk_python, ROOT / 'tools' / 'scientific-gmsh-vtk-consumer.py',
          '--input', output, '--result', vtk_result])
    math3d_result = directory / 'math3d-result.json'
    call([node, ROOT / 'tools' / 'math3d-gmsh-import-handoff.mjs', '--checkout', checkout,
          '--input', output, '--result', math3d_result], timeout=120)
    malformed = directory / 'malformed.obj'
    malformed.write_text('v 0 0 0\nv 1 0 0\nf 1 2 99\n', encoding='utf-8')
    vtk_rejection = directory / 'vtk-rejection.json'
    call([vtk_python, ROOT / 'tools' / 'scientific-gmsh-vtk-consumer.py', '--input', malformed,
          '--result', vtk_rejection, '--expect-reject'])
    math3d_rejection = directory / 'math3d-rejection.json'
    call([node, ROOT / 'tools' / 'math3d-gmsh-import-handoff.mjs', '--checkout', checkout,
          '--input', malformed, '--result', math3d_rejection, '--expect-reject'], timeout=120)
    if not comparable(*(json.loads(path.read_text()) for path in (handoff_report, vtk_result, math3d_result))):
        raise RuntimeError('Gmsh handoff geometry, topology, orientation or scale changed.')
    if any(json.loads(path.read_text())['state'] != 'rejected' for path in (vtk_rejection, math3d_rejection)):
        raise RuntimeError('A malformed Gmsh handoff was accepted.')
    files57 = [output, handoff_report, vtk_result, math3d_result, malformed, vtk_rejection, math3d_rejection]
    l7 = seal(directory, 'DS-SCI-057', {**foundation_fields, 'sourceL6': str(l6),
              'sourceL6Sha256': sha(l6), 'verdict': 'passed',
              'handoffReport': str(handoff_report), 'vtkResult': str(vtk_result),
              'math3dResult': str(math3d_result), 'vtkRejection': str(vtk_rejection),
              'math3dRejection': str(math3d_rejection)}, sources, files57)
    verify(l7)
    return [l5, l6, l7]


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('run', 'verify'))
    parser.add_argument('--foundation')
    parser.add_argument('--vtk-python')
    parser.add_argument('--math3d-checkout')
    parser.add_argument('--output-root')
    parser.add_argument('--record')
    args = parser.parse_args()
    if args.command == 'run':
        if not all((args.foundation, args.vtk_python, args.math3d_checkout, args.output_root)):
            parser.error('run requires foundation, vtk-python, math3d-checkout and output-root')
        print(json.dumps({'records': [str(path) for path in run(
            args.foundation, args.vtk_python, args.math3d_checkout, args.output_root)]}))
    else:
        if not args.record:
            parser.error('verify requires record')
        record = verify(args.record)
        print(json.dumps({'record': args.record, 'ticket': record['ticket'], 'verdict': record['verdict']}))
