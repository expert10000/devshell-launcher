import { readFile, writeFile, stat } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseObj, encodeMesh, decodeMesh, runWorker } from './math3d-native-protocol.mjs';
import { meshStats } from './math3d-mesh-comparison.mjs';

const hash = bytes => createHash('sha256').update(bytes).digest('hex');
export function booleanParameters(parameters) {
  if (!['union', 'intersection', 'difference'].includes(parameters.operation)) throw new Error('Choose Union, Intersection, or Difference A minus B.');
  if (typeof parameters.outputName !== 'string' || !/^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}\.m3dm$/.test(parameters.outputName)) throw new Error('Output must be a safe M3DM filename.');
  if (['operand-a.m3dm', 'operand-b.m3dm'].includes(parameters.outputName.toLowerCase())) throw new Error('Operand snapshot filenames are reserved.');
  const scale = parameters.scaleB;
  const translate = parameters.translateB;
  if (typeof scale !== 'number' || !Number.isFinite(scale) || scale < 0.000001 || scale > 1000) throw new Error('Mesh B scale must be between 0.000001 and 1000.');
  if (!Array.isArray(translate) || translate.length !== 3 || translate.some(value => typeof value !== 'number' || !Number.isFinite(value) || Math.abs(value) > 1000000)) throw new Error('Mesh B translation requires three finite coordinates within +/-1000000.');
  return { operation: parameters.operation, scaleB: scale, translateB: translate, outputName: parameters.outputName };
}

export async function executeBoolean(requestPath, worker) {
  if ((await stat(requestPath)).size > 65536) throw new Error('Boolean request exceeds 64 KiB.');
  const request = JSON.parse(await readFile(requestPath, 'utf8'));
  const directory = path.resolve(request.workingDirectory);
  if (directory !== path.dirname(path.resolve(requestPath)) || request.schemaVersion !== 1 || request.recipeId !== 'cgal.boolean' || request.runtimeId !== 'cgal-win-conda' || !/^[0-9a-f]{32}$/.test(request.runId)) throw new Error('Invalid managed Boolean request.');
  if (request.inputArtifacts?.length !== 2) throw new Error('Select exactly two registered input meshes.');
  const parameters = booleanParameters(request.parameters);
  const outputName = parameters.outputName;
  const objName = outputName.replace(/\.m3dm$/, '.obj');
  const expectedOutputs = [outputName, objName, 'operand-a.m3dm', 'operand-b.m3dm'];
  if (!expectedOutputs.every(name => request.outputArtifacts?.some(item => item.path === name))) throw new Error('Boolean outputs are not registered in the request.');
  const meshes = [], validations = [];
  for (const [index, input] of request.inputArtifacts.entries()) {
    const source = path.resolve(input.path);
    const relative = path.relative(path.resolve(request.datasetRoot), source);
    if (!relative || relative.startsWith('..') || path.isAbsolute(relative) || (await stat(source)).size > 33554432) throw new Error('Input must be a bounded registered dataset copy.');
    if (hash(await readFile(source)) !== input.sha256) throw new Error('An input dataset changed during validation. Run again with the current copy.');
    const folder = `validation-${index === 0 ? 'a' : 'b'}`;
    const validation = JSON.parse(await readFile(path.join(directory, folder, 'results.json'), 'utf8'));
    const record = validation.artifacts?.find(item => item.path === 'operand.obj');
    if (validation.state !== 'succeeded' || validation.recipeId !== 'cgal.validate' || validation.after?.closed !== true || validation.diagnostics?.length !== 0 || !record) throw new Error(`Mesh ${index === 0 ? 'A' : 'B'} must pass CGAL validation and be closed.`);
    const validatedInput = validation.inputArtifacts?.[0];
    if (validatedInput?.sha256 !== input.sha256 || validatedInput?.datasetId !== input.datasetId) throw new Error('Validation belongs to a different input mesh.');
    const file = path.join(directory, folder, 'operand.obj');
    if ((await stat(file)).size > 33554432) throw new Error('Validated operand exceeds 32 MiB.');
    const bytes = await readFile(file);
    if (hash(bytes) !== record.sha256 || bytes.length !== record.bytes) throw new Error('Validated mesh was modified.');
    let mesh = parseObj(bytes.toString('utf8'));
    if (mesh.faces.length > 100000) throw new Error('Boolean operands are limited to 100000 triangles each.');
    if (index === 1) mesh = { ...mesh, vertices: mesh.vertices.map(vertex => vertex.map((value, axis) => value * parameters.scaleB + parameters.translateB[axis])) };
    // The stored snapshot is exactly the float32 mesh consumed by the native worker.
    mesh = decodeMesh(encodeMesh(mesh));
    const statistics = meshStats(mesh);
    if (!statistics.closed || statistics.signedVolume <= 0) throw new Error(`Mesh ${index === 0 ? 'A' : 'B'} must be a closed, consistently oriented solid with positive signed volume.`);
    meshes.push(mesh);
    validations.push({ role: index === 0 ? 'A' : 'B', resultReference: `${folder}/results.json`, datasetId: input.datasetId, sha256: input.sha256, statistics });
  }
  const left = encodeMesh(meshes[0]), right = encodeMesh(meshes[1]);
  const operation = { union: 1, difference: 2, intersection: 3 }[parameters.operation];
  console.log(`Running ${parameters.operation}: A ${meshes[0].faces.length} triangles, B ${meshes[1].faces.length} triangles.`);
  const response = await runWorker(worker, request.runId, left, right, path.join(process.env.CMAKE_PREFIX_PATH || '', 'bin'), operation);
  if (response.status !== 0) throw new Error(`Native Boolean rejected the inputs: ${response.message}`);
  const output = decodeMesh(response.mesh);
  if (output.faces.length > 200000) throw new Error('Boolean output exceeds the 200000-triangle laboratory limit.');
  const after = meshStats(output);
  if (output.faces.length > 0 && (!after.closed || after.signedVolume <= 0)) throw new Error('Native output is not a closed, consistently oriented solid.');
  const artifacts = [];
  async function save(name, bytes, role) {
    const file = path.join(directory, name);
    try { await stat(file); throw new Error('Boolean output already exists.'); } catch (error) { if (error.code !== 'ENOENT') throw error; }
    await writeFile(file, bytes, { flag: 'wx' });
    artifacts.push({ path: name, role, mediaType: name.endsWith('.obj') ? 'model/obj' : 'application/octet-stream', bytes: Buffer.byteLength(bytes), sha256: hash(bytes) });
  }
  await save(outputName, response.mesh, 'result');
  if (output.faces.length) await save(objName, '# DevShell native Boolean result\n' + output.vertices.map(vertex => `v ${vertex.join(' ')}`).join('\n') + '\n' + output.faces.map(face => `f ${face.map(index => index + 1).join(' ')}`).join('\n') + '\n', 'result');
  await save('operand-a.m3dm', left, 'operand');
  await save('operand-b.m3dm', right, 'operand');
  const result = {
    schemaVersion: 1, runId: request.runId, profileId: request.profileId, runtimeId: request.runtimeId, recipeId: request.recipeId,
    state: 'succeeded', exitCode: 0, operation: 'cgal.boolean', durationMs: response.durationMs,
    versions: { math3dWorker: 'protocol 1' }, engine: 'MATH3D native CGAL worker', validatedCapabilities: ['mesh.boolean'],
    before: validations[0].statistics, after, diagnostics: [], inputArtifacts: request.inputArtifacts, artifacts,
    boolean: { operation: parameters.operation, scaleB: parameters.scaleB, translateB: parameters.translateB, empty: output.faces.length === 0,
      operands: validations, snapshots: { a: 'operand-a.m3dm', b: 'operand-b.m3dm' }, outputArtifact: outputName },
    scope: 'CGAL validation of both registered inputs followed by native Boolean computation on retained float32 snapshots. Clipping and transparency affect display only. Empty results have an M3DM artifact; OBJ export is available for nonempty results.',
    logReference: 'full.log', provenance: request.provenance,
  };
  await writeFile(path.join(directory, 'results.json'), JSON.stringify(result, null, 2) + '\n');
  console.log(`Succeeded: ${output.faces.length} triangles, volume ${after.volume}${result.boolean.empty ? ' (empty result)' : ''}.`);
  return result;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try { await executeBoolean(process.argv[2], process.argv[3]); }
  catch (error) {
    console.error(error.message);
    try {
      const requestPath = path.resolve(process.argv[2]);
      const request = JSON.parse(await readFile(requestPath, 'utf8'));
      if (path.resolve(request.workingDirectory) === path.dirname(requestPath))
        await writeFile(path.join(path.dirname(requestPath), 'results.json'), JSON.stringify({ schemaVersion: 1, runId: request.runId, profileId: request.profileId,
          runtimeId: request.runtimeId, recipeId: 'cgal.boolean', state: 'failed', artifacts: [], validatedCapabilities: [], diagnostics: [{ severity: 'error', message: error.message }] }));
    } catch { /* The managed runner also records invocation failures. */ }
    process.exitCode = 1;
  }
}
