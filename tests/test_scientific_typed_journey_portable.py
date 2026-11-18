"""Offline typed bundle policy and the exact stage-parent regression."""
import json
import base64
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/scientific-broker'))
from portable_typed_journey import closed_obj, compact, digest, permitted, stage_relations, verify  # noqa: E402


class PortableTypedJourneyTests(unittest.TestCase):
    def test_closed_distinct_source_and_changed_orientation(self):
        source = (ROOT / 'scientific/fixtures/cgal-repair-quad/cube-closed.obj').read_bytes()
        self.assertGreater(closed_obj(source)['volume'], 0)
        changed = source.replace(b'f 1 3 2', b'f 1 2 3', 1)
        with self.assertRaisesRegex(ValueError, 'closed oriented'):
            closed_obj(changed)

    def test_local_path_is_outside_portable_format_policy(self):
        permitted('measurement.json', b'{"unit":"mm2"}')
        with self.assertRaisesRegex(ValueError, 'local absolute path'):
            permitted('measurement.json', json.dumps({'path': 'C:\\private\\mesh.obj'}).encode())

    def test_signed_archive_refuses_missing_payload_and_changed_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            key = Ed25519PrivateKey.generate()
            public = key.public_key().public_bytes(serialization.Encoding.Raw,
                                                    serialization.PublicFormat.Raw)
            trust = root / 'trust.json'
            trust.write_text(json.dumps({'schemaVersion': 1, 'keys': [{
                'keyId': 'test-key', 'publicKeyBase64': base64.b64encode(public).decode(),
                'validFromUtc': '2020-01-01T00:00:00+00:00',
                'validUntilUtc': '2030-01-01T00:00:00+00:00'}]}), encoding='utf-8')
            manifest = {'schemaVersion': 1, 'kind': 'scientific.portable-typed-journey',
                        'signingKeyId': 'test-key', 'objects': {'a' * 64: 4}}
            body = compact(manifest)
            signature = compact({'algorithm': 'Ed25519', 'keyId': 'test-key',
                'signedAtUtc': datetime.now(timezone.utc).isoformat(),
                'signatureBase64': base64.b64encode(key.sign(body)).decode()})
            bundle = root / 'missing.zip'
            with zipfile.ZipFile(bundle, 'w') as archive:
                archive.writestr('manifest.json', body)
                archive.writestr('manifest.sha256', digest(body))
                archive.writestr('manifest.signature.json', signature)
                archive.writestr('candidate.json', b'{}')
                archive.writestr('support/six-capability.zip', b'zip')
            with self.assertRaisesRegex(ValueError, 'archive inventory changed'):
                verify(bundle, trust)
            changed = root / 'changed.zip'
            with zipfile.ZipFile(changed, 'w') as archive:
                archive.writestr('manifest.json', compact({**manifest, 'sourceCommit': 'b' * 40}))
                archive.writestr('manifest.sha256', digest(compact({**manifest, 'sourceCommit': 'b' * 40})))
                archive.writestr('manifest.signature.json', signature)
                archive.writestr('candidate.json', b'{}')
                archive.writestr('support/six-capability.zip', b'zip')
            with self.assertRaisesRegex(ValueError, 'signature changed'):
                verify(changed, trust)

    def test_scipy_parent_is_vtk_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            hashes = ['a' * 64, 'b' * 64, 'c' * 64]
            p = {'sourceCommit': 'd' * 40, 'math3dCommit': 'e' * 40,
                 'sourceSnapshotSha256': 'f' * 64, 'lengthUnit': 'mm', 'frame': 'world',
                 'booleanSourceASha256': hashes[0], 'booleanSourceBSha256': hashes[1],
                 'booleanSurfaceSha256': hashes[2], 'gmshMeshSha256': '1' * 64,
                 'gmshBoundarySha256': '2' * 64, 'vtkArtifactSha256': '3' * 64,
                 'convertedObjSha256': '4' * 64}
            candidate = {'sourceCommit': p['sourceCommit'], 'math3dCommit': p['math3dCommit'],
                         'desktop': {'sourceRunId': '0' * 32}}

            def write(name, value):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value), encoding='utf-8')

            def stage(operation, parent, run_id, inputs, outputs, dimension=None):
                value = {'schemaVersion': 1, 'state': 'succeeded', 'operation': operation,
                         'sourceRunId': parent, 'runId': run_id,
                         'sourceCommit': p['sourceCommit'],
                         'sourceSnapshotSha256': p['sourceSnapshotSha256'],
                         'lengthUnit': 'mm', 'frame': 'world',
                         'inputHashes': inputs, 'outputHashes': outputs}
                if dimension is not None:
                    value['dimension'] = dimension
                return value

            write('typed-provenance.json', p)
            gmsh = stage('gmsh.mesh', '0' * 32, '5' * 32,
                         {'boolean-surface': hashes[2]}, {'gmsh-mesh': p['gmshMeshSha256']}, 3)
            gmsh['physicalGroups'] = {'BooleanVolume': {'dimension': 3},
                                      'InputBoundary': {'dimension': 2}}
            write('gmsh/results.json', gmsh)
            write('boundary/results.json', stage('gmsh.extract-boundary', '5' * 32, '6' * 32,
                {'gmsh-mesh': p['gmshMeshSha256']}, {'gmsh-boundary': p['gmshBoundarySha256']}, 2))
            write('vtk/results.json', stage('mesh.inspect', '6' * 32, '7' * 32,
                {'gmsh-boundary': p['gmshBoundarySha256']}, {'vtk-analysis': p['vtkArtifactSha256']}))
            scipy = stage('scipy.measure', '7' * 32, '8' * 32,
                          {'vtk-analysis': p['vtkArtifactSha256']}, {})
            write('scipy/measurement.json', scipy)
            write('conversion.json', {'sourceArtifactSha256': p['vtkArtifactSha256'],
                                      'objSha256': p['convertedObjSha256']})
            self.assertEqual(stage_relations(root, candidate, hashes)['frame'], 'world')
            scipy['sourceRunId'] = '6' * 32
            write('scipy/measurement.json', scipy)
            with self.assertRaisesRegex(ValueError, 'parent changed'):
                stage_relations(root, candidate, hashes)


if __name__ == '__main__':
    unittest.main()
