import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { createHash, randomUUID } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { booleanParameters, executeBoolean } from '../tools/run-math3d-boolean.mjs';
import { parseObj, encodeMesh, decodeMesh } from '../tools/math3d-native-protocol.mjs';
import { meshStats } from '../tools/math3d-mesh-comparison.mjs';

const worker = process.env.DEVSHELL_BOOLEAN_WORKER;
const gmshPython = process.env.DEVSHELL_SCIENTIFIC_PYTHON;
const vtkPython = process.env.DEVSHELL_VTK_PYTHON;
const math3dRoot = process.env.DEVSHELL_MATH3D_ROOT;
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const cube = { vertices: [[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]],
  faces: [[0,2,1],[0,3,2],[4,5,6],[4,6,7],[0,1,5],[0,5,4],[1,2,6],[1,6,5],[2,3,7],[2,7,6],[3,0,4],[3,4,7]] };
const obj = cube.vertices.map(v => `v ${v.join(' ')}`).join('\n') + '\n' + cube.faces.map(f => `f ${f.map(i => i + 1).join(' ')}`).join('\n') + '\n';
const smallerObj = cube.vertices.map(v => `v ${v.map(n => n / 2).join(' ')}`).join('\n') + '\n' + cube.faces.map(f => `f ${f.map(i => i + 1).join(' ')}`).join('\n') + '\n';
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

async function fixture(parameters = {}, secondObj = obj) {
  const root = await mkdtemp(path.join(tmpdir(), 'devshell-boolean-'));
  const directory = path.join(root, randomUUID().replaceAll('-', ''));
  const datasetRoot = path.join(root, 'datasets');
  await mkdir(directory); await mkdir(datasetRoot);
  const source = path.join(datasetRoot, 'cube.obj'); await writeFile(source, obj);
  const input = { path: source, datasetId: 'cube.obj', sha256: sha(obj), bytes: Buffer.byteLength(obj), mediaType: 'model/obj' };
  const secondSource = secondObj === obj ? source : path.join(datasetRoot, 'cube-small.obj');
  if (secondSource !== source) await writeFile(secondSource, secondObj);
  const secondInput = { path: secondSource, datasetId: path.basename(secondSource), sha256: sha(secondObj), bytes: Buffer.byteLength(secondObj), mediaType: 'model/obj' };
  const request = { schemaVersion: 1, runId: path.basename(directory), profileId: 'test-profile', runtimeId: 'cgal-win-conda', recipeId: 'cgal.boolean',
    workingDirectory: directory, datasetRoot, parameters: { ...standard, ...parameters }, inputArtifacts: [{ ...input, role: 'A' }, { ...secondInput, role: 'B' }],
    outputArtifacts: ['result.m3dm', 'result.obj', 'operand-a.m3dm', 'operand-b.m3dm'].map(name => ({ path: name })) };
  for (const role of ['a','b']) {
    const folder = path.join(directory, `validation-${role}`); await mkdir(folder);
    const sourceMesh = role === 'a' ? obj : secondObj; const sourceInput = role === 'a' ? input : secondInput;
    await writeFile(path.join(folder, 'operand.obj'), sourceMesh);
    await writeFile(path.join(folder, 'results.json'), JSON.stringify({ state: 'succeeded', recipeId: 'cgal.validate', after: { closed: true }, diagnostics: [], inputArtifacts: [sourceInput],
      artifacts: [{ path: 'operand.obj', bytes: Buffer.byteLength(sourceMesh), sha256: sha(sourceMesh) }] }));
  }
  const file = path.join(directory, 'request.json'); await writeFile(file, JSON.stringify(request));
  return { directory, source, file };
}
test('native Boolean accepts two different registered source hashes and retains both', { skip: !worker }, async () => {
  const data = await fixture({ operation: 'difference', translateB: [0,0,0], scaleB: 1 }, smallerObj);
  const result = await executeBoolean(data.file, worker);
  assert.notEqual(result.inputArtifacts[0].sha256, result.inputArtifacts[1].sha256);
  assert.equal(result.boolean.operands[0].sha256, result.inputArtifacts[0].sha256);
  assert.equal(result.boolean.operands[1].sha256, result.inputArtifacts[1].sha256);
  assert.ok(Math.abs(result.after.volume - 7) < 1e-6);
  assert.equal(result.after.closed, true);
  assert.equal(result.after.components, 2);
  for (const item of result.artifacts) assert.equal(sha(await readFile(path.join(data.directory, item.path))), item.sha256);
});
test('distinct-input native Boolean result enters bounded Gmsh volume bridge', { skip: !worker || !gmshPython }, async () => {
  const data = await fixture({ operation: 'union', translateB: [1,0,0], scaleB: 1 }, smallerObj);
  const boolean = await executeBoolean(data.file, worker);
  assert.notEqual(boolean.inputArtifacts[0].sha256, boolean.inputArtifacts[1].sha256);
  const surface = path.join(data.directory, 'result.obj');
  const artifact = boolean.artifacts.find(item => item.path === 'result.obj');
  assert.equal(sha(await readFile(surface)), artifact.sha256);
  const gmshDirectory = path.join(data.directory, 'gmsh'); await mkdir(gmshDirectory);
  const gmshRequest = path.join(gmshDirectory, 'request.json');
  await writeFile(gmshRequest, JSON.stringify({ schemaVersion: 1, operation: 'gmsh.mesh',
    runId: randomUUID().replaceAll('-', ''), sourceRunId: boolean.runId, sourceCommit: 'a'.repeat(40),
    sourceSnapshotSha256: 'b'.repeat(64), inputId: 'boolean-surface', workingDirectory: gmshDirectory,
    artifactRoot: data.directory, lengthUnit: 'mm', frame: 'world', meshSize: 0.5,
    inputArtifact: { path: surface, sha256: artifact.sha256, bytes: artifact.bytes } }));
  const gmsh = JSON.parse(execFileSync(gmshPython, ['tools/scientific-gmsh-boolean-volume.py', '--request', gmshRequest],
    { cwd: path.resolve('.'), encoding: 'utf8', timeout: 120000 }));
  assert.equal(gmsh.inputHashes['boolean-surface'], artifact.sha256);
  assert.equal(gmsh.dimension, 3);
  assert.ok(gmsh.tetrahedra > 0);
  assert.ok(Math.abs(gmsh.tetrahedralVolume - boolean.after.volume) < 0.02 * boolean.after.volume);
  if (vtkPython) {
    const boundaryDirectory = path.join(data.directory, 'boundary'); await mkdir(boundaryDirectory);
    const boundaryRequest = path.join(boundaryDirectory, 'request.json');
    const msh = path.join(gmshDirectory, 'volume.msh');
    await writeFile(boundaryRequest, JSON.stringify({ schemaVersion: 1, operation: 'gmsh.extract-boundary',
      runId: randomUUID().replaceAll('-', ''), sourceRunId: gmsh.runId, sourceCommit: 'a'.repeat(40),
      sourceSnapshotSha256: 'b'.repeat(64), inputId: 'gmsh-mesh', workingDirectory: boundaryDirectory,
      artifactRoot: data.directory, lengthUnit: 'mm', frame: 'world',
      inputArtifact: { path: msh, sha256: gmsh.output.sha256, bytes: gmsh.output.bytes } }));
    const boundary = JSON.parse(execFileSync(gmshPython, ['tools/scientific-gmsh-boundary-extract.py', '--request', boundaryRequest],
      { cwd: path.resolve('.'), encoding: 'utf8', timeout: 120000 }));
    assert.equal(boundary.inputHashes['gmsh-mesh'], gmsh.output.sha256);
    const vtkDirectory = path.join(data.directory, 'vtk'); await mkdir(vtkDirectory);
    const vtp = path.join(vtkDirectory, 'analysis.vtp');
    const boundaryObj = path.join(boundaryDirectory, 'boundary.obj');
    const vtkRequest = path.join(vtkDirectory, 'request.json');
    await writeFile(vtkRequest, JSON.stringify({ schemaVersion: 1, operation: 'mesh.inspect',
      runId: randomUUID().replaceAll('-', ''), sourceRunId: boundary.runId,
      sourceCommit: 'a'.repeat(40), sourceSnapshotSha256: 'b'.repeat(64),
      inputId: 'gmsh-boundary', workingDirectory: vtkDirectory, artifactRoot: data.directory,
      lengthUnit: 'mm', frame: 'world', inputArtifact: {
        path: boundaryObj, sha256: boundary.output.sha256, bytes: boundary.output.bytes } }));
    const inspected = JSON.parse(execFileSync(vtkPython,
      ['tools/scientific-vtk-boundary-inspect.py', '--request', vtkRequest],
      { cwd: path.resolve('.'), encoding: 'utf8', timeout: 120000 }));
    assert.ok(inspected.triangles > 12);
    assert.equal(inspected.inputHashes['gmsh-boundary'], boundary.output.sha256);
    assert.ok(Math.abs(inspected.enclosedVolume - boolean.after.volume) < 0.02 * boolean.after.volume);
    const previewBytes = await readFile(path.join(vtkDirectory, 'preview.png'));
    assert.equal(sha(previewBytes), inspected.preview.sha256);
    assert.equal(previewBytes.readUInt32BE(16), 640);
    assert.equal(previewBytes.readUInt32BE(20), 480);
    const scipyDirectory = path.join(data.directory, 'scipy'); await mkdir(scipyDirectory);
    const scipyRequest = path.join(scipyDirectory, 'request.json');
    const vtkBytes = await readFile(vtp);
    await writeFile(scipyRequest, JSON.stringify({ schemaVersion: 1, operation: 'scipy.measure',
      runId: randomUUID().replaceAll('-', ''), sourceRunId: boundary.runId, sourceCommit: 'a'.repeat(40),
      sourceSnapshotSha256: 'b'.repeat(64), inputId: 'vtk-analysis', workingDirectory: scipyDirectory,
      artifactRoot: data.directory, lengthUnit: 'mm', frame: 'world',
      inputArtifact: { path: vtp, sha256: sha(vtkBytes), bytes: vtkBytes.length } }));
    const measured = JSON.parse(execFileSync(gmshPython, ['tools/scientific-scipy-surface-measure.py', '--request', scipyRequest],
      { cwd: path.resolve('.'), encoding: 'utf8', timeout: 120000 }));
    assert.equal(measured.inputHashes['vtk-analysis'], sha(vtkBytes));
    assert.equal(measured.measurement.unit, 'mm2');
    assert.ok(Math.abs(measured.measurement.value - inspected.surfaceArea) <= measured.measurement.tolerance);
    if (math3dRoot) {
      const converted = path.join(data.directory, 'converted.obj');
      const conversion = JSON.parse(execFileSync(vtkPython,
        ['tools/scientific-workbench-math3d-convert.py', '--source', vtp,
          '--expected-sha', sha(vtkBytes), '--output', converted],
        { cwd: path.resolve('.'), encoding: 'utf8', timeout: 120000 }));
      const measurementPath = path.join(scipyDirectory, 'measurement.json');
      const measurementBytes = await readFile(measurementPath);
      const consumerCommit = execFileSync('git', ['-C', math3dRoot, 'rev-parse', 'HEAD'], { encoding: 'utf8' }).trim();
      const provenance = { schemaVersion: 1, kind: 'scientific.typed-journey',
        sourceCommit: 'a'.repeat(40), sourceSnapshotSha256: 'b'.repeat(64),
        math3dCommit: consumerCommit, convertedObjSha256: conversion.objSha256,
        vtkArtifactSha256: sha(vtkBytes), measurementSha256: sha(measurementBytes),
        booleanSourceASha256: boolean.inputArtifacts[0].sha256,
        booleanSourceBSha256: boolean.inputArtifacts[1].sha256,
        booleanSurfaceSha256: artifact.sha256, gmshMeshSha256: gmsh.output.sha256,
        gmshBoundarySha256: boundary.output.sha256,
        lengthUnit: 'mm', frame: 'world', geometryGeneration: 4,
        measurementGeneration: 5, consumerGeneration: 6, measurement: measured.measurement };
      const provenancePath = path.join(data.directory, 'typed-provenance.json');
      const provenanceBytes = Buffer.from(JSON.stringify(provenance));
      await writeFile(provenancePath, provenanceBytes);
      const productDirectory = path.join(data.directory, 'product');
      execFileSync('node', ['tools/math3d-vtk-read-product.mjs', '--checkout', math3dRoot,
        '--source', converted, '--expected-sha', conversion.objSha256,
        '--provenance', provenancePath, '--provenance-sha', sha(provenanceBytes),
        '--measurement', measurementPath, '--measurement-sha', sha(measurementBytes),
        '--output', productDirectory], { cwd: path.resolve('.'), encoding: 'utf8', timeout: 180000 });
      const product = JSON.parse(await readFile(path.join(productDirectory, 'product.json')));
      assert.equal(product.verdict, 'passed');
      assert.equal(product.consumerCommit, consumerCommit);
      assert.equal(product.typedMeasurement.sha256, sha(measurementBytes));
      assert.equal(product.typedMeasurement.value, measured.measurement.value);
      const document = JSON.parse(await readFile(path.join(productDirectory, 'vtk-mesh-document.json')));
      assert.deepEqual(document.source.origin.devshell.measurement, measured.measurement);
      const coldPath = path.join(data.directory, 'cold-reopen.json');
      const reopened = JSON.parse(execFileSync('node', ['tools/math3d-typed-cold-reopen.mjs',
        '--checkout', math3dRoot, '--product', productDirectory,
        '--provenance', provenancePath, '--output', coldPath],
      { cwd: path.resolve('.'), encoding: 'utf8', timeout: 180000 }));
      assert.equal(reopened.verdict, 'passed');
      assert.equal(reopened.newProcess, true);
      assert.notEqual(reopened.producerPid, reopened.reopenPid);
      assert.equal(reopened.documentSha256, product.documentSha256);
      assert.equal(reopened.measurementSha256, sha(measurementBytes));
      await writeFile(path.join(productDirectory, 'read.m3dm'), Buffer.concat([
        await readFile(path.join(productDirectory, 'read.m3dm')), Buffer.from([0]) ]));
      assert.throws(() => execFileSync('node', ['tools/math3d-typed-cold-reopen.mjs',
        '--checkout', math3dRoot, '--product', productDirectory,
        '--provenance', provenancePath, '--output', path.join(data.directory, 'tampered-reopen.json')],
      { cwd: path.resolve('.'), encoding: 'utf8', timeout: 180000, stdio: 'pipe' }));
    }
  }
});
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
