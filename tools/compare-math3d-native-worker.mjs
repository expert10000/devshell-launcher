import { spawn } from 'node:child_process';
import { createHash, randomUUID } from 'node:crypto';
import { readFile, readdir, mkdir, stat, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const scientific = path.join(root, '.scientific');
const runs = path.join(scientific, 'runs');
const fixtures = [
  { name: 'Tetrahedron', datasetId: 'math3d/basic/01_tetrahedron.obj', vertices: 4, faces: 4, output: 'math3d-native-self-union.m3dm' },
  { name: 'Cube', datasetId: 'math3d/basic/02_cube.obj', vertices: 8, faces: 12, output: 'math3d-native-cube-self-union.m3dm' },
  { name: 'Overlapping cubes', datasetId: 'math3d/basic/02_cube.obj', vertices: 8, faces: 12, offsetX: 1, output: 'math3d-native-overlapping-cubes-union.m3dm' },
  { name: 'Overlapping cubes intersection', datasetId: 'math3d/basic/02_cube.obj', vertices: 8, faces: 12, offsetX: 1, operation: 3, output: 'math3d-native-overlapping-cubes-intersection.m3dm' },
  { name: 'Overlapping cubes difference', datasetId: 'math3d/basic/02_cube.obj', vertices: 8, faces: 12, offsetX: 1, operation: 2, output: 'math3d-native-overlapping-cubes-difference.m3dm' },
];
const worker = process.argv[2] || path.join(scientific, 'builds', 'math3d-native-worker', 'Release', 'math3d-cgal-worker.exe');
const sha256 = data => createHash('sha256').update(data).digest('hex');

async function latestBaseline(datasetId) {
  let found;
  for (const entry of await readdir(runs, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const file = path.join(runs, entry.name, 'results.json');
    try {
      const result = JSON.parse(await readFile(file, 'utf8'));
      if (result.recipeId !== 'cgal.validate' || result.state !== 'succeeded' ||
          (process.argv[4] && result.profileId !== process.argv[4]) ||
          !result.inputArtifacts?.some(item => item.datasetId === datasetId)) continue;
      const modified = (await stat(file)).mtimeMs;
      if (!found || modified > found.modified) found = { result, modified, file };
    } catch (error) {
      if (error.code !== 'ENOENT' && !(error instanceof SyntaxError)) throw error;
    }
  }
  if (!found) throw new Error(`No successful DevShell validation for ${datasetId} was found`);
  return found;
}

function parseObj(source, fixture) {
  const vertices = [];
  const faces = [];
  for (const line of source.split(/\r?\n/)) {
    const parts = line.trim().split(/\s+/);
    if (parts[0] === 'v') {
      if (parts.length !== 4) throw new Error('Expected three coordinates per OBJ vertex');
      const vertex = parts.slice(1).map(Number);
      if (vertex.some(value => !Number.isFinite(value))) throw new Error('Non-finite OBJ vertex');
      vertices.push(vertex);
    } else if (parts[0] === 'f') {
      if (parts.length !== 4) throw new Error('Only triangular OBJ faces are supported');
      const face = parts.slice(1).map(token => Number(token.split('/')[0]) - 1);
      if (face.some(index => !Number.isInteger(index) || index < 0 || index >= vertices.length))
        throw new Error('Invalid OBJ face index');
      faces.push(face);
    }
  }
  if (vertices.length !== fixture.vertices || faces.length !== fixture.faces)
    throw new Error(`Expected the registered ${fixture.name} fixture`);
  return { vertices, faces };
}

function encodeMesh({ vertices, faces }) {
  const output = Buffer.alloc(32 + vertices.length * 12 + faces.length * 12);
  output.write('M3DM', 0, 'ascii');
  output.writeUInt16LE(1, 4);
  output.writeUInt16LE(32, 6);
  output.writeUInt32LE(vertices.length, 8);
  output.writeUInt32LE(faces.length, 12);
  output.writeUInt32LE(vertices.length * 12, 16);
  output.writeUInt32LE(faces.length * 12, 20);
  output.writeUInt32LE(output.length, 24);
  vertices.forEach((vertex, index) => vertex.forEach((value, axis) => output.writeFloatLE(value, 32 + index * 12 + axis * 4)));
  const faceOffset = 32 + vertices.length * 12;
  faces.forEach((face, index) => face.forEach((value, corner) => output.writeUInt32LE(value, faceOffset + index * 12 + corner * 4)));
  return output;
}

function decodeMesh(data) {
  if (data.length < 32 || data.toString('ascii', 0, 4) !== 'M3DM' ||
      data.readUInt16LE(4) !== 1 || data.readUInt16LE(6) !== 32 ||
      data.readUInt32LE(24) !== data.length || data.readUInt32LE(28) !== 0)
    throw new Error('Invalid MATH3D output mesh header');
  const vertexCount = data.readUInt32LE(8);
  const faceCount = data.readUInt32LE(12);
  if (data.readUInt32LE(16) !== vertexCount * 12 || data.readUInt32LE(20) !== faceCount * 12 ||
      data.length !== 32 + (vertexCount + faceCount) * 12)
    throw new Error('Invalid MATH3D output mesh length');
  const vertices = Array.from({ length: vertexCount }, (_, index) =>
    Array.from({ length: 3 }, (_, axis) => data.readFloatLE(32 + index * 12 + axis * 4)));
  const offset = 32 + vertexCount * 12;
  const faces = Array.from({ length: faceCount }, (_, index) =>
    Array.from({ length: 3 }, (_, corner) => data.readUInt32LE(offset + index * 12 + corner * 4)));
  if (vertices.some(vertex => vertex.some(value => !Number.isFinite(value))) ||
      faces.some(face => face.some(index => index >= vertexCount)))
    throw new Error('Invalid MATH3D output mesh payload');
  return { vertices, faces };
}

function meshStats(mesh) {
  const edges = new Map();
  const neighbors = Array.from({ length: mesh.vertices.length }, () => new Set());
  let signedVolume = 0, area = 0;
  for (const [a, b, c] of mesh.faces) {
    const p = mesh.vertices[a], q = mesh.vertices[b], r = mesh.vertices[c];
    const cross = [(q[1] - p[1]) * (r[2] - p[2]) - (q[2] - p[2]) * (r[1] - p[1]),
      (q[2] - p[2]) * (r[0] - p[0]) - (q[0] - p[0]) * (r[2] - p[2]),
      (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])];
    area += Math.hypot(...cross) / 2;
    signedVolume += (p[0] * (q[1] * r[2] - q[2] * r[1]) +
      p[1] * (q[2] * r[0] - q[0] * r[2]) + p[2] * (q[0] * r[1] - q[1] * r[0])) / 6;
    for (const [u, v] of [[a, b], [b, c], [c, a]]) {
      const key = `${Math.min(u, v)}:${Math.max(u, v)}`;
      const edge = edges.get(key) || { count: 0, direction: 0 };
      edge.count += 1;
      edge.direction += u < v ? 1 : -1;
      edges.set(key, edge);
      neighbors[u].add(v); neighbors[v].add(u);
    }
  }
  const boundaryEdges = [...edges.values()].filter(edge => edge.count === 1).length;
  const nonManifoldEdges = [...edges.values()].filter(edge => edge.count > 2).length;
  const orientationConflicts = [...edges.values()].filter(edge => edge.count === 2 && edge.direction !== 0).length;
  const used = new Set(mesh.faces.flat());
  const visited = new Set();
  let components = 0;
  for (const vertex of used) {
    if (visited.has(vertex)) continue;
    components += 1;
    const pending = [vertex]; visited.add(vertex);
    while (pending.length) for (const adjacent of neighbors[pending.pop()])
      if (!visited.has(adjacent)) { visited.add(adjacent); pending.push(adjacent); }
  }
  const bounds = [0, 1, 2].flatMap(axis => [Math.min(...mesh.vertices.map(vertex => vertex[axis])),
    Math.max(...mesh.vertices.map(vertex => vertex[axis]))]);
  return { vertices: mesh.vertices.length, edges: edges.size, faces: mesh.faces.length,
    boundaryEdges, nonManifoldEdges, orientationConflicts, components,
    euler: used.size - edges.size + mesh.faces.length,
    closed: boundaryEdges === 0 && nonManifoldEdges === 0 && orientationConflicts === 0 && mesh.faces.length > 0,
    bounds, area, volume: Math.abs(signedVolume) };
}

const dot = (a, b) => a.reduce((sum, value, index) => sum + value * b[index], 0);
const sub = (a, b) => a.map((value, index) => value - b[index]);
const distanceToSegment = (point, a, b) => {
  const ab = sub(b, a), lengthSquared = dot(ab, ab);
  const t = lengthSquared ? Math.max(0, Math.min(1, dot(sub(point, a), ab) / lengthSquared)) : 0;
  return Math.hypot(...sub(point, a.map((value, index) => value + t * ab[index])));
};

function distanceToTriangle(point, a, b, c) {
  const ab = sub(b, a), ac = sub(c, a), ap = sub(point, a);
  const normal = [ab[1] * ac[2] - ab[2] * ac[1], ab[2] * ac[0] - ab[0] * ac[2], ab[0] * ac[1] - ab[1] * ac[0]];
  const normalSquared = dot(normal, normal);
  const d00 = dot(ab, ab), d01 = dot(ab, ac), d11 = dot(ac, ac);
  const d20 = dot(ap, ab), d21 = dot(ap, ac), denominator = d00 * d11 - d01 * d01;
  if (normalSquared > 0 && denominator > 0) {
    const v = (d11 * d20 - d01 * d21) / denominator;
    const w = (d00 * d21 - d01 * d20) / denominator;
    if (v >= -1e-12 && w >= -1e-12 && v + w <= 1 + 1e-12)
      return Math.abs(dot(ap, normal)) / Math.sqrt(normalSquared);
  }
  return Math.min(distanceToSegment(point, a, b), distanceToSegment(point, b, c), distanceToSegment(point, c, a));
}

function surfaceSamples(mesh) {
  const samples = [...mesh.vertices];
  const edges = new Set();
  for (const face of mesh.faces) {
    const points = face.map(index => mesh.vertices[index]);
    samples.push([0, 1, 2].map(axis => points.reduce((sum, point) => sum + point[axis], 0) / 3));
    for (const [a, b] of [[0, 1], [1, 2], [2, 0]]) {
      const key = `${Math.min(face[a], face[b])}:${Math.max(face[a], face[b])}`;
      if (edges.has(key)) continue;
      edges.add(key);
      samples.push(points[a].map((value, axis) => (value + points[b][axis]) / 2));
    }
  }
  return samples;
}

function directedSurfaceDeviation(source, target) {
  return Math.max(...surfaceSamples(source).map(point => Math.min(...target.faces.map(face =>
    distanceToTriangle(point, ...face.map(index => target.vertices[index]))))));
}

function numericComparison(input, output, before, after) {
  if (!output || !after) return null;
  const scale = Math.max(1, before.bounds[1] - before.bounds[0], before.bounds[3] - before.bounds[2], before.bounds[5] - before.bounds[4]);
  return {
    metrics: {
      boundsDelta: Math.max(...before.bounds.map((value, index) => Math.abs(value - after.bounds[index]))),
      areaDelta: Math.abs(before.area - after.area), volumeDelta: Math.abs(before.volume - after.volume),
      sampledSurfaceDeviation: Math.max(directedSurfaceDeviation(input, output), directedSurfaceDeviation(output, input)),
      triangleCountDelta: after.faces - before.faces,
    },
    tolerances: { bounds: 1e-5 * scale, area: 1e-5 * scale ** 2,
      volume: 1e-5 * scale ** 3, sampledSurface: 1e-5 * scale },
  };
}

function makeRequest(jobId, leftMesh, rightMesh, operation) {
  const job = Buffer.from(jobId, 'utf8');
  const header = Buffer.alloc(28);
  header.write('M3DC', 0, 'ascii');
  header.writeUInt16LE(1, 4);
  header.writeUInt16LE(3, 6);
  header.writeUInt32LE(job.length, 8);
  header.writeUInt32LE(leftMesh.length, 12);
  header.writeUInt32LE(rightMesh.length, 16);
  header.writeUInt32LE(operation, 20);
  return Buffer.concat([header, job, leftMesh, rightMesh]);
}

async function runWorker(jobId, leftMesh, rightMesh, libraryBin, operation) {
  const env = { ...process.env };
  const pathKey = Object.keys(env).find(key => key.toLowerCase() === 'path') || 'Path';
  env[pathKey] = `${libraryBin};${env[pathKey] || ''}`;
  const started = Date.now();
  const response = await new Promise((resolve, reject) => {
    const child = spawn(worker, [], { env, windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'] });
    const stdout = [], stderr = [];
    let bytes = 0;
    const timer = setTimeout(() => child.kill(), 30000);
    child.stdout.on('data', chunk => {
      bytes += chunk.length;
      if (bytes > 16 * 1024 * 1024) child.kill();
      else stdout.push(chunk);
    });
    child.stderr.on('data', chunk => stderr.push(chunk));
    child.stdin.on('error', () => {});
    child.on('error', reject);
    child.on('close', code => {
      clearTimeout(timer);
      if (code !== 0) reject(new Error(`MATH3D worker exited ${code}: ${Buffer.concat(stderr).toString('utf8')}`));
      else resolve(Buffer.concat(stdout));
    });
    child.stdin.end(makeRequest(jobId, leftMesh, rightMesh, operation));
  });
  if (response.length < 28 || response.toString('ascii', 0, 4) !== 'M3DC' ||
      response.readUInt16LE(4) !== 1 || response.readUInt32LE(20) !== 3 || response.readUInt32LE(24) !== 0)
    throw new Error('Invalid MATH3D worker response header');
  const jobBytes = response.readUInt32LE(8);
  const meshBytes = response.readUInt32LE(12);
  const messageBytes = response.readUInt32LE(16);
  if (response.length !== 28 + jobBytes + meshBytes + messageBytes ||
      response.toString('utf8', 28, 28 + jobBytes) !== jobId)
    throw new Error('Invalid MATH3D worker response length or job ID');
  return { status: response.readUInt16LE(6),
    mesh: response.subarray(28 + jobBytes, 28 + jobBytes + meshBytes),
    message: response.toString('utf8', 28 + jobBytes + meshBytes),
    durationMs: Date.now() - started };
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
  const rightMesh = fixture.offsetX ? {
    vertices: inputMesh.vertices.map(vertex => [vertex[0] + fixture.offsetX, vertex[1], vertex[2]]),
    faces: inputMesh.faces,
  } : inputMesh;
  const minimumX = Math.min(...inputMesh.vertices.map(vertex => vertex[0]));
  const maximumX = Math.max(...inputMesh.vertices.map(vertex => vertex[0]));
  const operation = fixture.operation || 1;
  const targetMinimumX = operation === 3 ? minimumX + fixture.offsetX : minimumX;
  const targetMaximumX = operation === 2 ? minimumX + fixture.offsetX : operation === 1 ? maximumX + (fixture.offsetX || 0) : maximumX;
  const referenceMesh = fixture.offsetX ? {
    vertices: inputMesh.vertices.map(vertex => [vertex[0] === maximumX ? targetMaximumX : targetMinimumX, vertex[1], vertex[2]]),
    faces: inputMesh.faces,
  } : inputMesh;
  const leftBytes = encodeMesh(inputMesh), rightBytes = encodeMesh(rightMesh);
  const configure = baseline.result.steps?.find(step => step.stage === 'configure');
  if (!configure?.executable) throw new Error('Baseline does not identify the CGAL Library/bin environment');
  const response = await runWorker(`${jobId}-${fixture.name.toLowerCase().replaceAll(' ', '-')}`, leftBytes, rightBytes, path.dirname(configure.executable), operation);
  durationMs += response.durationMs;
  const outputMesh = response.status === 0 ? decodeMesh(response.mesh) : null;
  const before = meshStats(inputMesh), reference = meshStats(referenceMesh);
  const after = outputMesh ? meshStats(outputMesh) : null;
  const quantitative = numericComparison(referenceMesh, outputMesh, reference, after);
  const expected = baseline.result.after;
  const caseChecks = [
    { name: 'CGAL baseline matches registered input', passed: ['vertices', 'edges', 'faces', 'boundaryEdges', 'closed'].every(key => before[key] === expected?.[key]) && baseline.result.diagnostics?.length === 0,
      expected, actual: before },
    { name: fixture.offsetX ? `native overlapping-cubes ${operation === 2 ? 'difference' : operation === 3 ? 'intersection' : 'union'} accepted` : 'native Boolean self-union accepted', passed: response.status === 0 && !!outputMesh,
      expected: 'status 0 with M3DM output', actual: `status ${response.status}: ${response.message}` },
    { name: 'closed single-shell topology', passed: !!after && after.closed && after.components === 1 && after.euler === 2 && after.volume > 0,
      expected: { closed: true, components: 1, euler: 2, positiveVolume: true }, actual: after },
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
    rightOperand: { sourceDatasetId: fixture.datasetId, translateX: fixture.offsetX || 0,
      encodedSha256: sha256(rightBytes), bounds: meshStats(rightMesh).bounds } });
}
const passed = checks.filter(check => check.passed).length;
const succeeded = passed === checks.length;
const scope = `MATH3D native Boolean comparison: tetrahedron and cube self-unions plus overlapping-cube union, intersection, and difference; ${passed}/${checks.length} checks passed. The second cube is translated +1 X. Analytic volumes: union 12, intersection 4, difference A-B 4; X bounds [-1,2], [0,1], and [-1,0] respectively. Sampled surface deviation is not a full Hausdorff proof.`;
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
await writeFile(path.join(runDir, 'full.log'), `${scope}\n${checks.map(check => `${check.passed ? 'PASS' : 'FAIL'} ${check.name}: ${JSON.stringify(check.actual)}`).join('\n')}\n`);
console.log(`${succeeded ? 'PASS' : 'FAIL'} ${passed}/${checks.length}: ${scope}`);
console.log(`Saved ${path.join(runDir, 'results.json')}`);
if (!succeeded) process.exitCode = 1;
