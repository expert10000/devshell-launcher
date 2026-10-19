import { createHash, randomUUID } from 'node:crypto';
import { readFile, readdir, mkdir, stat, writeFile, appendFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { parseObj, encodeMesh, decodeMesh, runWorker } from './math3d-native-protocol.mjs';
import { fixtures, referenceMesh, transform } from './math3d-boolean-fixtures.mjs';
import { meshStats, numericComparison } from './math3d-mesh-comparison.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const scientific = path.join(root, '.scientific');
const runs = path.join(scientific, 'runs');
const worker = process.argv[2] || path.join(scientific, 'builds', 'math3d-native-worker', 'Release', 'math3d-cgal-worker.exe');
const sha256 = data => createHash('sha256').update(data).digest('hex');

async function latestBaseline(datasetId) {
  let found;
  for (const entry of await readdir(runs, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const file = path.join(runs, entry.name, 'results.json');
    try {
      if ((await stat(file)).size > 1048576) continue;
      const result = JSON.parse(await readFile(file, 'utf8'));
      if (result.recipeId !== 'cgal.validate' || result.state !== 'succeeded' ||
          (process.argv[4] && result.profileId !== process.argv[4]) ||
          !result.inputArtifacts?.some(item => item.datasetId === datasetId)) continue;
      if (result.runtimeId !== 'cgal-win-conda' || result.diagnostics?.length !== 0) continue;
      const manifest = JSON.parse(await readFile(path.join(scientific, 'datasets', 'manifest.json'), 'utf8'));
      const entry = manifest.entries.find(item => item.id === datasetId);
      const input = result.inputArtifacts.find(item => item.datasetId === datasetId);
      const currentPath = entry && path.resolve(scientific, 'datasets', entry.path);
      if (!currentPath || path.resolve(input.path).toLowerCase() !== currentPath.toLowerCase() || input.sha256 !== entry.sha256 || sha256(await readFile(currentPath)) !== input.sha256) continue;
      const configure = result.steps?.find(step => step.stage === 'configure');
      if (!configure?.executable || (process.env.CMAKE_PREFIX_PATH && path.resolve(configure.executable).toLowerCase() !== path.resolve(process.env.CMAKE_PREFIX_PATH, 'bin', 'cmake.exe').toLowerCase())) continue;
      const output = result.artifacts?.find(item => item.path.endsWith('.obj'));
      if (!output || path.isAbsolute(output.path) || output.path.includes('..') || output.path.includes('\\') || output.path.includes(':')) continue;
      const bytes = await readFile(path.join(runs, path.basename(path.dirname(file)), output.path)).catch(() => null);
      if (!bytes || sha256(bytes) !== output.sha256 || bytes.length !== output.bytes) continue;
      const modified = (await stat(file)).mtimeMs;
      if (!found || modified > found.modified) found = { result, modified, file };
    } catch (error) {
      if (error.code !== 'ENOENT' && !(error instanceof SyntaxError) && !(error instanceof TypeError)) throw error;
    }
  }
  if (!found) throw new Error(`No successful DevShell validation for ${datasetId} was found`);
  return found;
}

const managedDirectory = process.argv[3] ? path.resolve(process.argv[3]) : '';
const jobId = managedDirectory ? path.basename(managedDirectory) : randomUUID().replaceAll('-', '');
await stat(worker);
const runDir = managedDirectory || path.join(runs, jobId);
await mkdir(runDir, { recursive: true });
const cases = [], checks = [], artifacts = [], inputArtifacts = [];
let durationMs = 0;
for (const fixture of fixtures) {
  const baseline = await latestBaseline(fixture.datasetId);
  const inputArtifact = baseline.result.inputArtifacts.find(item => item.datasetId === fixture.datasetId);
  const inputPath = path.resolve(inputArtifact.path);
  const datasetRoot = path.resolve(scientific, 'datasets');
  const relative = path.relative(datasetRoot, inputPath);
  if (!relative || relative.startsWith('..') || path.isAbsolute(relative))
    throw new Error('Baseline input is outside registered local copies');
  const source = await readFile(inputPath);
  const inputHash = sha256(source);
  if (inputHash !== inputArtifact.sha256) throw new Error(`Registered ${fixture.name} SHA-256 has changed`);
  const inputMesh = parseObj(source.toString('utf8'), fixture);
  const rightMesh = transform(inputMesh, fixture.scale, fixture.offsetX);
  const operation = fixture.operation || 1;
  const referenceGeometry = referenceMesh(inputMesh, fixture);
  const leftBytes = encodeMesh(inputMesh), rightBytes = encodeMesh(rightMesh);
  const configure = baseline.result.steps?.find(step => step.stage === 'configure');
  if (!configure?.executable) throw new Error('Baseline does not identify the CGAL Library/bin environment');
  const response = await runWorker(worker, `${jobId}-${fixture.name.toLowerCase().replaceAll(' ', '-')}`, leftBytes, rightBytes, path.dirname(configure.executable), operation);
  durationMs += response.durationMs;
  const outputMesh = response.status === 0 ? decodeMesh(response.mesh) : null;
  const before = meshStats(inputMesh), reference = meshStats(referenceGeometry);
  const after = outputMesh ? meshStats(outputMesh) : null;
  const quantitative = numericComparison(referenceGeometry, outputMesh, reference, after);
  const expected = baseline.result.after;
  const caseChecks = [
    { name: 'CGAL baseline matches registered input', passed: ['vertices', 'edges', 'faces', 'boundaryEdges', 'closed'].every(key => before[key] === expected?.[key]) && baseline.result.diagnostics?.length === 0,
      expected, actual: before },
    { name: fixture.relation ? `native ${fixture.relation}-cubes ${operation === 2 ? 'difference' : operation === 3 ? 'intersection' : 'union'} accepted` : 'native Boolean self-union accepted', passed: response.status === 0 && !!outputMesh,
      expected: 'status 0 with M3DM output', actual: `status ${response.status}: ${response.message}` },
    { name: reference.faces === 0 ? 'empty intersection' : 'expected closed-shell topology', passed: !!after && after.closed === reference.closed && after.components === reference.components && after.euler === reference.euler && (reference.faces === 0 ? after.vertices === 0 && after.faces === 0 : after.volume > 0),
      expected: { closed: reference.closed, components: reference.components, euler: reference.euler, empty: reference.faces === 0 }, actual: after },
    { name: 'bounds within tolerance', passed: !!quantitative && quantitative.metrics.boundsDelta <= quantitative.tolerances.bounds,
      expected: quantitative?.tolerances.bounds, actual: quantitative?.metrics.boundsDelta },
    { name: 'surface area within tolerance', passed: !!quantitative && quantitative.metrics.areaDelta <= quantitative.tolerances.area,
      expected: quantitative?.tolerances.area, actual: quantitative?.metrics.areaDelta },
    { name: 'enclosed volume within tolerance', passed: !!quantitative && quantitative.metrics.volumeDelta <= quantitative.tolerances.volume,
      expected: quantitative?.tolerances.volume, actual: quantitative?.metrics.volumeDelta },
    { name: 'sampled surface deviation within tolerance', passed: !!quantitative && quantitative.metrics.sampledSurfaceDeviation <= quantitative.tolerances.sampledSurface,
      expected: quantitative?.tolerances.sampledSurface, actual: quantitative?.metrics.sampledSurfaceDeviation },
  ];
  checks.push(...caseChecks.map(check => ({ ...check, name: `${fixture.name}: ${check.name}` })));
  if (!inputArtifacts.some(item => item.datasetId === fixture.datasetId))
    inputArtifacts.push({ ...inputArtifact, path: inputPath, sha256: inputHash });
  if (outputMesh) {
    await writeFile(path.join(runDir, fixture.output), response.mesh);
    artifacts.push({ path: fixture.output, mediaType: 'application/octet-stream', bytes: response.mesh.length, sha256: sha256(response.mesh) });
  }
  cases.push({ name: fixture.name, datasetId: fixture.datasetId, operation: operation === 2 ? 'difference' : operation === 3 ? 'intersection' : 'union', baselineRunId: baseline.result.runId,
    baselineResult: baseline.file, workerStatus: response.status, workerMessage: response.message,
    before, reference, after, ...quantitative, outputArtifact: outputMesh ? fixture.output : null,
    rightOperand: { sourceDatasetId: fixture.datasetId, translateX: fixture.offsetX || 0, scale: fixture.scale || 1,
      encodedSha256: sha256(rightBytes), bounds: meshStats(rightMesh).bounds } });
}
const passed = checks.filter(check => check.passed).length;
const succeeded = passed === checks.length;
const scope = `MATH3D native Boolean comparison: tetrahedron and cube self-unions, plus overlapping, face-touching, disjoint, and contained cube union/intersection/difference; ${passed}/${checks.length} checks passed across ${cases.length} cases. Empty intersections, separate shells, and the contained difference cavity have explicit expectations. Sampled surface deviation is not a full Hausdorff proof.`;
const result = {
  schemaVersion: 1, runId: jobId, runtimeId: 'cgal-win-conda',
  recipeId: 'integration.math3d.native-boolean', operation: 'mesh.boolean',
  engine: 'MATH3D native CGAL worker', profileId: process.argv[4] || null,
  state: succeeded ? 'succeeded' : 'failed', exitCode: succeeded ? 0 : 1,
  durationMs, versions: { math3dWorker: 'protocol 1' },
  validatedCapabilities: succeeded ? ['mesh.boolean'] : [],
  before: cases[0].before, after: cases[0].after,
  diagnostics: succeeded ? [] : checks.filter(check => !check.passed).map(check => ({ severity: 'error', message: check.name })),
  inputArtifacts, artifacts,
  comparison: { verdict: succeeded ? 'pass' : 'fail', passed, total: checks.length,
    workerExecutable: worker, cases, checks },
  scope, provenance: { inputPolicy: 'Registered local copy, SHA-256 checked',
    transport: 'MATH3D M3DC binary protocol; worker in separate process' },
  logReference: 'full.log',
};
const requestPath = path.join(runDir, 'request.json');
try { await stat(requestPath); }
catch (error) {
  if (error.code !== 'ENOENT') throw error;
  await writeFile(requestPath, JSON.stringify({
    schemaVersion: 1, runId: jobId, profileId: result.profileId, runtimeId: result.runtimeId,
    recipeId: result.recipeId, operation: result.operation, parameters: {},
    workingDirectory: runDir, datasetRoot: path.join(scientific, 'datasets'), timeoutSeconds: 90,
    inputArtifacts, outputArtifacts: artifacts.map(({ path: artifactPath, mediaType }) => ({ path: artifactPath, mediaType })),
    provenance: result.provenance,
  }, null, 2) + '\n');
}
await writeFile(path.join(runDir, 'results.json'), JSON.stringify(result, null, 2) + '\n');
await (managedDirectory ? appendFile : writeFile)(path.join(runDir, 'full.log'), `${scope}\n${checks.map(check => `${check.passed ? 'PASS' : 'FAIL'} ${check.name}: ${JSON.stringify(check.actual)}`).join('\n')}\n`);
console.log(`${succeeded ? 'PASS' : 'FAIL'} ${passed}/${checks.length}: ${scope}`);
console.log(`Saved ${path.join(runDir, 'results.json')}`);
if (!succeeded) process.exitCode = 1;
