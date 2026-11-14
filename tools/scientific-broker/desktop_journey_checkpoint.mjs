import { createHash } from 'node:crypto'
import { existsSync, readFileSync, renameSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

const names = new Set(['previewCancelled', 'previewSucceeded', 'previewTorus', 'previewStar',
  'automatic', 'manual', 'fallback', 'cancelled', 'torusManual', 'starManual'])
const digest = bytes => createHash('sha256').update(bytes).digest('hex')
const fileHash = path => digest(readFileSync(path))
const body = value => JSON.stringify(Object.fromEntries(Object.entries(value).filter(([key]) => key !== 'checkpointSha256')))

export function save(path, value) {
  value.checkpointSha256 = digest(body(value))
  const temporary = `${path}.tmp`
  writeFileSync(temporary, JSON.stringify(value, null, 2))
  renameSync(temporary, path)
}

export function open(path, context) {
  if (!existsSync(path)) {
    const value = { schemaVersion: 1, kind: 'scientific.desktop-inspect-journey-checkpoint', context, actions: {} }
    save(path, value)
    return value
  }
  const value = JSON.parse(readFileSync(path, 'utf8'))
  if (value.schemaVersion !== 1 || value.kind !== 'scientific.desktop-inspect-journey-checkpoint'
      || value.checkpointSha256 !== digest(body(value)) || JSON.stringify(value.context) !== JSON.stringify(context))
    throw new Error('Desktop journey checkpoint seal or source identity changed.')
  for (const name of Object.keys(value.actions)) readAction(value, name)
  return value
}

export function readAction(value, name) {
  if (!names.has(name)) throw new Error('Unknown desktop journey action.')
  const saved = value.actions[name]
  if (!saved) return null
  if (!/^[0-9a-f]{32}$/.test(saved.runId)) throw new Error('Invalid desktop journey run ID.')
  const directory = join(value.context.runs, saved.runId)
  const paths = { request: join(directory, 'request.json'), result: join(directory, 'results.json'),
    snapshot: join(directory, 'source-snapshot.json') }
  if (fileHash(paths.request) !== saved.requestSha256 || fileHash(paths.result) !== saved.resultSha256
      || fileHash(paths.snapshot) !== saved.snapshotSha256)
    throw new Error(`${name} desktop journey evidence changed.`)
  const request = JSON.parse(readFileSync(paths.request, 'utf8'))
  const result = JSON.parse(readFileSync(paths.result, 'utf8'))
  const snapshot = JSON.parse(readFileSync(paths.snapshot, 'utf8'))
  const preview = name.startsWith('preview')
  const expectedState = name === 'cancelled' || name === 'previewCancelled' ? 'cancelled' : 'succeeded'
  const expectedRecipe = preview ? 'l9.math3d-inspect-preview' : 'l9.math3d-inspect-selection'
  const inputHash = name === 'fallback' ? value.context.fallbackSha256
    : name === 'previewTorus' || name === 'torusManual' ? value.context.torusSha256
      : name === 'previewStar' || name === 'starManual' ? value.context.starSha256
        : value.context.acceptedSha256
  if (request.runId !== saved.runId || result.runId !== saved.runId
      || request.recipeId !== expectedRecipe || result.recipeId !== expectedRecipe
      || result.state !== expectedState || request.inputArtifacts?.[0]?.sha256 !== inputHash
      || request.parameters?.classRecord !== value.context.classRecord
      || snapshot.repositories?.devshell?.commit !== value.context.sourceCommit
      || snapshot.repositories?.math3d?.commit !== value.context.math3dCommit
      || (expectedState === 'cancelled' && result.selection)
      || (expectedState === 'succeeded' && !result.selection))
    throw new Error(`${name} desktop journey action is incomplete or stale.`)
  return { name: saved.runId, result }
}

export function record(path, value, name, runId) {
  if (!names.has(name) || value.actions[name]) throw new Error('Desktop journey action already recorded.')
  const directory = join(value.context.runs, runId)
  const saved = { runId, requestSha256: fileHash(join(directory, 'request.json')),
    resultSha256: fileHash(join(directory, 'results.json')),
    snapshotSha256: fileHash(join(directory, 'source-snapshot.json')) }
  value.actions[name] = saved
  try { readAction(value, name) } catch (error) { delete value.actions[name]; throw error }
  save(path, value)
  return readAction(value, name)
}
