import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { verifyTypedMeasurement } from '../tools/math3d-typed-measurement.mjs';

const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const measurement = { kind: 'surface-area', value: 26, tolerance: 1e-9, unit: 'mm2',
  frame: 'world', sourceArtifactSha256: 'd'.repeat(64) };
const record = { schemaVersion: 1, operation: 'scipy.measure', state: 'succeeded',
  sourceCommit: 'a'.repeat(40), sourceSnapshotSha256: 'b'.repeat(64),
  inputHashes: { 'vtk-analysis': 'd'.repeat(64) }, measurement };
const bytes = Buffer.from(JSON.stringify(record));
const provenance = { schemaVersion: 1, kind: 'scientific.typed-journey',
  convertedObjSha256: 'e'.repeat(64), math3dCommit: 'c'.repeat(40),
  sourceCommit: 'a'.repeat(40), sourceSnapshotSha256: 'b'.repeat(64),
  vtkArtifactSha256: 'd'.repeat(64), measurementSha256: sha(bytes),
  booleanSourceASha256: '1'.repeat(64), booleanSourceBSha256: '2'.repeat(64),
  booleanSurfaceSha256: '3'.repeat(64), gmshMeshSha256: '4'.repeat(64),
  gmshBoundarySha256: '5'.repeat(64),
  lengthUnit: 'mm', frame: 'world', geometryGeneration: 4,
  measurementGeneration: 5, consumerGeneration: 6, measurement };

test('typed numeric artifact binds geometry, frame, unit and consumer', () => {
  const accepted = verifyTypedMeasurement(bytes, sha(bytes), provenance, 'e'.repeat(64), 'c'.repeat(40));
  assert.equal(accepted.value, 26);
  assert.equal(accepted.unit, 'mm2');
  for (const changed of [
    { vtkArtifactSha256: 'f'.repeat(64) }, { lengthUnit: 'm' }, { frame: 'local' },
    { math3dCommit: 'f'.repeat(40) }, { measurementSha256: '0'.repeat(64) },
    { sourceSnapshotSha256: '0'.repeat(64) },
    { booleanSourceBSha256: '1'.repeat(64) },
  ]) assert.throws(() => verifyTypedMeasurement(bytes, sha(bytes), { ...provenance, ...changed }, 'e'.repeat(64), 'c'.repeat(40)));
  assert.throws(() => verifyTypedMeasurement(Buffer.concat([bytes, Buffer.from(' ')]), sha(bytes), provenance, 'e'.repeat(64), 'c'.repeat(40)));
});
