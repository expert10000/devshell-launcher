// Feed a converted VTK artifact to MATH3D's actual desktop OBJ importer.
import { createHash } from 'node:crypto'
import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { join, resolve, dirname } from 'node:path'
import { pathToFileURL } from 'node:url'

const options = new Map()
for (let index = 2; index < process.argv.length; index += 2) options.set(process.argv[index], process.argv[index + 1])
const checkout = resolve(options.get('--checkout') || '')
const input = resolve(options.get('--input') || '')
const resultPath = resolve(options.get('--result') || '')
if (!options.has('--checkout') || !options.has('--input') || !options.has('--result')) throw new Error('Checkout, input and result are required.')
if (!input.toLowerCase().endsWith('.obj')) throw new Error('MATH3D desktop importer handoff requires OBJ.')
const renderer = join(checkout, 'renderer')
const importer = join(renderer, 'src', 'mesh', 'surfaceMesh.ts')
const requireFromRenderer = createRequire(join(renderer, 'package.json'))
const vite = await import(pathToFileURL(requireFromRenderer.resolve('vite')).href)
const server = await vite.createServer({ root: renderer, server: { middlewareMode: true }, appType: 'custom' })
try {
  const { loadSurfaceMeshFromFile } = await server.ssrLoadModule('/src/mesh/surfaceMesh.ts')
  if (typeof loadSurfaceMeshFromFile !== 'function') throw new Error('MATH3D desktop mesh importer is unavailable.')
  const bytes = await readFile(input)
  if (!bytes.length || bytes.length > 32 * 1024 * 1024) throw new Error('Handoff OBJ exceeds the importer budget.')
  const file = new File([bytes], 'vtk-handoff.obj', { type: 'text/plain' })
  const mesh = await loadSurfaceMeshFromFile([file], { mergeVertices: true, useObjWorker: false })
  const positions = Array.from(mesh.positions)
  const indices = Array.from(mesh.indices || [])
  if (!positions.length || positions.length % 3 || !indices.length || indices.length % 3 ||
      positions.some(value => !Number.isFinite(value)) || indices.some(value => !Number.isInteger(value) || value < 0 || value >= positions.length / 3))
    throw new Error('MATH3D importer returned invalid mesh geometry.')
  const bounds = [0, 1, 2].flatMap(axis => {
    const values = positions.filter((_, index) => index % 3 === axis)
    return [Math.min(...values), Math.max(...values)]
  })
  const edges = new Map()
  let signedVolume = 0
  let surfaceArea = 0
  for (let index = 0; index < indices.length; index += 3) {
    const point = offset => positions.slice(3 * indices[index + offset], 3 * indices[index + offset] + 3)
    const [a, b, c] = [point(0), point(1), point(2)]
    const ab = b.map((value, axis) => value - a[axis])
    const ac = c.map((value, axis) => value - a[axis])
    const cross = [ab[1] * ac[2] - ab[2] * ac[1], ab[2] * ac[0] - ab[0] * ac[2], ab[0] * ac[1] - ab[1] * ac[0]]
    surfaceArea += Math.hypot(...cross) / 2
    signedVolume += a.reduce((total, value, axis) => total + value * cross[axis], 0) / 6
    for (const [a, b] of [[indices[index], indices[index + 1]], [indices[index + 1], indices[index + 2]], [indices[index + 2], indices[index]]]) {
      const key = [Math.min(a, b), Math.max(a, b)].join(':')
      edges.set(key, (edges.get(key) || 0) + 1)
    }
  }
  const digest = bytes => createHash('sha256').update(bytes).digest('hex')
  const result = {
    consumer: 'MATH3D desktop loadSurfaceMeshFromFile', consumerVersion: 1,
    importerSourceSha256: digest(await readFile(importer)), inputObjSha256: digest(bytes),
    format: mesh.source?.format || null, points: positions.length / 3, triangles: indices.length / 3,
    bounds, boundaryEdges: [...edges.values()].filter(count => count === 1).length,
    nonManifoldEdges: [...edges.values()].filter(count => count > 2).length,
    closed: [...edges.values()].every(count => count === 2), indicesInRange: true,
    signedVolume, surfaceArea
  }
  await mkdir(dirname(resultPath), { recursive: true })
  await writeFile(resultPath, JSON.stringify(result))
} finally {
  await server.close()
}
