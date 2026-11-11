"""Saved MATH3D Mesh document, M3DM reload and rendered viewer qualification."""
import argparse
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import uuid

from scientific_cgal_orientation_qualification import base, load, save, sha
from scientific_cgal_orientation_l7 import verify as verify_l7
from scientific_cgal_orientation_l8 import verify as verify_l8
from scientific_cgal_mesh_metrics import metrics

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(__file__).resolve()
PRODUCT = ROOT / 'tools/math3d-cgal-orientation-product.mjs'
VIEWER = ROOT / 'tools/math3d-cgal-orientation-viewer.mjs'
ROUNDTRIP = ROOT / 'tools/scientific-cgal-repair-m3dm-roundtrip.py'
roundtrip_spec = importlib.util.spec_from_file_location('orientation_m3dm_reload', ROUNDTRIP)
roundtrip_module = importlib.util.module_from_spec(roundtrip_spec)
roundtrip_spec.loader.exec_module(roundtrip_module)
read_m3dm, read_obj = roundtrip_module.read_m3dm, roundtrip_module.read_obj
inspect, oriented_faces = roundtrip_module.inspect, roundtrip_module.oriented_faces
NAMES = ('orientation-mesh-document.json', 'orientation-mesh-resource.bin', 'oriented.m3dm',
         'product.json', 'viewer.png', 'viewer.json')
CONSUMER_SOURCES = ('renderer/src/mesh/surfaceMesh.ts', 'renderer/src/mesh/meshDocumentAdapter.ts',
                    'renderer/src/mesh/meshResourceStore.ts', 'packages/core/src/meshDocument.ts',
                    'src/main/python/nativeCgalProtocol.ts')


def check_case(item, source, checkout, folder):
    product = Path(item['productDirectory']).resolve(strict=True)
    if product.parent != folder or item['sourcePath'] != str(source) or item['sourceSha256'] != sha(source):
        raise ValueError('Orientation L9 product source changed.')
    if set(item['files']) != set(NAMES):
        raise ValueError('Orientation L9 product file set changed.')
    for name in NAMES:
        if sha(product / name) != item['files'][name]:
            raise ValueError('Orientation L9 product file changed: ' + name)
    record = json.loads((product / 'product.json').read_text())
    viewer = json.loads((product / 'viewer.json').read_text())
    document = json.loads((product / 'orientation-mesh-document.json').read_text())
    if (record.get('kind') != 'scientific.cgal-orientation-math3d-product'
            or viewer.get('kind') != 'scientific.cgal-orientation-math3d-viewer'
            or record['verdict'] != 'passed' or viewer['verdict'] != 'passed'
            or record['sourceObjSha256'] != item['sourceSha256']
            or record['documentSha256'] != item['files']['orientation-mesh-document.json']
            or record['resourceSha256'] != item['files']['orientation-mesh-resource.bin']
            or record['m3dmSha256'] != item['files']['oriented.m3dm']
            or record['consumerSources'] != {name: sha(checkout / name) for name in CONSUMER_SOURCES}
            or document['identity']['id'] != record['documentId']
            or document['identity']['structuralHash'] != record['structuralHash']
            or viewer['documentId'] != record['documentId']
            or viewer['structuralHash'] != record['structuralHash']
            or viewer['viewerSourceSha256'] != sha(checkout / 'renderer/src/workspace/MeshDocumentViewport.tsx')
            or viewer['screenshotSha256'] != item['files']['viewer.png']
            or viewer['viewerState'] != 'mounted' or viewer['blueMeshPixels'] < 1000):
        raise ValueError('Orientation L9 MATH3D document or viewer changed.')
    source_vertices, source_faces = read_obj(source)
    restored_vertices, restored_faces = read_m3dm(product / 'oriented.m3dm')
    original, restored = inspect(source_vertices, source_faces), inspect(restored_vertices, restored_faces)
    measured = metrics(source)
    if (record['points'] != measured['vertices'] or record['triangles'] != measured['faces']
            or restored['points'] != original['points'] or restored['triangles'] != original['triangles']
            or oriented_faces(source_vertices, source_faces) != oriented_faces(restored_vertices, restored_faces)
            or not math.isclose(restored['signedVolume'], original['signedVolume'], rel_tol=1e-6, abs_tol=1e-6)
            or not math.isclose(restored['surfaceArea'], original['surfaceArea'], rel_tol=1e-6, abs_tol=1e-6)):
        raise ValueError('Independent orientation M3DM reload differs from accepted OBJ.')


def run(l8, node, output_root):
    support = verify_l8(l8)
    l7 = verify_l7(support['l7Path'])
    checkout = Path(l7['math3dCheckout']).resolve(strict=True)
    node = Path(node).resolve(strict=True)
    folder = Path(output_root).resolve() / uuid.uuid4().hex
    folder.mkdir(parents=True)
    outcomes = []
    for case in l7['cases']:
        source = Path(case['sourcePath']).resolve(strict=True)
        product = folder / case['caseId']
        for command in ([str(node), str(PRODUCT), '--checkout', str(checkout), '--source', str(source),
                         '--expected-sha', case['outputSha256'], '--output', str(product)],
                        [str(node), str(VIEWER), '--checkout', str(checkout), '--product', str(product)]):
            process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=240)
            if process.returncode:
                raise ValueError('Orientation L9 MATH3D product failed: ' + (process.stderr or process.stdout)[-1500:])
        item = {'caseId': case['caseId'], 'sourcePath': str(source),
                'sourceSha256': case['outputSha256'], 'productDirectory': str(product),
                'files': {name: sha(product / name) for name in NAMES}}
        check_case(item, source, checkout, folder)
        outcomes.append(item)
    report = {**base('scientific.cgal-orientation-L9'), 'l9SourceSha256': sha(SOURCE),
              'productSourceSha256': sha(PRODUCT), 'viewerToolSha256': sha(VIEWER),
              'roundtripSourceSha256': sha(ROUNDTRIP), 'l8Path': str(Path(l8).resolve()),
              'l8Sha256': sha(l8), 'math3dCheckout': str(checkout), 'cases': outcomes}
    target = save(folder, 'l9.json', report)
    verify(target)
    return target


def verify(path):
    path, report = load(path, 'scientific.cgal-orientation-L9')
    if (report['l9SourceSha256'] != sha(SOURCE)
            or report['productSourceSha256'] != sha(PRODUCT)
            or report['viewerToolSha256'] != sha(VIEWER)
            or report['roundtripSourceSha256'] != sha(ROUNDTRIP)
            or report['l8Sha256'] != sha(report['l8Path'])):
        raise ValueError('Orientation L9 tool or lower evidence changed.')
    support = verify_l8(report['l8Path'])
    l7 = verify_l7(support['l7Path'])
    checkout = Path(report['math3dCheckout']).resolve(strict=True)
    if checkout != Path(l7['math3dCheckout']).resolve(strict=True):
        raise ValueError('Orientation L9 MATH3D checkout changed.')
    if len(report['cases']) != len(l7['cases']):
        raise ValueError('Orientation L9 case set changed.')
    for item, case in zip(report['cases'], l7['cases']):
        if item['caseId'] != case['caseId'] or item['sourceSha256'] != case['outputSha256']:
            raise ValueError('Orientation L9 case identity changed.')
        check_case(item, Path(case['sourcePath']), checkout, path.parent)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('run', 'verify'))
    parser.add_argument('--source', required=True)
    parser.add_argument('--node')
    parser.add_argument('--output-root')
    args = parser.parse_args()
    target = run(args.source, args.node, args.output_root) if args.command == 'run' else Path(args.source).resolve()
    if args.command == 'verify':
        verify(target)
    print(json.dumps({'report': str(target), 'sha256': sha(target)}))
