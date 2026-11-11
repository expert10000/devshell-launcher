"""Live, linked CGAL mesh.inspect L5-L9 qualification and saved-evidence verifier."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

from scientific_cgal_corpus import sha as file_sha
from scientific_vtk_read_qualification import comparable, controlled_probe

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(__file__).resolve()
MANIFEST = ROOT / 'scientific/fixtures/cgal-inspect/manifest.v2.json'
ADAPTER = ROOT / 'tools/scientific-cgal-worker.py'
CONTRACT = ROOT / 'tools/scientific_worker_contract.py'
VTK = ROOT / 'tools/scientific-vtk-interop.py'
MATH3D = ROOT / 'tools/math3d-vtk-import-handoff.mjs'
PRODUCT = ROOT / 'tools/math3d-vtk-read-product.mjs'
VIEWER = ROOT / 'tools/math3d-vtk-read-viewer.mjs'
PRODUCT_FILES = ('vtk-mesh-document.json', 'vtk-mesh-resource.bin', 'read.m3dm',
                 'product.json', 'viewer.png', 'viewer.json')
CASES = ('tetra', 'octa', 'cube', 'affine', 'sphere-128', 'sphere-512', 'sphere-2048', 'open', 'nonmanifold', 'degenerate')


def sha(path):
    return file_sha(Path(path))


def manifest():
    value = json.loads(MANIFEST.read_text(encoding='utf-8'))
    if (value.get('schemaVersion') != 2 or value.get('suiteId') != 'cgal-mesh-inspect-v2'
            or value.get('capabilityId') != 'mesh.inspect'
            or tuple(item['caseId'] for item in value['cases']) != CASES):
        raise ValueError('CGAL inspection manifest identity changed.')
    for item in value['cases']:
        path = (ROOT / item['path']).resolve(strict=True)
        if not path.is_relative_to(ROOT) or sha(path) != item['sha256']:
            raise ValueError('CGAL inspection fixture changed: ' + item['caseId'])
    return value


def base(level):
    manifest()
    return {'schemaVersion': 1, 'kind': f'scientific.cgal-inspect-L{level}',
            'suiteId': 'cgal-mesh-inspect-v2', 'capabilityId': 'mesh.inspect',
            'verdict': 'passed', 'createdAtUtc': datetime.now(timezone.utc).isoformat(),
            'manifestSha256': sha(MANIFEST), 'adapterSha256': sha(ADAPTER),
            'contractSha256': sha(CONTRACT), 'qualificationSourceSha256': sha(SOURCE)}


def save(root, level, value):
    root.mkdir(parents=True, exist_ok=True)
    path = root / f'l{level}.json'
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, separators=(',', ':'), allow_nan=False)
    Path(str(path) + '.sha256').write_text(sha(path), encoding='utf-8')
    verify(path)
    return path


def run_case(case, worker, prefix, root):
    directory = root / case['caseId']
    dataset = directory / 'dataset'
    dataset.mkdir(parents=True)
    source = dataset / 'input.obj'
    shutil.copyfile(ROOT / case['path'], source)
    if sha(source) != case['sha256']:
        raise ValueError('Inspection input changed during staging.')
    # A valid but open surface is deliberately outside the shared closed-mesh contract.
    if case['caseId'] == 'open':
        rejected = directory / 'scope-rejection.json'
        rejected.write_text(json.dumps({'caseId': 'open', 'state': 'rejected',
                                         'inputSha256': case['sha256'], 'reason': 'boundary edges'}),
                            encoding='utf-8')
        return {'caseId': 'open', 'directory': str(directory), 'state': 'rejected',
                'inputSha256': case['sha256'], 'rejectionSha256': sha(rejected), 'outputSha256': None}
    request = {'schemaVersion': 1, 'runId': uuid.uuid4().hex, 'runtimeId': 'cgal-win-conda',
               'recipeId': 'cgal.validate', 'operation': 'mesh.inspect', 'parameters': {},
               'workingDirectory': str(directory), 'datasetRoot': str(dataset), 'timeoutSeconds': 120,
               'inputArtifacts': [{'path': str(source), 'sha256': case['sha256']}],
               'outputArtifacts': [{'path': 'inspected.obj'}]}
    request_path = directory / 'request.json'
    request_path.write_text(json.dumps(request, separators=(',', ':')), encoding='utf-8')
    environment = dict(os.environ)
    environment['PATH'] = os.pathsep.join(str(prefix / part) for part in
                                          ('Library/bin', 'Library/usr/bin', 'Scripts')) + os.pathsep + environment.get('PATH', '')
    environment['PYTHONNOUSERSITE'] = '1'
    completed = subprocess.run([str(prefix / 'python.exe'), str(ADAPTER), '--request', str(request_path),
                                '--worker', str(worker), '--prefix', str(prefix)], cwd=ROOT,
                               env=environment, capture_output=True, text=True, timeout=150)
    result_path = directory / 'results.json'
    if not result_path.is_file():
        raise ValueError('Inspection worker saved no result: ' + completed.stderr[-800:])
    result = json.loads(result_path.read_text(encoding='utf-8-sig'))
    output = directory / 'inspected.obj'
    accepted = case['expected'] == 'accepted'
    if (result.get('runId') != request['runId'] or result.get('operation') != 'mesh.inspect'
            or result.get('recipeId') != 'cgal.validate'
            or result.get('state') != ('succeeded' if accepted else 'failed')
            or (completed.returncode == 0) != accepted or output.is_file() != accepted
            or bool(result.get('artifacts')) != accepted):
        raise ValueError('Inspection worker outcome changed: ' + case['caseId'])
    if accepted:
        before, after = result['before'], result['after']
        if (before.get('points') != case['points'] or before.get('triangles') != case['triangles']
                or before.get('boundaryEdges') != 0 or before != after
                or result['engineDetails'].get('selfIntersections') is not False
                or case.get('outputSha256', sha(output)) != sha(output)):
            raise ValueError('Inspection geometry or topology changed: ' + case['caseId'])
    return {'caseId': case['caseId'], 'directory': str(directory), 'state': result['state'],
            'inputSha256': case['sha256'], 'requestSha256': sha(request_path),
            'resultSha256': sha(result_path), 'outputSha256': sha(output) if accepted else None}


def verify_case(saved, expected):
    directory = Path(saved['directory']).resolve(strict=True)
    source = directory / 'dataset/input.obj'
    if (saved['caseId'] != expected['caseId'] or sha(source) != expected['sha256']
            or saved['inputSha256'] != expected['sha256']):
        raise ValueError('Inspection case input changed.')
    output = directory / 'inspected.obj'
    if expected['caseId'] == 'open':
        rejection = directory / 'scope-rejection.json'
        if (saved['state'] != 'rejected' or sha(rejection) != saved['rejectionSha256']
                or json.loads(rejection.read_text()) != {'caseId': 'open', 'state': 'rejected',
                    'inputSha256': expected['sha256'], 'reason': 'boundary edges'}
                or output.exists()):
            raise ValueError('Open mesh was not rejected at scope gate.')
        return
    request_path, result_path = directory / 'request.json', directory / 'results.json'
    request = json.loads(request_path.read_text(encoding='utf-8'))
    result = json.loads(result_path.read_text(encoding='utf-8-sig'))
    accepted = expected['expected'] == 'accepted'
    if (sha(request_path) != saved['requestSha256'] or sha(result_path) != saved['resultSha256']
            or request.get('operation') != 'mesh.inspect' or request.get('recipeId') != 'cgal.validate'
            or request['inputArtifacts'][0]['sha256'] != expected['sha256']
            or request['inputArtifacts'][0]['path'] != str(source)
            or request['runId'] != result.get('runId') or result.get('operation') != 'mesh.inspect'
            or result.get('state') != ('succeeded' if accepted else 'failed')
            or saved['state'] != result['state'] or output.is_file() != accepted
            or saved['outputSha256'] != (sha(output) if accepted else None)
            or bool(result.get('artifacts')) != accepted):
        raise ValueError('Saved inspection worker evidence changed.')
    if accepted:
        before, after = result['before'], result['after']
        if (before.get('points') != expected['points'] or before.get('triangles') != expected['triangles']
                or before.get('boundaryEdges') != 0 or before != after
                or result['engineDetails'].get('selfIntersections') is not False
                or expected.get('outputSha256', sha(output)) != sha(output)):
            raise ValueError('Saved inspection geometry changed.')


def execute(arguments, timeout=150):
    completed = subprocess.run([str(value) for value in arguments], cwd=ROOT,
                               capture_output=True, text=True, timeout=timeout)
    if completed.returncode:
        raise ValueError('Inspection consumer failed: ' + (completed.stderr or completed.stdout)[-1000:])


def run(level, output_root, worker=None, prefix=None, source=None, vtk_python=None,
        node=None, checkout=None):
    folder = Path(output_root).resolve() / uuid.uuid4().hex
    folder.mkdir(parents=True)
    if level == 5:
        worker, prefix = Path(worker).resolve(strict=True), Path(prefix).resolve(strict=True)
        cases = [run_case(item, worker, prefix, folder) for item in manifest()['cases']]
        value = {**base(5), 'workerPath': str(worker), 'workerSha256': sha(worker),
                 'runtimePrefix': str(prefix), 'cases': cases}
    else:
        previous = verify(source)
        if Path(source).name != f'l{level-1}.json':
            raise ValueError('Wrong previous inspection qualification level.')
        value = {**base(level), f'l{level-1}Path': str(Path(source).resolve()),
                 f'l{level-1}Sha256': sha(source)}
        if level == 6:
            l5 = previous
            cases = [run_case(item, Path(l5['workerPath']), Path(l5['runtimePrefix']), folder)
                     for item in manifest()['cases']]
            if [(item['caseId'], item['state'], item['outputSha256']) for item in cases] != [
                    (item['caseId'], item['state'], item['outputSha256']) for item in l5['cases']]:
                raise ValueError('Inspection reproduction differs.')
            value['cases'] = cases
            value['comparison'] = 'state-and-output-sha256'
        elif level == 7:
            vtk_python, node, checkout = (Path(value).resolve(strict=True)
                                          for value in (vtk_python, node, checkout))
            accepted = [item for item in previous['cases'] if item['state'] == 'succeeded']
            consumers = []
            for item in accepted:
                source_obj = Path(item['directory']) / 'inspected.obj'
                vtk_result = folder / (item['caseId'] + '-vtk.json')
                math3d_result = folder / (item['caseId'] + '-math3d.json')
                execute([vtk_python, VTK, '--input', source_obj, '--result', vtk_result])
                execute([node, MATH3D, '--checkout', checkout, '--input', source_obj,
                         '--result', math3d_result])
                reference = json.loads(vtk_result.read_text())
                comparable(reference, json.loads(math3d_result.read_text()), 'MATH3D')
                consumers.append({'caseId': item['caseId'], 'sourcePath': str(source_obj),
                                  'sourceSha256': sha(source_obj), 'vtkPath': str(vtk_result),
                                  'vtkSha256': sha(vtk_result), 'math3dPath': str(math3d_result),
                                  'math3dSha256': sha(math3d_result)})
            value.update(cases=consumers, vtkPythonPath=str(vtk_python), vtkPythonSha256=sha(vtk_python),
                         nodePath=str(node), nodeSha256=sha(node), math3dCheckout=str(checkout),
                         importerSha256=sha(checkout / 'renderer/src/mesh/surfaceMesh.ts'),
                         vtkConsumerSha256=sha(VTK), math3dConsumerSha256=sha(MATH3D))
        elif level == 8:
            l7 = previous
            l6 = verify(l7['l6Path'])
            l5 = verify(l6['l5Path'])
            repeats = []
            for case in manifest()['cases']:
                if case['expected'] != 'accepted':
                    continue
                for index in range(3):
                    item = run_case(case, Path(l5['workerPath']), Path(l5['runtimePrefix']),
                                    folder / f'{case["caseId"]}-{index + 1}')
                    baseline = next(saved for saved in l5['cases'] if saved['caseId'] == case['caseId'])
                    if item['outputSha256'] != baseline['outputSha256']:
                        raise ValueError('Inspection stress replay changed.')
                    repeats.append(item)
            sleep_code = "import pathlib,sys,time;print('started',flush=True);time.sleep(30);pathlib.Path(sys.argv[1]).write_text('unexpected')"
            memory_code = "import pathlib,sys,time;blocks=[]\nwhile True:\n blocks.append(bytearray(16*1024*1024));time.sleep(.05)\npathlib.Path(sys.argv[1]).write_text('unexpected')"
            probes = {mode: controlled_probe(Path(l5['runtimePrefix']) / 'python.exe',
                                              memory_code if mode == 'memory' else sleep_code,
                                              folder / (mode + '-output.txt'), mode)
                      for mode in ('cancel', 'timeout', 'memory')}
            value.update(repeatCount=3, memoryLimitBytes=128 * 1024 * 1024,
                         repeats=repeats, probes=probes)
        elif level == 9:
            l7 = verify(previous['l7Path'])
            checkout = Path(l7['math3dCheckout'])
            products = []
            for item in l7['cases']:
                product = folder / item['caseId']
                execute([l7['nodePath'], PRODUCT, '--checkout', checkout,
                         '--source', item['sourcePath'], '--expected-sha', item['sourceSha256'],
                         '--output', product], 240)
                execute([l7['nodePath'], VIEWER, '--checkout', checkout, '--product', product], 240)
                products.append({'caseId': item['caseId'], 'sourcePath': item['sourcePath'],
                                 'sourceSha256': item['sourceSha256'], 'productDirectory': str(product),
                                 'files': {name: sha(product / name) for name in PRODUCT_FILES}})
            value.update(cases=products, math3dCheckout=str(checkout), productSourceSha256=sha(PRODUCT),
                         viewerSourceSha256=sha(VIEWER), consumerSources={name: sha(checkout / name)
                         for name in ('renderer/src/mesh/surfaceMesh.ts',
                                      'renderer/src/workspace/MeshDocumentViewport.tsx',
                                      'packages/core/src/meshDocument.ts')})
    return save(folder, level, value)


def verify(path):
    path = Path(path).resolve(strict=True)
    level = int(path.stem[1:])
    if level not in range(5, 10) or sha(path) != Path(str(path) + '.sha256').read_text().strip():
        raise ValueError('Inspection qualification seal changed.')
    report = json.loads(path.read_text(encoding='utf-8'))
    expected = base(level)
    if any(report.get(key) != value for key, value in expected.items() if key != 'createdAtUtc'):
        raise ValueError('Inspection source or contract drifted.')
    fixtures = manifest()['cases']
    if level == 5:
        if sha(report['workerPath']) != report['workerSha256'] or len(report['cases']) != len(fixtures):
            raise ValueError('Inspection L5 worker or cases changed.')
        for saved, fixture in zip(report['cases'], fixtures):
            verify_case(saved, fixture)
    else:
        previous_path = Path(report[f'l{level-1}Path']).resolve(strict=True)
        if sha(previous_path) != report[f'l{level-1}Sha256']:
            raise ValueError('Previous inspection level changed.')
        previous = verify(previous_path)
        if level == 6:
            if len(report['cases']) != len(fixtures) or report['comparison'] != 'state-and-output-sha256':
                raise ValueError('Inspection L6 comparison changed.')
            for saved, fixture in zip(report['cases'], fixtures):
                verify_case(saved, fixture)
            if [(item['state'], item['outputSha256']) for item in report['cases']] != [
                    (item['state'], item['outputSha256']) for item in previous['cases']]:
                raise ValueError('Inspection L6 reproduction changed.')
        elif level == 7:
            if (len(report['cases']) != 4 or sha(report['vtkPythonPath']) != report['vtkPythonSha256']
                    or sha(report['nodePath']) != report['nodeSha256']
                    or sha(Path(report['math3dCheckout']) / 'renderer/src/mesh/surfaceMesh.ts') != report['importerSha256']
                    or sha(VTK) != report['vtkConsumerSha256'] or sha(MATH3D) != report['math3dConsumerSha256']):
                raise ValueError('Inspection L7 consumer drifted.')
            for item in report['cases']:
                if any(sha(item[name + 'Path']) != item[name + 'Sha256'] for name in ('source', 'vtk', 'math3d')):
                    raise ValueError('Inspection L7 artifact changed.')
                comparable(json.loads(Path(item['vtkPath']).read_text()),
                           json.loads(Path(item['math3dPath']).read_text()), 'MATH3D')
        elif level == 8:
            if (report['repeatCount'] != 3 or len(report['repeats']) != 21
                    or report['memoryLimitBytes'] != 128 * 1024 * 1024):
                raise ValueError('Inspection L8 stress changed.')
            for item in report['repeats']:
                fixture = next(case for case in fixtures if case['caseId'] == item['caseId'])
                verify_case(item, fixture)
            for mode, state in (('cancel', 'cancelled'), ('timeout', 'timed-out'), ('memory', 'limited')):
                probe = report['probes'][mode]
                if probe['state'] != state or not probe['outputAbsent']:
                    raise ValueError('Inspection resilience probe changed.')
        else:
            if (len(report['cases']) != 4 or sha(PRODUCT) != report['productSourceSha256']
                    or sha(VIEWER) != report['viewerSourceSha256']):
                raise ValueError('Inspection L9 product changed.')
            for name, digest in report['consumerSources'].items():
                if sha(Path(report['math3dCheckout']) / name) != digest:
                    raise ValueError('Inspection product consumer drifted.')
            for item in report['cases']:
                if sha(item['sourcePath']) != item['sourceSha256']:
                    raise ValueError('Inspection product source changed.')
                for name in PRODUCT_FILES:
                    if sha(Path(item['productDirectory']) / name) != item['files'][name]:
                        raise ValueError('Inspection product payload changed.')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('l5', 'l6', 'l7', 'l8', 'l9', 'verify'))
    for option in ('worker', 'prefix', 'source', 'output-root', 'vtk-python', 'node', 'checkout'):
        parser.add_argument('--' + option)
    args = parser.parse_args()
    target = Path(args.source).resolve() if args.command == 'verify' else run(
        int(args.command[1]), args.output_root, args.worker, args.prefix, args.source,
        args.vtk_python, args.node, args.checkout)
    verify(target)
    print(json.dumps({'report': str(target), 'sha256': sha(target)}))
