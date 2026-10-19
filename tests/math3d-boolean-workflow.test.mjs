import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { createHash, randomUUID } from 'node:crypto';
import { booleanParameters, executeBoolean } from '../tools/run-math3d-boolean.mjs';
import { parseObj, encodeMesh, decodeMesh } from '../tools/math3d-native-protocol.mjs';
import { meshStats } from '../tools/math3d-mesh-comparison.mjs';

const worker = process.env.DEVSHELL_BOOLEAN_WORKER;
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const cube = { vertices: [[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]],
  faces: [[0,2,1],[0,3,2],[4,5,6],[4,6,7],[0,1,5],[0,5,4],[1,2,6],[1,6,5],[2,3,7],[2,7,6],[3,0,4],[3,4,7]] };
const obj = cube.vertices.map(v => `v ${v.join(' ')}`).join('\n') + '\n' + cube.faces.map(f => `f ${f.map(i => i + 1).join(' ')}`).join('\n') + '\n';
const standard = { inputAId: 'cube.obj', inputBId: 'cube.obj', operation: 'union', outputName: 'result.m3dm', scaleB: 1, translateB: [1,0,0] };

test('operation, transforms, and output filenames reject malformed requests', () => {
  for (const patch of [{ operation: 'shell' }, { scaleB: 0 }, { scaleB: -1 }, { scaleB: true }, { scaleB: Infinity }, { translateB: [0,0] }, { translateB: [NaN,0,0] }, { translateB: [0,0,1000001] }, { outputName: '../result.m3dm' }, { outputName: 'operand-a.m3dm' }])
    assert.throws(() => booleanParameters({ ...standard, ...patch }));
  assert.equal(booleanParameters(standard).operation, 'union');
});
test('binary mesh conversion preserves geometry and rejects invalid values', () => {
  const mesh = parseObj(obj);
  assert.deepEqual(decodeMesh(encodeMesh(mesh)), cube);
  assert.throws(() => encodeMesh({ ...mesh, vertices: [[Infinity,0,0]] }));
  const corrupt = encodeMesh(mesh); corrupt.writeUInt32LE(9999, 32 + mesh.vertices.length * 12);
  assert.throws(() => decodeMesh(corrupt));
  const empty = decodeMesh(encodeMesh({ vertices: [], faces: [] }));
  assert.equal(meshStats(empty).faces, 0);
});

async function fixture(parameters = {}) {
  const root = await mkdtemp(path.join(tmpdir(), 'devshell-boolean-'));
  const directory = path.join(root, randomUUID().replaceAll('-', ''));
  const datasetRoot = path.join(root, 'datasets');
  await mkdir(directory); await mkdir(datasetRoot);
  const source = path.join(datasetRoot, 'cube.obj'); await writeFile(source, obj);
  const input = { path: source, datasetId: 'cube.obj', sha256: sha(obj), bytes: Buffer.byteLength(obj), mediaType: 'model/obj' };
  const request = { schemaVersion: 1, runId: path.basename(directory), profileId: 'test-profile', runtimeId: 'cgal-win-conda', recipeId: 'cgal.boolean',
    workingDirectory: directory, datasetRoot, parameters: { ...standard, ...parameters }, inputArtifacts: [{ ...input, role: 'A' }, { ...input, role: 'B' }],
    outputArtifacts: ['result.m3dm', 'result.obj', 'operand-a.m3dm', 'operand-b.m3dm'].map(name => ({ path: name })) };
  for (const role of ['a','b']) {
    const folder = path.join(directory, `validation-${role}`); await mkdir(folder); await writeFile(path.join(folder, 'operand.obj'), obj);
    await writeFile(path.join(folder, 'results.json'), JSON.stringify({ state: 'succeeded', recipeId: 'cgal.validate', after: { closed: true }, diagnostics: [], inputArtifacts: [input],
      artifacts: [{ path: 'operand.obj', bytes: Buffer.byteLength(obj), sha256: sha(obj) }] }));
  }
  const file = path.join(directory, 'request.json'); await writeFile(file, JSON.stringify(request));
  return { directory, source, file };
}
test('changed source inputs and changed validated operands stop execution', async () => {
  const changed = await fixture(); await writeFile(changed.source, obj + '# changed');
  await assert.rejects(() => executeBoolean(changed.file, 'not-started'), /input dataset changed/);
  const tampered = await fixture(); await writeFile(path.join(tampered.directory, 'validation-b', 'operand.obj'), obj + '# changed');
  await assert.rejects(() => executeBoolean(tampered.file, 'not-started'), /Validated mesh was modified/);
});
for (const [operation, translateB, scaleB, volume, components] of [
  ['union',[1,0,0],1,12,1], ['intersection',[1,0,0],1,4,1], ['difference',[1,0,0],1,4,1],
  ['difference',[0,0,0],0.5,7,2], ['intersection',[3,0,0],1,0,0],
]) test(`native workflow ${operation}, scale ${scaleB}, offset ${translateB}`, { skip: !worker }, async () => {
  const data = await fixture({ operation, translateB, scaleB });
  const result = await executeBoolean(data.file, worker);
  assert.equal(result.state, 'succeeded');
  assert.ok(Math.abs(result.after.volume - volume) < 1e-6);
  assert.equal(result.after.components, components);
  assert.equal(result.artifacts.length, volume ? 4 : 3);
  for (const artifact of result.artifacts) assert.equal(sha(await readFile(path.join(data.directory, artifact.path))), artifact.sha256);
  const retained = decodeMesh(await readFile(path.join(data.directory, 'operand-b.m3dm')));
  assert.deepEqual(retained.vertices[0], cube.vertices[0].map((value, axis) => value * scaleB + translateB[axis]));
  assert.equal(await readFile(data.source, 'utf8'), obj);
});
