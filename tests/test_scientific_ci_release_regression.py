"""Signed CI exchange, fresh release gate and reviewed deterministic failure replay."""
import hashlib
import hmac
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools' / 'scientific-broker'))
import ci_evidence
import regression_fixtures
import release_certification
from broker import Broker, sha
from telemetry import host_fingerprint


class CapabilityScopedReleaseChecks(unittest.TestCase):
    def test_release_can_select_a_scoped_runtime_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local = root / 'inventory.json'
            local.write_text(json.dumps({'schemaVersion': 1, 'runtimes': [],
                                         'generatedAt': '2026-11-08T00:00:00Z'}), encoding='utf-8')
            content, inventory = release_certification.load_inventory(root, local)
            self.assertEqual(content, local.read_bytes())
            self.assertEqual(inventory['runtimes'], [])
            with self.assertRaisesRegex(ValueError, 'Unsupported release runtime inventory'):
                local.write_text('{}', encoding='utf-8')
                release_certification.load_inventory(root, local)

    def test_verify_keeps_surface_and_volume_gate_chains_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            support = [{'level': f'L{index}', 'capabilityId': 'mesh.generate3d',
                        'runId': f'volume-{index}', 'recordId': f'record-{index}'}
                       for index in range(10)]
            fresh = {'certifiedCapabilities': [
                {'runtimeId': 'gmsh-win-conda', 'capabilityId': 'mesh.generate', 'supportingRecords': support},
                {'runtimeId': 'gmsh-win-conda', 'capabilityId': 'mesh.generate3d', 'supportingRecords': support}]}
            fresh_path = root / 'fresh-capabilities.json'
            fresh_path.write_text(json.dumps(fresh), encoding='utf-8')
            Path(str(fresh_path) + '.sha256').write_text(sha(fresh_path), encoding='utf-8')
            now = release_certification.datetime.now(release_certification.timezone.utc)
            inventory = {'generatedAt': now.isoformat()}
            inventory_path = root / 'runtime-inventory.json'
            inventory_path.write_text(json.dumps(inventory), encoding='utf-8')
            report = {'schemaVersion': 1, 'kind': 'scientific.release-qualification-report',
                      'runtimeId': 'gmsh-win-conda', 'capabilityId': 'mesh.generate3d',
                      'createdAtUtc': now.isoformat(), 'inventoryPath': str(inventory_path),
                      'inventorySha256': sha(inventory_path), 'inventoryCapturedAtUtc': now.isoformat(),
                      'inventoryState': 'current', 'freshManifestSha256': sha(fresh_path),
                      'gateVerdicts': release_certification.gate_verdicts(
                          fresh, 'gmsh-win-conda', 'mesh.generate3d'),
                      'verdict': 'blocked', 'reasons': ['test-only blocked release']}
            report_path = root / 'qualification-report.json'
            report_path.write_text(json.dumps(report), encoding='utf-8')
            Path(str(report_path) + '.sha256').write_text(sha(report_path), encoding='utf-8')
            self.assertEqual(release_certification.verify_release(report_path)['gateVerdicts'],
                             report['gateVerdicts'])


@unittest.skipUnless(os.environ.get('SCIENTIFIC_BROKER_CONFIG'), 'Local qualified broker config required')
class EvidenceIntegration(unittest.TestCase):
    def setUp(self):
        self.config_path = Path(os.environ['SCIENTIFIC_BROKER_CONFIG']).resolve()
        self.broker = Broker(self.config_path)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def fresh_job(self, broker=None):
        broker = broker or self.broker
        source = broker.paths['datasetRoot'] / 'math3d' / 'basic' / '01_tetrahedron.obj'
        job = broker.submit({'schemaVersion': 1, 'runtimeId': 'cgal-win-conda',
                             'capabilityId': 'mesh.interop.vtk-math3d',
                             'input': {'path': str(source), 'sha256': sha(source)}})
        deadline = time.monotonic() + 30
        while job['state'] == 'running' and time.monotonic() < deadline:
            time.sleep(0.05)
            job = broker.snapshot(broker.jobs[job['jobId']])
        self.assertNotEqual('running', job['state'])
        return job

    def agent(self):
        key = self.root / 'agent.key'
        key.write_bytes(b'ci-agent-test-signing-key-' + b'0' * 32)
        profile = {'schemaVersion': 1, 'agentId': 'ci-test-agent',
                   'hostFingerprintSha256': host_fingerprint(), 'gpuCapable': False, 'keyFile': str(key)}
        agent_path = self.root / 'agent.json'
        agent_path.write_text(json.dumps(profile))
        trust_path = self.root / 'trusted.json'
        trust_path.write_text(json.dumps({'schemaVersion': 1, 'agents': [profile]}))
        return agent_path, trust_path, key

    def test_ci_bundle_authentication_suite_drift_and_gpu_gate(self):
        job = self.fresh_job()
        self.assertEqual('succeeded', job['state'], job['diagnostics'])
        agent, trusted, key = self.agent()
        bundle = ci_evidence.export_job(self.config_path, job['jobId'], agent, self.root / 'ci.zip')
        _, summary = ci_evidence.import_bundle(bundle, trusted, self.config_path, self.root / 'imports')
        self.assertEqual('matching-deployment', summary['applicability'])
        self.assertEqual('ci', summary['executionLocation'])
        self.assertEqual(job['jobId'], summary['sourceJobId'])
        self.assertFalse(summary['gpuQualification'])
        with self.assertRaisesRegex(ValueError, 'GPU evidence requires a GPU agent'):
            ci_evidence.export_job(self.config_path, job['jobId'], agent, self.root / 'gpu.zip', gpu_evidence=True)
        with self.assertRaisesRegex(ValueError, 'already been imported'):
            ci_evidence.import_bundle(bundle, trusted, self.config_path, self.root / 'imports')
        manifest_bytes, manifest, signature, members = ci_evidence.read_bundle(bundle)
        evidence = json.loads(members['evidence.json'])
        self.assertNotIn('path', json.dumps(evidence).lower())
        evidence['suiteRevisionSha256'] = '0' * 64
        members['evidence.json'] = ci_evidence.encoded(evidence)
        manifest['files']['evidence.json'] = {'sha256': ci_evidence.hash_bytes(members['evidence.json']),
                                              'bytes': len(members['evidence.json'])}
        manifest_bytes = ci_evidence.encoded(manifest)
        signature['manifestSha256'] = ci_evidence.hash_bytes(manifest_bytes)
        signature['mac'] = hmac.new(key.read_bytes(), manifest_bytes, hashlib.sha256).hexdigest()
        stale = self.root / 'stale.zip'
        with zipfile.ZipFile(stale, 'w') as archive:
            for name, data in members.items():
                archive.writestr(name, data)
            archive.writestr('manifest.json', manifest_bytes)
            archive.writestr('signature.json', ci_evidence.encoded(signature))
        _, imported = ci_evidence.import_bundle(stale, trusted, self.config_path, self.root / 'stale-imports')
        self.assertEqual('inconclusive', imported['applicability'])
        self.assertTrue(any('suite revision' in reason for reason in imported['reasons']))
        forged = self.root / 'forged.zip'
        with zipfile.ZipFile(forged, 'w') as archive:
            for name, data in members.items():
                archive.writestr(name, data)
            archive.writestr('manifest.json', manifest_bytes)
            signature['mac'] = '0' * 64
            archive.writestr('signature.json', ci_evidence.encoded(signature))
        with self.assertRaisesRegex(ValueError, 'signature mismatch'):
            ci_evidence.import_bundle(forged, trusted, self.config_path, self.root / 'forged-imports')
        evidence['gpuQualification'] = True
        members['evidence.json'] = ci_evidence.encoded(evidence)
        manifest['files']['evidence.json'] = {'sha256': ci_evidence.hash_bytes(members['evidence.json']),
                                              'bytes': len(members['evidence.json'])}
        manifest_bytes = ci_evidence.encoded(manifest)
        signature['manifestSha256'] = ci_evidence.hash_bytes(manifest_bytes)
        signature['mac'] = hmac.new(key.read_bytes(), manifest_bytes, hashlib.sha256).hexdigest()
        cpu_claim = self.root / 'cpu-gpu-claim.zip'
        with zipfile.ZipFile(cpu_claim, 'w') as archive:
            for name, data in members.items():
                archive.writestr(name, data)
            archive.writestr('manifest.json', manifest_bytes)
            archive.writestr('signature.json', ci_evidence.encoded(signature))
        with self.assertRaisesRegex(ValueError, 'CPU-only CI agent'):
            ci_evidence.import_bundle(cpu_claim, trusted, self.config_path, self.root / 'cpu-gpu-imports')

    def test_release_requires_fresh_current_desktop_evidence(self):
        installed = ROOT / 'BatchLauncher' / 'bin' / 'Release' / 'net8.0-windows'
        if not installed.is_dir():
            self.skipTest('Release launcher build is required')
        # A controlled exporter proves the record gate; the actual exporter is exercised separately.
        def current_export(repo, installed_root, math3d_root, profile_id, target):
            original = self.broker.paths['manifest']
            target.write_bytes(original.read_bytes())
            Path(str(target) + '.sha256').write_text(sha(target))
            return json.loads(target.read_text())
        report_path, report = release_certification.certify(
            self.config_path, installed, 'desktop-five', 'test-release', self.root / 'release', exporter=current_export)
        self.assertEqual('qualified', report['verdict'])
        self.assertEqual('stale', release_certification.inventory_state(
            {'generatedAt': '2020-01-01T00:00:00Z'}, release_certification.datetime.now(release_certification.timezone.utc)))
        self.assertEqual('current', report['inventoryState'])
        self.assertEqual([f'L{index}' for index in range(10)], [item['level'] for item in report['gateVerdicts']])
        self.assertTrue(all(item['state'] == 'current' for item in report['gateVerdicts']))
        self.assertEqual('qualified', release_certification.verify_release(report_path, self.config_path)['verdict'])
        inventory = report_path.parent / 'runtime-inventory.json'
        original_inventory = inventory.read_bytes()
        inventory.write_bytes(original_inventory + b' ')
        with self.assertRaisesRegex(ValueError, 'inventory hash mismatch'):
            release_certification.verify_release(report_path, self.config_path)
        inventory.write_bytes(original_inventory)
        manifest = report_path.parent / 'release-capabilities.json'
        manifest.write_bytes(manifest.read_bytes() + b' ')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            release_certification.verify_release(report_path, self.config_path)
        def empty_export(repo, installed_root, math3d_root, profile_id, target):
            value = {'schemaVersion': 1, 'kind': 'scientific.certified-capabilities',
                     'certifiedCapabilities': []}
            target.write_text(json.dumps(value))
            Path(str(target) + '.sha256').write_text(sha(target))
            return value
        blocked_path, blocked = release_certification.certify(
            self.config_path, installed, 'desktop-five', 'blocked-release', self.root / 'release', exporter=empty_export)
        self.assertEqual('blocked', blocked['verdict'])
        self.assertTrue(all(item['state'] == 'blocked' for item in blocked['gateVerdicts']))
        self.assertFalse((blocked_path.parent / 'release-capabilities.json').exists())
        self.assertEqual('blocked', release_certification.verify_release(blocked_path)['verdict'])

    def test_reviewed_public_fixture_replays_failure(self):
        config = json.loads(self.config_path.read_text())
        config['jobsRoot'] = str(self.root / 'limited-jobs')
        config['memoryLimitMiB'] = 1
        limited_path = self.root / 'limited-config.json'
        limited_path.write_text(json.dumps(config))
        limited = Broker(limited_path)
        source = self.fresh_job(limited)
        self.assertEqual('resource-exhausted', source['state'], source['diagnostics'])
        draft_path = regression_fixtures.draft(limited_path, source['jobId'], self.root / 'regressions')
        proposal = regression_fixtures.read(draft_path, 'scientific.regression-draft')
        self.assertFalse(proposal['privacy']['rawInputIncluded'])
        self.assertFalse(proposal['privacy']['pathsIncluded'])
        with self.assertRaisesRegex(ValueError, 'explicit public-fixture approval'):
            regression_fixtures.promote(limited_path, draft_path, 'tester', False, self.root / 'regressions')
        review_path, fixture_path = regression_fixtures.promote(
            limited_path, draft_path, 'tester', True, self.root / 'regressions')
        self.assertIsNotNone(fixture_path, regression_fixtures.read(review_path, 'scientific.regression-review'))
        fixture, replay = regression_fixtures.verify_fixture(limited_path, fixture_path, replay=True)
        self.assertEqual('resource-exhausted', fixture['expectedState'])
        self.assertEqual('resource-exhausted', replay['state'])
        self.assertFalse(fixture['privacy']['pathsIncluded'])
        original = fixture_path.read_bytes()
        fixture_path.write_bytes(original + b' ')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            regression_fixtures.verify_fixture(limited_path, fixture_path)
        fixture_path.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
