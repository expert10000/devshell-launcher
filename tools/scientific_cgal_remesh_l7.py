"""Independent VTK and MATH3D consumer qualification for accepted remesh outputs."""
import argparse
import json
import math
from pathlib import Path
import subprocess
import uuid

from scientific_cgal_mesh_metrics import metrics
from scientific_cgal_remesh_qualification import base, load, save, sha, verify_l6, verify_l5

ROOT = Path(__file__).resolve().parents[1]
VTK = ROOT / 'tools/scientific-vtk-interop.py'
MATH3D = ROOT / 'tools/math3d-vtk-import-handoff.mjs'
SOURCE = Path(__file__).resolve()


def accepted(l6):
    support = verify_l6(l6)
    l5 = verify_l5(support['reproductionPath'])
    return [(case['caseId'], Path(case['directory']) / 'remeshed.obj', case['outputSha256'])
            for case in l5['cases'] if case['state'] == 'succeeded']


def compare(item, source, vtk, math3d):
    measured = metrics(source)
    if (item['outputSha256'] != sha(source)
            or vtk.get('inputObjSha256') != item['outputSha256']
            or math3d.get('inputObjSha256') != item['outputSha256']
            or vtk.get('consumer') != 'VTK vtkOBJReader'
            or math3d.get('consumer') != 'MATH3D desktop loadSurfaceMeshFromFile'):
        raise ValueError('Remesh L7 consumer source identity changed.')
    for consumer in (vtk, math3d):
        if (consumer['points'] != measured['vertices'] or consumer['triangles'] != measured['faces']
                or consumer['boundaryEdges'] != 0 or consumer['nonManifoldEdges'] != 0
                or consumer['closed'] is not True
                or not math.isclose(consumer['signedVolume'], measured['signedVolume'], rel_tol=1e-6, abs_tol=1e-6)
                or not math.isclose(consumer['surfaceArea'], measured['area'], rel_tol=1e-6, abs_tol=1e-6)
                or len(consumer['bounds']) != 6
                or any(not math.isclose(actual, expected, rel_tol=1e-6, abs_tol=1e-6)
                       for actual, expected in zip(consumer['bounds'],
                                                   [value for pair in measured['bounds'] for value in pair]))):
            raise ValueError('Remesh L7 consumer geometry differs: ' + item['caseId'])


def run(l6, vtk_python, node, math3d_checkout, output_root):
    cases = accepted(l6)
    vtk_python = Path(vtk_python).resolve(strict=True)
    node = Path(node).resolve(strict=True)
    checkout = Path(math3d_checkout).resolve(strict=True)
    importer = checkout / 'renderer/src/mesh/surfaceMesh.ts'
    if not importer.is_file():
        raise ValueError('MATH3D desktop importer is unavailable.')
    folder = Path(output_root).resolve() / uuid.uuid4().hex
    folder.mkdir(parents=True)
    outcomes = []
    for case_id, source, output_sha in cases:
        vtk_path, math3d_path = folder / f'{case_id}-vtk.json', folder / f'{case_id}-math3d.json'
        for command in ([str(vtk_python), str(VTK), '--input', str(source), '--result', str(vtk_path)],
                        [str(node), str(MATH3D), '--checkout', str(checkout), '--input', str(source),
                         '--result', str(math3d_path)]):
            process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=120)
            if process.returncode:
                raise ValueError('Remesh L7 consumer failed: ' + (process.stderr or process.stdout)[-1000:])
        item = {'caseId': case_id, 'sourcePath': str(source), 'outputSha256': output_sha,
                'vtkPath': str(vtk_path), 'vtkSha256': sha(vtk_path),
                'math3dPath': str(math3d_path), 'math3dSha256': sha(math3d_path)}
        compare(item, source, json.loads(vtk_path.read_text()), json.loads(math3d_path.read_text()))
        outcomes.append(item)
    report = {**base('scientific.cgal-remesh-L7'), 'l7SourceSha256': sha(SOURCE),
              'l6Path': str(Path(l6).resolve()), 'l6Sha256': sha(l6),
              'vtkSourceSha256': sha(VTK), 'math3dConsumerSha256': sha(MATH3D),
              'math3dImporterSha256': sha(importer), 'math3dCheckout': str(checkout),
              'cases': outcomes}
    target = save(folder, 'l7.json', report)
    verify(target)
    return target


def verify(path):
    path, report = load(path, 'scientific.cgal-remesh-L7')
    importer = Path(report['math3dCheckout']) / 'renderer/src/mesh/surfaceMesh.ts'
    if (report['l7SourceSha256'] != sha(SOURCE)
            or report['vtkSourceSha256'] != sha(VTK)
            or report['math3dConsumerSha256'] != sha(MATH3D)
            or report['math3dImporterSha256'] != sha(importer)
            or report['l6Sha256'] != sha(report['l6Path'])):
        raise ValueError('Remesh L7 source identity changed.')
    sources = accepted(report['l6Path'])
    if len(sources) != 4 or [item['caseId'] for item in report['cases']] != [item[0] for item in sources]:
        raise ValueError('Remesh L7 accepted case set changed.')
    for item, (_, source, output_sha) in zip(report['cases'], sources):
        vtk, math3d = Path(item['vtkPath']), Path(item['math3dPath'])
        if (item['sourcePath'] != str(source) or item['outputSha256'] != output_sha
                or vtk.parent != path.parent or math3d.parent != path.parent
                or sha(vtk) != item['vtkSha256'] or sha(math3d) != item['math3dSha256']):
            raise ValueError('Remesh L7 consumer artifact changed.')
        compare(item, source, json.loads(vtk.read_text()), json.loads(math3d.read_text()))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('run', 'verify'))
    parser.add_argument('--source', required=True)
    parser.add_argument('--vtk-python')
    parser.add_argument('--node')
    parser.add_argument('--math3d-checkout')
    parser.add_argument('--output-root')
    args = parser.parse_args()
    target = run(args.source, args.vtk_python, args.node, args.math3d_checkout, args.output_root) if args.command == 'run' else Path(args.source).resolve()
    if args.command == 'verify':
        verify(target)
    print(json.dumps({'report': str(target), 'sha256': sha(target)}))
