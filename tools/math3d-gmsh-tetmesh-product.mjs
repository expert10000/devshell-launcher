// Import the versioned tetrahedral handoff into a saved MATH3D document and mount its boundary viewer.
import { createHash } from 'node:crypto'
import { readFile, writeFile, mkdir, stat } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

const args = new Map()
for (let index = 2; index < process.argv.length; index += 2) args.set(process.argv[index], process.argv[index + 1])
if (!args.has('--checkout') || !args.has('--handoff') || !args.has('--output')) throw new Error('Checkout, handoff and output are required.')
const checkout = resolve(args.get('--checkout'))
const handoff = JSON.parse(await readFile(resolve(args.get('--handoff')), 'utf8'))
const output = resolve(args.get('--output'))
const sha = bytes => createHash('sha256').update(bytes).digest('hex')
const contract = handoff.contract
if (handoff.schemaVersion !== 1 || handoff.runtimeId !== 'gmsh-win-conda'
    || handoff.capabilityId !== 'mesh.generate3d'
    || contract?.id !== 'math3d.tetrahedral-product-handoff' || contract.version !== 1
    || contract.documentFormat !== 'math3d.tetrahedral-mesh-document'
    || contract.resourceEncoding !== 'math3d.tetmesh-buffers.v1'
    || contract.viewer !== 'TetrahedralMeshViewport'
    || !/^[0-9a-f]{32}$/.test(handoff.sourceL8RunId ?? '')
    || !/^[0-9a-f]{64}$/.test(handoff.sourceL8RecordId ?? '')) throw new Error('Unsupported tetrahedral product contract.')
for (const file of [handoff.sourceMsh, handoff.resource, handoff.exporterReport]) {
  if (typeof file?.path !== 'string' || !/^[0-9a-f]{64}$/.test(file.sha256 ?? '')
      || (await stat(file.path)).size > 32 * 1024 * 1024
      || sha(await readFile(file.path)) !== file.sha256) throw new Error('Tetrahedral handoff artifact changed.')
}
const exported = JSON.parse(await readFile(handoff.exporterReport.path, 'utf8'))
if (exported.format !== 'M3DT' || exported.version !== 1
    || exported.sourceMshSha256 !== handoff.sourceMsh.sha256
    || exported.resourceSha256 !== handoff.resource.sha256)
  throw new Error('Tetrahedral exporter result changed.')
const manifestPath = join(checkout, 'scientific/volume-consumer.v1.json')
const manifest = JSON.parse(await readFile(manifestPath, 'utf8'))
if (manifest.schemaVersion !== 1 || manifest.artifactType !== 'mesh.tetrahedral'
    || manifest.documentFormat !== contract.documentFormat || !manifest.preservesCells
    || manifest.resourceEncoding !== contract.resourceEncoding)
  throw new Error('MATH3D tetrahedral consumer contract is incompatible.')
const renderer = join(checkout, 'renderer')
const requireFromRenderer = createRequire(join(renderer, 'package.json'))
const requireFromDevShell = createRequire(join(import.meta.dirname, '..', 'DevShell', 'ui', 'dev-ui-react', 'package.json'))
const vite = await import(pathToFileURL(requireFromRenderer.resolve('vite')).href)
const { chromium } = requireFromDevShell('playwright-core')
await mkdir(output, { recursive: true })
const server = await vite.createServer({ root: renderer, server: { host: '127.0.0.1', port: 0 } })
let browser
try {
  const { TetrahedralMeshDocumentAdapter } = await server.ssrLoadModule('/src/volume/tetrahedralMeshDocumentAdapter.ts')
  const sourceBytes = new Uint8Array(await readFile(handoff.resource.path))
  const imported = await TetrahedralMeshDocumentAdapter.importResource(sourceBytes, handoff.sourceMsh.sha256)
  const pkg = imported.exportPackage()
  if (imported.geometry().points.length !== exported.points || imported.geometry().cells.length !== exported.tetrahedra
      || imported.geometry().boundary.length !== exported.boundaryTriangles || Math.abs(imported.geometry().volume - 1) > 1e-6)
    throw new Error('MATH3D did not import the fixed tetrahedral cube.')
  const documentPath = join(output, 'tetra-document.json')
  const resourcePath = join(output, 'tetra-resource.m3dt')
  await writeFile(documentPath, JSON.stringify(pkg.document))
  await writeFile(resourcePath, pkg.resourceBytes)
  const savedDocument = JSON.parse(await readFile(documentPath, 'utf8'))
  const savedResource = new Uint8Array(await readFile(resourcePath))
  const reopened = await TetrahedralMeshDocumentAdapter.restore({ document: savedDocument, resourceBytes: savedResource })
  if (reopened.geometry().cells.length !== exported.tetrahedra || reopened.document().identity.id !== savedDocument.identity.id)
    throw new Error('MATH3D could not reopen its saved tetrahedral document.')
  const altered = new Uint8Array(savedResource)
  altered[altered.length - 1] ^= 1
  let tamperRejected = false
  try { await TetrahedralMeshDocumentAdapter.restore({ document: savedDocument, resourceBytes: altered }) }
  catch { tamperRejected = true }
  if (!tamperRejected) throw new Error('MATH3D accepted a modified tetrahedral resource.')
  await server.listen()
  const port = server.httpServer.address().port
  browser = await chromium.launch({ executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless: true,
    args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-webgl', '--disable-gpu-sandbox'] })
  const page = await browser.newPage({ viewport: { width: 900, height: 700 } })
  await page.route(`http://127.0.0.1:${port}/`, route => route.fulfill({ status: 200, contentType: 'text/html',
    body: '<!doctype html><html><body style="margin:0"><div id="root" style="width:900px;height:700px"></div><script type="module">import RefreshRuntime from "/@react-refresh"; RefreshRuntime.injectIntoGlobalHook(window); window.$RefreshReg$=()=>{}; window.$RefreshSig$=()=>type=>type; window.__vite_plugin_react_preamble_installed__=true;</script></body></html>' }))
  await page.goto(`http://127.0.0.1:${port}/`)
  await page.waitForFunction(() => window.__vite_plugin_react_preamble_installed__ === true)
  await page.evaluate(async ({ saved, bytes }) => {
    const React = await import('/node_modules/.vite/deps/react.js')
    const ReactDom = await import('/node_modules/.vite/deps/react-dom_client.js')
    const react = React.default ?? React, reactDom = ReactDom.default ?? ReactDom
    const { TetrahedralMeshDocumentAdapter } = await import('/src/volume/tetrahedralMeshDocumentAdapter.ts')
    const { TetrahedralMeshViewport } = await import('/src/volume/TetrahedralMeshViewport.tsx')
    const adapter = await TetrahedralMeshDocumentAdapter.restore({ document: saved, resourceBytes: new Uint8Array(bytes) })
    reactDom.createRoot(document.getElementById('root')).render(react.createElement(TetrahedralMeshViewport, { adapter }))
  }, { saved: savedDocument, bytes: Array.from(savedResource) })
  const viewport = page.getByTestId('tetrahedral-mesh-viewport')
  await viewport.waitFor({ timeout: 30_000 })
  const canvas = viewport.locator('canvas').first()
  await canvas.waitFor({ timeout: 30_000 })
  const canvasSize = await canvas.evaluate(element => ({ width: element.width, height: element.height }))
  if (await viewport.getAttribute('data-document-id') !== savedDocument.identity.id
      || await viewport.getAttribute('data-source-hash') !== savedDocument.identity.structuralHash
      || Number(await viewport.getAttribute('data-tetrahedra')) !== exported.tetrahedra
      || canvasSize.width < 100 || canvasSize.height < 100)
    throw new Error('MATH3D tetrahedral viewport did not bind the reopened cells.')
  const screenshot = await viewport.screenshot({ path: join(output, 'viewer.png') })
  if (screenshot.length < 1000) throw new Error('MATH3D tetrahedral viewer image is empty.')
  const blueMeshPixels = await page.evaluate(async encoded => {
    const bytes = Uint8Array.from(atob(encoded), character => character.charCodeAt(0))
    const bitmap = await createImageBitmap(new Blob([bytes], { type: 'image/png' }))
    const canvas = document.createElement('canvas')
    canvas.width = bitmap.width; canvas.height = bitmap.height
    const context = canvas.getContext('2d', { willReadFrequently: true })
    context.drawImage(bitmap, 0, 0)
    const rgba = context.getImageData(0, 0, canvas.width, canvas.height).data
    let count = 0
    for (let index = 0; index < rgba.length; index += 4)
      if (rgba[index + 2] > rgba[index] + 30 && rgba[index + 2] > rgba[index + 1] + 15) count++
    return count
  }, screenshot.toString('base64'))
  if (blueMeshPixels < 1000) throw new Error('MATH3D tetrahedral viewer did not render the cube boundary.')
  const sourceFiles = [
    'scientific/volume-consumer.v1.json', 'packages/core/src/tetrahedralMeshDocument.ts',
    'renderer/src/volume/tetrahedralMeshDocumentAdapter.ts', 'renderer/src/volume/TetrahedralMeshViewport.tsx',
    'renderer/src/workspace/MeshDocumentViewport.tsx', 'renderer/src/components/SurfaceViewer.tsx',
  ]
  const consumerSources = Object.fromEntries(await Promise.all(sourceFiles.map(async name => [name, sha(await readFile(join(checkout, name)))])))
  const report = { schemaVersion: 1, contractVersion: 1, contractSha256: sha(Buffer.from(JSON.stringify(contract))),
    sourceL8RunId: handoff.sourceL8RunId, sourceL8RecordId: handoff.sourceL8RecordId,
    sourceMshSha256: handoff.sourceMsh.sha256, exportedResourceSha256: handoff.resource.sha256,
    documentSha256: sha(await readFile(documentPath)), resourceSha256: sha(savedResource), viewerSha256: sha(screenshot),
    documentId: savedDocument.identity.id, structuralHash: savedDocument.identity.structuralHash,
    points: reopened.geometry().points.length, tetrahedra: reopened.geometry().cells.length,
    boundaryTriangles: reopened.geometry().boundary.length, volume: reopened.geometry().volume,
    bounds: reopened.geometry().bounds, canvasSize, blueMeshPixels, tamperRejected,
    viewer: 'TetrahedralMeshViewport', viewerState: 'mounted', regression: 'passed', consumerSources,
    consumerSourcesSha256: sha(Buffer.from(JSON.stringify(consumerSources))) }
  await writeFile(join(output, 'regression.json'), JSON.stringify(report))
  console.log(JSON.stringify(report))
} finally {
  await browser?.close()
  await server.close()
}
