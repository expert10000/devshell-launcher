// Persist a verified CGAL repair as MATH3D Mesh resources and M3DM bytes.
import { createHash } from 'node:crypto'
import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { basename, dirname, join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

const args = new Map()
for (let i = 2; i < process.argv.length; i += 2) args.set(process.argv[i], process.argv[i + 1])
if (!['--checkout', '--run-directory', '--handoff', '--output'].every(key => args.has(key)))
  throw new Error('Checkout, managed run, verified handoff and output are required.')
const checkout = resolve(args.get('--checkout'))
const run = resolve(args.get('--run-directory'))
const handoffPath = resolve(args.get('--handoff'))
const output = resolve(args.get('--output'))
const sha = bytes => createHash('sha256').update(bytes).digest('hex')
const readJson = async path => JSON.parse(await readFile(path, 'utf8'))
const requestPath = join(run, 'request.json'), resultPath = join(run, 'results.json')
const [request, result, handoff] = await Promise.all([readJson(requestPath), readJson(resultPath), readJson(handoffPath)])
const name = request.outputArtifacts?.[0]?.path
if (typeof name !== 'string' || basename(name) !== name || !/^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}\.obj$/.test(name))
  throw new Error('Saved repair output name is unsafe.')
const source = join(run, name)
const sourceBytes = await readFile(source)
if (sourceBytes.length < 1 || sourceBytes.length > 32 * 1024 * 1024
  || request.workingDirectory !== run || request.runId !== result.runId
  || result.state !== 'succeeded' || !result.validatedCapabilities?.includes('mesh.repair')
  || handoff.verdict !== 'passed' || handoff.runId !== result.runId
  || handoff.requestSha256 !== sha(await readFile(requestPath))
  || handoff.resultSha256 !== sha(await readFile(resultPath))
  || handoff.outputSha256 !== sha(sourceBytes)
  || !result.artifacts?.some(item => item.path === name && item.sha256 === handoff.outputSha256))
  throw new Error('Managed repair or MATH3D importer evidence changed.')

const renderer = join(checkout, 'renderer')
const requireFromRenderer = createRequire(join(renderer, 'package.json'))
const vite = await import(pathToFileURL(requireFromRenderer.resolve('vite')).href)
const server = await vite.createServer({ root: renderer, server: { middlewareMode: true }, appType: 'custom' })
try {
  const { loadSurfaceMeshFromFile } = await server.ssrLoadModule('/src/mesh/surfaceMesh.ts')
  const { MeshDocumentAdapter } = await server.ssrLoadModule('/src/mesh/meshDocumentAdapter.ts')
  const { encodeM3DMesh, decodeM3DMesh } = await import(pathToFileURL(join(checkout, 'src/main/python/nativeCgalProtocol.ts')).href)
  const imported = await loadSurfaceMeshFromFile([new File([sourceBytes], 'repaired.obj', { type: 'text/plain' })],
    { mergeVertices: true, useObjWorker: false })
  const points = imported.positions.length / 3
  const triangles = (imported.indices?.length ?? 0) / 3
  if (points !== result.after?.vertices || triangles !== result.after?.faces
    || points !== handoff.consumer?.points || triangles !== handoff.consumer?.triangles)
    throw new Error('MATH3D imported geometry differs from managed repair evidence.')
  const adapter = MeshDocumentAdapter.fromMesh(imported)
  const pkg = adapter.exportPackage()
  await mkdir(output, { recursive: true })
  const documentPath = join(output, 'repair-mesh-document.json')
  const resourcePath = join(output, 'repair-mesh-resource.bin')
  const m3dmPath = join(output, 'repaired.m3dm')
  await writeFile(documentPath, JSON.stringify(pkg.document))
  await writeFile(resourcePath, pkg.resourceBytes)
  const restored = MeshDocumentAdapter.restore({ document: await readJson(documentPath),
    resourceBytes: new Uint8Array(await readFile(resourcePath)) })
  const mesh = restored.mesh()
  if (mesh.positions.length / 3 !== points || mesh.indices?.length / 3 !== triangles
    || restored.document().identity.structuralHash !== pkg.document.identity.structuralHash)
    throw new Error('MATH3D did not reopen the saved Mesh document.')
  const encoded = encodeM3DMesh(new Float32Array(mesh.positions), new Uint32Array(mesh.indices))
  await writeFile(m3dmPath, encoded)
  const decoded = decodeM3DMesh(await readFile(m3dmPath))
  if (decoded.vertexCount !== points || decoded.triCount !== triangles
    || !Buffer.from(decoded.positions).equals(Buffer.from(new Float32Array(mesh.positions).buffer))
    || !Buffer.from(decoded.indices).equals(Buffer.from(new Uint32Array(mesh.indices).buffer)))
    throw new Error('MATH3D could not reopen the saved M3DM resource.')
  const sources = ['renderer/src/mesh/surfaceMesh.ts', 'renderer/src/mesh/meshDocumentAdapter.ts',
    'renderer/src/mesh/meshResourceStore.ts', 'packages/core/src/meshDocument.ts',
    'src/main/python/nativeCgalProtocol.ts']
  const consumerSources = Object.fromEntries(await Promise.all(sources.map(async path => [path, sha(await readFile(join(checkout, path)))])))
  const report = { schemaVersion: 1, kind: 'scientific.cgal-repair-math3d-product', verdict: 'passed',
    runId: result.runId, recipeId: result.recipeId, sourceObjSha256: sha(sourceBytes),
    sourceResultSha256: sha(await readFile(resultPath)), handoffSha256: sha(await readFile(handoffPath)),
    documentSha256: sha(await readFile(documentPath)), resourceSha256: sha(await readFile(resourcePath)),
    m3dmSha256: sha(await readFile(m3dmPath)), documentId: pkg.document.identity.id,
    structuralHash: pkg.document.identity.structuralHash, points, triangles, consumerSources }
  await writeFile(join(output, 'product.json'), JSON.stringify(report, null, 2))
  console.log(JSON.stringify({ verdict: report.verdict, runId: report.runId, output }))
} finally {
  await server.close()
}
