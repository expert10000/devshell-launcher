"""Local, sealed Gmsh L0-L4 foundation evidence; never a release certification."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid

from broker import sha


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = 'gmsh-win-conda'
SUITE = 'scientific.gmsh.foundation.v1'


def invoke(argv, *, timeout=120, env=None, cwd=ROOT):
    result = subprocess.run([str(item) for item in argv], cwd=cwd, env=env,
                            capture_output=True, text=True, timeout=timeout, errors='replace')
    if result.returncode:
        raise RuntimeError(f'{argv[0]} exited {result.returncode}: {result.stdout[-1000:]} {result.stderr[-1000:]}')
    return result.stdout + result.stderr


def inputs(prefix, cmake):
    prefix = Path(prefix).resolve(strict=True)
    python = prefix / 'python.exe'
    gmsh_module = prefix / 'Lib' / 'site-packages' / 'gmsh.py'
    paths = {
        'manifest': ROOT / 'runtimes' / RUNTIME / 'runtime.json',
        'fixture': ROOT / 'scientific' / 'fixtures' / 'gmsh' / 'square.geo',
        'worker': ROOT / 'tools' / 'scientific-gmsh-worker.py',
        'contract': ROOT / 'tools' / 'scientific_worker_contract.py',
        'smokeSource': ROOT / 'scientific' / 'smoke' / 'gmsh' / 'main.cpp',
        'smokeBuild': ROOT / 'scientific' / 'smoke' / 'gmsh' / 'CMakeLists.txt',
        'runtimeLab': ROOT / 'tools' / 'runtime-lab' / 'bin' / 'Debug' / 'net8.0' / 'runtime-lab.dll',
        'python': python, 'gmshModule': gmsh_module,
        'gmshDll': prefix / 'Library' / 'bin' / 'gmsh-4.15.dll',
        'gmshLibrary': prefix / 'Library' / 'lib' / 'gmsh.dll.lib',
        'gmshHeader': prefix / 'Library' / 'include' / 'gmsh.h',
        'cmake': Path(cmake).resolve(strict=True), 'suite': Path(__file__),
    }
    # The DLL name is versioned in the Conda package, but the loader name is stable.
    if not paths['gmshDll'].is_file():
        paths['gmshDll'] = prefix / 'Library' / 'bin' / 'gmsh.dll'
    return {name: {'path': str(path.resolve(strict=True)), 'sha256': sha(path)} for name, path in paths.items()}


def mesh_inspection(python, artifact):
    code = ('import gmsh,json; gmsh.initialize(); gmsh.option.setNumber("General.Terminal",0); '
            'gmsh.open(__import__("sys").argv[1]); '
            'n,c,_=gmsh.model.mesh.getNodes(); t,e,_=gmsh.model.mesh.getElements(2); '
            'print(json.dumps({"nodes":len(n),"triangles":sum(len(x) for k,x in zip(t,e) if k==2),'
            '"bounds":[min(c[i::3]) for i in range(3)]+[max(c[i::3]) for i in range(3)]})); gmsh.finalize()')
    output = invoke([python, '-c', code, artifact], timeout=30)
    return json.loads(output.strip().splitlines()[-1])


def run(prefix, cmake, output_root):
    source = inputs(prefix, cmake)
    declaration = json.loads(Path(source['manifest']['path']).read_text(encoding='utf-8'))['foundation']
    if (declaration['recipeId'] != 'gmsh.mesh2d'
            or ROOT / declaration['worker'] != Path(source['worker']['path'])
            or ROOT / declaration['fixture'] != Path(source['fixture']['path'])
            or ROOT / declaration['cppSmoke'] != ROOT / 'scientific' / 'smoke' / 'gmsh'):
        raise ValueError('Gmsh registered foundation recipe differs from the test suite.')
    prefix = Path(prefix).resolve()
    python = Path(source['python']['path'])
    work = Path(output_root).resolve() / uuid.uuid4().hex
    work.mkdir(parents=True, exist_ok=False)
    probe = work / 'probe'
    invoke([ROOT / 'tools' / 'runtime-lab' / 'bin' / 'Debug' / 'net8.0' / 'runtime-lab.exe',
            'probe', RUNTIME, '--manifest-root', ROOT / 'runtimes', '--prefix', prefix,
            '--run-id', uuid.uuid4().hex, '--output', probe], timeout=120)
    probe_result = json.loads((probe / 'results.json').read_text(encoding='utf-8'))
    if probe_result['state'] != 'succeeded' or any(p['status'] != 'passed' for p in probe_result['probeResults']):
        raise RuntimeError('Gmsh runtime probes did not pass.')
    build = work / 'build'
    invoke([cmake, '-S', ROOT / 'scientific' / 'smoke' / 'gmsh', '-B', build,
            '-G', 'Visual Studio 17 2022', '-A', 'x64',
            '-DCMAKE_PREFIX_PATH=' + str(prefix / 'Library')], timeout=120)
    invoke([cmake, '--build', build, '--config', 'Release', '--parallel', '2'], timeout=120)
    executable = build / 'Release' / 'devshell_gmsh_smoke.exe'
    env = dict(os.environ)
    env['PATH'] = str(prefix / 'Library' / 'bin') + os.pathsep + env.get('PATH', '')
    linked_output = invoke([executable], env=env, timeout=30)
    if 'gmsh C++ surface nodes:' not in linked_output:
        raise RuntimeError('Linked Gmsh smoke did not report surface nodes.')
    dataset = work / 'dataset'
    dataset.mkdir()
    fixture = dataset / 'square.geo'
    shutil.copyfile(source['fixture']['path'], fixture)
    cases = {}
    for name, size in (('positive', 0.2), ('rejection', 0.0)):
        case = work / name
        case.mkdir()
        request = {'schemaVersion': 1, 'runId': uuid.uuid4().hex,
                   'runtimeId': RUNTIME, 'recipeId': 'gmsh.mesh2d',
                   'workingDirectory': str(case), 'datasetRoot': str(dataset),
                   'inputArtifacts': [{'path': str(fixture), 'sha256': sha(fixture)}],
                   'outputArtifacts': [{'path': 'square.msh'}], 'parameters': {'meshSize': size}}
        (case / 'request.json').write_text(json.dumps(request, indent=2), encoding='utf-8')
        child = subprocess.run([str(python), str(ROOT / 'tools' / 'scientific-gmsh-worker.py'),
                                '--request', str(case / 'request.json')], cwd=ROOT / 'tools', env=env,
                               capture_output=True, text=True, timeout=60, errors='replace')
        (case / 'full.log').write_text(child.stdout + child.stderr, encoding='utf-8')
        result = json.loads((case / 'results.json').read_text(encoding='utf-8'))
        expected = 'succeeded' if name == 'positive' else 'failed'
        if result['state'] != expected or (child.returncode == 0) != (name == 'positive'):
            raise RuntimeError(f'Gmsh {name} worker verdict is unexpected.')
        if name == 'rejection' and ((case / 'square.msh').exists() or result['artifacts']):
            raise RuntimeError('Rejected Gmsh request left an artifact.')
        cases[name] = {'runId': request['runId'], 'state': expected,
                       'request': str(case / 'request.json'), 'result': str(case / 'results.json'),
                       'log': str(case / 'full.log')}
    artifact = work / 'positive' / 'square.msh'
    mesh = mesh_inspection(python, artifact)
    if mesh['nodes'] < 4 or mesh['triangles'] < 2 or any(abs(x-y) > 1e-9 for x,y in zip(mesh['bounds'], [0,0,0,1,1,0])):
        raise RuntimeError('Independent Gmsh artifact reload failed.')
    evidence = {'probeResult': str(probe / 'results.json'), 'linkedExecutable': str(executable),
                'linkedStdout': linked_output[-2000:], 'cases': cases,
                'artifact': str(artifact), 'meshReload': mesh}
    files = [evidence['probeResult'], evidence['linkedExecutable'], evidence['artifact']]
    for case in cases.values():
        files.extend(case[key] for key in ('request', 'result', 'log'))
    record = {'schemaVersion': 1, 'suiteId': SUITE, 'runtimeId': RUNTIME,
              'capabilityId': 'mesh.generate2d.fixed-square', 'releaseCertified': False,
              'createdAtUtc': datetime.now(timezone.utc).isoformat(),
              'levels': {f'L{i}': {'verdict': 'passed', 'reason': text} for i, text in enumerate((
                  'Manifest discovered and environment bound.', 'Python executable passed.',
                  'Gmsh package import and version passed.',
                  'Bounded positive/rejection probes and typed worker passed.',
                  'Gmsh C++ API compiled, linked and executed.'))},
              'laterLevels': 'L5-L9 unqualified; excluded from certified manifests.',
              'sources': source, 'evidence': evidence,
              'evidenceHashes': {path: sha(path) for path in files}}
    path = work / 'foundation.json'
    path.write_text(json.dumps(record, indent=2), encoding='utf-8')
    Path(str(path) + '.sha256').write_text(sha(path), encoding='utf-8')
    verify(path)
    return path, record


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('Gmsh foundation record hash mismatch.')
    record = json.loads(path.read_text(encoding='utf-8'))
    if record.get('suiteId') != SUITE or record.get('releaseCertified') is not False:
        raise ValueError('Invalid Gmsh foundation identity.')
    source = inputs(Path(record['sources']['python']['path']).parent, record['sources']['cmake']['path'])
    if source != record['sources']:
        raise ValueError('Gmsh source, package or toolchain drift.')
    declaration = json.loads(Path(source['manifest']['path']).read_text(encoding='utf-8'))['foundation']
    if (declaration['recipeId'] != 'gmsh.mesh2d'
            or ROOT / declaration['worker'] != Path(source['worker']['path'])
            or ROOT / declaration['fixture'] != Path(source['fixture']['path'])):
        raise ValueError('Gmsh registered foundation recipe changed.')
    if any(sha(file) != digest for file, digest in record['evidenceHashes'].items()):
        raise ValueError('Gmsh evidence hash mismatch.')
    probe = json.loads(Path(record['evidence']['probeResult']).read_text(encoding='utf-8'))
    if probe['state'] != 'succeeded' or {p['id'] for p in probe['probeResults'] if p['status'] == 'passed'} != {
            'python.version', 'gmsh.version', 'gmsh.surface2d', 'gmsh.surface2d.reject'}:
        raise ValueError('Gmsh probe evidence is incomplete.')
    cases = record['evidence']['cases']
    positive = json.loads(Path(cases['positive']['result']).read_text(encoding='utf-8'))
    rejected = json.loads(Path(cases['rejection']['result']).read_text(encoding='utf-8'))
    artifact = record['evidence']['artifact']
    if (positive['state'] != 'succeeded' or positive['artifacts'][0]['sha256'] != sha(artifact)
            or rejected['state'] != 'failed' or rejected['artifacts']
            or Path(cases['rejection']['result']).with_name('square.msh').exists()):
        raise ValueError('Gmsh typed worker evidence is inconsistent.')
    if record['evidence']['meshReload'] != mesh_inspection(source['python']['path'], artifact):
        raise ValueError('Gmsh saved mesh reload differs.')
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('run', 'verify'))
    parser.add_argument('--prefix')
    parser.add_argument('--cmake')
    parser.add_argument('--output-root')
    parser.add_argument('--record')
    args = parser.parse_args()
    if args.command == 'run':
        if not all((args.prefix, args.cmake, args.output_root)):
            parser.error('run requires --prefix, --cmake and --output-root')
        path, record = run(args.prefix, args.cmake, args.output_root)
    else:
        if not args.record:
            parser.error('verify requires --record')
        path, record = args.record, verify(args.record)
    print(json.dumps({'record': str(path), 'levels': record['levels'],
                      'releaseCertified': record['releaseCertified']}))


if __name__ == '__main__':
    main()
