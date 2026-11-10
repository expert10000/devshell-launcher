"""Sealed, independently verifiable managed CGAL remesh qualification."""
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
from scientific_cgal_remesh_guard import verify as verify_guard

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'scientific/fixtures/cgal-remesh-qualification/manifest.json'
POLICY = ROOT / 'schemas/scientific-remesh-guard.v2.json'
ADAPTER = ROOT / 'tools/scientific-cgal-worker.py'
GUARD = ROOT / 'tools/scientific_cgal_remesh_guard.py'
CASES = ('accepted', 'volume-loss', 'malformed-open', 'affine-accepted', 'affine-volume-loss',
         'cube-accepted', 'cube-volume-loss', 'octa-accepted', 'octa-volume-loss',
         'inward-invalid', 'nonmanifold-invalid', 'degenerate-invalid')


def sha(path):
    return file_sha(Path(path))


def fixture_manifest():
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    if (manifest.get('schemaVersion') != 1 or manifest.get('suiteId') != 'cgal-remesh-guarded-v2'
            or manifest.get('capabilityId') != 'mesh.remesh'
            or [item['caseId'] for item in manifest['cases']] != list(CASES)
            or manifest.get('policy') != str(POLICY.relative_to(ROOT)).replace('\\', '/')):
        raise ValueError('Remesh qualification fixture manifest changed.')
    for item in manifest['cases']:
        path = (ROOT / item['path']).resolve(strict=True)
        if not path.is_relative_to(ROOT) or sha(path) != item['sha256']:
            raise ValueError('Remesh qualification fixture changed: ' + item['caseId'])
    return manifest


def save(root, name, value):
    root.mkdir(parents=True, exist_ok=True)
    path = root / name
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, separators=(',', ':'), allow_nan=False)
    Path(str(path) + '.sha256').write_text(sha(path), encoding='utf-8')
    return path


def load(path, kind):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('Remesh qualification report hash mismatch.')
    report = json.loads(path.read_text(encoding='utf-8'))
    if (report.get('schemaVersion') != 1 or report.get('kind') != kind
            or report.get('verdict') != 'passed' or report.get('manifestSha256') != sha(MANIFEST)
            or report.get('policySha256') != sha(POLICY)
            or report.get('adapterSha256') != sha(ADAPTER)
            or report.get('guardSha256') != sha(GUARD)
            or report.get('qualificationSourceSha256') != sha(Path(__file__))):
        raise ValueError('Remesh qualification source or report changed.')
    fixture_manifest()
    return path, report


def base(kind):
    fixture_manifest()
    return {'schemaVersion': 1, 'kind': kind, 'verdict': 'passed',
            'createdAtUtc': datetime.now(timezone.utc).isoformat(),
            'manifestSha256': sha(MANIFEST), 'policySha256': sha(POLICY),
            'adapterSha256': sha(ADAPTER), 'guardSha256': sha(GUARD),
            'qualificationSourceSha256': sha(Path(__file__))}


def managed_case(item, worker, prefix, root):
    directory = root / item['caseId']
    directory.mkdir()
    dataset = directory / 'dataset'
    dataset.mkdir()
    source = dataset / 'input.obj'
    shutil.copyfile(ROOT / item['path'], source)
    request = {'schemaVersion': 1, 'runId': uuid.uuid4().hex,
               'runtimeId': 'cgal-win-conda', 'recipeId': 'cgal.remesh',
               'workingDirectory': str(directory), 'datasetRoot': str(dataset),
               'inputArtifacts': [{'path': str(source), 'sha256': sha(source)}],
               'outputArtifacts': [{'path': 'remeshed.obj'}],
               'parameters': {'targetEdge': item['targetEdge'], 'iterations': item['iterations'],
                              'preserveBoundary': False}}
    request_path = directory / 'request.json'
    request_path.write_text(json.dumps(request), encoding='utf-8')
    process = subprocess.run([str(prefix / 'python.exe'), str(ADAPTER), '--request', str(request_path),
                              '--worker', str(worker), '--prefix', str(prefix)],
                             cwd=ROOT, capture_output=True, text=True, timeout=120)
    result_path = directory / 'results.json'
    if not result_path.is_file():
        raise ValueError('Managed remesh did not save a result: ' + process.stderr[-800:])
    result = json.loads(result_path.read_text(encoding='utf-8-sig'))
    expected = 'succeeded' if item['expected'] == 'accepted' else 'failed'
    output = directory / 'remeshed.obj'
    if (result.get('runId') != request['runId'] or result.get('recipeId') != 'cgal.remesh'
            or result.get('state') != expected or output.exists() != (expected == 'succeeded')
            or bool(result.get('artifacts')) != (expected == 'succeeded')
            or ('mesh.remesh' in result.get('validatedCapabilities', [])) != (expected == 'succeeded')):
        raise ValueError('Managed remesh publication state differs: ' + item['caseId'])
    evidence = result.get('guardEvidence')
    if item['expected'] == 'invalid-input':
        if evidence is not None:
            raise ValueError('Invalid input reached the remesh worker.')
    else:
        if not evidence or evidence['state'] != item['expected']:
            raise ValueError('Managed guard decision differs: ' + item['caseId'])
        report_path = directory / evidence['path']
        guard = verify_guard(report_path)
        if (sha(report_path) != evidence['sha256'] or guard['state'] != evidence['state']
                or guard['policySha256'] != evidence['policySha256']
                or guard['sourceSha256'] != item['sha256']
                or guard['parameters'] != {'targetEdge': item['targetEdge'],
                                           'iterations': item['iterations'], 'preserveBoundary': 0}):
            raise ValueError('Managed guard evidence differs: ' + item['caseId'])
        if expected == 'succeeded' and sha(output) != guard['acceptedSha256']:
            raise ValueError('Published remesh differs from guard acceptance.')
        if item['expected'] == 'rejected' and not guard['measurements']['decision']['checks']['relativeVolume'] is False:
            raise ValueError('Adverse remesh no longer demonstrates volume loss.')
    return {'caseId': item['caseId'], 'directory': str(directory),
            'requestSha256': sha(request_path), 'resultSha256': sha(result_path),
            'state': result['state'], 'outputSha256': sha(output) if output.exists() else None,
            'guardReportSha256': evidence['sha256'] if evidence else None}


def verify_case(saved, item):
    directory = Path(saved['directory']).resolve(strict=True)
    request_path, result_path, output = (directory / name for name in
                                        ('request.json', 'results.json', 'remeshed.obj'))
    request = json.loads(request_path.read_text(encoding='utf-8'))
    result = json.loads(result_path.read_text(encoding='utf-8-sig'))
    if (saved['caseId'] != item['caseId'] or sha(request_path) != saved['requestSha256']
            or sha(result_path) != saved['resultSha256']
            or request.get('runId') != result.get('runId')
            or request['inputArtifacts'][0]['sha256'] != item['sha256']
            or sha(request['inputArtifacts'][0]['path']) != item['sha256']
            or request['parameters'] != {'targetEdge': item['targetEdge'],
                                         'iterations': item['iterations'], 'preserveBoundary': False}
            or saved['state'] != result['state']
            or saved['outputSha256'] != (sha(output) if output.exists() else None)):
        raise ValueError('Saved managed remesh case changed: ' + item['caseId'])
    expected = 'succeeded' if item['expected'] == 'accepted' else 'failed'
    if (saved['state'] != expected or output.exists() != (expected == 'succeeded')
            or bool(result.get('artifacts')) != (expected == 'succeeded')):
        raise ValueError('Saved managed remesh state changed.')
    evidence = result.get('guardEvidence')
    if item['expected'] == 'invalid-input':
        if evidence is not None or saved['guardReportSha256'] is not None:
            raise ValueError('Invalid input acquired guard evidence.')
    else:
        if not evidence or evidence['sha256'] != saved['guardReportSha256']:
            raise ValueError('Saved guard link changed.')
        guard = verify_guard(directory / evidence['path'])
        if (guard['state'] != item['expected'] or guard['sourceSha256'] != item['sha256']
                or guard['policySha256'] != sha(POLICY)
                or guard['acceptedSha256'] != saved['outputSha256']):
            raise ValueError('Saved guard result changed.')
        if item['expected'] == 'rejected' and guard['measurements']['decision']['checks']['relativeVolume']:
            raise ValueError('Volume-loss rejection no longer holds.')


def run_l5(worker, prefix, root):
    worker, prefix, root = Path(worker).resolve(strict=True), Path(prefix).resolve(strict=True), Path(root).resolve()
    manifest = fixture_manifest()
    folder = root / uuid.uuid4().hex
    folder.mkdir(parents=True)
    cases = [managed_case(item, worker, prefix, folder) for item in manifest['cases']]
    report = {**base('scientific.cgal-remesh-L5'), 'workerPath': str(worker),
              'workerSha256': sha(worker), 'runtimePrefix': str(prefix), 'cases': cases}
    path = save(folder, 'l5.json', report)
    verify_l5(path)
    return path


def verify_l5(path):
    path, report = load(path, 'scientific.cgal-remesh-L5')
    manifest = fixture_manifest()
    if (sha(report['workerPath']) != report['workerSha256']
            or len(report['cases']) != len(manifest['cases'])):
        raise ValueError('Remesh L5 worker or case set changed.')
    for saved, item in zip(report['cases'], manifest['cases']):
        if Path(saved['directory']).resolve().parent != path.parent:
            raise ValueError('Remesh L5 case escaped its evidence folder.')
        verify_case(saved, item)
    return report


def run_l6(l5, root):
    baseline = verify_l5(l5)
    path = run_l5(baseline['workerPath'], baseline['runtimePrefix'], root)
    reproduction = verify_l5(path)
    comparable = lambda case: (case['caseId'], case['state'], case['outputSha256'])
    if [comparable(case) for case in baseline['cases']] != [comparable(case) for case in reproduction['cases']]:
        raise ValueError('Remesh L6 changed publication outcome or accepted bytes.')
    report = {**base('scientific.cgal-remesh-L6'), 'baselinePath': str(Path(l5).resolve()),
              'baselineSha256': sha(l5), 'reproductionPath': str(path),
              'reproductionSha256': sha(path), 'comparison': 'state-and-accepted-output-sha256'}
    target = save(Path(root).resolve() / uuid.uuid4().hex, 'l6.json', report)
    verify_l6(target)
    return target


def verify_l6(path):
    _, report = load(path, 'scientific.cgal-remesh-L6')
    if (sha(report['baselinePath']) != report['baselineSha256']
            or sha(report['reproductionPath']) != report['reproductionSha256']
            or report['comparison'] != 'state-and-accepted-output-sha256'):
        raise ValueError('Remesh L6 evidence link changed.')
    baseline = verify_l5(report['baselinePath'])
    reproduction = verify_l5(report['reproductionPath'])
    comparable = lambda case: (case['caseId'], case['state'], case['outputSha256'])
    if [comparable(case) for case in baseline['cases']] != [comparable(case) for case in reproduction['cases']]:
        raise ValueError('Remesh L6 reproduction differs.')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('l5', 'l6', 'verify-l5', 'verify-l6'))
    parser.add_argument('--worker')
    parser.add_argument('--prefix')
    parser.add_argument('--source')
    parser.add_argument('--output-root')
    args = parser.parse_args()
    if args.command == 'l5':
        target = run_l5(args.worker, args.prefix, args.output_root)
    elif args.command == 'l6':
        target = run_l6(args.source, args.output_root)
    else:
        target = Path(args.source).resolve()
        (verify_l5 if args.command == 'verify-l5' else verify_l6)(target)
    print(json.dumps({'report': str(target), 'sha256': sha(target)}))


if __name__ == '__main__':
    main()
