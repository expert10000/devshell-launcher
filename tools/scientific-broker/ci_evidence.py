"""Authenticated, redacted CI evidence bundles for broker scientific jobs."""
import argparse
from datetime import datetime, timezone
import hashlib
import hmac
import json
from pathlib import Path
import re
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark import environment_fingerprint
from broker import Broker, sha
from telemetry import host_fingerprint

HEX32 = re.compile(r'[0-9a-f]{32}\Z')
HEX64 = re.compile(r'[0-9a-f]{64}\Z')
AGENT = re.compile(r'[A-Za-z0-9_.-]{3,64}\Z')
MAX_BUNDLE = 34 * 1024 * 1024


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('utf-8')


def hash_bytes(data):
    return hashlib.sha256(data).hexdigest()


def key_bytes(path):
    data = Path(path).read_bytes().strip()
    if len(data) < 32:
        raise ValueError('CI signing key must contain at least 32 bytes.')
    return data


def agent_profile(path):
    profile = json.loads(Path(path).read_text(encoding='utf-8'))
    if (profile.get('schemaVersion') != 1 or not isinstance(profile.get('agentId'), str)
            or not AGENT.fullmatch(profile['agentId'])
            or not isinstance(profile.get('hostFingerprintSha256'), str)
            or not HEX64.fullmatch(profile['hostFingerprintSha256'])
            or type(profile.get('gpuCapable')) is not bool or not isinstance(profile.get('keyFile'), str)):
        raise ValueError('Invalid CI agent profile.')
    return profile


def export_job(config_path, job_id, agent_path, destination, gpu_evidence=False):
    if not HEX32.fullmatch(job_id):
        raise ValueError('Invalid broker job ID.')
    profile = agent_profile(agent_path)
    if profile['hostFingerprintSha256'] != host_fingerprint():
        raise ValueError('CI agent host fingerprint changed.')
    broker = Broker(config_path)
    if job_id not in broker.jobs:
        raise ValueError('Broker job is unavailable.')
    job = broker.snapshot(broker.jobs[job_id])
    if job['state'] == 'running' or job['capabilityId'] != 'mesh.interop.vtk-math3d':
        raise ValueError('Only terminal certified CGAL jobs can be exported.')
    entry = broker.capabilities[0]
    if job['certificationRecordId'] != entry['recordId']:
        raise ValueError('Job certification differs from current deployed evidence.')
    broker.source(job_id)  # Source-snapshot hash is checked; contents remain local.
    telemetry = broker.telemetry(job_id)
    saved_result = Path(job['directory']) / 'broker-result.json'
    if not saved_result.is_file():
        raise ValueError('Final broker result is unavailable.')
    persisted = json.loads(saved_result.read_text(encoding='utf-8'))
    if persisted.get('jobId') != job_id or persisted.get('state') != job['state']:
        raise ValueError('Saved broker result identity changed.')
    gpu = telemetry.get('gpu', {})
    if gpu_evidence:
        if not profile['gpuCapable'] or gpu.get('state') != 'recorded' or gpu.get('samples', 0) < 1:
            raise ValueError('GPU evidence requires a GPU agent and recorded GPU collector.')
        raise ValueError('The fixed CGAL CPU capability does not grant GPU qualification.')
    artifacts = []
    members = {}
    if job['state'] == 'succeeded':
        data = broker.artifact(job_id, 'l5-positive.obj')
        if hash_bytes(data) != entry['referenceArtifactSha256']:
            raise ValueError('Certified artifact differs from fixed reference.')
        members['output/mesh.obj'] = data
        artifacts.append({'name': 'mesh.obj', 'sha256': hash_bytes(data), 'bytes': len(data), 'mediaType': 'model/obj'})
    evidence = {'schemaVersion': 1, 'kind': 'scientific.ci-job-evidence',
                'executionLocation': 'ci', 'agentId': profile['agentId'],
                'hostFingerprintSha256': profile['hostFingerprintSha256'],
                'gpuAgent': profile['gpuCapable'], 'gpuQualification': False,
                'sourceJobId': job_id, 'runtimeId': job['runtimeId'], 'capabilityId': job['capabilityId'],
                'jobState': job['state'], 'certificationRecordId': entry['recordId'],
                'suiteRevisionSha256': entry['suiteRevisionSha256'],
                'environmentFingerprintSha256': environment_fingerprint(entry),
                'manifestSha256': sha(broker.paths['manifest']),
                'sourceSnapshotSha256': job['sourceSnapshotSha256'],
                'brokerResultSha256': sha(saved_result),
                'contractVersion': job['contractVersion'],
                'artifacts': artifacts,
                'telemetry': {name: {key: metric.get(key) for key in ('state', 'collector', 'unit', 'scope', 'value', 'samples')}
                              for name in ('cpu', 'ram', 'gpu', 'vram') if isinstance((metric := telemetry.get(name)), dict)}}
    members['evidence.json'] = encoded(evidence)
    manifest = {'schemaVersion': 1, 'kind': 'scientific.ci-evidence-bundle',
                'agentId': profile['agentId'], 'sourceJobId': job_id,
                'files': {name: {'sha256': hash_bytes(data), 'bytes': len(data)} for name, data in sorted(members.items())}}
    manifest_bytes = encoded(manifest)
    signature = {'schemaVersion': 1, 'algorithm': 'HMAC-SHA256', 'agentId': profile['agentId'],
                 'manifestSha256': hash_bytes(manifest_bytes),
                 'mac': hmac.new(key_bytes(profile['keyFile']), manifest_bytes, hashlib.sha256).hexdigest()}
    destination = Path(destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('xb') as stream:
        with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
            for name, data in sorted(members.items()):
                bundle.writestr(name, data)
            bundle.writestr('manifest.json', manifest_bytes)
            bundle.writestr('signature.json', encoded(signature))
    return destination


def read_bundle(path):
    path = Path(path)
    if path.stat().st_size > MAX_BUNDLE:
        raise ValueError('CI bundle exceeds size budget.')
    with zipfile.ZipFile(path) as bundle:
        names = bundle.namelist()
        if len(names) != len(set(names)) or set(names) - {'evidence.json', 'output/mesh.obj', 'manifest.json', 'signature.json'}:
            raise ValueError('CI bundle contains unexpected or duplicate members.')
        if not {'evidence.json', 'manifest.json', 'signature.json'} <= set(names):
            raise ValueError('CI bundle lacks required members.')
        if (sum(item.file_size for item in bundle.infolist()) > MAX_BUNDLE
                or any(item.file_size > MAX_BUNDLE or item.is_dir() for item in bundle.infolist())):
            raise ValueError('CI bundle member exceeds size budget.')
        members = {name: bundle.read(name) for name in names}
    manifest_bytes = members.pop('manifest.json')
    signature = json.loads(members.pop('signature.json'))
    manifest = json.loads(manifest_bytes)
    if (manifest.get('schemaVersion') != 1 or manifest.get('kind') != 'scientific.ci-evidence-bundle'
            or not isinstance(manifest.get('files'), dict) or set(manifest['files']) != set(members)):
        raise ValueError('CI bundle manifest contract mismatch.')
    for name, data in members.items():
        if manifest['files'][name] != {'sha256': hash_bytes(data), 'bytes': len(data)}:
            raise ValueError('CI bundle member hash mismatch: ' + name)
    return manifest_bytes, manifest, signature, members


def import_bundle(bundle_path, trusted_agents_path, config_path, output_root):
    manifest_bytes, manifest, signature, members = read_bundle(bundle_path)
    trust = json.loads(Path(trusted_agents_path).read_text(encoding='utf-8'))
    if trust.get('schemaVersion') != 1 or not isinstance(trust.get('agents'), list):
        raise ValueError('Invalid trusted CI agent registry.')
    agents = [item for item in trust['agents'] if isinstance(item, dict)
              and item.get('agentId') == manifest['agentId']]
    if len(agents) != 1:
        raise ValueError('CI agent is not uniquely trusted.')
    agent = agents[0]
    if (not isinstance(agent.get('hostFingerprintSha256'), str)
            or not HEX64.fullmatch(agent['hostFingerprintSha256'])
            or type(agent.get('gpuCapable')) is not bool
            or not isinstance(agent.get('keyFile'), str)):
        raise ValueError('Trusted CI agent profile is invalid.')
    if (signature.get('schemaVersion') != 1 or signature.get('algorithm') != 'HMAC-SHA256'
            or signature.get('agentId') != manifest['agentId']
            or signature.get('manifestSha256') != hash_bytes(manifest_bytes)
            or not hmac.compare_digest(signature.get('mac', ''),
                                       hmac.new(key_bytes(agent['keyFile']), manifest_bytes, hashlib.sha256).hexdigest())):
        raise ValueError('CI agent signature mismatch.')
    evidence = json.loads(members['evidence.json'])
    if (evidence.get('schemaVersion') != 1 or evidence.get('kind') != 'scientific.ci-job-evidence'
            or evidence.get('executionLocation') != 'ci' or evidence.get('agentId') != manifest['agentId']
            or evidence.get('sourceJobId') != manifest['sourceJobId']
            or evidence.get('hostFingerprintSha256') != agent.get('hostFingerprintSha256')
            or evidence.get('gpuAgent') != agent.get('gpuCapable')
            or evidence.get('runtimeId') != 'cgal-win-conda'
            or evidence.get('capabilityId') != 'mesh.interop.vtk-math3d'
            or not HEX32.fullmatch(evidence.get('sourceJobId', ''))):
        raise ValueError('CI evidence agent, host or capability identity mismatch.')
    if evidence.get('gpuQualification') and not agent['gpuCapable']:
        raise ValueError('CPU-only CI agent cannot claim GPU qualification.')
    if evidence.get('gpuQualification'):
        raise ValueError('Fixed CGAL broker job cannot claim GPU qualification.')
    if evidence.get('jobState') == 'succeeded':
        artifact = evidence.get('artifacts', [])
        if (len(artifact) != 1 or 'output/mesh.obj' not in members
                or artifact[0].get('sha256') != hash_bytes(members['output/mesh.obj'])
                or artifact[0].get('bytes') != len(members['output/mesh.obj'])):
            raise ValueError('CI output artifact identity mismatch.')
    elif evidence.get('jobState') not in ('failed', 'partial', 'cancelled', 'timed-out', 'resource-exhausted') or evidence.get('artifacts') or 'output/mesh.obj' in members:
        raise ValueError('CI terminal state or artifact contract mismatch.')
    reasons = []
    try:
        broker = Broker(config_path)
        entry = broker.capabilities[0]
        for field, label in [('manifestSha256', 'certified manifest'), ('suiteRevisionSha256', 'suite revision'),
                             ('certificationRecordId', 'qualification record'),
                             ('environmentFingerprintSha256', 'environment fingerprint')]:
            expected = sha(broker.paths['manifest']) if field == 'manifestSha256' else (
                environment_fingerprint(entry) if field == 'environmentFingerprintSha256' else entry[field if field != 'certificationRecordId' else 'recordId'])
            if evidence.get(field) != expected:
                reasons.append(label + ' differs from current deployment')
        if evidence.get('artifacts') and evidence['artifacts'][0]['sha256'] != entry['referenceArtifactSha256']:
            reasons.append('output differs from certified reference')
    except (OSError, ValueError, KeyError) as error:
        reasons.append('current deployment cannot be verified: ' + str(error))
    digest = sha(bundle_path)
    output_root = Path(output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    summary = {'schemaVersion': 1, 'kind': 'scientific.ci-import', 'bundleId': digest,
               'bundleSha256': digest, 'bundleName': digest + '.zip',
               'importedAtUtc': datetime.now(timezone.utc).isoformat(),
               'trust': 'agent-authenticated', 'applicability': 'matching-deployment' if not reasons else 'inconclusive',
               'reasons': reasons, 'executionLocation': 'ci', 'agentId': evidence['agentId'],
               'hostFingerprintSha256': evidence['hostFingerprintSha256'],
               'gpuAgent': evidence['gpuAgent'], 'gpuQualification': False,
               'runtimeId': evidence['runtimeId'], 'capabilityId': evidence['capabilityId'],
               'jobState': evidence['jobState'], 'sourceJobId': evidence['sourceJobId'],
               'certificationRecordId': evidence['certificationRecordId'],
               'suiteRevisionSha256': evidence['suiteRevisionSha256'],
               'environmentFingerprintSha256': evidence['environmentFingerprintSha256']}
    saved_bundle = output_root / (digest + '.zip')
    saved_summary = output_root / (digest + '.json')
    if saved_bundle.exists() or saved_summary.exists():
        raise ValueError('CI bundle has already been imported; saved evidence is immutable.')
    saved_bundle.write_bytes(Path(bundle_path).read_bytes())
    with saved_summary.open('x', encoding='utf-8') as stream:
        json.dump(summary, stream, separators=(',', ':'))
    Path(str(saved_summary) + '.sha256').write_text(sha(saved_summary), encoding='utf-8')
    return saved_summary, summary


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    export = sub.add_parser('export')
    export.add_argument('--config', required=True)
    export.add_argument('--job-id', required=True)
    export.add_argument('--agent', required=True)
    export.add_argument('--output', required=True)
    export.add_argument('--gpu-evidence', action='store_true')
    imported = sub.add_parser('import')
    imported.add_argument('--bundle', required=True)
    imported.add_argument('--trusted-agents', required=True)
    imported.add_argument('--config', required=True)
    imported.add_argument('--output-root', required=True)
    args = parser.parse_args()
    if args.command == 'export':
        print(json.dumps({'bundle': str(export_job(args.config, args.job_id, args.agent, args.output, args.gpu_evidence))}))
    else:
        path, summary = import_bundle(args.bundle, args.trusted_agents, args.config, args.output_root)
        print(json.dumps({'summary': str(path), 'applicability': summary['applicability'], 'reasons': summary['reasons']}))


if __name__ == '__main__':
    main()
