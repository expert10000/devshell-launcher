"""Publish current six-capability, comparative and managed desktop inspection evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import uuid

from advisor import advise_shared
from class_inspect_qualification import run as qualify_classes, verify as verify_classes
from comparable_inspect import run as measure_shared, verify as verify_shared
from desktop_inspect_journey import create as seal_desktop, verify as verify_desktop
from inspect_classes import policy as class_policy
from inspect_ranking import decide
from math3d_inspect_product import run as run_product, verify as verify_product
from math3d_release_identity import verify as verify_math3d
from portable_six_evidence import export as export_bundle, verify as verify_bundle
from six_capability_release import verify as verify_release
from six_capability_report import compare as build_report, verify as verify_report
from advisor import verify_shared_advice


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_checkpoint(path, value):
    body = {key: item for key, item in value.items() if key != 'checkpointSha256'}
    value['checkpointSha256'] = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    temporary = Path(str(path) + '.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temporary.replace(path)


def load_checkpoint(path):
    value = json.loads(Path(path).read_text(encoding='utf-8'))
    body = {key: item for key, item in value.items() if key != 'checkpointSha256'}
    expected = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if value.get('checkpointSha256') != expected or value.get('schemaVersion') != 1:
        raise ValueError('Publication checkpoint seal changed.')
    return value


def publish(release_path, math3d_root, signing_key, key_id, output_root, port=9330, samples=7, checkpoint=None):
    release_path = Path(release_path).resolve(strict=True)
    release = verify_release(release_path)
    repo = Path(release['repo']).resolve(strict=True)
    math3d = Path(math3d_root).resolve(strict=True)
    if math3d != Path(release['math3dRoot']).resolve(strict=True):
        raise ValueError('Publication MATH3D checkout differs from the release.')
    verify_math3d(math3d, release['math3dIdentity'])
    if not 5 <= samples <= 20:
        raise ValueError('Use 5–20 paired class samples.')
    root = Path(checkpoint).resolve().parent if checkpoint else Path(output_root).resolve() / uuid.uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    checkpoint_path = root / 'checkpoint.json'
    if checkpoint:
        if Path(checkpoint).resolve() != checkpoint_path or not checkpoint_path.is_file():
            raise ValueError('Resume requires the publication checkpoint in its run directory.')
        saved = load_checkpoint(checkpoint_path)
        if (saved.get('release') != str(release_path) or saved.get('releaseSha256') != sha(release_path)
                or saved.get('sourceCommit') != release['sourceCommit']
                or saved.get('math3dRoot') != str(math3d) or saved.get('math3dIdentity') != release['math3dIdentity']
                or saved.get('keyId') != key_id or saved.get('samples') != samples):
            raise ValueError('Publication checkpoint source, release, consumer or policy drifted.')
    else:
        saved = {'schemaVersion': 1, 'kind': 'scientific.six-inspect-publication-checkpoint',
                 'release': str(release_path), 'releaseSha256': sha(release_path),
                 'sourceCommit': release['sourceCommit'], 'math3dRoot': str(math3d),
                 'math3dIdentity': release['math3dIdentity'], 'keyId': key_id,
                 'samples': samples, 'stages': {}}
        save_checkpoint(checkpoint_path, saved)
    print('PUBLICATION=' + str(root), flush=True)
    print('CHECKPOINT=' + str(checkpoint_path), flush=True)

    def stage(name, build, verify):
        previous = saved['stages'].get(name)
        if previous:
            path = (root / previous['path']).resolve(strict=True)
            if not path.is_relative_to(root) or sha(path) != previous['sha256']:
                raise ValueError(name + ' publication checkpoint artifact changed.')
            return path, verify(path)
        path, result = build()
        path = Path(path).resolve(strict=True)
        if not path.is_relative_to(root):
            raise ValueError(name + ' publication artifact escaped its run directory.')
        saved['stages'][name] = {'path': str(path.relative_to(root)), 'sha256': sha(path)}
        save_checkpoint(checkpoint_path, saved)
        print('STAGE=' + name, flush=True)
        return path, result

    class_path, classes = stage('classes', lambda: qualify_classes(release_path, root / 'class-inspect', samples), verify_classes)
    shared_path, shared = stage('shared', lambda: measure_shared(release_path, root / 'shared-inspect', 7), verify_shared)
    tier = 'sphere-128'
    advice_path, _ = stage('advice', lambda: advise_shared(shared_path, tier, None, root / 'advice'), verify_shared_advice)
    exact_input = repo / 'scientific/fixtures/inspect-shared/sphere-128.obj'
    product_path, _ = stage('product', lambda: run_product(shared_path, exact_input, math3d, root / 'product-exact'),
                            lambda path: verify_product(path, shared_path, exact_input))
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
    def desktop():
        if not runs_path.is_file():
            completed = subprocess.run(command, cwd=repo, text=True, capture_output=True, timeout=2400)
            (root / 'desktop-journey.log').write_text(completed.stdout + completed.stderr, encoding='utf-8')
            if completed.returncode or not runs_path.is_file():
                raise ValueError('Managed desktop product journey failed; see ' + str(root / 'desktop-journey.log'))
        return seal_desktop(release_path, class_path,
            json.loads(runs_path.read_text(encoding='utf-8')), root / 'desktop-journey.json')
    journey_path, _ = stage('desktop', desktop, lambda path: verify_desktop(path, release_path, class_path))
    report_path, _ = stage('report', lambda: build_report(release_path, root / 'report', 5, shared_path,
                            advice_path, product_path, class_path, journey_path), verify_report)
    bundle = root / 'six-capability-inspection.zip'
    trust = repo / 'schemas/scientific-evidence-trust.v1.json'
    def make_bundle():
        info = export_bundle(release_path, bundle, signing_key, key_id, shared_path,
                             report_path, advice_path, product_path, class_path, journey_path)
        return bundle, info
    bundle_path, bundle_info = stage('bundle', make_bundle, lambda path: verify_bundle(path, trust))
    verdict = verify_bundle(bundle_path, trust)
    if verdict['manifestSha256'] != bundle_info['manifestSha256'] or verdict['signature'] != 'trusted':
        raise ValueError('Signed publication did not verify offline.')
    record = {'schemaVersion': 1, 'kind': 'scientific.six-inspect-publication',
              'sourceCommit': release['sourceCommit'], 'math3dCommit': release['math3dIdentity']['commit'],
              'release': str(release_path), 'classes': str(class_path), 'shared': str(shared_path),
              'advisor': str(advice_path), 'product': str(product_path),
              'desktopJourney': str(journey_path), 'report': str(report_path),
              'bundle': str(bundle_path), 'manifestSha256': verdict['manifestSha256'],
              'classIds': list(classes['classes']), 'sharedTiers': list(shared['tiers']),
              'desktopInput': str(accepted), 'signingKeyId': key_id}
    temporary = root / 'publication.json.tmp'
    temporary.write_text(json.dumps(record, indent=2), encoding='utf-8')
    temporary.replace(root / 'publication.json')
    return root / 'publication.json', record


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', nargs='?', choices=('run', 'resume'), default='run')
    parser.add_argument('--release-record')
    parser.add_argument('--math3d-root')
    parser.add_argument('--signing-key', required=True)
    parser.add_argument('--key-id')
    parser.add_argument('--output-root')
    parser.add_argument('--checkpoint')
    parser.add_argument('--port', type=int, default=9330)
    parser.add_argument('--samples', type=int, default=7)
    args = parser.parse_args()
    if args.command == 'resume':
        if not args.checkpoint:
            parser.error('resume requires --checkpoint')
        previous = load_checkpoint(args.checkpoint)
        if args.release_record and str(Path(args.release_record).resolve()) != previous['release']:
            parser.error('resume release differs from checkpoint')
        if args.math3d_root and str(Path(args.math3d_root).resolve()) != previous['math3dRoot']:
            parser.error('resume MATH3D checkout differs from checkpoint')
        args.release_record, args.math3d_root = previous['release'], previous['math3dRoot']
        args.key_id, args.samples = previous['keyId'], previous['samples']
        args.output_root = str(Path(args.checkpoint).resolve().parent.parent)
    elif not all((args.release_record, args.math3d_root, args.key_id, args.output_root)):
        parser.error('run requires release, MATH3D checkout, key ID and output root')
    path, record = publish(args.release_record, args.math3d_root, args.signing_key,
                           args.key_id, args.output_root, args.port, args.samples, args.checkpoint)
    print(json.dumps({'record': str(path), 'bundle': record['bundle'],
                      'sourceCommit': record['sourceCommit'], 'manifestSha256': record['manifestSha256']}))
