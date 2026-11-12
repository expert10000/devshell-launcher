"""Choose a qualified inspection backend and reopen its artifact in MATH3D."""
import argparse
import hashlib
from html import escape
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

from advisor import advise_shared, verify_shared_advice, advise_class, verify_class_advice
from broker import Broker, sha
from comparable_inspect import policy, verify as verify_shared, verify_release
from inspect_ranking import decide as decide_class, policy as ranking_policy, rank_class

ROOT = Path(__file__).resolve().parents[2]
PROVIDERS = {'cgal-win-conda': 'cgal', 'vtk-win-conda': 'vtk'}
PRODUCT_FILES = ('vtk-mesh-document.json', 'vtk-mesh-resource.bin', 'read.m3dm',
                 'product.json', 'viewer.png', 'viewer.json')


def choose(shared_record, input_path, manual_provider=None, class_record=None):
    """Fail closed to the MATH3D importer when measured scope cannot be verified."""
    if manual_provider and manual_provider not in PROVIDERS:
        raise ValueError('Unknown manual inspection provider.')
    digest = sha(input_path)
    if class_record:
        try:
            advice = decide_class(class_record, input_path, manual_provider)
        except (ValueError, OSError, KeyError, TypeError) as error:
            return {'state': 'fallback', 'selectedProvider': 'math3d-direct',
                    'manualProvider': manual_provider, 'reason': 'Bounded class evidence is stale: ' + str(error)[:240],
                    'inputSha256': digest}
        if advice['selectedProvider'] is None:
            return {'state': 'fallback', 'selectedProvider': 'math3d-direct',
                    'manualProvider': manual_provider, 'reason': advice['reason'],
                    'inputSha256': digest, 'classRecordSha256': sha(class_record)}
        phase = advice['evidence'].get('phases', {})
        return {'state': advice['state'], 'selectedProvider': advice['selectedProvider'],
                'recommendedProvider': advice['recommendation'], 'manualProvider': manual_provider,
                'reason': advice['reason'] or 'Paired cold and warm evidence clears the ranking policy.',
                'inputSha256': digest, 'classId': advice['classId'],
                'classRecordSha256': sha(class_record),
                'rankingPolicySha256': advice['rankingPolicySha256'],
                'rankingEvidence': advice['evidence'], 'configPaths': advice['configPaths'],
                'mediansMs': phase.get('coldInvocationMs', {}).get('mediansMs', {}),
                'median95PctBootstrapMs': {name: phase.get('coldInvocationMs', {}).get('pairedCgalMinusVtk95PctMs', [])
                                           for name in PROVIDERS}}
    if not shared_record:
        return {'state': 'fallback', 'selectedProvider': 'math3d-direct',
                'manualProvider': manual_provider, 'reason': 'No shared evidence was supplied.',
                'inputSha256': digest}
    try:
        scope = verify_shared(shared_record)
        contract, _ = policy(verify_release(scope['releaseRecord'])['repo'])
    except (ValueError, OSError, KeyError, TypeError) as error:
        return {'state': 'fallback', 'selectedProvider': 'math3d-direct',
                'manualProvider': manual_provider, 'reason': 'Shared evidence is stale: ' + str(error)[:240],
                'inputSha256': digest}
    tier = next((item for item in contract['tiers'] if digest in
                 (item['cgalSha256'], item['vtkSha256'])), None)
    if tier is None:
        return {'state': 'fallback', 'selectedProvider': 'math3d-direct',
                'manualProvider': manual_provider,
                'reason': 'Input hash is outside the qualified shared fixtures.',
                'inputSha256': digest, 'scopeRecordSha256': sha(shared_record)}
    measurements = scope['tiers'][tier['id']]['measurements']
    release = verify_release(scope['releaseRecord'])
    ranking, ranking_sha = ranking_policy(release['repo'])
    ranking_evidence = rank_class({'runs': {name: measurements[name]['runs'] for name in ('cgal', 'vtk')},
                                   'statistics': {name: measurements[name]['phases'] for name in ('cgal', 'vtk')}},
                                  tier['id'], ranking)
    medians = {name: measurements[provider]['statistics']['medianMs']
               for name, provider in PROVIDERS.items()}
    intervals = {name: measurements[provider]['statistics']['median95PctBootstrapMs']
                 for name, provider in PROVIDERS.items()}
    ranked = ranking_evidence['recommendation']
    selected = manual_provider or ranked
    if selected is None:
        return {'state': 'fallback', 'selectedProvider': 'math3d-direct',
                'manualProvider': manual_provider, 'reason': ranking_evidence['reason'],
                'inputSha256': digest, 'scopeRecordSha256': sha(shared_record),
                'rankingPolicySha256': ranking_sha, 'rankingEvidence': ranking_evidence}
    return {'state': 'qualified' if not manual_provider else 'manual',
            'selectedProvider': selected, 'recommendedProvider': ranked,
            'manualProvider': manual_provider, 'tier': tier['id'], 'tierCases':
            {name: tier[provider + 'Case'] for name, provider in PROVIDERS.items()},
            'fixturePaths': {name: tier[provider + 'Fixture'] for name, provider in PROVIDERS.items()},
            'fixtureSha256': {name: tier[provider + 'Sha256'] for name, provider in PROVIDERS.items()},
            'reason': 'Manual qualified provider retained.' if manual_provider else
            'Paired cold and warm evidence clears the ranking policy.',
            'mediansMs': medians, 'median95PctBootstrapMs': intervals,
            'rankingPolicySha256': ranking_sha, 'rankingEvidence': ranking_evidence,
            'inputSha256': digest, 'scopeRecordSha256': sha(shared_record),
            'configPaths': scope['configPaths']}


def wait(broker, request):
    job_id = broker.submit(request)['jobId']
    deadline = time.monotonic() + 180
    while broker.jobs[job_id]['state'] == 'running' and time.monotonic() < deadline:
        time.sleep(.1)
    job = broker.snapshot(broker.jobs[job_id])
    if job['state'] != 'succeeded':
        raise ValueError('Selected inspection broker job failed: ' + str(job['diagnostics']))
    promotion = broker.promote(job_id)
    if promotion['decision'] != 'allowed':
        raise ValueError('Selected inspection promotion was blocked: ' + str(promotion['reasons']))
    artifact_name = 'inspected.obj' if broker.inspect else 'read.obj'
    artifact = Path(job['directory']) / artifact_name
    if sha(artifact) != hashlib.sha256(broker.artifact(job_id, artifact_name)).hexdigest():
        raise ValueError('Selected broker artifact transport changed.')
    return job, promotion, artifact


def run(shared_record, input_path, math3d_checkout, output, manual_provider=None, node='node', class_record=None):
    input_path = Path(input_path).resolve(strict=True)
    checkout = Path(math3d_checkout).resolve(strict=True)
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('Advised MATH3D product output already exists.')
    output.mkdir(parents=True)
    selection = choose(shared_record, input_path, manual_provider, class_record)
    selection['inputPath'] = str(input_path)
    source = input_path
    if selection['state'] != 'fallback':
        provider = selection['selectedProvider']
        side = PROVIDERS[provider]
        if class_record:
            source = input_path
            broker = Broker(selection['configPaths'][side])
            request_scope = {'classId': selection['classId']}
            target_name = selection['classId']
        else:
            scope = verify_shared(shared_record)
            broker = Broker(scope['configPaths'][side])
            source = Path(verify_release(scope['releaseRecord'])['repo']) / selection['fixturePaths'][provider]
            source = source.resolve(strict=True)
            if sha(source) != selection['fixtureSha256'][provider]:
                raise ValueError('Selected provider fixture changed.')
            request_scope = {'caseId': selection['tierCases'][provider]}
            target_name = selection['tier']
        target = broker.paths['datasetRoot'] / ('advised-' + target_name + '-' + side + '.obj')
        shutil.copyfile(source, target)
        job, promotion, artifact = wait(broker, {'schemaVersion': 1,
            'runtimeId': broker.runtime_id, 'capabilityId': broker.capability_id,
            **request_scope,
            'input': {'path': str(target), 'sha256': sha(target)}, 'timeoutSeconds': 120})
        source = artifact
        advice_path = (advise_class(class_record, input_path, manual_provider, output / 'advice')[0]
                       if class_record else advise_shared(shared_record, selection['tier'], manual_provider,
                                                          output / 'advice')[0])
        selection.update(jobId=job['jobId'], brokerResultSha256=sha(Path(job['directory']) / 'broker-result.json'),
                         promotionSha256=promotion['sha256'], promotedArtifactSha256=sha(source),
                         adviceRecord=str(advice_path))
        (verify_class_advice if class_record else verify_shared_advice)(selection['adviceRecord'])
    product = output / 'product'
    for command in ([node, str(ROOT / 'tools/math3d-vtk-read-product.mjs'), '--checkout', str(checkout),
                     '--source', str(source), '--expected-sha', sha(source), '--output', str(product)],
                    [node, str(ROOT / 'tools/math3d-vtk-read-viewer.mjs'), '--checkout', str(checkout),
                     '--product', str(product)]):
        completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=300)
        if completed.returncode:
            raise ValueError('MATH3D product path failed: ' + (completed.stderr or completed.stdout)[-1200:])
    selection['productFiles'] = {name: sha(product / name) for name in PRODUCT_FILES}
    selection['sourceObjSha256'] = sha(source)
    selection['kind'] = 'scientific.math3d-advised-inspect-product'
    selection['schemaVersion'] = 1
    html = output / 'selection.html'
    html.write_text(render_html(selection), encoding='utf-8')
    selection['selectionHtmlSha256'] = sha(html)
    record = output / 'selection.json'
    record.write_text(json.dumps(selection, indent=2), encoding='utf-8')
    Path(str(record) + '.sha256').write_text(sha(record), encoding='utf-8')
    verify(record, shared_record, input_path, class_record)
    return record, selection


def verify(path, shared_record, input_path, class_record=None):
    path = Path(path).resolve(strict=True)
    if sha(path) != Path(str(path) + '.sha256').read_text().strip():
        raise ValueError('Advised product seal changed.')
    value = json.loads(path.read_text(encoding='utf-8'))
    expected = choose(shared_record, input_path, value['manualProvider'], class_record)
    if any(value.get(key) != data for key, data in expected.items()):
        raise ValueError('Advised selection or current evidence changed.')
    if Path(value['inputPath']).resolve(strict=True) != Path(input_path).resolve(strict=True):
        raise ValueError('Advised input path changed.')
    if sha(path.parent / 'selection.html') != value['selectionHtmlSha256'] \
            or (path.parent / 'selection.html').read_text(encoding='utf-8') != render_html(value):
        raise ValueError('Visible selection rationale changed.')
    for name, digest in value['productFiles'].items():
        if name not in PRODUCT_FILES or sha(path.parent / 'product' / name) != digest:
            raise ValueError('MATH3D advised product changed.')
    if set(value['productFiles']) != set(PRODUCT_FILES):
        raise ValueError('MATH3D product evidence is incomplete.')
    product = json.loads((path.parent / 'product' / 'product.json').read_text(encoding='utf-8'))
    viewer = json.loads((path.parent / 'product' / 'viewer.json').read_text(encoding='utf-8'))
    if (product.get('verdict') != 'passed' or product.get('sourceObjSha256') != value['sourceObjSha256']
            or viewer.get('verdict') != 'passed' or viewer.get('documentSha256') != product.get('documentSha256')):
        raise ValueError('MATH3D saved document or viewport evidence changed.')
    if value['state'] != 'fallback':
        (verify_class_advice if class_record else verify_shared_advice)(value['adviceRecord'])
        broker = Broker(value['configPaths'][PROVIDERS[value['selectedProvider']]])
        job = broker.jobs.get(value['jobId'])
        if job is None or sha(Path(job['directory']) / 'broker-result.json') != value['brokerResultSha256']:
            raise ValueError('Advised broker result changed.')
        artifact = Path(job['directory']) / ('inspected.obj' if broker.inspect else 'read.obj')
        if sha(artifact) != value['promotedArtifactSha256'] or sha(artifact) != value['sourceObjSha256']:
            raise ValueError('Advised transport artifact changed.')
        if broker.promote(value['jobId'])['decision'] != 'allowed':
            raise ValueError('Advised broker promotion is stale.')
    elif sha(input_path) != value['sourceObjSha256']:
        raise ValueError('Direct MATH3D import source changed.')
    return value


def render_html(value):
    selected = escape(value['selectedProvider'])
    recommended = escape(value.get('recommendedProvider', 'unavailable'))
    reason = escape(value['reason'])
    tier = escape(value.get('classId') or value.get('tier') or 'outside qualified scope')
    phases = value.get('rankingEvidence', {}).get('phases', {})
    rows = ''.join('<tr><td>' + escape(name) + '</td><td>' +
                   escape(str(phase['mediansMs'].get('cgal-win-conda'))) + ' ms</td><td>' +
                   escape(str(phase['mediansMs'].get('vtk-win-conda'))) + ' ms</td><td>' +
                   escape(str(phase['pairedCgalMinusVtk95PctMs'])) + ' ms</td></tr>'
                   for name, phase in phases.items())
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><title>MATH3D inspection choice</title>'
            '<style>body{font:16px system-ui;max-width:950px;margin:2rem auto;color:#17212f}'
            'table{border-collapse:collapse}td,th{padding:.5rem;border:1px solid #bbb}'
            'img{max-width:100%;border:1px solid #ddd}</style><h1>MATH3D mesh inspection</h1>'
            '<p><strong>Selected:</strong> ' + selected + '</p><p><strong>Recommended:</strong> ' +
            recommended + '</p><p><strong>Qualified tier:</strong> ' + tier + '</p><p>' + reason + '</p>'
            '<table><tr><th>Phase</th><th>CGAL median</th><th>VTK median</th><th>Paired CGAL−VTK 95% interval</th></tr>' +
            rows + '</table><h2>Saved MATH3D viewport</h2><img src="product/viewer.png" alt="Reopened mesh"></html>')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('preview', 'run', 'verify'))
    parser.add_argument('--shared-record')
    parser.add_argument('--class-record')
    parser.add_argument('--input', required=True)
    parser.add_argument('--math3d-checkout')
    parser.add_argument('--output')
    parser.add_argument('--record')
    parser.add_argument('--manual-provider')
    options = parser.parse_args()
    if options.command == 'preview':
        print(json.dumps(choose(options.shared_record, options.input, options.manual_provider,
                                options.class_record)))
        raise SystemExit(0)
    if options.command == 'run':
        path, value = run(options.shared_record, options.input, options.math3d_checkout,
                          options.output, options.manual_provider, class_record=options.class_record)
    else:
        path = options.record
        value = verify(path, options.shared_record, options.input, options.class_record)
    print(json.dumps({'record': str(path), 'selectedProvider': value['selectedProvider'],
                      'reason': value['reason']}))
