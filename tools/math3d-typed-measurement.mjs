import { createHash } from 'node:crypto';

const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const hex = value => typeof value === 'string' && /^[0-9a-f]{64}$/.test(value);
const commit = value => typeof value === 'string' && /^[0-9a-f]{40}$/.test(value);
const canonical = value => Array.isArray(value) ? value.map(canonical) : value && typeof value === 'object'
  ? Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([key, item]) => [key, canonical(item)])) : value;

export function verifyTypedMeasurement(bytes, expectedSha, provenance, sourceObjSha, consumerCommit) {
  if (!hex(expectedSha) || sha(bytes) !== expectedSha || !provenance
    || provenance.schemaVersion !== 1 || provenance.kind !== 'scientific.typed-journey'
    || provenance.convertedObjSha256 !== sourceObjSha || provenance.math3dCommit !== consumerCommit
    || !commit(provenance.sourceCommit) || !hex(provenance.sourceSnapshotSha256)
    || !hex(provenance.vtkArtifactSha256) || provenance.measurementSha256 !== expectedSha
    || !hex(provenance.booleanSourceASha256) || !hex(provenance.booleanSourceBSha256)
    || provenance.booleanSourceASha256 === provenance.booleanSourceBSha256
    || !hex(provenance.booleanSurfaceSha256) || !hex(provenance.gmshMeshSha256)
    || !hex(provenance.gmshBoundarySha256)
    || provenance.geometryGeneration !== 4 || provenance.measurementGeneration !== 5
    || provenance.consumerGeneration !== 6
    || !['m', 'mm'].includes(provenance.lengthUnit) || typeof provenance.frame !== 'string' || !provenance.frame)
    throw new Error('Typed MATH3D measurement identity is invalid.');
  let result;
  try { result = JSON.parse(bytes.toString('utf8')); } catch { throw new Error('Typed MATH3D measurement JSON is invalid.'); }
  const measurement = result.measurement;
  if (result.schemaVersion !== 1 || result.operation !== 'scipy.measure' || result.state !== 'succeeded'
    || result.sourceCommit !== provenance.sourceCommit
    || result.sourceSnapshotSha256 !== provenance.sourceSnapshotSha256
    || result.inputHashes?.['vtk-analysis'] !== provenance.vtkArtifactSha256
    || measurement?.kind !== 'surface-area' || measurement.unit !== provenance.lengthUnit + '2'
    || measurement.frame !== provenance.frame || measurement.sourceArtifactSha256 !== provenance.vtkArtifactSha256
    || !Number.isFinite(measurement.value) || measurement.value <= 0
    || !Number.isFinite(measurement.tolerance) || measurement.tolerance < 0
    || !provenance.measurement || JSON.stringify(canonical(provenance.measurement)) !== JSON.stringify(canonical(measurement)))
    throw new Error('Typed MATH3D measurement does not match VTK, units, frame or source.');
  return { sha256: expectedSha, kind: measurement.kind, value: measurement.value,
    unit: measurement.unit, tolerance: measurement.tolerance, frame: measurement.frame,
    sourceArtifactSha256: measurement.sourceArtifactSha256 };
}
