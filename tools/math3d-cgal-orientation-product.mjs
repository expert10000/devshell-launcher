// Import a guarded orientation into MATH3D's saved Mesh document and M3DM formats.
import { createHash } from 'node:crypto'
import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

const args = new Map()
for (let index = 2; index < process.argv.length; index += 2) args.set(process.argv[index], process.argv[index + 1])
if (!['--checkout', '--source', '--expected-sha', '--output'].every(key => args.has(key)))
  throw new Error('MATH3D checkout, guarded OBJ identity and output are required.')
const checkout = resolve(args.get('--checkout'))
const source = resolve(args.get('--source'))
const output = resolve(args.get('--output'))
const sha = bytes => createHash('sha256').update(bytes).digest('hex')
const sourceBytes = await readFile(source)
if (sourceBytes.length < 1 || sourceBytes.length > 32 * 1024 * 1024
  || !source.toLowerCase().endsWith('.obj') || sha(sourceBytes) !== args.get('--expected-sha'))
  throw new Error('Guarded orientation source changed or exceeds the product budget.')

const renderer = join(checkout, 'renderer')
const requireFromRenderer = createRequire(join(renderer, 'package.json'))
const vite = await import(pathToFileURL(requireFromRenderer.resolve('vite')).href)
const server = await vite.createServer({ root: renderer, server: { middlewareMode: true }, appType: 'custom' })
try {
  const { loadSurfaceMeshFromFile } = await server.ssrLoadModule('/src/mesh/surfaceMesh.ts')
  const { MeshDocumentAdapter } = await server.ssrLoadModule('/src/mesh/meshDocumentAdapter.ts')
  const { encodeM3DMesh, decodeM3DMesh } = await import(pathToFileURL(join(checkout, 'src/main/python/nativeCgalProtocol.ts')).href)
  const imported = await loadSurfaceMeshFromFile([new File([sourceBytes], 'guarded-orientation.obj', { type: 'text/plain' })],
    { mergeVertices: true, useObjWorker: false })
  const points = imported.positions.length / 3
  const triangles = (imported.indices?.length ?? 0) / 3
  if (points < 4 || triangles < 4) throw new Error('MATH3D importer returned an empty orientation.')
  const adapter = MeshDocumentAdapter.fromMesh(imported)
  const pkg = adapter.exportPackage()
  await mkdir(output, { recursive: true })
  const documentPath = join(output, 'orientation-mesh-document.json')
  const resourcePath = join(output, 'orientation-mesh-resource.bin')
  const m3dmPath = join(output, 'oriented.m3dm')
  await writeFile(documentPath, JSON.stringify(pkg.document))
  await writeFile(resourcePath, pkg.resourceBytes)
  const restored = MeshDocumentAdapter.restore({ document: JSON.parse(await readFile(documentPath, 'utf8')),
    resourceBytes: new Uint8Array(await readFile(resourcePath)) })
  const mesh = restored.mesh()
  if (mesh.positions.length / 3 !== points || mesh.indices?.length / 3 !== triangles
    || restored.document().identity.structuralHash !== pkg.document.identity.structuralHash)
    throw new Error('Saved orientation Mesh document failed to reopen.')
  const encoded = encodeM3DMesh(new Float32Array(mesh.positions), new Uint32Array(mesh.indices))
  await writeFile(m3dmPath, encoded)
  const decoded = decodeM3DMesh(await readFile(m3dmPath))
  if (decoded.vertexCount !== points || decoded.triCount !== triangles
    || !Buffer.from(decoded.positions).equals(Buffer.from(new Float32Array(mesh.positions).buffer))
    || !Buffer.from(decoded.indices).equals(Buffer.from(new Uint32Array(mesh.indices).buffer)))
    throw new Error('Saved orientation M3DM failed to reopen.')
  const sources = ['renderer/src/mesh/surfaceMesh.ts', 'renderer/src/mesh/meshDocumentAdapter.ts',
    'renderer/src/mesh/meshResourceStore.ts', 'packages/core/src/meshDocument.ts',
    'src/main/python/nativeCgalProtocol.ts']
  const consumerSources = Object.fromEntries(await Promise.all(sources.map(async path => [path, sha(await readFile(join(checkout, path)))])))
  const report = { schemaVersion: 1, kind: 'scientific.cgal-orientation-math3d-product', verdict: 'passed',
    sourceObjSha256: sha(sourceBytes), documentSha256: sha(await readFile(documentPath)),
    resourceSha256: sha(await readFile(resourcePath)), m3dmSha256: sha(await readFile(m3dmPath)),
    documentId: pkg.document.identity.id, structuralHash: pkg.document.identity.structuralHash,
    points, triangles, consumerSources }
  await writeFile(join(output, 'product.json'), JSON.stringify(report, null, 2))
  console.log(JSON.stringify({ verdict: report.verdict, documentId: report.documentId, output }))
} finally {
  await server.close()
}
