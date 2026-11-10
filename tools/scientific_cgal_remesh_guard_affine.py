"""Seeded affine pass/reject replay for the local remesh publication guard."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

from scientific_cgal_corpus import sha
from scientific_cgal_remesh_adverse_affine import verify as verify_adverse
from scientific_cgal_remesh_guard import run as run_guard, verify as verify_guard


MODES = (('eligible', 0.75, 1, 'accepted'), ('adverse', 0.5, 2, 'rejected'))


def check_case(item, source_case, mode, root):
    label, edge, iterations, expected_state = mode
    path = Path(item['guardReport']).resolve(strict=True)
    if path.parent.parent != root or path.name != 'guarded.json' or sha(path) != item['guardReportSha256']:
        raise ValueError('Affine guard case path or report changed.')
    guard = verify_guard(path)
    parameters = source_case['parameters']
    expected = {'targetEdge': edge * parameters['scale'],
                'iterations': iterations, 'preserveBoundary': 0}
    if (guard['sourceSha256'] != source_case['inputSha256'] or guard['parameters'] != expected
            or guard['state'] != expected_state or item['state'] != expected_state
            or item['candidateSha256'] != guard['candidateSha256']
            or (label == 'adverse' and guard['candidateSha256'] != source_case['outputSha256'])):
        raise ValueError('Affine guard state or native candidate changed.')


def run(source_report, output_root):
    source = Path(source_report).resolve(strict=True)
    adverse = verify_adverse(source)
    worker, prefix = adverse['workerPath'], adverse['runtimePrefix']
    root = Path(output_root).resolve() / uuid.uuid4().hex
    root.mkdir(parents=True)
    cases = []
    for index, source_case in enumerate(adverse['cases']):
        parameters = source_case['parameters']
        input_path = Path(source_case['directory']) / 'input.obj'
        for mode in MODES:
            label, edge, iterations, _ = mode
            path, guard = run_guard(worker, prefix, input_path,
                                    edge * parameters['scale'], iterations, 0, root)
            item = {'caseIndex': index, 'mode': label, 'guardReport': str(path),
                    'guardReportSha256': sha(path), 'candidateSha256': guard['candidateSha256'],
                    'state': guard['state']}
            check_case(item, source_case, mode, root)
            cases.append(item)
    report = {'schemaVersion': 1, 'kind': 'scientific.cgal-remesh-guard-affine',
              'createdAtUtc': datetime.now(timezone.utc).isoformat(),
              'sourceReport': str(source), 'sourceReportSha256': sha(source),
              'cases': cases, 'acceptedCount': sum(item['state'] == 'accepted' for item in cases),
              'verdict': 'passed'}
    target = root / 'guard-affine.json'
    with target.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, separators=(',', ':'))
    Path(str(target) + '.sha256').write_text(sha(target), encoding='utf-8')
    verify(target)
    return target, report


def verify(path):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('Affine guard report hash mismatch.')
    report = json.loads(path.read_text(encoding='utf-8'))
    source = Path(report['sourceReport']).resolve(strict=True)
    adverse = verify_adverse(source)
    expected = [(index, source_case, mode)
                for index, source_case in enumerate(adverse['cases']) for mode in MODES]
    if (report.get('schemaVersion') != 1 or report.get('kind') != 'scientific.cgal-remesh-guard-affine'
            or report.get('verdict') != 'passed' or sha(source) != report.get('sourceReportSha256')
            or len(report.get('cases', [])) != len(expected)):
        raise ValueError('Affine guard report identity changed.')
    paths = set()
    for item, (index, source_case, mode) in zip(report['cases'], expected):
        if (item['caseIndex'] != index or item['mode'] != mode[0]
                or item['guardReport'] in paths):
            raise ValueError('Affine guard case identity changed.')
        paths.add(item['guardReport'])
        check_case(item, source_case, mode, path.parent)
    if report.get('acceptedCount') != len(adverse['cases']):
        raise ValueError('Affine guard acceptance count changed.')
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
