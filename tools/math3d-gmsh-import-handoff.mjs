// Independent consumer check for the fixed Gmsh 2D OBJ handoff.
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
const renderer = join(checkout, 'renderer')
const importer = join(renderer, 'src', 'mesh', 'surfaceMesh.ts')
const requireFromRenderer = createRequire(join(renderer, 'package.json'))
const vite = await import(pathToFileURL(requireFromRenderer.resolve('vite')).href)
const server = await vite.createServer({ root: renderer, server: { middlewareMode: true }, appType: 'custom' })
const hash = data => createHash('sha256').update(data).digest('hex')
let result
try {
  const { loadSurfaceMeshFromFile } = await server.ssrLoadModule('/src/mesh/surfaceMesh.ts')
  try {
    const mesh = await loadSurfaceMeshFromFile([new File([bytes], 'gmsh-handoff.obj', { type: 'text/plain' })], { mergeVertices: true, useObjWorker: false })
    const positions = Array.from(mesh.positions)
    const indices = Array.from(mesh.indices || [])
    if (!positions.length || positions.length % 3 || !indices.length || indices.length % 3 ||
        positions.some(value => !Number.isFinite(value)) ||
        indices.some(value => !Number.isInteger(value) || value < 0 || value >= positions.length / 3)) throw new Error('Invalid consumer mesh.')
    if (args.has('--expect-reject')) {
      result = { state: 'accepted' }
      throw new Error('Malformed Gmsh handoff was accepted.')
    }
    const bounds = [0, 1, 2].flatMap(axis => {
      const values = positions.filter((_, index) => index % 3 === axis)
      return [Math.min(...values), Math.max(...values)]
    })
    const edges = new Map()
    let signedAreaXY = 0
    for (let i = 0; i < indices.length; i += 3) {
      const [a, b, c] = [0, 1, 2].map(offset => positions.slice(3 * indices[i + offset], 3 * indices[i + offset] + 3))
      signedAreaXY += ((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) / 2
      for (const [u, v] of [[indices[i], indices[i + 1]], [indices[i + 1], indices[i + 2]], [indices[i + 2], indices[i]]]) {
        const edge = [Math.min(u, v), Math.max(u, v)].join(':')
        edges.set(edge, (edges.get(edge) || 0) + 1)
      }
    }
    result = { state: 'accepted', inputObjSha256: hash(bytes), importerSourceSha256: hash(await readFile(importer)),
      points: positions.length / 3, triangles: indices.length / 3, bounds,
      signedAreaXY, boundaryEdges: [...edges.values()].filter(count => count === 1).length,
      nonManifoldEdges: [...edges.values()].filter(count => count > 2).length }
  } catch (error) {
    if (!args.has('--expect-reject')) throw error
    if (result?.state === 'accepted') throw error
    result = { state: 'rejected', inputObjSha256: hash(bytes), importerSourceSha256: hash(await readFile(importer)), reason: String(error) }
  }
} finally {
  await server.close()
}
await writeFile(resolve(args.get('--result')), JSON.stringify(result, null, 2))
console.log(JSON.stringify(result))
