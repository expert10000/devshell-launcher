import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { open, readAction, record, save } from '../tools/scientific-broker/desktop_journey_checkpoint.mjs'

const root = mkdtempSync(join(tmpdir(), 'desktop-journey-'))
try {
  const runId = 'a'.repeat(32)
  const directory = join(root, 'runs', runId)
  mkdirSync(directory, { recursive: true })
  const sha = value => createHash('sha256').update(value).digest('hex')
  const context = { runs: join(root, 'runs'), classRecord: join(root, 'classes.json'),
    classRecordSha256: 'b'.repeat(64), acceptedSha256: 'c'.repeat(64),
    fallbackSha256: 'd'.repeat(64), sourceCommit: 'e'.repeat(40), math3dCommit: 'f'.repeat(40) }
  const request = { runId, recipeId: 'l9.math3d-inspect-selection',
    inputArtifacts: [{ sha256: context.acceptedSha256 }], parameters: { classRecord: context.classRecord } }
  const result = { runId, recipeId: request.recipeId, state: 'succeeded', selection: { selectedProvider: 'cgal-win-conda' } }
  const snapshot = { repositories: { devshell: { commit: context.sourceCommit }, math3d: { commit: context.math3dCommit } } }
  writeFileSync(join(directory, 'request.json'), JSON.stringify(request))
  writeFileSync(join(directory, 'results.json'), JSON.stringify(result))
  writeFileSync(join(directory, 'source-snapshot.json'), JSON.stringify(snapshot))
  const path = join(root, 'checkpoint.json')
  const value = open(path, context)
  record(path, value, 'automatic', runId)
  assert.equal(readAction(open(path, context), 'automatic').name, runId)
  assert.throws(() => open(path, { ...context, sourceCommit: '0'.repeat(40) }), /source identity/)
  const altered = JSON.parse(readFileSync(path, 'utf8'))
  altered.actions.automatic.resultSha256 = sha('changed')
  writeFileSync(path, JSON.stringify(altered))
  assert.throws(() => open(path, context), /seal/)
  save(path, value)
  writeFileSync(join(directory, 'results.json'), JSON.stringify({ ...result, state: 'running' }))
  assert.throws(() => open(path, context), /evidence changed/)
  writeFileSync(join(directory, 'results.json'), JSON.stringify(result))
  const incomplete = { ...value, actions: {} }
  assert.equal(readAction(incomplete, 'automatic'), null)
  assert.equal(Object.keys(incomplete.actions).length, 0)
} finally {
  rmSync(root, { recursive: true, force: true })
}
