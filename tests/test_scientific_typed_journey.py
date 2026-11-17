import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('journey', ROOT / 'tools/scientific-broker/verify_typed_journey.py')
journey = importlib.util.module_from_spec(spec)
spec.loader.exec_module(journey)
contract = json.loads(journey.CONTRACT.read_text(encoding='utf-8'))


def write(root, name, content):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    data = content if isinstance(content, bytes) else json.dumps(content, sort_keys=True).encode()
    path.write_bytes(data)
    return {'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def fixture(root, duplicate_source=False):
    manifest = {'schemaVersion': 1, 'contractSha256': journey.sha(journey.CONTRACT),
                'sourceCommit': 'a' * 40, 'sourceSnapshotSha256': 'c' * 64, 'math3dCommit': 'b' * 40,
                'lengthUnit': 'mm', 'frame': {'id': 'world', 'handedness': 'right', 'axes': ['x', 'y', 'z']}, 'stages': []}
    artifacts = {}
    saved = {}
    for generation, name in enumerate(contract['stageOrder']):
        run_id = format(generation + 1, '032x')
        inputs = contract['requiredInputs'][name]
        outputs = []
        for role in contract['requiredOutputs'][name]:
            original = 'document' if role == 'reopened-document' else 'export' if role == 'reopened-export' else role
            if duplicate_source and role == 'source-b':
                original = 'source-a'
            content = saved.get(original, (original + '-' + run_id).encode())
            saved[role] = content
            artifact = write(root, f'artifacts/{role}.bin', content)
            artifact.update(id=role, mediaType='application/octet-stream', frame='world', lengthUnit='mm',
                            generation=generation, parents=inputs, producedBy=run_id)
            outputs.append(artifact)
            artifacts[role] = artifact
        result = {'runId': run_id, 'operation': contract['operations'][name], 'state': 'succeeded',
                  'sourceCommit': manifest['sourceCommit'],
                  'sourceSnapshotSha256': manifest['sourceSnapshotSha256'],
                  'inputHashes': {role: artifacts[role]['sha256'] for role in inputs},
                  'outputHashes': {item['id']: item['sha256'] for item in outputs}}
        if name in ('math3d', 'save', 'cold-reopen'):
            result['consumerCommit'] = manifest['math3dCommit']
        if name == 'validate':
            result['topology'] = {role: {'closed': True, 'manifold': True, 'positiveVolume': True} for role in inputs}
        if name == 'scipy':
            result['measurement'] = {'value': 2.5, 'unit': 'mm2', 'tolerance': 0.01}
        if name == 'cold-reopen':
            result['newProcess'] = True
        evidence = write(root, f'evidence/{name}.json', result)
        manifest['stages'].append({'id': name, 'state': 'succeeded', 'operation': contract['operations'][name],
                                   'runId': run_id, 'inputs': inputs, 'outputs': outputs, 'evidence': evidence})
    write(root, 'journey.json', manifest)
    return manifest


class TypedJourneyTests(unittest.TestCase):
    def test_chain_and_cold_reopen_relations(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture(Path(directory))
            self.assertEqual(journey.verify(directory)['artifacts'], 14)

    def test_tampered_payload_and_duplicate_boolean_source_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = fixture(root)
            (root / 'artifacts/gmsh-mesh.bin').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'content or size changed'):
                journey.verify(root)
            fixture(root, duplicate_source=True)
            with self.assertRaisesRegex(ValueError, 'two distinct source hashes'):
                journey.verify(root)

    def test_stage_order_path_and_unit_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = fixture(root)
            manifest['stages'][2], manifest['stages'][3] = manifest['stages'][3], manifest['stages'][2]
            write(root, 'journey.json', manifest)
            with self.assertRaisesRegex(ValueError, 'out of order'):
                journey.verify(root)
            manifest = fixture(root)
            manifest['stages'][0]['outputs'][0]['path'] = '../escape.bin'
            write(root, 'journey.json', manifest)
            with self.assertRaisesRegex(ValueError, 'escapes'):
                journey.verify(root)
            manifest = fixture(root)
            manifest['stages'][5]['outputs'][0]['lengthUnit'] = 'm'
            write(root, 'journey.json', manifest)
            with self.assertRaisesRegex(ValueError, 'unit'):
                journey.verify(root)

    def test_result_tamper_and_consumer_drift_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            path = root / 'evidence/boolean.json'
            record = json.loads(path.read_text(encoding='utf-8'))
            record['inputHashes']['validated-b'] = '0' * 64
            write(root, 'evidence/boolean.json', record)
            with self.assertRaisesRegex(ValueError, 'content or size changed'):
                journey.verify(root)
            manifest = fixture(root)
            manifest['math3dCommit'] = 'd' * 40
            write(root, 'journey.json', manifest)
            with self.assertRaisesRegex(ValueError, 'different MATH3D consumer'):
                journey.verify(root)


if __name__ == '__main__':
    unittest.main()
