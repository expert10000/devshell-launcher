"""Publish current six-capability, comparative and managed desktop inspection evidence."""
import argparse
import json
from pathlib import Path
import subprocess
import uuid

from advisor import advise_shared
from class_inspect_qualification import run as qualify_classes
from comparable_inspect import run as measure_shared
from desktop_inspect_journey import create as seal_desktop
from inspect_classes import policy as class_policy
from inspect_ranking import decide
from math3d_inspect_product import run as run_product
from math3d_release_identity import verify as verify_math3d
from portable_six_evidence import export as export_bundle, verify as verify_bundle
from six_capability_release import verify as verify_release
from six_capability_report import compare as build_report


def publish(release_path, math3d_root, signing_key, key_id, output_root, port=9330, samples=7):
    release_path = Path(release_path).resolve(strict=True)
    release = verify_release(release_path)
    repo = Path(release['repo']).resolve(strict=True)
    math3d = Path(math3d_root).resolve(strict=True)
    if math3d != Path(release['math3dRoot']).resolve(strict=True):
        raise ValueError('Publication MATH3D checkout differs from the release.')
    verify_math3d(math3d, release['math3dIdentity'])
    if not 5 <= samples <= 20:
        raise ValueError('Use 5–20 paired class samples.')
    root = Path(output_root).resolve() / uuid.uuid4().hex
    root.mkdir(parents=True)
    print('PUBLICATION=' + str(root), flush=True)
    class_path, classes = qualify_classes(release_path, root / 'class-inspect', samples)
    shared_path, shared = measure_shared(release_path, root / 'shared-inspect', 7)
    tier = 'sphere-128'
    advice_path, _ = advise_shared(shared_path, tier, None, root / 'advice')
    exact_input = repo / 'scientific/fixtures/inspect-shared/sphere-128.obj'
    product_path, _ = run_product(shared_path, exact_input, math3d, root / 'product-exact')
    policy, _ = class_policy(repo)
    accepted = None
    for entry in policy['classes']:
        input_path = repo / entry['holdoutFixture']
        if decide(class_path, input_path)['recommendation']:
            accepted = input_path
            break
    if accepted is None:
        raise ValueError('All bounded classes abstained; automatic desktop selection cannot be certified.')
    fallback = repo / 'scientific/fixtures/cgal/open-square.obj'
    runs_path = root / 'desktop-runs.json'
    command = ['powershell', '-NoProfile', '-File',
        str(repo / 'tools/Run-Scientific-Desktop-Acceptance.ps1'),
        '-Scenario', 'CgalInspect', '-ExistingWorktree', str(repo), '-SkipBuild',
        '-ProductJourney', '-Math3DCheckout', str(math3d), '-ClassRecord', str(class_path),
        '-InspectInput', str(accepted), '-FallbackInput', str(fallback),
        '-JourneyRunsOutput', str(runs_path), '-CdpPort', str(port)]
    completed = subprocess.run(command, cwd=repo, text=True, capture_output=True, timeout=2400)
    (root / 'desktop-journey.log').write_text(completed.stdout + completed.stderr, encoding='utf-8')
    if completed.returncode or not runs_path.is_file():
        raise ValueError('Managed desktop product journey failed; see ' + str(root / 'desktop-journey.log'))
    journey_path, _ = seal_desktop(release_path, class_path,
        json.loads(runs_path.read_text(encoding='utf-8')), root / 'desktop-journey.json')
    report_path, _ = build_report(release_path, root / 'report', 5, shared_path,
                                  advice_path, product_path, class_path, journey_path)
    bundle = root / 'six-capability-inspection.zip'
    bundle_info = export_bundle(release_path, bundle, signing_key, key_id, shared_path,
                                report_path, advice_path, product_path, class_path, journey_path)
    verdict = verify_bundle(bundle, repo / 'schemas/scientific-evidence-trust.v1.json')
    if verdict['manifestSha256'] != bundle_info['manifestSha256'] or verdict['signature'] != 'trusted':
        raise ValueError('Signed publication did not verify offline.')
    record = {'schemaVersion': 1, 'kind': 'scientific.six-inspect-publication',
              'sourceCommit': release['sourceCommit'], 'math3dCommit': release['math3dIdentity']['commit'],
              'release': str(release_path), 'classes': str(class_path), 'shared': str(shared_path),
              'advisor': str(advice_path), 'product': str(product_path),
              'desktopJourney': str(journey_path), 'report': str(report_path),
              'bundle': str(bundle), 'manifestSha256': verdict['manifestSha256'],
              'classIds': list(classes['classes']), 'sharedTiers': list(shared['tiers']),
              'desktopInput': str(accepted), 'signingKeyId': key_id}
    (root / 'publication.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    return root / 'publication.json', record


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--release-record', required=True)
    parser.add_argument('--math3d-root', required=True)
    parser.add_argument('--signing-key', required=True)
    parser.add_argument('--key-id', required=True)
    parser.add_argument('--output-root', required=True)
    parser.add_argument('--port', type=int, default=9330)
    parser.add_argument('--samples', type=int, default=7)
    args = parser.parse_args()
    path, record = publish(args.release_record, args.math3d_root, args.signing_key,
                           args.key_id, args.output_root, args.port, args.samples)
    print(json.dumps({'record': str(path), 'bundle': record['bundle'],
                      'sourceCommit': record['sourceCommit'], 'manifestSha256': record['manifestSha256']}))
