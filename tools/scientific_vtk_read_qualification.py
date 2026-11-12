"""Linked, independently verified VTK mesh.read L5-L9 evidence."""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import time
import uuid

import psutil

from scientific_vtk_read_scope import MANIFEST, WORKER, CONTRACT, ROOT, manifest, run as live_scope, verify as verify_scope, sha

SOURCE = Path(__file__).resolve()
PARSER = ROOT / 'tools/scientific-artifact-roundtrip.py'
VTK = ROOT / 'tools/scientific-vtk-interop.py'
MATH3D = ROOT / 'tools/math3d-vtk-import-handoff.mjs'
PRODUCT = ROOT / 'tools/math3d-vtk-read-product.mjs'
VIEWER = ROOT / 'tools/math3d-vtk-read-viewer.mjs'
M3DM = ROOT / 'tools/scientific-cgal-repair-m3dm-roundtrip.py'
product_spec = importlib.util.spec_from_file_location('vtk_read_m3dm', M3DM)
product_module = importlib.util.module_from_spec(product_spec)
product_spec.loader.exec_module(product_module)
read_obj, read_m3dm, oriented_faces = product_module.read_obj, product_module.read_m3dm, product_module.oriented_faces
FILES = ('vtk-mesh-document.json', 'vtk-mesh-resource.bin', 'read.m3dm', 'product.json', 'viewer.png', 'viewer.json')
CONSUMERS = ('renderer/src/mesh/surfaceMesh.ts', 'renderer/src/mesh/meshDocumentAdapter.ts',
             'renderer/src/mesh/meshResourceStore.ts', 'packages/core/src/meshDocument.ts',
             'src/main/python/nativeCgalProtocol.ts', 'renderer/src/workspace/MeshDocumentViewport.tsx')


def base(level):
    manifest()
    return {'schemaVersion': 1, 'kind': f'scientific.vtk-read-L{level}', 'verdict': 'passed',
            'createdAtUtc': datetime.now(timezone.utc).isoformat(), 'capabilityId': 'mesh.read',
            'suiteId': 'vtk-mesh-read-v4', 'manifestSha256': sha(MANIFEST),
            'workerSourceSha256': sha(WORKER), 'contractSha256': sha(CONTRACT),
            'scopeSourceSha256': sha(ROOT / 'tools/scientific_vtk_read_scope.py'),
            'qualificationSourceSha256': sha(SOURCE)}


def save(folder, level, report):
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f'l{level}.json'
    with target.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, separators=(',', ':'), allow_nan=False)
    Path(str(target) + '.sha256').write_text(sha(target), encoding='utf-8')
    verify(target)
    return target


def load(path, level):
    path = Path(path).resolve(strict=True)
    if path.name != f'l{level}.json' or sha(path) != Path(str(path) + '.sha256').read_text().strip():
        raise ValueError('VTK qualification seal changed.')
    report = json.loads(path.read_text(encoding='utf-8'))
    expected = base(level)
    if any(report.get(key) != value for key, value in expected.items() if key != 'createdAtUtc'):
        raise ValueError('VTK qualification source or identity changed.')
    return path, report


def linked(report, lower, level):
    prior = Path(report[f'l{lower}Path']).resolve(strict=True)
    if sha(prior) != report[f'l{lower}Sha256']:
        raise ValueError('VTK lower qualification changed.')
    verify(prior)
    if prior.name != f'l{lower}.json' or level != lower + 1:
        raise ValueError('VTK qualification chain is invalid.')
    return json.loads(prior.read_text())


def accepted(l6):
    replay = verify_scope(l6['replayPath'])
    return [(case['caseId'], Path(case['directory']) / 'mesh.vtp', case['outputSha256'])
            for case in replay['cases'] if case['state'] == 'succeeded']


def run_l5(python, output_root):
    folder = Path(output_root).resolve() / uuid.uuid4().hex
    folder.mkdir(parents=True)
    scope_path, scope = live_scope(python, folder)
    return save(folder, 5, {**base(5), 'scopePath': str(scope_path), 'scopeSha256': sha(scope_path),
                            'pythonPath': scope['pythonPath'], 'pythonSha256': scope['pythonSha256'],
                            'cases': scope['cases']})


def run_l6(source, output_root):
    l5 = verify(source)
    folder = Path(output_root).resolve() / uuid.uuid4().hex
    folder.mkdir(parents=True)
    replay_path, replay = live_scope(l5['pythonPath'], folder)
    if [(item['caseId'], item['state'], item['outputSha256']) for item in l5['cases']] != [
        (item['caseId'], item['state'], item['outputSha256']) for item in replay['cases']]:
        raise ValueError('VTK L6 replay differs from L5.')
    return save(folder, 6, {**base(6), 'l5Path': str(Path(source).resolve()), 'l5Sha256': sha(source),
                            'replayPath': str(replay_path), 'replaySha256': sha(replay_path),
                            'comparison': 'state-and-output-sha256'})


def execute(arguments, timeout=120):
    completed = subprocess.run([str(item) for item in arguments], cwd=ROOT, text=True,
                               capture_output=True, timeout=timeout)
    if completed.returncode:
        raise ValueError('VTK consumer failed: ' + (completed.stderr or completed.stdout)[-1200:])


def comparable(reference, observed, name):
    if observed['points'] != reference['points'] or observed['triangles'] != reference['triangles']:
        raise ValueError(name + ' mesh counts changed.')
    for field in ('boundaryEdges', 'nonManifoldEdges', 'closed'):
        if observed[field] != reference[field]:
            raise ValueError(name + ' topology changed.')
    for actual, expected in zip(observed['bounds'], reference['bounds']):
        if not math.isclose(actual, expected, rel_tol=1e-6, abs_tol=1e-6):
            raise ValueError(name + ' bounds changed.')
    for field in ('signedVolume', 'surfaceArea'):
        if not math.isclose(observed[field], reference[field], rel_tol=1e-6, abs_tol=1e-6):
            raise ValueError(name + ' geometry changed.')


def run_l7(source, vtk_python, node, checkout, output_root):
    l6 = verify(source)
    vtk_python, node, checkout = (Path(item).resolve(strict=True) for item in (vtk_python, node, checkout))
    importer = checkout / 'renderer/src/mesh/surfaceMesh.ts'
    if not importer.is_file():
        raise ValueError('MATH3D importer is unavailable.')
    folder = Path(output_root).resolve() / uuid.uuid4().hex
    folder.mkdir(parents=True)
    cases = []
    for case_id, vtp, digest in accepted(l6):
        obj, reload, vtk, math3d = (folder / f'{case_id}{suffix}' for suffix in
                                   ('.obj', '-reload.json', '-vtk.json', '-math3d.json'))
        execute([vtk_python, PARSER, '--input', vtp, '--result', reload, '--export-obj', obj])
        execute([vtk_python, VTK, '--input', obj, '--result', vtk])
        execute([node, MATH3D, '--checkout', checkout, '--input', obj, '--result', math3d])
        reference = json.loads(reload.read_text())
        if reference['artifactSha256'] != digest or reference['exportObjSha256'] != sha(obj):
            raise ValueError('VTK VTP reload changed.')
        comparable(reference, json.loads(vtk.read_text()), 'VTK')
        comparable(reference, json.loads(math3d.read_text()), 'MATH3D')
        cases.append({'caseId': case_id, 'sourcePath': str(vtp), 'sourceSha256': digest,
                      'objPath': str(obj), 'objSha256': sha(obj),
                      'reloadPath': str(reload), 'reloadSha256': sha(reload),
                      'vtkPath': str(vtk), 'vtkSha256': sha(vtk),
                      'math3dPath': str(math3d), 'math3dSha256': sha(math3d)})
    report = {**base(7), 'l6Path': str(Path(source).resolve()), 'l6Sha256': sha(source),
              'vtkPythonPath': str(vtk_python), 'vtkPythonSha256': sha(vtk_python),
              'nodePath': str(node), 'nodeSha256': sha(node), 'math3dCheckout': str(checkout),
              'math3dImporterSha256': sha(importer), 'parserSha256': sha(PARSER),
              'vtkConsumerSha256': sha(VTK), 'math3dConsumerSha256': sha(MATH3D), 'cases': cases}
    return save(folder, 7, report)


def controlled_probe(python, code, marker, mode):
    started = time.monotonic()
    child = subprocess.Popen([str(python), '-c', code, str(marker)], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    process = psutil.Process(child.pid)
    peak = 0
    try:
        while child.poll() is None:
            elapsed = time.monotonic() - started
            try:
                peak = max(peak, process.memory_info().rss)
            except psutil.NoSuchProcess:
                break
            if ((mode == 'cancel' and elapsed >= .5) or (mode == 'timeout' and elapsed >= 1)
                    or (mode == 'memory' and peak >= 128 * 1024 * 1024)):
                child.kill()
                break
            if elapsed > 10:
                raise ValueError('VTK process control probe did not reach its limit.')
            time.sleep(.01)
        child.communicate(timeout=2)
    finally:
        if child.poll() is None:
            child.kill(); child.communicate(timeout=2)
    if marker.exists() or child.returncode == 0 or (mode == 'memory' and peak < 128 * 1024 * 1024):
        raise ValueError('VTK limited child published output or missed its limit.')
    return {'state': {'cancel': 'cancelled', 'timeout': 'timed-out', 'memory': 'limited'}[mode],
            'durationMs': round((time.monotonic() - started) * 1000), 'peakRssBytes': peak, 'outputAbsent': True}


def run_l8(source, output_root):
    l7 = verify(source)
    folder = Path(output_root).resolve() / uuid.uuid4().hex
    folder.mkdir(parents=True)
    repeats = []
    for case in l7['cases']:
        for index in range(3):
            target = folder / f"{case['caseId']}-{index + 1}.json"
            execute([l7['vtkPythonPath'], VTK, '--input', case['objPath'], '--result', target])
            if json.loads(target.read_text()) != json.loads(Path(case['vtkPath']).read_text()):
                raise ValueError('VTK repeated read changed.')
            repeats.append({'caseId': case['caseId'], 'repeat': index + 1,
                            'path': str(target), 'sha256': sha(target)})
    sleep_code = "import pathlib,sys,time;print('started',flush=True);time.sleep(30);pathlib.Path(sys.argv[1]).write_text('unexpected')"
    memory_code = "import pathlib,sys,time;blocks=[]\nwhile True:\n blocks.append(bytearray(16*1024*1024));time.sleep(.05)\npathlib.Path(sys.argv[1]).write_text('unexpected')"
    probes = {mode: controlled_probe(l7['vtkPythonPath'], memory_code if mode == 'memory' else sleep_code,
                                      folder / (mode + '-output.txt'), mode)
              for mode in ('cancel', 'timeout', 'memory')}
    return save(folder, 8, {**base(8), 'l7Path': str(Path(source).resolve()), 'l7Sha256': sha(source),
                            'repeatCount': 3, 'memoryLimitBytes': 128 * 1024 * 1024,
                            'repeats': repeats, 'probes': probes})


def run_l9(source, output_root):
    l8 = verify(source)
    l7 = verify(l8['l7Path'])
    checkout = Path(l7['math3dCheckout'])
    folder = Path(output_root).resolve() / uuid.uuid4().hex
    folder.mkdir(parents=True)
    cases = []
    for case in l7['cases']:
        product = folder / case['caseId']
        execute([l7['nodePath'], PRODUCT, '--checkout', checkout, '--source', case['objPath'],
                 '--expected-sha', case['objSha256'], '--output', product], 240)
        execute([l7['nodePath'], VIEWER, '--checkout', checkout, '--product', product], 240)
        cases.append({'caseId': case['caseId'], 'sourcePath': case['objPath'],
                      'sourceSha256': case['objSha256'], 'productDirectory': str(product),
                      'files': {name: sha(product / name) for name in FILES}})
    report = {**base(9), 'l8Path': str(Path(source).resolve()), 'l8Sha256': sha(source),
              'math3dCheckout': str(checkout), 'productSourceSha256': sha(PRODUCT),
              'viewerSourceSha256': sha(VIEWER), 'm3dmParserSha256': sha(M3DM),
              'consumerSources': {name: sha(checkout / name) for name in CONSUMERS}, 'cases': cases}
    return save(folder, 9, report)


def verify(path):
    path = Path(path).resolve(strict=True)
    level = int(path.stem[1:])
    path, report = load(path, level)
    if level == 5:
        scope = verify_scope(report['scopePath'])
        if (sha(report['scopePath']) != report['scopeSha256'] or report['cases'] != scope['cases']
                or report['pythonPath'] != scope['pythonPath'] or report['pythonSha256'] != scope['pythonSha256']):
            raise ValueError('VTK L5 scope changed.')
    elif level == 6:
        l5 = linked(report, 5, level)
        replay = verify_scope(report['replayPath'])
        if (report['comparison'] != 'state-and-output-sha256' or sha(report['replayPath']) != report['replaySha256']
                or [(item['caseId'], item['state'], item['outputSha256']) for item in l5['cases']] !=
                   [(item['caseId'], item['state'], item['outputSha256']) for item in replay['cases']]):
            raise ValueError('VTK L6 reproduction changed.')
    elif level == 7:
        l6 = linked(report, 6, level)
        checkout = Path(report['math3dCheckout']).resolve(strict=True)
        if (sha(report['vtkPythonPath']) != report['vtkPythonSha256'] or sha(report['nodePath']) != report['nodeSha256']
                or sha(checkout / 'renderer/src/mesh/surfaceMesh.ts') != report['math3dImporterSha256']
                or sha(PARSER) != report['parserSha256'] or sha(VTK) != report['vtkConsumerSha256']
                or sha(MATH3D) != report['math3dConsumerSha256']):
            raise ValueError('VTK L7 consumer source changed.')
        sources = accepted(l6)
        if len(report['cases']) != len(sources):
            raise ValueError('VTK L7 case set changed.')
        for item, (case_id, vtp, digest) in zip(report['cases'], sources):
            if item['caseId'] != case_id or item['sourcePath'] != str(vtp) or item['sourceSha256'] != digest:
                raise ValueError('VTK L7 source case changed.')
            for name in ('obj', 'reload', 'vtk', 'math3d'):
                target = Path(item[name + 'Path']).resolve(strict=True)
                if target.parent != path.parent or sha(target) != item[name + 'Sha256']:
                    raise ValueError('VTK L7 consumer artifact changed.')
            reload = json.loads(Path(item['reloadPath']).read_text())
            if reload['artifactSha256'] != digest or reload['exportObjSha256'] != item['objSha256']:
                raise ValueError('VTK L7 reload changed.')
            for name in ('vtk', 'math3d'):
                observed = json.loads(Path(item[name + 'Path']).read_text())
                if observed['inputObjSha256'] != item['objSha256']:
                    raise ValueError('VTK L7 consumer source changed.')
                comparable(reload, observed, name)
    elif level == 8:
        l7 = linked(report, 7, level)
        if report['repeatCount'] != 3 or report['memoryLimitBytes'] != 128 * 1024 * 1024:
            raise ValueError('VTK L8 policy changed.')
        expected = [(case, index) for case in l7['cases'] for index in range(1, 4)]
        if len(report['repeats']) != len(expected):
            raise ValueError('VTK L8 repeat count changed.')
        for item, (case, index) in zip(report['repeats'], expected):
            target = Path(item['path']).resolve(strict=True)
            if (item['caseId'] != case['caseId'] or item['repeat'] != index or target.parent != path.parent
                    or sha(target) != item['sha256']
                    or json.loads(target.read_text()) != json.loads(Path(case['vtkPath']).read_text())):
                raise ValueError('VTK L8 repeat changed.')
        for mode, state in (('cancel', 'cancelled'), ('timeout', 'timed-out'), ('memory', 'limited')):
            probe = report['probes'][mode]
            if probe['state'] != state or not probe['outputAbsent'] or (path.parent / (mode + '-output.txt')).exists():
                raise ValueError('VTK L8 process limit changed.')
        if report['probes']['memory']['peakRssBytes'] < report['memoryLimitBytes']:
            raise ValueError('VTK L8 memory cap was not observed.')
    elif level == 9:
        l8 = linked(report, 8, level)
        l7 = verify(l8['l7Path'])
        checkout = Path(report['math3dCheckout']).resolve(strict=True)
        if (checkout != Path(l7['math3dCheckout']).resolve() or sha(PRODUCT) != report['productSourceSha256']
                or sha(VIEWER) != report['viewerSourceSha256'] or sha(M3DM) != report['m3dmParserSha256']
                or report['consumerSources'] != {name: sha(checkout / name) for name in CONSUMERS}
                or len(report['cases']) != len(l7['cases'])):
            raise ValueError('VTK L9 product sources changed.')
        for item, source in zip(report['cases'], l7['cases']):
            product = Path(item['productDirectory']).resolve(strict=True)
            if (item['caseId'] != source['caseId'] or item['sourcePath'] != source['objPath']
                    or item['sourceSha256'] != source['objSha256'] or product.parent != path.parent
                    or set(item['files']) != set(FILES)):
                raise ValueError('VTK L9 product case changed.')
            for name in FILES:
                if sha(product / name) != item['files'][name]:
                    raise ValueError('VTK L9 product artifact changed.')
            record = json.loads((product / 'product.json').read_text())
            viewer = json.loads((product / 'viewer.json').read_text())
            document = json.loads((product / 'vtk-mesh-document.json').read_text())
            if (record['kind'] != 'scientific.vtk-read-math3d-product' or viewer['kind'] != 'scientific.vtk-read-math3d-viewer'
                    or record['verdict'] != 'passed' or viewer['verdict'] != 'passed'
                    or record['sourceObjSha256'] != item['sourceSha256']
                    or record['documentSha256'] != item['files']['vtk-mesh-document.json']
                    or record['resourceSha256'] != item['files']['vtk-mesh-resource.bin']
                    or record['m3dmSha256'] != item['files']['read.m3dm']
                    or record['consumerSources'] != {name: report['consumerSources'][name] for name in CONSUMERS[:-1]}
                    or document['identity']['id'] != record['documentId']
                    or viewer['documentId'] != record['documentId'] or viewer['structuralHash'] != record['structuralHash']
                    or viewer['screenshotSha256'] != item['files']['viewer.png']
                    or viewer['viewerSourceSha256'] != report['consumerSources'][CONSUMERS[-1]]
                    or viewer['viewerState'] != 'mounted' or viewer['blueMeshPixels'] < 1000):
                raise ValueError('VTK L9 saved document or viewer changed.')
            vertices, faces = read_obj(item['sourcePath'])
            restored_vertices, restored_faces = read_m3dm(product / 'read.m3dm')
            if (len(restored_vertices) != len(vertices) or len(restored_faces) != len(faces)
                    or oriented_faces(vertices, faces) != oriented_faces(restored_vertices, restored_faces)):
                raise ValueError('VTK L9 M3DM round trip changed topology or winding.')
    else:
        raise ValueError('Unsupported VTK qualification level.')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('l5', 'l6', 'l7', 'l8', 'l9', 'verify'))
    parser.add_argument('--source')
    parser.add_argument('--python')
    parser.add_argument('--vtk-python')
    parser.add_argument('--node')
    parser.add_argument('--math3d-checkout')
    parser.add_argument('--output-root')
    options = parser.parse_args()
    if options.command == 'l5': target = run_l5(options.python, options.output_root)
    elif options.command == 'l6': target = run_l6(options.source, options.output_root)
    elif options.command == 'l7': target = run_l7(options.source, options.vtk_python, options.node, options.math3d_checkout, options.output_root)
    elif options.command == 'l8': target = run_l8(options.source, options.output_root)
    elif options.command == 'l9': target = run_l9(options.source, options.output_root)
    else:
        target = Path(options.source).resolve()
        verify(target)
    print(json.dumps({'report': str(target), 'sha256': sha(target)}))
