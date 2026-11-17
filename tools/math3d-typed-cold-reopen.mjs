// Reopen a saved typed Mesh document in a fresh MATH3D consumer process.
import { createHash } from 'node:crypto';
import { readFile, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { execFileSync } from 'node:child_process';

const args = new Map();
for (let index = 2; index < process.argv.length; index += 2) args.set(process.argv[index], process.argv[index + 1]);
if (!['--checkout', '--product', '--provenance', '--output'].every(key => args.has(key)))
  throw new Error('MATH3D checkout, product, provenance and output are required.');
const checkout = resolve(args.get('--checkout'));
const productDirectory = resolve(args.get('--product'));
const output = resolve(args.get('--output'));
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const canonical = value => Array.isArray(value) ? value.map(canonical) : value && typeof value === 'object'
  ? Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([key, item]) => [key, canonical(item)])) : value;
const same = (a, b) => JSON.stringify(canonical(a)) === JSON.stringify(canonical(b));
const product = JSON.parse(await readFile(join(productDirectory, 'product.json'), 'utf8'));
const provenanceBytes = await readFile(resolve(args.get('--provenance')));
const provenance = JSON.parse(provenanceBytes.toString('utf8'));
const commit = execFileSync('git', ['-C', checkout, 'rev-parse', 'HEAD'], { encoding: 'utf8' }).trim();
if (product.verdict !== 'passed' || product.consumerCommit !== commit
  || provenance.kind !== 'scientific.typed-journey' || provenance.math3dCommit !== commit
  || product.provenanceSha256 !== sha(provenanceBytes)
  || product.typedMeasurement?.sha256 !== provenance.measurementSha256
  || product.producerPid === process.pid || !Number.isInteger(product.producerPid))
  throw new Error('Typed product, measurement, producer process or consumer commit changed.');
for (const [relative, expected] of Object.entries(product.consumerSources ?? {})) {
  const path = resolve(checkout, relative);
  if (!path.startsWith(checkout + '\\') && !path.startsWith(checkout + '/'))
    throw new Error('MATH3D consumer source path escaped checkout.');
  if (sha(await readFile(path)) !== expected) throw new Error('MATH3D consumer source drifted: ' + relative);
}
const documentBytes = await readFile(join(productDirectory, 'vtk-mesh-document.json'));
const resourceBytes = await readFile(join(productDirectory, 'vtk-mesh-resource.bin'));
const m3dmBytes = await readFile(join(productDirectory, 'read.m3dm'));
if (documentBytes.length > 32 * 1024 * 1024 || resourceBytes.length > 32 * 1024 * 1024
  || m3dmBytes.length > 32 * 1024 * 1024 || sha(documentBytes) !== product.documentSha256
  || sha(resourceBytes) !== product.resourceSha256 || sha(m3dmBytes) !== product.m3dmSha256)
  throw new Error('Saved document, resource or export bytes changed.');
const document = JSON.parse(documentBytes.toString('utf8'));
if (!same(document.source?.origin?.devshell, provenance)
  || document.identity?.id !== product.documentId
  || document.identity?.structuralHash !== product.structuralHash)
  throw new Error('Saved document identity or typed provenance changed.');
const renderer = join(checkout, 'renderer');
const requireFromRenderer = createRequire(join(renderer, 'package.json'));
const vite = await import(pathToFileURL(requireFromRenderer.resolve('vite')).href);
const server = await vite.createServer({ root: renderer, server: { middlewareMode: true }, appType: 'custom' });
try {
  const { MeshDocumentAdapter } = await server.ssrLoadModule('/src/mesh/meshDocumentAdapter.ts');
  const { decodeM3DMesh } = await import(pathToFileURL(join(checkout, 'src/main/python/nativeCgalProtocol.ts')).href);
  const restored = MeshDocumentAdapter.restore({ document,
    resourceBytes: new Uint8Array(resourceBytes) });
  const mesh = restored.mesh();
  const decoded = decodeM3DMesh(m3dmBytes);
  if (restored.document().identity.structuralHash !== product.structuralHash
    || mesh.positions.length / 3 !== product.points || mesh.indices.length / 3 !== product.triangles
    || decoded.vertexCount !== product.points || decoded.triCount !== product.triangles
    || !same(mesh.source?.devshell, provenance))
    throw new Error('Cold-reopened geometry or provenance differs from the saved product.');
  const record = { schemaVersion: 1, kind: 'scientific.typed-journey-cold-reopen', verdict: 'passed',
    newProcess: true, producerPid: product.producerPid, reopenPid: process.pid,
    sourceCommit: provenance.sourceCommit, sourceSnapshotSha256: provenance.sourceSnapshotSha256,
    consumerCommit: commit, documentId: product.documentId, structuralHash: product.structuralHash,
    documentSha256: product.documentSha256, resourceSha256: product.resourceSha256,
    exportSha256: product.m3dmSha256, measurementSha256: provenance.measurementSha256,
    lengthUnit: provenance.lengthUnit, frame: provenance.frame,
    generation: provenance.consumerGeneration + 2, points: product.points, triangles: product.triangles };
  await writeFile(output, JSON.stringify(record, null, 2) + '\n', { flag: 'wx' });
  console.log(JSON.stringify(record));
} finally {
  await server.close();
}
