// Candidate Gmsh volume boundary checked through MATH3D's surface importer.
import { createHash } from 'node:crypto'
import { readFile, writeFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

const args = new Map()
for (let i = 2; i < process.argv.length; i += 2) args.set(process.argv[i], process.argv[i + 1])
if (!args.has('--checkout') || !args.has('--input') || !args.has('--result')) throw new Error('Missing checkout, input or result.')
const checkout = resolve(args.get('--checkout'))
const input = resolve(args.get('--input'))
const bytes = await readFile(input)
if (!bytes.length || bytes.length > 32 * 1024 * 1024 || !input.toLowerCase().endsWith('.obj')) throw new Error('Invalid OBJ handoff.')
const hash = data => createHash('sha256').update(data).digest('hex')
const importer = join(checkout, 'renderer/src/mesh/surfaceMesh.ts')
const renderer = join(checkout, 'renderer')
const requireFromRenderer = createRequire(join(renderer, 'package.json'))
const vite = await import(pathToFileURL(requireFromRenderer.resolve('vite')).href)
const server = await vite.createServer({ root: renderer, server: { middlewareMode: true }, appType: 'custom' })
let result
try {
  const { loadSurfaceMeshFromFile } = await server.ssrLoadModule('/src/mesh/surfaceMesh.ts')
  try {
    const mesh = await loadSurfaceMeshFromFile([new File([bytes], 'gmsh-volume-boundary.obj', { type: 'text/plain' })], { mergeVertices: true, useObjWorker: false })
    const points = Array.from(mesh.positions)
    const faces = Array.from(mesh.indices || [])
    if (points.length < 24 || points.length % 3 || faces.length < 36 || faces.length % 3 ||
        points.some(x => !Number.isFinite(x)) || faces.some(i => !Number.isInteger(i) || i < 0 || i >= points.length / 3))
      throw new Error('MATH3D imported invalid cube boundary data.')
    const edges = new Map()
    let area = 0, volume = 0
    for (let i = 0; i < faces.length; i += 3) {
      const ids = faces.slice(i, i + 3)
      if (new Set(ids).size !== 3) throw new Error('MATH3D imported a degenerate boundary face.')
      const [a, b, c] = ids.map(id => points.slice(3 * id, 3 * id + 3))
      const u = b.map((x, j) => x - a[j]), v = c.map((x, j) => x - a[j])
      const n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
      const center = a.map((x, j) => (x + b[j] + c[j]) / 3 - 0.5)
      if (n.reduce((sum, x, j) => sum + x * center[j], 0) <= 1e-9) throw new Error('MATH3D boundary orientation is inward.')
      area += Math.hypot(...n) / 2
      volume += a.reduce((sum, x, j) => sum + x * n[j], 0) / 6
      for (const [u, v] of [[ids[0], ids[1]], [ids[1], ids[2]], [ids[2], ids[0]]]) {
        const key = `${Math.min(u, v)}:${Math.max(u, v)}`
        edges.set(key, (edges.get(key) || 0) + 1)
      }
    }
    const bounds = [0, 1, 2].flatMap(axis => {
      const values = points.filter((_, index) => index % 3 === axis)
      return [Math.min(...values), Math.max(...values)]
    })
    if (bounds.some((x, i) => Math.abs(x - [0,1,0,1,0,1][i]) > 1e-6) ||
        Math.abs(area - 6) > 1e-5 || Math.abs(volume - 1) > 1e-5 || [...edges.values()].some(count => count !== 2))
      throw new Error('MATH3D boundary geometry or topology differs from the cube.')
    if (args.has('--expect-reject')) throw new Error('Invalid cube boundary was accepted by MATH3D.')
    result = { state: 'accepted', inputObjSha256: hash(bytes), importerSourceSha256: hash(await readFile(importer)),
      points: points.length / 3, triangles: faces.length / 3, bounds, surfaceArea: area, signedVolume: volume,
      boundaryEdges: [...edges.values()].filter(v => v === 1).length,
      nonManifoldEdges: [...edges.values()].filter(v => v > 2).length }
  } catch (error) {
    if (!args.has('--expect-reject') || String(error).includes('was accepted by MATH3D')) throw error
    result = { state: 'rejected', inputObjSha256: hash(bytes), importerSourceSha256: hash(await readFile(importer)), reason: String(error) }
  }
} finally { await server.close() }
await writeFile(resolve(args.get('--result')), JSON.stringify(result, null, 2))
console.log(JSON.stringify(result))
