"""Local, noncertifying DS-SCI-067–069 unit-cube volume evidence."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

from broker import sha

ROOT = Path(__file__).resolve().parents[2]
SUITE = 'scientific.gmsh.candidate-volume.v1'
SOURCES = [ROOT / name for name in (
    'scientific/fixtures/gmsh/cube.geo', 'scientific/fixtures/gmsh/tampered-cube.geo',
    'tools/scientific-gmsh-volume-worker.py', 'tools/scientific_worker_contract.py',
    'tools/scientific-gmsh-volume-handoff.py', 'tools/scientific-gmsh-volume-vtk.py',
    'tools/math3d-gmsh-volume-consumer.mjs', 'tools/scientific-broker/gmsh_volume.py',
    'tests/test_scientific_gmsh_volume.py')]


def invoke(command, *, timeout=90, cwd=ROOT):
    process = subprocess.run([str(item) for item in command], cwd=cwd, timeout=timeout,
                             capture_output=True, text=True, encoding='utf-8', errors='replace',
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if process.returncode:
        raise RuntimeError(f'{command[0]} exited {process.returncode}: {process.stdout[-800:]} {process.stderr[-800:]}')
    return process


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def worker_case(root, name, python, fixture, parameters, expected):
    case = root / name
    case.mkdir()
    source = root / 'dataset' / fixture
    request = {'schemaVersion': 1, 'runId': uuid.uuid4().hex, 'runtimeId': 'gmsh-win-conda',
               'recipeId': 'gmsh.volume3d.cube', 'workingDirectory': str(case),
               'datasetRoot': str(source.parent),
               'inputArtifacts': [{'path': str(source), 'sha256': sha(source)}],
               'outputArtifacts': [{'path': 'cube.msh'}], 'parameters': parameters}
    (case / 'request.json').write_text(json.dumps(request, indent=2), encoding='utf-8')
    process = subprocess.run([str(python), str(ROOT / 'tools/scientific-gmsh-volume-worker.py'),
                              '--request', str(case / 'request.json')], cwd=ROOT / 'tools',
                             timeout=90, capture_output=True, text=True, encoding='utf-8', errors='replace',
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    (case / 'full.log').write_text(process.stdout + process.stderr, encoding='utf-8')
    result = read(case / 'results.json')
    artifact = case / 'cube.msh'
    if result['state'] != expected or (process.returncode == 0) != (expected == 'succeeded'):
        raise RuntimeError(f'{name} ended in the wrong state: {result.get("diagnostics")}')
    if expected == 'succeeded':
        if (len(result['artifacts']) != 1 or result['artifacts'][0]['sha256'] != sha(artifact)
                or result['validatedCapabilities'] != ['mesh.generate3d.cube']):
            raise RuntimeError('Typed volume artifact or capability differs.')
    elif artifact.exists() or result['artifacts'] or not result['diagnostics']:
        raise RuntimeError('Rejected volume case left an artifact or no diagnostic.')
    return result


def seal(root, ticket, fields, files, sources, parent=None):
    record = {'schemaVersion': 1, 'suiteId': SUITE, 'ticket': ticket,
              'createdAtUtc': datetime.now(timezone.utc).isoformat(),
              'releaseCertified': False, 'volumePromotionAllowed': False,
              'sourceCommit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'sources': sources,
              'suiteRevisionSha256': hashlib.sha256(json.dumps(sources, sort_keys=True).encode()).hexdigest(),
              'files': {str(Path(file).resolve()): sha(file) for file in files},
              **fields}
    if parent:
        record['parentRecord'] = str(parent)
        record['parentSha256'] = sha(parent)
    path = root / (ticket + '.json')
    with path.open('x', encoding='utf-8') as stream:
        json.dump(record, stream, indent=2)
    Path(str(path) + '.sha256').write_text(sha(path), encoding='utf-8')
    verify(path)
    return path


def compare_consumer(result, reload, artifact):
    return (result.get('state') == 'accepted' and result.get('inputObjSha256') == artifact
            and result.get('points') == reload['boundaryPoints']
            and result.get('triangles') == reload['boundaryTriangles']
            and result.get('boundaryEdges') == 0 and result.get('nonManifoldEdges') == 0
            and all(abs(a-b) < 1e-6 for a,b in zip(result['bounds'], reload['bounds']))
            and abs(result['surfaceArea']-reload['surfaceArea']) < 1e-5
            and abs(result['signedVolume']-reload['volume']) < 1e-5)


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('Gmsh volume record hash mismatch.')
    record = read(path)
    ticket = record.get('ticket')
    if (record.get('schemaVersion') != 1 or record.get('suiteId') != SUITE
            or ticket not in ('DS-SCI-067','DS-SCI-068','DS-SCI-069')
            or record.get('releaseCertified') is not False or record.get('volumePromotionAllowed') is not False
            or record.get('sourceCommit') != subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip()):
        raise ValueError('Gmsh volume identity or source commit changed.')
    if any(sha(source) != digest for source,digest in record['sources'].items()):
        raise ValueError('Gmsh volume source drift.')
    if record['suiteRevisionSha256'] != hashlib.sha256(json.dumps(record['sources'], sort_keys=True).encode()).hexdigest():
        raise ValueError('Gmsh volume suite revision changed.')
    if any(sha(file) != digest for file,digest in record['files'].items()):
        raise ValueError('Gmsh volume evidence hash mismatch.')
    if ticket != 'DS-SCI-067':
        parent = Path(record['parentRecord'])
        if sha(parent) != record['parentSha256'] or verify(parent)['ticket'] != ('DS-SCI-067' if ticket == 'DS-SCI-068' else 'DS-SCI-068'):
            raise ValueError('Gmsh volume parent evidence changed.')
    if ticket == 'DS-SCI-067':
        positive = read(record['positiveResult'])
        if (positive['state'] != 'succeeded' or positive['validatedCapabilities'] != ['mesh.generate3d.cube']
                or positive['artifacts'][0]['sha256'] != record['artifactSha256']
                or sha(record['artifact']) != record['artifactSha256']):
            raise ValueError('Typed candidate volume worker evidence changed.')
        for result in record['rejections'].values():
            child = read(result)
            if child['state'] != 'failed' or child['artifacts'] or not child['diagnostics']:
                raise ValueError('Candidate volume worker rejection changed.')
    elif ticket == 'DS-SCI-068':
        first = read(record['firstResult'])
        second = read(record['secondResult'])
        reload = read(record['reloadResult'])
        if (first['artifacts'][0]['sha256'] != second['artifacts'][0]['sha256']
                or first['artifacts'][0]['sha256'] != record['artifactSha256']
                or reload['sourceMshSha256'] != record['artifactSha256']
                or reload['tetrahedra'] < 6 or abs(reload['volume']-1) > 1e-6
                or abs(reload['surfaceArea']-6) > 1e-5
                or reload['boundaryEdges'] != 0 or reload['nonManifoldEdges'] != 0):
            raise ValueError('Candidate volume reproduction or reload changed.')
    else:
        reload = read(record['reloadResult'])
        artifact = sha(record['boundaryObj'])
        if (reload['outputObjSha256'] != artifact
                or not compare_consumer(read(record['vtkResult']), reload, artifact)
                or not compare_consumer(read(record['math3dResult']), reload, artifact)
                or read(record['vtkRejection'])['state'] != 'rejected'
                or read(record['math3dRejection'])['state'] != 'rejected'
                or read(record['math3dResult'])['importerSourceSha256'] !=
                    sha(record['math3dImporter'])):
            raise ValueError('Candidate volume consumer evidence changed.')
    return record


def run(gmsh_python, vtk_python, math3d, output_root):
    gmsh_python, vtk_python = Path(gmsh_python).resolve(strict=True), Path(vtk_python).resolve(strict=True)
    math3d = Path(math3d).resolve(strict=True)
    importer = math3d / 'renderer/src/mesh/surfaceMesh.ts'
    importer.resolve(strict=True)
    root = Path(output_root).resolve() / uuid.uuid4().hex
    root.mkdir(parents=True)
    dataset = root / 'dataset'
    dataset.mkdir()
    for name in ('cube.geo','tampered-cube.geo'):
        shutil.copyfile(ROOT / 'scientific/fixtures/gmsh' / name, dataset / name)
    package_files = list((gmsh_python.parent.parent / 'conda-meta').glob('gmsh-*.json'))
    package_files += list((vtk_python.parent.parent / 'conda-meta').glob('vtk-*.json'))
    package_files += list((gmsh_python.parent / 'Lib/site-packages').glob('gmsh-*.dist-info/METADATA'))
    sources = {str(source):sha(source) for source in SOURCES + [gmsh_python, vtk_python, importer] + package_files}
    first = worker_case(root,'positive-a',gmsh_python,'cube.geo',{'meshSize':0.35},'succeeded')
    changed = worker_case(root,'reject-geometry',gmsh_python,'tampered-cube.geo',{'meshSize':0.35},'failed')
    invalid = worker_case(root,'reject-parameter',gmsh_python,'cube.geo',{'meshSize':0},'failed')
    first_msh = root / 'positive-a/cube.msh'
    record67 = seal(root,'DS-SCI-067',
                    {'capabilityId':'mesh.generate3d.cube','positiveResult':str(root/'positive-a/results.json'),
                     'artifact':str(first_msh),'artifactSha256':sha(first_msh),
                     'rejections':{'changedGeometry':str(root/'reject-geometry/results.json'),
                                   'invalidParameter':str(root/'reject-parameter/results.json')},
                     'verdict':'passed'},
                    [dataset/'cube.geo',dataset/'tampered-cube.geo',
                     root/'positive-a/request.json',root/'positive-a/results.json',root/'positive-a/full.log',first_msh,
                     root/'reject-geometry/request.json',root/'reject-geometry/results.json',root/'reject-geometry/full.log',
                     root/'reject-parameter/request.json',root/'reject-parameter/results.json',root/'reject-parameter/full.log'],sources)
    second = worker_case(root,'positive-b',gmsh_python,'cube.geo',{'meshSize':0.35},'succeeded')
    second_msh = root / 'positive-b/cube.msh'
    if sha(first_msh) != sha(second_msh):
        raise ValueError('Fixed Gmsh volume bytes did not reproduce across runs.')
    reload_path = root / 'reload.json'
    invoke([gmsh_python,ROOT/'tools/scientific-gmsh-volume-handoff.py','--input',first_msh,
            '--result',reload_path])
    reload = read(reload_path)
    record68 = seal(root,'DS-SCI-068',
                    {'firstResult':str(root/'positive-a/results.json'),
                     'secondResult':str(root/'positive-b/results.json'),
                     'reloadResult':str(reload_path),'artifactSha256':sha(first_msh),'verdict':'passed'},
                    [root/'positive-b/request.json',root/'positive-b/results.json',root/'positive-b/full.log',second_msh,reload_path],
                    sources,record67)
    obj = root / 'boundary.obj'
    boundary_path = root / 'boundary.json'
    invoke([gmsh_python,ROOT/'tools/scientific-gmsh-volume-handoff.py','--input',first_msh,
            '--output',obj,'--result',boundary_path])
    boundary = read(boundary_path)
    if any(boundary[key] != reload[key] for key in ('points','tetrahedra','volume','surfaceArea','bounds')):
        raise ValueError('Boundary extraction changed the reloaded volume.')
    vtk_path,math3d_path = root/'vtk.json',root/'math3d.json'
    invoke([vtk_python,ROOT/'tools/scientific-gmsh-volume-vtk.py','--input',obj,'--result',vtk_path])
    invoke(['node',ROOT/'tools/math3d-gmsh-volume-consumer.mjs','--checkout',math3d,
            '--input',obj,'--result',math3d_path])
    bad = root / 'flipped-face.obj'
    lines = obj.read_text(encoding='utf-8').splitlines()
    index = next(i for i,line in enumerate(lines) if line.startswith('f '))
    parts = lines[index].split()
    lines[index] = f'f {parts[1]} {parts[3]} {parts[2]}'
    bad.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    vtk_reject,math3d_reject = root/'vtk-rejection.json',root/'math3d-rejection.json'
    invoke([vtk_python,ROOT/'tools/scientific-gmsh-volume-vtk.py','--input',bad,
            '--result',vtk_reject,'--expect-reject'])
    invoke(['node',ROOT/'tools/math3d-gmsh-volume-consumer.mjs','--checkout',math3d,
            '--input',bad,'--result',math3d_reject,'--expect-reject'])
    record69 = seal(root,'DS-SCI-069',
                    {'reloadResult':str(boundary_path),'boundaryObj':str(obj),
                     'vtkResult':str(vtk_path),'math3dResult':str(math3d_path),
                     'vtkRejection':str(vtk_reject),'math3dRejection':str(math3d_reject),
                     'math3dImporter':str(importer),'verdict':'passed'},
                    [boundary_path,obj,vtk_path,math3d_path,bad,vtk_reject,math3d_reject],sources,record68)
    return [record67,record68,record69]


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command',choices=('run','verify'))
    parser.add_argument('--gmsh-python')
    parser.add_argument('--vtk-python')
    parser.add_argument('--math3d-checkout')
    parser.add_argument('--output-root')
    parser.add_argument('--record')
    args = parser.parse_args()
    if args.command == 'run':
        if not all((args.gmsh_python,args.vtk_python,args.math3d_checkout,args.output_root)):
            parser.error('run requires both Python interpreters, MATH3D and output root')
        paths = run(args.gmsh_python,args.vtk_python,args.math3d_checkout,args.output_root)
        print(json.dumps({'records':[str(path) for path in paths],'verdict':'passed'}))
    else:
        if not args.record:
            parser.error('verify requires --record')
        print(json.dumps({'record':args.record,'verdict':verify(args.record)['verdict']}))
