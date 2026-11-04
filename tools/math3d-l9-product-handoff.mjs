// Validate a runtime-lab mesh result, persist a MATH3D Mesh document, then mount its real viewer.
import { createHash } from 'node:crypto'
import { readFile, writeFile, mkdir, stat } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { dirname, join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

const options = new Map()
for (let index = 2; index < process.argv.length; index += 2) options.set(process.argv[index], process.argv[index + 1])
if (!options.has('--checkout') || !options.has('--handoff') || !options.has('--output'))
  throw new Error('Checkout, handoff and output are required.')
const checkout = resolve(options.get('--checkout'))
const output = resolve(options.get('--output'))
const handoffPath = resolve(options.get('--handoff'))
const renderer = join(checkout, 'renderer')
const requireFromRenderer = createRequire(join(renderer, 'package.json'))
const requireFromDevShell = createRequire(join(import.meta.dirname, '..', 'DevShell', 'ui', 'dev-ui-react', 'package.json'))
const vite = await import(pathToFileURL(requireFromRenderer.resolve('vite')).href)
const { chromium } = requireFromDevShell('playwright-core')
const sha = bytes => createHash('sha256').update(bytes).digest('hex')
const readJson = async path => JSON.parse(await readFile(path, 'utf8'))
const handoff = await readJson(handoffPath)
const contract = handoff.contract
if (handoff.schemaVersion !== 1 || contract?.id !== 'math3d.mesh-product-handoff'
  || contract.version !== 1 || contract.workerResultSchemaVersion !== 1
  || contract.meshDocumentSchemaVersion !== 1 || contract.inputFormat !== 'obj'
  || contract.viewer !== 'MeshDocumentViewport' || handoff.runtimeId !== 'cgal-win-conda'
  || handoff.capabilityId !== 'mesh.interop.vtk-math3d'
  || !/^[0-9a-f]{32}$/.test(handoff.sourceL8RunId ?? '')
  || !/^[0-9a-f]{64}$/.test(handoff.sourceL8RecordId ?? '')) throw new Error('Unsupported broker-to-MATH3D contract.')
for (const file of [handoff.workerRequest, handoff.workerResult, handoff.artifact]) {
  if (typeof file?.path !== 'string' || !/^[0-9a-f]{64}$/.test(file.sha256 ?? ''))
    throw new Error('Handoff file identity is missing.')
  if ((await stat(file.path)).size > 32 * 1024 * 1024 || sha(await readFile(file.path)) !== file.sha256)
    throw new Error('Handoff file hash or size changed.')
}
const workerRequest = await readJson(handoff.workerRequest.path)
const workerResult = await readJson(handoff.workerResult.path)
if (workerRequest.schemaVersion !== 1 || workerResult.schemaVersion !== 1
  || workerResult.state !== 'succeeded'
  || !workerResult.validatedCapabilities?.includes('mesh.validate')
  || !workerResult.artifacts?.some(item => item.sha256 === handoff.artifact.sha256 && item.path === 'l5-positive.obj'))
  throw new Error('The broker worker did not verify the output artifact.')

await mkdir(output, { recursive: true })
const server = await vite.createServer({ root: renderer, server: { host: '127.0.0.1', port: 0 } })
let browser
try {
  const { loadSurfaceMeshFromFile } = await server.ssrLoadModule('/src/mesh/surfaceMesh.ts')
  const { MeshDocumentAdapter } = await server.ssrLoadModule('/src/mesh/meshDocumentAdapter.ts')
  const sourceBytes = await readFile(handoff.artifact.path)
  const imported = await loadSurfaceMeshFromFile([new File([sourceBytes], 'broker-output.obj', { type: 'text/plain' })],
    { mergeVertices: true, useObjWorker: false })
  if (imported.positions.length !== 12 || imported.indices?.length !== 12)
    throw new Error('The MATH3D scene importer did not produce the fixed tetrahedron.')
  const adapter = MeshDocumentAdapter.fromMesh(imported)
  const pkg = adapter.exportPackage()
  const documentPath = join(output, 'mesh-document.json')
  const resourcePath = join(output, 'mesh-resource.bin')
  await writeFile(documentPath, JSON.stringify(pkg.document))
  await writeFile(resourcePath, pkg.resourceBytes)
  const savedDocument = await readJson(documentPath)
  const savedResource = new Uint8Array(await readFile(resourcePath))
  const restored = MeshDocumentAdapter.restore({ document: savedDocument, resourceBytes: savedResource })
  const mesh = restored.mesh()
  if (mesh.positions.length !== 12 || mesh.indices?.length !== 12
    || restored.document().identity.structuralHash !== savedDocument.identity.structuralHash)
    throw new Error('MATH3D could not reopen its saved Mesh scene artifact.')
  await server.listen()
  const port = server.httpServer.address().port
  const edge = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
  browser = await chromium.launch({ executablePath: edge, headless: true,
    args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-webgl', '--disable-gpu-sandbox'] })
  const page = await browser.newPage({ viewport: { width: 900, height: 700 } })
  await page.route(`http://127.0.0.1:${port}/`, route => route.fulfill({ status: 200, contentType: 'text/html',
    body: '<!doctype html><html><body style="margin:0"><div id="root" style="width:900px;height:700px"></div><script type="module">import RefreshRuntime from "/@react-refresh"; RefreshRuntime.injectIntoGlobalHook(window); window.$RefreshReg$=()=>{}; window.$RefreshSig$=()=>type=>type; window.__vite_plugin_react_preamble_installed__=true;</script></body></html>' }))
  await page.goto(`http://127.0.0.1:${port}/`)
  await page.waitForFunction(() => window.__vite_plugin_react_preamble_installed__ === true)
  await page.evaluate(async ({ positions, indices, saved }) => {
    const React = await import('/node_modules/.vite/deps/react.js')
    const ReactDom = await import('/node_modules/.vite/deps/react-dom_client.js')
    const react = React.default ?? React
    const reactDom = ReactDom.default ?? ReactDom
    const { MeshDocumentViewport } = await import('/src/workspace/MeshDocumentViewport.tsx')
    const mesh = { id: saved.identity.id, label: saved.metadata.label,
      source: { kind: 'import', filename: 'broker-output.obj' },
      positions: new Float32Array(positions), indices: new Uint32Array(indices) }
    reactDom.createRoot(document.getElementById('root')).render(react.createElement(MeshDocumentViewport,
      { documentId: saved.identity.id, revision: saved.identity.revision,
        hash: saved.identity.structuralHash,
        view: { mesh, picking: false, onInspect: () => {}, onPick: () => {}, onCancelPick: () => {} } }))
  }, { positions: Array.from(mesh.positions), indices: Array.from(mesh.indices), saved: savedDocument })
  const viewport = page.getByTestId('document-mesh-viewport')
  await viewport.waitFor({ timeout: 30_000 })
  const canvas = viewport.locator('canvas').first()
  await canvas.waitFor({ timeout: 30_000 })
  const canvasSize = await canvas.evaluate(element => ({ width: element.width, height: element.height }))
  const documentId = await viewport.getAttribute('data-document-id')
  const sourceHash = await viewport.getAttribute('data-source-hash')
  if (documentId !== savedDocument.identity.id || sourceHash !== savedDocument.identity.structuralHash
    || canvasSize.width < 100 || canvasSize.height < 100)
    throw new Error('MATH3D viewer did not mount the reopened Mesh scene.')
  const screenshotPath = join(output, 'viewer.png')
  const screenshot = await viewport.screenshot({ path: screenshotPath })
  if (screenshot.length < 1000) throw new Error('MATH3D viewer screenshot is empty.')
  const blueMeshPixels = await page.evaluate(async encoded => {
    const binary = atob(encoded)
    const bytes = Uint8Array.from(binary, character => character.charCodeAt(0))
    const bitmap = await createImageBitmap(new Blob([bytes], { type: 'image/png' }))
    const surface = document.createElement('canvas')
    surface.width = bitmap.width; surface.height = bitmap.height
    const context = surface.getContext('2d', { willReadFrequently: true })
    context.drawImage(bitmap, 0, 0)
    const rgba = context.getImageData(0, 0, surface.width, surface.height).data
    let count = 0
    for (let index = 0; index < rgba.length; index += 4)
      if (rgba[index + 2] > rgba[index] + 30 && rgba[index + 2] > rgba[index + 1] + 15) count++
    return count
  }, screenshot.toString('base64'))
  if (blueMeshPixels < 1000) throw new Error('MATH3D viewer screenshot did not contain the mesh.')
  const sourceFiles = [
    'renderer/src/mesh/surfaceMesh.ts', 'renderer/src/mesh/meshDocumentAdapter.ts',
    'renderer/src/mesh/meshResourceStore.ts', 'renderer/src/workspace/MeshDocumentViewport.tsx',
    'renderer/src/components/SurfaceViewer.tsx', 'packages/core/src/meshDocument.ts'
  ]
  const consumerSources = Object.fromEntries(await Promise.all(sourceFiles.map(async name => [name, sha(await readFile(join(checkout, name)))])))
  const report = { schemaVersion: 1, contractVersion: 1, contractSha256: sha(Buffer.from(JSON.stringify(contract))),
    sourceL8RunId: handoff.sourceL8RunId, sourceL8RecordId: handoff.sourceL8RecordId,
    workerRequestSha256: handoff.workerRequest.sha256, workerResultSha256: handoff.workerResult.sha256,
    sourceArtifactSha256: handoff.artifact.sha256,
    documentSha256: sha(await readFile(documentPath)), resourceSha256: sha(savedResource),
    screenshotSha256: sha(screenshot), documentId, structuralHash: sourceHash,
    points: mesh.positions.length / 3, triangles: mesh.indices.length / 3,
    viewer: 'MeshDocumentViewport', canvasSize, blueMeshPixels, viewerState: 'mounted',
    regression: 'passed', consumerSources }
  await writeFile(join(output, 'regression.json'), JSON.stringify(report))
} finally {
  await browser?.close()
  await server.close()
}
