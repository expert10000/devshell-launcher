// Export the promoted broker mesh using MATH3D's native M3DM codec.
import { createHash } from 'node:crypto'
import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { parseObj } from '../math3d-native-protocol.mjs'

const options = new Map()
for (let index = 2; index < process.argv.length; index += 2) options.set(process.argv[index], process.argv[index + 1])
for (const key of ['--checkout', '--handoff', '--promotion', '--promotion-sha256', '--output'])
  if (!options.has(key)) throw new Error(`${key} is required.`)
const sha = bytes => createHash('sha256').update(bytes).digest('hex')
const checkout = resolve(options.get('--checkout'))
const handoffBytes = await readFile(resolve(options.get('--handoff')))
const promotionBytes = await readFile(resolve(options.get('--promotion')))
if (sha(promotionBytes) !== options.get('--promotion-sha256')) throw new Error('Promotion record hash mismatch.')
const handoff = JSON.parse(handoffBytes)
const promotion = JSON.parse(promotionBytes)
const request = JSON.parse(await readFile(handoff.workerRequest.path, 'utf8'))
if (promotion.schemaVersion !== 1 || promotion.kind !== 'scientific.math3d-promotion'
  || promotion.decision !== 'allowed' || promotion.contractVersion !== 1
  || promotion.sourceJobId !== request.runId || promotion.handoffSha256 !== sha(handoffBytes)
  || promotion.artifactSha256 !== handoff.artifact.sha256)
  throw new Error('MATH3D promotion is blocked or does not match this broker job.')
const sourceBytes = await readFile(handoff.artifact.path)
if (sha(sourceBytes) !== handoff.artifact.sha256) throw new Error('Promoted source artifact hash mismatch.')
const { vertices, faces } = parseObj(sourceBytes.toString('utf8'))
if (vertices.length !== 4 || faces.length !== 4) throw new Error('The fixed qualified mesh geometry changed.')
const positions = new Float32Array(vertices.flat())
const indices = new Uint32Array(faces.flat())
const codecPath = join(checkout, 'src', 'main', 'python', 'nativeCgalProtocol.ts')
const { encodeM3DMesh, decodeM3DMesh } = await import(pathToFileURL(codecPath).href)
const output = resolve(options.get('--output'))
await mkdir(output, { recursive: true })
const bytes = encodeM3DMesh(positions, indices)
const path = join(output, 'qualified-mesh.m3dm')
await writeFile(path, bytes)
const reloaded = decodeM3DMesh(await readFile(path))
if (reloaded.vertexCount !== vertices.length || reloaded.triCount !== faces.length
  || !Buffer.from(reloaded.positions).equals(Buffer.from(positions.buffer))
  || !Buffer.from(reloaded.indices).equals(Buffer.from(indices.buffer)))
  throw new Error('MATH3D could not reload the saved M3DM mesh.')
const report = { schemaVersion: 1, sourceJobId: request.runId, promotionId: promotion.promotionId,
  promotionSha256: sha(promotionBytes), sourceArtifactSha256: sha(sourceBytes),
  m3dmSha256: sha(bytes), codecSourceSha256: sha(await readFile(codecPath)),
  format: 'M3DM', version: 1, points: vertices.length, triangles: faces.length,
  math3dReload: 'passed' }
await writeFile(join(output, 'm3dm-write.json'), JSON.stringify(report))
