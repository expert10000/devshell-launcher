import { test } from 'node:test'
import assert from 'node:assert/strict'
import { runtimeEvidenceLabel } from '../DevShell/ui/dev-ui-react/src/scientificRuntimeEvidence.ts'

test('missing and failed inventory cannot reuse a prior recorded success', () => {
  assert.match(runtimeEvidenceLabel({ configured: true, loading: false, loadError: '', recordedState: undefined }), /Inventory missing/)
  assert.equal(runtimeEvidenceLabel({ configured: true, loading: false, loadError: 'missing file', recordedState: 'ready' }), 'Inventory load failed')
  assert.equal(runtimeEvidenceLabel({ configured: true, loading: true, loadError: '', recordedState: 'ready' }), 'Inventory loading')
})

test('recorded ready and managed success stay separate from qualification', () => {
  const label = runtimeEvidenceLabel({ configured: true, loading: false, loadError: '', recordedState: 'ready', version: '9.6.1', managedJobState: 'succeeded' })
  assert.equal(label, 'Recorded ready / 9.6.1 / managed test succeeded')
  assert.ok(!label.toLowerCase().includes('qualified'))
  assert.equal(runtimeEvidenceLabel({ configured: true, loading: false, loadError: '', recordedState: 'failed' }), 'Recorded failed / unknown version')
})

test('unconfigured provider and edited definition never inherit installation evidence', () => {
  assert.equal(runtimeEvidenceLabel({ configured: false, loading: false, loadError: '', recordedState: 'ready' }), 'Not configured')
  assert.equal(runtimeEvidenceLabel({ configured: true, loading: false, loadError: '', recordedState: 'ready', edited: true }), 'Definition edited / recorded evidence stale')
})
