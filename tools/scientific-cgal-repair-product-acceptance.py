"""Replay managed repair through MATH3D save, independent reload, and viewer."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PRODUCT = ROOT / 'tools/math3d-cgal-repair-product.mjs'
ROUNDTRIP = ROOT / 'tools/scientific-cgal-repair-m3dm-roundtrip.py'
VIEWER = ROOT / 'tools/math3d-cgal-repair-viewer.mjs'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def invoke(arguments, directory, label):
    process = subprocess.run(arguments, cwd=ROOT, capture_output=True, text=True, timeout=180)
    (directory / (label + '.log')).write_text(process.stdout + process.stderr, encoding='utf-8')
    if process.returncode != 0:
        raise ValueError(label + ' failed: ' + process.stderr[-1500:])


def run(acceptance_path, checkout, node):
    acceptance_path, checkout = Path(acceptance_path).resolve(strict=True), Path(checkout).resolve(strict=True)
    root = acceptance_path.parent
    acceptance = json.loads(acceptance_path.read_text(encoding='utf-8'))
    expected = {'cgal.fill-one-hole', 'cgal.fill-quad-hole', 'cgal.fill-two-quad-holes', 'cgal.fill-bounded-holes'}
    if (acceptance.get('verdict') != 'passed' or {case['recipeId'] for case in acceptance['cases']} != expected
            or not acceptance.get('wrongOperationResultSha256') or not acceptance.get('changedHashResultSha256')):
        raise ValueError('Managed repair acceptance is incomplete')
    records = []
    for case in acceptance['cases']:
        operation = case['recipeId'].removeprefix('cgal.')
        directory = root / operation
        handoff = directory / 'handoff.json'
        if (not handoff.is_file() or case.get('math3dHandoffSha256') != sha(handoff)
                or case['resultSha256'] != sha(directory / 'results.json')
                or case['outputSha256'] != sha(directory / 'repaired.obj')):
            raise ValueError(operation + ': managed source or importer evidence changed')
        product = directory / 'product'
        invoke([node, str(PRODUCT), '--checkout', str(checkout), '--run-directory', str(directory),
                '--handoff', str(handoff), '--output', str(product)], directory, 'product')
        invoke([sys.executable, str(ROUNDTRIP), '--run-directory', str(directory), '--handoff', str(handoff),
                '--product-directory', str(product), '--report', str(product / 'roundtrip.json')], directory, 'roundtrip')
        invoke([node, str(VIEWER), '--checkout', str(checkout), '--product', str(product)], directory, 'viewer')
        saved = json.loads((product / 'product.json').read_text(encoding='utf-8'))
        reloaded = json.loads((product / 'roundtrip.json').read_text(encoding='utf-8'))
        viewed = json.loads((product / 'viewer.json').read_text(encoding='utf-8'))
        if (saved['verdict'] != reloaded['verdict'] or viewed['verdict'] != 'passed'
                or saved['m3dmSha256'] != reloaded['m3dmSha256']
                or saved['m3dmSha256'] != viewed['m3dmSha256']
                or saved['runId'] != reloaded['runId'] or saved['runId'] != viewed['runId']
                or viewed['blueMeshPixels'] < 1000 or viewed['screenshotSha256'] != sha(product / 'viewer.png')):
            raise ValueError(operation + ': saved document, reload and viewer disagree')
        records.append({'recipeId': case['recipeId'], 'sourceRunId': saved['runId'],
                        'm3dmSha256': saved['m3dmSha256'], 'documentSha256': saved['documentSha256'],
                        'roundtripSha256': sha(product / 'roundtrip.json'),
                        'viewerSha256': sha(product / 'viewer.json'),
                        'screenshotSha256': viewed['screenshotSha256'],
                        'blueMeshPixels': viewed['blueMeshPixels']})
    # A changed M3DM must fail the separate Python reader before it can be published.
    source_product = root / 'fill-bounded-holes' / 'product'
    tampered = root / 'tampered-product'
    tampered.mkdir()
    for name in ('product.json', 'repair-mesh-document.json', 'repair-mesh-resource.bin', 'repaired.m3dm'):
        shutil.copyfile(source_product / name, tampered / name)
    changed = bytearray((tampered / 'repaired.m3dm').read_bytes())
    changed[-1] ^= 1
    (tampered / 'repaired.m3dm').write_bytes(changed)
    process = subprocess.run([sys.executable, str(ROUNDTRIP), '--run-directory', str(root / 'fill-bounded-holes'),
                              '--handoff', str(root / 'fill-bounded-holes' / 'handoff.json'),
                              '--product-directory', str(tampered), '--report', str(tampered / 'roundtrip.json')],
                             cwd=ROOT, capture_output=True, text=True, timeout=60)
    if process.returncode == 0 or (tampered / 'roundtrip.json').exists():
        raise ValueError('Changed M3DM was accepted by the independent reader')
    report = {'schemaVersion': 1, 'kind': 'scientific.cgal-repair-product-acceptance', 'verdict': 'passed',
              'managedAcceptanceSha256': sha(acceptance_path), 'productSourceSha256': sha(PRODUCT),
              'roundtripSourceSha256': sha(ROUNDTRIP), 'viewerSourceSha256': sha(VIEWER),
              'cases': records, 'changedM3dmRejected': True}
    destination = root / 'product-acceptance.json'
    destination.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'verdict': 'passed', 'report': str(destination), 'cases': len(records)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--managed-acceptance', required=True)
    parser.add_argument('--checkout', required=True)
    parser.add_argument('--node', default='node')
    args = parser.parse_args()
    run(args.managed_acceptance, args.checkout, args.node)
