"""Live, versioned VTK mesh.read scope with sealed accepted and rejected cases."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(__file__).resolve()
MANIFEST = ROOT / 'scientific/fixtures/vtk/read/manifest.v2.json'
WORKER = ROOT / 'tools/scientific-mesh-worker.py'
CONTRACT = ROOT / 'tools/scientific_worker_contract.py'
CASES = ('tetra', 'cube', 'octa', 'affine', 'open', 'disconnected', 'empty', 'truncated', 'invalid')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def manifest():
    value = json.loads(MANIFEST.read_text(encoding='utf-8'))
    if (value.get('schemaVersion') != 2 or value.get('kind') != 'scientific.vtk-mesh-read-scope'
            or value.get('capabilityId') != 'mesh.read' or value.get('suiteId') != 'vtk-mesh-read-v2'
            or value.get('license') != 'CC0-1.0' or value.get('vtkVersion') != '9.6.1'
            or tuple(item.get('caseId') for item in value.get('cases', [])) != CASES):
        raise ValueError('VTK read scope identity changed.')
    for case in value['cases']:
        path = (ROOT / case['path']).resolve(strict=True)
        if not path.is_relative_to(ROOT) or sha(path) != case['sha256']:
            raise ValueError('VTK read fixture changed: ' + case['caseId'])
        if case['expected'] == 'accepted':
            before = case.get('before')
            if (not isinstance(before, dict) or before.get('points', 0) < 4
                    or before.get('triangles', 0) < 2 or before.get('nonManifoldEdges') != 0
                    or len(case.get('outputSha256', '')) != 64):
                raise ValueError('VTK accepted-case contract changed.')
        elif case['expected'] != 'rejected' or not case.get('errorContains'):
            raise ValueError('VTK rejected-case contract changed.')
    return value


def check_case(case, folder, saved=None):
    folder = Path(folder).resolve(strict=True)
    request_path, result_path = folder / 'request.json', folder / 'results.json'
    request = json.loads(request_path.read_text(encoding='utf-8'))
    result = json.loads(result_path.read_text(encoding='utf-8-sig'))
    source = Path(request['inputArtifacts'][0]['path']).resolve(strict=True)
    output = folder / 'mesh.vtp'
    accepted = case['expected'] == 'accepted'
    if (request.get('schemaVersion') != 1 or request.get('recipeId') != 'mesh.inspect'
            or request.get('runtimeId') != 'vtk-win-conda' or Path(request['workingDirectory']).resolve() != folder
            or source.parent != folder / 'dataset' or sha(source) != case['sha256']
            or request['inputArtifacts'][0].get('sha256') != case['sha256']
            or request['outputArtifacts'][0].get('path') != 'mesh.vtp'
            or result.get('runId') != request.get('runId')
            or result.get('versions', {}).get('vtk') != '9.6.1'
            or result.get('state') != ('succeeded' if accepted else 'failed')
            or output.exists() != accepted or bool(result.get('artifacts')) != accepted):
        raise ValueError('VTK read case evidence changed: ' + case['caseId'])
    if accepted:
        artifact = result['artifacts'][0]
        if (result.get('before') != case['before'] or result.get('after') != case['before']
                or 'mesh.read' not in result.get('validatedCapabilities', [])
                or sha(output) != case['outputSha256'] or artifact.get('sha256') != sha(output)
                or artifact.get('bytes') != output.stat().st_size):
            raise ValueError('VTK accepted output changed: ' + case['caseId'])
    elif (result.get('validatedCapabilities') or case['errorContains'] not in
          ' '.join(item.get('message', '') for item in result.get('diagnostics', []))):
        raise ValueError('VTK rejection changed: ' + case['caseId'])
    entry = {'caseId': case['caseId'], 'directory': str(folder),
             'requestSha256': sha(request_path), 'resultSha256': sha(result_path),
             'state': result['state'], 'outputSha256': sha(output) if accepted else None}
    if saved is not None and entry != saved:
        raise ValueError('VTK saved case changed: ' + case['caseId'])
    return entry


def run(python, output_root):
    fixture = manifest()
    python = Path(python).resolve(strict=True)
    folder = Path(output_root).resolve() / uuid.uuid4().hex
    folder.mkdir(parents=True)
    entries = []
    for case in fixture['cases']:
        directory = folder / case['caseId']
        dataset = directory / 'dataset'
        dataset.mkdir(parents=True)
        source = ROOT / case['path']
        copied = dataset / source.name
        shutil.copyfile(source, copied)
        request = {'schemaVersion': 1, 'runId': uuid.uuid4().hex, 'runtimeId': 'vtk-win-conda',
                   'recipeId': 'mesh.inspect', 'operation': 'mesh.read',
                   'workingDirectory': str(directory), 'datasetRoot': str(dataset),
                   'parameters': {}, 'inputArtifacts': [{'path': str(copied), 'sha256': case['sha256']}],
                   'outputArtifacts': [{'path': 'mesh.vtp'}]}
        (directory / 'request.json').write_text(json.dumps(request, separators=(',', ':')), encoding='utf-8')
        completed = subprocess.run([str(python), str(WORKER), '--request', str(directory / 'request.json')],
                                   cwd=directory, text=True, capture_output=True, timeout=60)
        (directory / 'full.log').write_text(completed.stdout + completed.stderr, encoding='utf-8')
        if (completed.returncode == 0) != (case['expected'] == 'accepted'):
            raise ValueError('VTK worker exit state changed: ' + case['caseId'])
        entries.append(check_case(case, directory))
    report = {'schemaVersion': 1, 'kind': 'scientific.vtk-mesh-read-scope', 'verdict': 'passed',
              'createdAtUtc': datetime.now(timezone.utc).isoformat(), 'suiteId': fixture['suiteId'],
              'capabilityId': 'mesh.read', 'manifestSha256': sha(MANIFEST), 'workerSourceSha256': sha(WORKER),
              'contractSha256': sha(CONTRACT), 'scopeSourceSha256': sha(SOURCE),
              'pythonPath': str(python), 'pythonSha256': sha(python), 'cases': entries}
    path = folder / 'scope.json'
    path.write_text(json.dumps(report, separators=(',', ':')), encoding='utf-8')
    Path(str(path) + '.sha256').write_text(sha(path), encoding='utf-8')
    verify(path)
    return path, report


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('VTK scope seal changed.')
    report = json.loads(path.read_text(encoding='utf-8'))
    fixture = manifest()
    if (report.get('schemaVersion') != 1 or report.get('kind') != 'scientific.vtk-mesh-read-scope'
            or report.get('verdict') != 'passed' or report.get('suiteId') != fixture['suiteId']
            or report.get('capabilityId') != 'mesh.read' or report.get('manifestSha256') != sha(MANIFEST)
            or report.get('workerSourceSha256') != sha(WORKER) or report.get('contractSha256') != sha(CONTRACT)
            or report.get('scopeSourceSha256') != sha(SOURCE)
            or sha(Path(report['pythonPath'])) != report['pythonSha256']
            or len(report.get('cases', [])) != len(CASES)):
        raise ValueError('VTK scope sources or identity changed.')
    for case, saved in zip(fixture['cases'], report['cases']):
        directory = Path(saved['directory']).resolve(strict=True)
        if directory.parent != path.parent or directory.name != case['caseId']:
            raise ValueError('VTK scope case escaped its run directory.')
        check_case(case, directory, saved)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('run', 'verify'))
    parser.add_argument('--python')
    parser.add_argument('--output-root')
    parser.add_argument('--report')
    options = parser.parse_args()
    if options.command == 'run':
        path, _ = run(options.python, options.output_root)
    else:
        path = Path(options.report).resolve(strict=True)
        verify(path)
    print(json.dumps({'report': str(path), 'sha256': sha(path)}))
