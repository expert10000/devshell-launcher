// Mount a reopened guarded orientation Mesh document in the actual MATH3D viewport.
import { createHash } from 'node:crypto'
import { readFile, writeFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

const args = new Map()
for (let i = 2; i < process.argv.length; i += 2) args.set(process.argv[i], process.argv[i + 1])
if (!args.has('--checkout') || !args.has('--product')) throw new Error('MATH3D checkout and product directory are required.')
const checkout = resolve(args.get('--checkout')), product = resolve(args.get('--product'))
const renderer = join(checkout, 'renderer')
const requireFromRenderer = createRequire(join(renderer, 'package.json'))
const requireFromDevShell = createRequire(join(import.meta.dirname, '..', 'DevShell', 'ui', 'dev-ui-react', 'package.json'))
const vite = await import(pathToFileURL(requireFromRenderer.resolve('vite')).href)
const { chromium } = requireFromDevShell('playwright-core')
const sha = bytes => createHash('sha256').update(bytes).digest('hex')
const readJson = async path => JSON.parse(await readFile(path, 'utf8'))
const documentPath = join(product, 'orientation-mesh-document.json')
const resourcePath = join(product, 'orientation-mesh-resource.bin')
const m3dmPath = join(product, 'oriented.m3dm')
const [record, document, resource, m3dm] = await Promise.all([
  readJson(join(product, 'product.json')), readJson(documentPath), readFile(resourcePath), readFile(m3dmPath)])
if (record.verdict !== 'passed' || record.documentSha256 !== sha(await readFile(documentPath))
  || record.resourceSha256 !== sha(resource) || record.m3dmSha256 !== sha(m3dm)
) throw new Error('Saved orientation document or independent reload changed.')

const server = await vite.createServer({ root: renderer, server: { host: '127.0.0.1', port: 0 } })
let browser
try {
  const { MeshDocumentAdapter } = await server.ssrLoadModule('/src/mesh/meshDocumentAdapter.ts')
  const restored = MeshDocumentAdapter.restore({ document, resourceBytes: new Uint8Array(resource) })
  const mesh = restored.mesh()
  if (mesh.positions.length / 3 !== record.points || mesh.indices?.length / 3 !== record.triangles
    || restored.document().identity.structuralHash !== record.structuralHash)
    throw new Error('Saved orientation Mesh document did not reopen before viewing.')
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
    const react = React.default ?? React, reactDom = ReactDom.default ?? ReactDom
    const { MeshDocumentViewport } = await import('/src/workspace/MeshDocumentViewport.tsx')
    const mesh = { id: saved.identity.id, label: saved.metadata.label,
      source: { kind: 'import', filename: 'oriented.m3dm' },
      positions: new Float32Array(positions), indices: new Uint32Array(indices) }
    reactDom.createRoot(document.getElementById('root')).render(react.createElement(MeshDocumentViewport,
      { documentId: saved.identity.id, revision: saved.identity.revision, hash: saved.identity.structuralHash,
        view: { mesh, picking: false, onInspect: () => {}, onPick: () => {}, onCancelPick: () => {} } }))
  }, { positions: Array.from(mesh.positions), indices: Array.from(mesh.indices), saved: document })
  const viewport = page.getByTestId('document-mesh-viewport')
  await viewport.waitFor({ timeout: 30_000 })
  const canvas = viewport.locator('canvas').first()
  await canvas.waitFor({ timeout: 30_000 })
  const canvasSize = await canvas.evaluate(element => ({ width: element.width, height: element.height }))
  if (await viewport.getAttribute('data-document-id') !== record.documentId
    || await viewport.getAttribute('data-source-hash') !== record.structuralHash
    || canvasSize.width < 100 || canvasSize.height < 100)
    throw new Error('Orientation Mesh viewer did not mount the reopened document.')
  await page.evaluate(() => window.dispatchEvent(new CustomEvent('math3d:capture-autofit', { detail: { padding: 1.34 } })))
  await page.waitForTimeout(250)
  const screenshot = await viewport.screenshot({ path: join(product, 'viewer.png') })
  if (screenshot.length < 1000) throw new Error('Orientation Mesh viewer image is empty.')
  const blueMeshPixels = await page.evaluate(async encoded => {
    const bytes = Uint8Array.from(atob(encoded), character => character.charCodeAt(0))
    const bitmap = await createImageBitmap(new Blob([bytes], { type: 'image/png' }))
    const surface = document.createElement('canvas')
    surface.width = bitmap.width; surface.height = bitmap.height
    const context = surface.getContext('2d', { willReadFrequently: true })
    context.drawImage(bitmap, 0, 0)
    const rgba = context.getImageData(0, 0, surface.width, surface.height).data
    let count = 0
    for (let i = 0; i < rgba.length; i += 4)
      if (rgba[i + 2] > rgba[i] + 30 && rgba[i + 2] > rgba[i + 1] + 15) count++
    return count
  }, screenshot.toString('base64'))
  if (blueMeshPixels < 1000) throw new Error('Orientation Mesh viewer screenshot did not contain the mesh.')
  const report = { schemaVersion: 1, kind: 'scientific.cgal-orientation-math3d-viewer', verdict: 'passed',
    documentId: record.documentId, structuralHash: record.structuralHash,
    documentSha256: record.documentSha256, resourceSha256: record.resourceSha256,
    m3dmSha256: record.m3dmSha256,
    screenshotSha256: sha(screenshot), viewerSourceSha256: sha(await readFile(join(checkout, 'renderer/src/workspace/MeshDocumentViewport.tsx'))),
    canvasSize, blueMeshPixels, viewerState: 'mounted' }
  await writeFile(join(product, 'viewer.json'), JSON.stringify(report, null, 2))
  console.log(JSON.stringify({ verdict: 'passed', documentId: report.documentId, blueMeshPixels }))
} finally {
  await browser?.close()
  await server.close()
}
