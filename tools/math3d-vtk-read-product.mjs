// Import a guarded VTK read into MATH3D's saved Mesh document and M3DM formats.
import { createHash } from 'node:crypto'
import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { execFileSync } from 'node:child_process'
import { verifyTypedMeasurement } from './math3d-typed-measurement.mjs'

const args = new Map()
for (let index = 2; index < process.argv.length; index += 2) args.set(process.argv[index], process.argv[index + 1])
if (!['--checkout', '--source', '--expected-sha', '--output'].every(key => args.has(key)))
  throw new Error('MATH3D checkout, guarded OBJ identity and output are required.')
const checkout = resolve(args.get('--checkout'))
const source = resolve(args.get('--source'))
const output = resolve(args.get('--output'))
const sha = bytes => createHash('sha256').update(bytes).digest('hex')
const canonical = value => Array.isArray(value) ? value.map(canonical) : value && typeof value === 'object'
  ? Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([key, item]) => [key, canonical(item)])) : value
const sourceBytes = await readFile(source)
if (sourceBytes.length < 1 || sourceBytes.length > 32 * 1024 * 1024
  || !source.toLowerCase().endsWith('.obj') || sha(sourceBytes) !== args.get('--expected-sha'))
  throw new Error('Guarded VTK read source changed or exceeds the product budget.')
const consumerCommit = execFileSync('git', ['-C', checkout, 'rev-parse', 'HEAD'], { encoding: 'utf8' }).trim()
let provenance = null
let provenanceSha256 = null
let typedMeasurement = null
if (args.has('--provenance')) {
  const bytes = await readFile(resolve(args.get('--provenance')))
  provenanceSha256 = sha(bytes)
  if (provenanceSha256 !== args.get('--provenance-sha')) throw new Error('Workbench handoff provenance changed.')
  provenance = JSON.parse(bytes.toString('utf8'))
  if (provenance.schemaVersion !== 1 || !['scientific.workbench-math3d-handoff', 'scientific.typed-journey'].includes(provenance.kind)
    || provenance.convertedObjSha256 !== sha(sourceBytes) || provenance.math3dCommit !== consumerCommit)
    throw new Error('Workbench artifact or MATH3D consumer identity changed.')
  if (provenance.kind === 'scientific.typed-journey') {
    if (!args.has('--measurement') || !args.has('--measurement-sha')) throw new Error('Typed MATH3D handoff requires its SciPy measurement.')
    const measurementBytes = await readFile(resolve(args.get('--measurement')))
    if (measurementBytes.length < 1 || measurementBytes.length > 65536) throw new Error('Typed measurement exceeds 64 KiB.')
    typedMeasurement = verifyTypedMeasurement(measurementBytes, args.get('--measurement-sha'), provenance, sha(sourceBytes), consumerCommit)
  } else if (args.has('--measurement') || args.has('--measurement-sha')) {
    throw new Error('A measurement requires typed journey provenance.')
  }
}

const renderer = join(checkout, 'renderer')
const requireFromRenderer = createRequire(join(renderer, 'package.json'))
const vite = await import(pathToFileURL(requireFromRenderer.resolve('vite')).href)
const server = await vite.createServer({ root: renderer, server: { middlewareMode: true }, appType: 'custom' })
try {
  const { loadSurfaceMeshFromFile } = await server.ssrLoadModule('/src/mesh/surfaceMesh.ts')
  const { MeshDocumentAdapter } = await server.ssrLoadModule('/src/mesh/meshDocumentAdapter.ts')
  const { encodeM3DMesh, decodeM3DMesh } = await import(pathToFileURL(join(checkout, 'src/main/python/nativeCgalProtocol.ts')).href)
  const imported = await loadSurfaceMeshFromFile([new File([sourceBytes], 'vtk-read.obj', { type: 'text/plain' })],
    { mergeVertices: true, useObjWorker: false })
  if (provenance) imported.source = { ...imported.source, devshell: provenance }
  const points = imported.positions.length / 3
  const triangles = (imported.indices?.length ?? 0) / 3
  if (points < 4 || triangles < 2) throw new Error('MATH3D importer returned an empty VTK read.')
  const adapter = MeshDocumentAdapter.fromMesh(imported)
  const pkg = adapter.exportPackage()
  await mkdir(output, { recursive: true })
  const documentPath = join(output, 'vtk-mesh-document.json')
  const resourcePath = join(output, 'vtk-mesh-resource.bin')
  const m3dmPath = join(output, 'read.m3dm')
  await writeFile(documentPath, JSON.stringify(pkg.document))
  await writeFile(resourcePath, pkg.resourceBytes)
  const restored = MeshDocumentAdapter.restore({ document: JSON.parse(await readFile(documentPath, 'utf8')),
    resourceBytes: new Uint8Array(await readFile(resourcePath)) })
  const mesh = restored.mesh()
  const reload = { points: mesh.positions.length / 3 === points, triangles: mesh.indices?.length / 3 === triangles,
    structuralHash: restored.document().identity.structuralHash === pkg.document.identity.structuralHash,
    provenance: !provenance || JSON.stringify(canonical(mesh.source.devshell)) === JSON.stringify(canonical(provenance)),
    provenancePresent: !provenance || !!mesh.source.devshell }
  if (!Object.values(reload).every(Boolean))
    throw new Error('Saved VTK read Mesh document failed to reopen: ' + JSON.stringify(reload))
  const encoded = encodeM3DMesh(new Float32Array(mesh.positions), new Uint32Array(mesh.indices))
  await writeFile(m3dmPath, encoded)
  const decoded = decodeM3DMesh(await readFile(m3dmPath))
  if (decoded.vertexCount !== points || decoded.triCount !== triangles
    || !Buffer.from(decoded.positions).equals(Buffer.from(new Float32Array(mesh.positions).buffer))
    || !Buffer.from(decoded.indices).equals(Buffer.from(new Uint32Array(mesh.indices).buffer)))
    throw new Error('Saved VTK read M3DM failed to reopen.')
  const sources = ['renderer/src/mesh/surfaceMesh.ts', 'renderer/src/mesh/meshDocumentAdapter.ts',
    'renderer/src/mesh/meshResourceStore.ts', 'packages/core/src/meshDocument.ts',
    'src/main/python/nativeCgalProtocol.ts']
  const consumerSources = Object.fromEntries(await Promise.all(sources.map(async path => [path, sha(await readFile(join(checkout, path)))])))
  const report = { schemaVersion: 1, kind: 'scientific.vtk-read-math3d-product', verdict: 'passed',
    sourceObjSha256: sha(sourceBytes), documentSha256: sha(await readFile(documentPath)),
    resourceSha256: sha(await readFile(resourcePath)), m3dmSha256: sha(await readFile(m3dmPath)),
    documentId: pkg.document.identity.id, structuralHash: pkg.document.identity.structuralHash,
    points, triangles, consumerCommit, consumerSources, provenanceSha256,
    ...(typedMeasurement ? { typedMeasurement, producerPid: process.pid } : {}) }
  await writeFile(join(output, 'product.json'), JSON.stringify(report, null, 2))
  console.log(JSON.stringify({ verdict: report.verdict, documentId: report.documentId, output }))
} finally {
  await server.close()
}
