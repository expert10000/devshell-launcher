import { spawn } from 'node:child_process';

export function parseObj(source, fixture) {
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
  if (fixture && (vertices.length !== fixture.vertices || faces.length !== fixture.faces))
    throw new Error(`Expected the registered ${fixture.name} fixture`);
  return { vertices, faces };
}

export function encodeMesh({ vertices, faces }) {
  if (vertices.some(vertex => vertex.length !== 3 || vertex.some(value => !Number.isFinite(Math.fround(value))))) throw new Error('Mesh coordinates exceed finite float32 range.');
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

export function decodeMesh(data) {
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

export function makeRequest(jobId, leftMesh, rightMesh, operation) {
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

export async function runWorker(worker, jobId, leftMesh, rightMesh, libraryBin, operation) {
  const env = { ...process.env };
  const pathKey = Object.keys(env).find(key => key.toLowerCase() === 'path') || 'Path';
  env[pathKey] = `${libraryBin};${env[pathKey] || ''}`;
  const started = Date.now();
  const response = await new Promise((resolve, reject) => {
    const child = spawn(worker, [], { env, windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'] });
    const stdout = [], stderr = [];
    let bytes = 0, stderrBytes = 0, timedOut = false, overflow = false;
    const timer = setTimeout(() => { timedOut = true; child.kill(); }, 30000);
    child.stdout.on('data', chunk => {
      bytes += chunk.length;
      if (bytes > 64 * 1024 * 1024) { overflow = true; child.kill(); }
      else stdout.push(chunk);
    });
    child.stderr.on('data', chunk => { if (stderrBytes < 65536) stderr.push(chunk.subarray(0, 65536 - stderrBytes)); stderrBytes += chunk.length; });
    child.stdin.on('error', () => {});
    child.on('error', reject);
    child.on('close', code => {
      clearTimeout(timer);
      if (timedOut) reject(new Error('Native Boolean worker exceeded 30 seconds.'));
      else if (overflow) reject(new Error('Native Boolean output exceeds 64 MiB.'));
      else if (code !== 0) reject(new Error(`MATH3D worker exited ${code}: ${Buffer.concat(stderr).toString('utf8')}`));
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
