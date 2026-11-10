"""Replay all six sealed tetrahedron remesh settings through the local guard."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

from scientific_cgal_corpus import CORPUS, sha
from scientific_cgal_remesh_fidelity import SETTINGS, verify as verify_fidelity
from scientific_cgal_remesh_guard import run as run_guard, verify as verify_guard


def check_case(item, baseline, root):
    guard_path = Path(item['guardReport']).resolve(strict=True)
    if (guard_path.parent.parent != root or guard_path.name != 'guarded.json'
            or sha(guard_path) != item['guardReportSha256']):
        raise ValueError('Guard suite case path or report changed.')
    guard = verify_guard(guard_path)
    expected = {'targetEdge': baseline['targetEdge'], 'iterations': baseline['iterations'],
                'preserveBoundary': 0}
    expected_state = 'accepted' if baseline['fidelity']['volumeEligible'] else 'rejected'
    if (guard['parameters'] != expected or guard['candidateSha256'] != baseline['outputSha256']
            or guard['state'] != expected_state or item['state'] != expected_state
            or guard['candidateSha256'] != item['candidateSha256']):
        raise ValueError('Guard suite diverged from the sealed native baseline.')


def run(source_report, output_root):
    source = Path(source_report).resolve(strict=True)
    baseline = verify_fidelity(source)
    worker, prefix = baseline['workerPath'], baseline['runtimePrefix']
    root = Path(output_root).resolve() / uuid.uuid4().hex
    root.mkdir(parents=True)
    cases = []
    for index, (setting, original) in enumerate(zip(SETTINGS, baseline['cases'])):
        guard_path, guard = run_guard(worker, prefix, CORPUS / 'closed-tetra.obj',
                                      setting[0], setting[1], 0, root)
        item = {'index': index, 'guardReport': str(guard_path),
                'guardReportSha256': sha(guard_path), 'candidateSha256': guard['candidateSha256'],
                'state': guard['state']}
        check_case(item, original, root)
        cases.append(item)
    report = {'schemaVersion': 1, 'kind': 'scientific.cgal-remesh-guard-suite',
              'createdAtUtc': datetime.now(timezone.utc).isoformat(),
              'sourceReport': str(source), 'sourceReportSha256': sha(source),
              'cases': cases, 'acceptedCount': sum(item['state'] == 'accepted' for item in cases),
              'verdict': 'passed'}
    target = root / 'guard-suite.json'
    with target.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, separators=(',', ':'))
    Path(str(target) + '.sha256').write_text(sha(target), encoding='utf-8')
    verify(target)
    return target, report


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('Guard suite report hash mismatch.')
    report = json.loads(path.read_text(encoding='utf-8'))
    source = Path(report['sourceReport']).resolve(strict=True)
    baseline = verify_fidelity(source)
    if (report.get('schemaVersion') != 1 or report.get('kind') != 'scientific.cgal-remesh-guard-suite'
            or report.get('verdict') != 'passed' or sha(source) != report.get('sourceReportSha256')
            or len(report.get('cases', [])) != len(SETTINGS)):
        raise ValueError('Guard suite identity changed.')
    paths = set()
    for index, (item, original) in enumerate(zip(report['cases'], baseline['cases'])):
        if item['index'] != index or item['guardReport'] in paths:
            raise ValueError('Guard suite case identity changed.')
        paths.add(item['guardReport'])
        check_case(item, original, path.parent)
    if report.get('acceptedCount') != sum(item['state'] == 'accepted' for item in report['cases']):
        raise ValueError('Guard suite acceptance count changed.')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('run', 'verify'))
    parser.add_argument('--source-report')
    parser.add_argument('--output-root')
    parser.add_argument('--report')
    options = parser.parse_args()
    if options.command == 'run':
        if not options.source_report or not options.output_root:
            parser.error('run requires source-report and output-root')
        target, value = run(options.source_report, options.output_root)
    else:
        if not options.report:
            parser.error('verify requires report')
        target, value = Path(options.report).resolve(), verify(options.report)
    print(json.dumps({'report': str(target), 'accepted': value['acceptedCount'],
                      'cases': len(value['cases'])}))
