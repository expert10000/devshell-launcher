import { spawn } from 'node:child_process';
import { createHash, randomUUID } from 'node:crypto';
import { readFile, readdir, mkdir, stat, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const scientific = path.join(root, '.scientific');
const runs = path.join(scientific, 'runs');
const datasetId = 'math3d/basic/01_tetrahedron.obj';
const worker = process.argv[2] || path.join(scientific, 'builds', 'math3d-native-worker', 'Release', 'math3d-cgal-worker.exe');
const sha256 = data => createHash('sha256').update(data).digest('hex');

async function latestBaseline() {
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

function parseObj(source) {
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
  if (vertices.length !== 4 || faces.length !== 4) throw new Error('Expected the registered tetrahedron fixture');
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
  for (const [a, b, c] of mesh.faces) {
    for (const [u, v] of [[a, b], [b, c], [c, a]]) {
      const key = `${Math.min(u, v)}:${Math.max(u, v)}`;
      edges.set(key, (edges.get(key) || 0) + 1);
    }
  }
  const boundaryEdges = [...edges.values()].filter(count => count === 1).length;
  return { vertices: mesh.vertices.length, edges: edges.size, faces: mesh.faces.length,
    boundaryEdges, closed: boundaryEdges === 0 && mesh.faces.length > 0 };
}

function geometrySignature(mesh) {
  const vertexKey = vertex => vertex.map(value => value.toFixed(6)).join(',');
  return JSON.stringify(mesh.faces.map(face => face.map(index => vertexKey(mesh.vertices[index])).sort().join('|')).sort());
}

function makeRequest(jobId, mesh) {
  const job = Buffer.from(jobId, 'utf8');
  const header = Buffer.alloc(28);
  header.write('M3DC', 0, 'ascii');
  header.writeUInt16LE(1, 4);
  header.writeUInt16LE(3, 6);
  header.writeUInt32LE(job.length, 8);
  header.writeUInt32LE(mesh.length, 12);
  header.writeUInt32LE(mesh.length, 16);
  header.writeUInt32LE(1, 20); // union, not DevShell's validate operation
  return Buffer.concat([header, job, mesh, mesh]);
}

async function runWorker(jobId, mesh, libraryBin) {
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
    child.stdin.end(makeRequest(jobId, mesh));
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

const baseline = await latestBaseline();
const inputArtifact = baseline.result.inputArtifacts.find(item => item.datasetId === datasetId);
const inputPath = path.resolve(inputArtifact.path);
const datasetRoot = path.resolve(scientific, 'datasets');
const relative = path.relative(datasetRoot, inputPath);
if (relative.startsWith('..') || path.isAbsolute(relative)) throw new Error('Baseline input is outside registered local copies');
const source = await readFile(inputPath);
const inputHash = sha256(source);
if (inputHash !== inputArtifact.sha256) throw new Error('Registered tetrahedron SHA-256 has changed');
const inputMesh = parseObj(source.toString('utf8'));
const managedDirectory = process.argv[3] ? path.resolve(process.argv[3]) : '';
const jobId = managedDirectory ? path.basename(managedDirectory) : randomUUID().replaceAll('-', '');
const configure = baseline.result.steps?.find(step => step.stage === 'configure');
if (!configure?.executable) throw new Error('Baseline does not identify the CGAL Library/bin environment');
const libraryBin = path.dirname(configure.executable);
await stat(worker);
const response = await runWorker(jobId, encodeMesh(inputMesh), libraryBin);
const outputMesh = response.status === 0 ? decodeMesh(response.mesh) : null;
const inputStats = meshStats(inputMesh);
const outputStats = outputMesh ? meshStats(outputMesh) : null;
const expected = baseline.result.after;
const checks = [
  { name: 'registered input SHA-256', passed: inputHash === inputArtifact.sha256,
    expected: inputArtifact.sha256, actual: inputHash },
  { name: 'native Boolean self-union accepted', passed: response.status === 0 && !!outputMesh,
    expected: 'status 0 with M3DM output', actual: `status ${response.status}: ${response.message}` },
  { name: 'mesh geometry and counts', passed: !!outputMesh &&
      ['vertices', 'edges', 'faces', 'boundaryEdges', 'closed'].every(key => outputStats[key] === expected[key]) &&
      geometrySignature(outputMesh) === geometrySignature(inputMesh),
    expected: expected, actual: outputStats },
  { name: 'clean diagnostics', passed: response.status === 0 && baseline.result.diagnostics?.length === 0,
    expected: 'DevShell validation: none; MATH3D Boolean: status 0',
    actual: `DevShell: ${baseline.result.diagnostics?.length ?? 'unknown'}; MATH3D: ${response.message}` },
];
const passed = checks.filter(check => check.passed).length;
const succeeded = passed === checks.length;
const runDir = managedDirectory || path.join(runs, jobId);
await mkdir(runDir, { recursive: true });
const outputName = 'math3d-native-self-union.m3dm';
if (outputMesh) await writeFile(path.join(runDir, outputName), response.mesh);
const scope = `MATH3D native binary-protocol Boolean self-union versus DevShell JSON-contract tetrahedron validation: ${passed}/${checks.length} checks passed. Operations differ; this is an integration smoke test, not equivalent validation.`;
const result = {
  schemaVersion: 1, runId: jobId, runtimeId: 'cgal-win-conda',
  recipeId: 'integration.math3d.native-boolean', operation: 'mesh.boolean.union',
  engine: 'MATH3D native CGAL worker', profileId: baseline.result.profileId,
  state: succeeded ? 'succeeded' : 'failed', exitCode: succeeded ? 0 : 1,
  durationMs: response.durationMs, versions: { cgal: baseline.result.versions?.cgal, math3dWorker: 'protocol 1' },
  validatedCapabilities: succeeded ? ['mesh.boolean'] : [],
  before: inputStats, after: outputStats,
  diagnostics: succeeded ? [] : checks.filter(check => !check.passed).map(check => ({ severity: 'error', message: check.name })),
  inputArtifacts: [{ ...inputArtifact, path: inputPath, sha256: inputHash }],
  artifacts: outputMesh ? [{ path: outputName, mediaType: 'application/octet-stream',
    bytes: response.mesh.length, sha256: sha256(response.mesh) }] : [],
  comparison: { verdict: succeeded ? 'pass' : 'fail', passed, total: checks.length,
    baselineRunId: baseline.result.runId, baselineResult: baseline.file,
    workerExecutable: worker, workerStatus: response.status, workerMessage: response.message, checks },
  scope, provenance: { inputPolicy: 'Registered local copy, SHA-256 checked',
    transport: 'MATH3D M3DC binary protocol; worker in separate process' },
  logReference: 'full.log',
};
await writeFile(path.join(runDir, 'results.json'), JSON.stringify(result, null, 2) + '\n');
await writeFile(path.join(runDir, 'full.log'), `${scope}\n${checks.map(check => `${check.passed ? 'PASS' : 'FAIL'} ${check.name}: ${JSON.stringify(check.actual)}`).join('\n')}\n`);
console.log(`${succeeded ? 'PASS' : 'FAIL'} ${passed}/${checks.length}: ${scope}`);
console.log(`Saved ${path.join(runDir, 'results.json')}`);
if (!succeeded) process.exitCode = 1;
