"""Version migration gates and release verdicts preserve evidence limits."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools' / 'scientific-broker'))
import contract_migration
import release_matrix
from broker import sha


def registry(field='input'):
    return {'schemaVersion': 1, 'schemaId': 'test.contract',
            'parameterSchemas': {'request.v1': {'type': 'object', 'required': [field],
                'properties': {field: {'type': 'string'}}, 'additionalProperties': False}},
            'resultSchemas': {}, 'capabilities': []}


class MigrationPolicy(unittest.TestCase):
    def test_optional_minor_patch_and_explicit_major_rename(self):
        old = registry()
        optional = registry()
        optional['parameterSchemas']['request.v1']['properties']['label'] = {'type': 'string'}
        self.assertEqual('compatible', contract_migration.assess(old, optional, '1.0.0', '1.1.0', [])['verdict'])
        self.assertEqual('blocked', contract_migration.assess(old, optional, '1.0.0', '1.0.1', [])['verdict'])
        new = registry('artifact')
        self.assertEqual('blocked', contract_migration.assess(old, new, '1.0.0', '2.0.0', [])['verdict'])
        rule = {'id': 'rename-input', 'scope': 'parameterSchemas.request.v1',
                'operation': 'rename-field', 'from': 'input', 'to': 'artifact',
                'oldFixture': {'input': 'mesh.obj'}, 'newFixture': {'artifact': 'mesh.obj'}}
        result = contract_migration.assess(old, new, '1.0.0', '2.0.0', [rule])
        self.assertEqual('migratable', result['verdict'])
        self.assertEqual(['rename-input'], result['verifiedMigrationIds'])
        rule['newFixture'] = {'artifact': 5}
        self.assertEqual('blocked', contract_migration.assess(old, new, '1.0.0', '2.0.0', [rule])['verdict'])
        malformed = registry()
        malformed['capabilities'] = [{'id': 'broken', 'version': 1, 'parametersSchema': 'missing',
                                      'resultSchema': 'missing', 'providers': []}]
        self.assertEqual('blocked', contract_migration.assess(old, malformed, '1.0.0', '2.0.0', [])['verdict'])

    def test_real_registry_report_and_hash_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            policy = ROOT / 'schemas' / 'scientific-contract-migrations.v1.json'
            path, report = contract_migration.check(policy, directory)
            self.assertEqual('passed', report['verdict'])
            self.assertEqual(report, contract_migration.verify(path, policy))
            path.write_bytes(path.read_bytes() + b' ')
            with self.assertRaisesRegex(ValueError, 'report hash mismatch'):
                contract_migration.verify(path, policy)


class ReleaseCoverage(unittest.TestCase):
    def test_certified_chain_and_unqualified_version_are_distinct(self):
        now = datetime.now(timezone.utc).isoformat()
        inventory = {'generatedAt': now, 'runtimes': [
            {'id': 'cgal-win-conda', 'version': '6.0.1', 'state': 'ready'},
            {'id': 'vtk-win-conda', 'version': '9.5', 'state': 'ready'},
            {'id': 'gmsh-win-conda', 'version': None, 'state': 'missing'}]}
        support = [{'level': f'L{number}', 'runId': 'a' * 32} for number in range(10)]
        qualified = {'verdict': 'qualified', 'capabilities': [{
            'runtimeId': 'cgal-win-conda', 'capabilityId': 'mesh.interop.vtk-math3d',
            'recordId': 'b' * 64, 'productContractSha256': 'c' * 64,
            'supportingRecords': support}]}
        blocked = {'verdict': 'blocked', 'capabilities': []}
        left = {'releaseTag': '1.0', 'releaseId': 'a', 'releaseReportPath': 'left.json',
                'rows': release_matrix.rows(qualified, inventory, 'current')}
        right_inventory = {**inventory, 'runtimes': [
            inventory['runtimes'][0], {'id': 'vtk-win-conda', 'version': '9.6', 'state': 'ready'}, inventory['runtimes'][2]]}
        right = {'releaseTag': '1.1', 'releaseId': 'b', 'releaseReportPath': 'right.json',
                 'rows': release_matrix.rows(blocked, right_inventory, 'current')}
        by_id = {item['provider']: item for item in release_matrix.compare(left, right)['rows']}
        self.assertEqual('qualification-not-current', by_id['cgal-win-conda']['verdict'])
        self.assertEqual('version-changed-unqualified', by_id['vtk-win-conda']['verdict'])
        self.assertEqual('contract-evidence', left['rows'][-1]['confidence'])
        self.assertEqual([], left['rows'][-1]['qualifiedCapabilities'])
        self.assertEqual('no-evidence', left['rows'][2]['confidence'])  # VTK-m is not registered.
        self.assertEqual('stale', release_matrix.age_state({'generatedAt': '2026-01-01T00:00:00Z'},
            {'createdAtUtc': now}))

    def test_blocked_release_snapshots_verify_and_remain_inconclusive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inventory = root / 'runtime-report.json'
            inventory.write_text(json.dumps({'schemaVersion': 1, 'generatedAt': datetime.now(timezone.utc).isoformat(),
                'runtimes': [{'id': 'gmsh-win-conda', 'version': None, 'state': 'missing'}]}))
            snapshots = []
            for index in (1, 2):
                folder = root / f'release-{index}'
                folder.mkdir()
                fresh = folder / 'fresh-capabilities.json'
                fresh.write_text(json.dumps({'schemaVersion': 1, 'kind': 'scientific.certified-capabilities',
                                             'certifiedCapabilities': []}))
                Path(str(fresh) + '.sha256').write_text(sha(fresh))
                release = folder / 'qualification-report.json'
                release.write_text(json.dumps({'schemaVersion': 1, 'kind': 'scientific.release-qualification-report',
                    'releaseId': f'release-{index}', 'releaseTag': f'v{index}', 'sourceCommit': str(index),
                    'createdAtUtc': datetime.now(timezone.utc).isoformat(), 'verdict': 'blocked',
                    'reasons': ['No current L9 evidence'], 'freshManifestSha256': sha(fresh), 'capabilities': []}))
                Path(str(release) + '.sha256').write_text(sha(release))
                snapshot, saved = release_matrix.snapshot(release, inventory, root / 'snapshots')
                self.assertEqual(saved, release_matrix.verify_snapshot(snapshot))
                snapshots.append(snapshot)
            path, report = release_matrix.matrix(*snapshots, root / 'matrix')
            self.assertEqual('inconclusive', report['verdict'])
            self.assertEqual(6, len(release_matrix.verify_matrix(path)['rows']))
            inventory.write_bytes(inventory.read_bytes() + b' ')
            with self.assertRaisesRegex(ValueError, 'source evidence changed'):
                release_matrix.verify_matrix(path)


if __name__ == '__main__':
    unittest.main()
