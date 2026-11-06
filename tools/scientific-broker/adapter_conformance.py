"""Contract-level conformance matrix across registered scientific providers."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
from broker import Broker, sha
from telemetry import host_fingerprint

ROOT = Path(__file__).resolve().parents[2]
PROVIDERS = ('cgal-win-conda', 'vtk-win-conda', 'python-win-conda', 'sage-wsl', 'gmsh-win-conda')
FIELDS = ('contract', 'errors', 'cancellation', 'progress', 'typedValues', 'artifactHashes')


def case(state, detail, evidence=None):
    return {'state': state, 'detail': detail, 'evidence': evidence}


def verdict(cases):
    states = {item['state'] for item in cases.values()}
    return 'failed' if 'failed' in states else 'incomplete' if 'unavailable' in states else 'passed'


def wait_job(broker, job_id, timeout=35):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = broker.snapshot(broker.jobs[job_id])
        if job['state'] != 'running':
            return job
        time.sleep(0.025)
    broker.cancel(job_id)
    raise TimeoutError('Conformance broker job did not finish.')


def cgal_cases(config_path, directory):
    broker = Broker(config_path)
    entry = broker.capabilities[0]
    source = broker.paths['datasetRoot'] / 'math3d' / 'basic' / '01_tetrahedron.obj'
    request = {'schemaVersion': 1, 'runtimeId': 'cgal-win-conda', 'capabilityId': 'mesh.interop.vtk-math3d',
               'input': {'path': str(source), 'sha256': sha(source)}}
    cases = {}
    discovered = broker.discover()['providers']
    cases['contract'] = case('passed' if len(discovered) == 1 and discovered[0]['runtimeId'] == 'cgal-win-conda' else 'failed',
                             'Certified broker discovery is provider-scoped.', entry['recordId'])
    before = len(broker.jobs)
    rejected = False
    try:
        broker.submit({**request, 'input': {'path': str(source), 'sha256': '0' * 64}})
    except ValueError:
        rejected = True
    cases['errors'] = case('passed' if rejected and len(broker.jobs) == before else 'failed',
                           'Bad input hash must be rejected before a worker starts.')
    started = broker.submit(request)
    finished = wait_job(broker, started['jobId'])
    typed = (finished['state'] == 'succeeded' and type(finished.get('contractVersion')) is int
             and finished.get('runtimeId') == 'cgal-win-conda' and isinstance(finished.get('artifacts'), list))
    cases['typedValues'] = case('passed' if typed else 'failed',
                                 'Broker job uses typed status, contract and artifact fields.', started['jobId'])
    cases['progress'] = case('passed' if started['state'] == 'running' and started['progress'] == 0
                             and finished.get('progress') == 100 else 'failed',
                             'Broker job advances from queued to terminal progress.', started['jobId'])
    try:
        raw = broker.artifact(started['jobId'], 'l5-positive.obj')
        expected = next(item for item in finished['artifacts'] if item['path'] == 'l5-positive.obj')
        valid = hashlib.sha256(raw).hexdigest() == expected['sha256'] == entry['referenceArtifactSha256']
    except (OSError, ValueError, KeyError, StopIteration):
        valid = False
    cases['artifactHashes'] = case('passed' if valid else 'failed',
                                   'Transport bytes match registered and certified SHA-256.', started['jobId'])
    # A test-only release barrier holds the real broker process before its adapter starts.
    barrier = directory / 'never-release.gate'
    broker.batch_release_gate = barrier
    held = broker.submit(request)
    deadline = time.monotonic() + 5
    while 'workerPid' not in broker.snapshot(broker.jobs[held['jobId']]) and time.monotonic() < deadline:
        time.sleep(0.005)
    broker.cancel(held['jobId'])
    stopped = wait_job(broker, held['jobId'])
    cases['cancellation'] = case('passed' if stopped['state'] == 'cancelled' and not stopped['artifacts']
                                and stopped.get('cleanup', {}).get('state') == 'passed' else 'failed',
                                'Cancellation terminates the held worker and exposes no artifact.', held['jobId'])
    return cases


def vtk_cases(config_path, runtime_report, directory):
    broker = Broker(config_path)
    report = json.loads(Path(runtime_report).read_text(encoding='utf-8'))
    runtime = next((item for item in report.get('runtimes', []) if item.get('id') == 'vtk-win-conda'), None)
    prefix = Path(runtime['environmentRoot']) if runtime and runtime.get('environmentRoot') else None
    if prefix is None or not (prefix / 'python.exe').is_file():
        return {field: case('unavailable', 'Dedicated VTK Python is not installed in the recorded prefix.') for field in FIELDS}
    manifest = json.loads((ROOT / 'runtimes' / 'vtk-win-conda' / 'runtime.json').read_text(encoding='utf-8'))
    cases = {'contract': case('passed' if manifest['id'] == 'vtk-win-conda' else 'failed',
                              'Versioned VTK runtime manifest and adapter request agree.')}
    work = directory / 'vtk-worker'
    dataset = work / 'dataset'
    dataset.mkdir(parents=True)
    source = broker.paths['datasetRoot'] / 'math3d' / 'basic' / '01_tetrahedron.obj'
    copied = dataset / 'input.obj'
    shutil.copyfile(source, copied)
    request = {'schemaVersion': 1, 'runId': uuid.uuid4().hex, 'runtimeId': 'vtk-win-conda',
               'recipeId': 'mesh.inspect', 'operation': 'mesh.inspect', 'parameters': {},
               'workingDirectory': str(work), 'datasetRoot': str(dataset), 'timeoutSeconds': 60,
               'inputArtifacts': [{'path': str(copied), 'sha256': sha(copied)}],
               'outputArtifacts': [{'path': 'conformance.vtp', 'mediaType': 'application/vnd.vtk.vtp'}]}
    request_path = work / 'request.json'
    request_path.write_text(json.dumps(request), encoding='utf-8')
    env = os.environ.copy()
    env['PATH'] = os.pathsep.join([str(prefix), str(prefix / 'Library' / 'bin'), str(prefix / 'Scripts'), env.get('PATH', '')])
    env['PYTHONNOUSERSITE'] = '1'
    command = [str(prefix / 'python.exe'), str(ROOT / 'tools' / 'scientific-mesh-worker.py'), '--request', str(request_path)]
    completed = subprocess.run(command, cwd=work, env=env, capture_output=True, text=True,
                               timeout=75, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    result_path = work / 'results.json'
    result = json.loads(result_path.read_text(encoding='utf-8')) if result_path.is_file() else {}
    typed = (completed.returncode == 0 and result.get('state') == 'succeeded'
             and result.get('runtimeId') == 'vtk-win-conda' and result.get('runId') == request['runId']
             and type(result.get('after', {}).get('points')) is int
             and type(result.get('after', {}).get('triangles')) is int)
    cases['typedValues'] = case('passed' if typed else 'failed',
                                 'VTK result has typed counts and matching run identity.', request['runId'])
    try:
        output = work / 'conformance.vtp'
        artifact = next(item for item in result['artifacts'] if item['path'] == 'conformance.vtp')
        valid = sha(output) == artifact['sha256'] and output.stat().st_size == artifact['bytes']
    except (OSError, KeyError, StopIteration):
        valid = False
    cases['artifactHashes'] = case('passed' if valid else 'failed',
                                   'VTK output matches its registered bytes and SHA-256.', request['runId'])
    bad = dict(request)
    bad['runId'] = uuid.uuid4().hex
    bad['inputArtifacts'] = [{'path': str(copied), 'sha256': '0' * 64}]
    bad_work = directory / 'vtk-reject'
    bad_work.mkdir()
    bad_dataset = bad_work / 'dataset'
    bad_dataset.mkdir()
    shutil.copyfile(copied, bad_dataset / 'input.obj')
    bad['workingDirectory'] = str(bad_work)
    bad['datasetRoot'] = str(bad_dataset)
    bad['inputArtifacts'][0]['path'] = str(bad_dataset / 'input.obj')
    bad_path = bad_work / 'request.json'
    bad_path.write_text(json.dumps(bad), encoding='utf-8')
    rejected = subprocess.run([str(prefix / 'python.exe'), str(ROOT / 'tools' / 'scientific-mesh-worker.py'), '--request', str(bad_path)],
                              cwd=bad_work, env=env, capture_output=True, text=True, timeout=30,
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    cases['errors'] = case('passed' if rejected.returncode != 0 and not (bad_work / 'conformance.vtp').exists() else 'failed',
                           'Changed input hash must reject without a successful VTP artifact.', bad['runId'])
    cases['cancellation'] = case('unavailable', 'VTK adapter has no versioned cancellation acknowledgement; process termination alone is insufficient.')
    cases['progress'] = case('unavailable', 'VTK adapter emits only its terminal result, not versioned progress events.')
    return cases


def probe_cases(runtime_id, runtime_report):
    manifest = json.loads((ROOT / 'runtimes' / runtime_id / 'runtime.json').read_text(encoding='utf-8'))
    cases = {field: case('unavailable', 'No registered version 1 worker adapter for this provider.') for field in FIELDS}
    cases['contract'] = case('passed' if manifest.get('schemaVersion') == 1 and manifest.get('id') == runtime_id else 'failed',
                             'Versioned provider manifest is present; no worker adapter is certified.')
    if runtime_id == 'sage-wsl':
        distro = os.environ.get('MATH3D_WSL_DISTRO', 'Ubuntu')
        script = ('for candidate in /usr/bin/sage /usr/local/bin/sage '
                  '"$HOME/miniforge3/envs/sage/bin/sage" "$HOME/mambaforge/envs/sage/bin/sage" '
                  '"$HOME/miniconda3/envs/sage/bin/sage"; do '
                  'if test -x "$candidate"; then exec "$candidate" -python -c "$1"; fi; done; exit 127')
        for key, probe_id in [('typedValues', 'sage.factor'), ('errors', 'sage.factor.reject')]:
            probe = next(item for item in manifest['probes'] if item['id'] == probe_id)
            code = probe['arguments'][-1]
            try:
                result = subprocess.run(['wsl.exe', '-d', distro, '--exec', 'sh', '-lc', script, 'sh', code],
                                        capture_output=True, text=True, timeout=min(probe['timeoutSeconds'] + 5, 55),
                                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                if key == 'typedValues':
                    lines = [line for line in result.stdout.splitlines() if line.strip().startswith('{')]
                    value = json.loads(lines[-1]) if lines else {}
                    valid = (result.returncode == 0 and value.get('status') == 'succeeded'
                             and value.get('result', {}).get('verified') is True)
                else:
                    valid = result.returncode == 0 and 'rejected invalid coefficient:' in result.stdout
                cases[key] = case('passed' if valid else 'unavailable',
                                  'Sage managed probe checked exact typed value or expected rejection; no artifact worker contract.')
            except (OSError, ValueError, subprocess.SubprocessError):
                pass
        return cases
    try:
        report = json.loads(Path(runtime_report).read_text(encoding='utf-8'))
        runtime = next((item for item in report['runtimes'] if item.get('id') == runtime_id), None)
        prefix = runtime.get('environmentRoot') if runtime else None
        if not prefix and runtime_id in ('python-win-conda', 'gmsh-win-conda'):
            prefix = str(Path(report['runtimeRoot']) / 'devshell-scientific')
        python = Path(prefix) / 'python.exe' if prefix else Path('unavailable')
        if not python.is_file():
            return cases
        env = os.environ.copy()
        env['PATH'] = os.pathsep.join([str(python.parent), str(python.parent / 'Library' / 'bin'),
                                      str(python.parent / 'Scripts'), env.get('PATH', '')])
        env['PYTHONNOUSERSITE'] = '1'
        names = ('scipy.solve', 'scipy.solve.reject') if runtime_id == 'python-win-conda' else ('gmsh.surface2d', 'gmsh.surface2d.reject')
        for key, probe_id in zip(('typedValues', 'errors'), names):
            probe = next(item for item in manifest['probes'] if item['id'] == probe_id)
            result = subprocess.run([str(python), *probe['arguments']], env=env, capture_output=True, text=True,
                                    timeout=min(probe['timeoutSeconds'] + 5, 45),
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            marker = ('solution:' if runtime_id == 'python-win-conda' else 'surface elements:') if key == 'typedValues' else 'expected rejection:'
            cases[key] = case('passed' if result.returncode == 0 and marker in result.stdout else 'unavailable',
                              'Provider probe checked a typed smoke value or expected rejection; this is not worker conformance.'
                              if result.returncode == 0 else f'Probe exited {result.returncode}; inspect the provider runtime and DLL path.')
    except (OSError, ValueError, KeyError, StopIteration, subprocess.SubprocessError):
        pass
    return cases


def run(config_path, runtime_report, output_root):
    directory = Path(output_root).resolve() / uuid.uuid4().hex
    directory.mkdir(parents=True)
    providers = []
    for runtime_id in PROVIDERS:
        manifest = ROOT / 'runtimes' / runtime_id / 'runtime.json'
        try:
            if runtime_id == 'cgal-win-conda':
                cases = cgal_cases(config_path, directory)
            elif runtime_id == 'vtk-win-conda':
                cases = vtk_cases(config_path, runtime_report, directory)
            else:
                cases = probe_cases(runtime_id, runtime_report)
        except Exception as error:
            cases = {field: case('failed', 'Harness or provider check failed: ' + str(error)[:250]) for field in FIELDS}
        providers.append({'runtimeId': runtime_id, 'manifestSha256': sha(manifest),
                          'cases': cases, 'verdict': verdict(cases)})
    report = {'schemaVersion': 1, 'kind': 'scientific.adapter-conformance',
              'createdAtUtc': datetime.now(timezone.utc).isoformat(),
              'suiteRevisionSha256': sha(Path(__file__)), 'hostFingerprintSha256': host_fingerprint(),
              'providers': providers, 'qualificationImpact': 'none; conformance cannot grant L0-L9 or certify Gmsh'}
    target = directory / 'conformance.json'
    with target.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
    Path(str(target) + '.sha256').write_text(sha(target), encoding='utf-8')
    return target, report


def verify_record(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('Conformance record hash mismatch.')
    report = json.loads(path.read_text(encoding='utf-8'))
    if (report.get('schemaVersion') != 1 or report.get('kind') != 'scientific.adapter-conformance'
            or [item.get('runtimeId') for item in report.get('providers', [])] != list(PROVIDERS)):
        raise ValueError('Conformance record has an invalid schema or provider set.')
    for provider in report['providers']:
        cases = provider.get('cases', {})
        if (set(cases) != set(FIELDS)
                or any(item.get('state') not in ('passed', 'failed', 'unavailable') for item in cases.values())
                or provider.get('verdict') != verdict(cases)):
            raise ValueError('Conformance case or verdict mismatch.')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config')
    parser.add_argument('--runtime-report')
    parser.add_argument('--output-root')
    parser.add_argument('--verify')
    args = parser.parse_args()
    if args.verify:
        record = verify_record(args.verify)
        print(json.dumps({'record': args.verify, 'providers': {item['runtimeId']: item['verdict'] for item in record['providers']}}))
        return
    if not (args.config and args.runtime_report and args.output_root):
        parser.error('--config, --runtime-report and --output-root are required for a run')
    target, report = run(args.config, args.runtime_report, args.output_root)
    print(json.dumps({'record': str(target), 'providers': {item['runtimeId']: item['verdict'] for item in report['providers']}}))
    if any(item['verdict'] == 'failed' for item in report['providers']):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
