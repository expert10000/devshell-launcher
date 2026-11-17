// Live product journey, including abstaining torus and large-star classes.
import assert from 'node:assert/strict'
import { existsSync, readFileSync, readdirSync, renameSync, writeFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { createRequire } from 'node:module'
import { join } from 'node:path'
import { setTimeout as delay } from 'node:timers/promises'
import { scientificDesktopPage } from './scientific-desktop-page.mjs'
import { open as openCheckpoint, readAction, record as recordAction } from '../tools/scientific-broker/desktop_journey_checkpoint.mjs'

const require = createRequire(import.meta.url)
const { chromium } = require(join(import.meta.dirname, '..', 'DevShell', 'ui', 'dev-ui-react', 'node_modules', 'playwright-core'))
const runs = process.env.DEVSHELL_SCIENTIFIC_RUNS_ROOT
const classRecord = process.env.DEVSHELL_DESKTOP_CLASS_RECORD
const acceptedInput = process.env.DEVSHELL_DESKTOP_INSPECT_INPUT
const fallbackInput = process.env.DEVSHELL_DESKTOP_FALLBACK_INPUT
const torusInput = process.env.DEVSHELL_DESKTOP_TORUS_INPUT
const starInput = process.env.DEVSHELL_DESKTOP_STAR_INPUT
const output = process.env.DEVSHELL_DESKTOP_JOURNEY_RUNS
for (const [name, value] of Object.entries({ runs, classRecord, acceptedInput, fallbackInput,
  torusInput, starInput, output }))
  assert.ok(value, `Set ${name} for the managed inspection journey`)
const sourceCommit = process.env.DEVSHELL_DESKTOP_SOURCE_COMMIT
const math3dCommit = process.env.DEVSHELL_DESKTOP_MATH3D_COMMIT
assert.ok(sourceCommit && math3dCommit, 'Pass release source and MATH3D identities to the desktop journey')
const sha = path => createHash('sha256').update(readFileSync(path)).digest('hex')
const checkpointPath = `${output}.checkpoint.json`
const checkpoint = openCheckpoint(checkpointPath, {
  runs, classRecord, classRecordSha256: sha(classRecord), acceptedSha256: sha(acceptedInput),
  fallbackSha256: sha(fallbackInput), torusSha256: sha(torusInput), starSha256: sha(starInput),
  sourceCommit, math3dCommit,
})

async function completed(before, expectedState, recipeId = 'l9.math3d-inspect-selection', timeoutMs = 600_000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    for (const name of readdirSync(runs)) {
      if (before.has(name) || !/^[0-9a-f]{32}$/.test(name)) continue
      const path = join(runs, name, 'results.json')
      if (!existsSync(path)) continue
      let result
      try { result = JSON.parse(readFileSync(path, 'utf8')) } catch { continue }
      if (result.recipeId !== recipeId) continue
      assert.equal(result.state, expectedState, `${name}: ${result.state} / ${JSON.stringify(result.diagnostics)}`)
      return { name, result }
    }
    await delay(500)
  }
  throw new Error(`Managed inspection did not finish as ${expectedState}`)
}

const browser = await chromium.connectOverCDP(process.env.DEVSHELL_CDP_URL)
try {
  const page = await scientificDesktopPage(browser)
  page.setDefaultTimeout(120_000)
  await page.getByText('RUNTIMES / Scientific', { exact: true }).click()
  const main = page.getByRole('main', { name: 'Scientific Runtimes' })
  await main.getByLabel('Scientific execution environment').selectOption('windows-native')
  await main.locator('.scientific-runtime-item').filter({ hasText: 'CGAL' }).first().click()
  await main.getByRole('navigation', { name: 'Scientific runtime sections' })
    .getByRole('button', { name: 'Integration', exact: true }).click()
  const panel = main.getByRole('region', { name: 'MATH3D inspection backend selection' })
  async function ensurePanel() {
    if (await panel.isVisible().catch(() => false)) return
    await page.getByText('RUNTIMES / Scientific', { exact: true }).click()
    await main.getByLabel('Scientific execution environment').selectOption('windows-native')
    await main.locator('.scientific-runtime-item').filter({ hasText: 'CGAL' }).first().click()
    await main.getByRole('navigation', { name: 'Scientific runtime sections' })
      .getByRole('button', { name: 'Integration', exact: true }).click()
    await panel.waitFor()
    await panel.getByLabel('Bounded inspection class record').fill(classRecord)
  }
  await panel.getByLabel('Bounded inspection class record').fill(classRecord)
  await panel.getByLabel('Inspection OBJ input').fill(acceptedInput)
  if (!readAction(checkpoint, 'previewCancelled')) {
    const before = new Set(readdirSync(runs))
    await panel.getByRole('button', { name: 'Verify and preview' }).click()
    await panel.getByRole('button', { name: 'Stop', exact: true }).click()
    const saved = await completed(before, 'cancelled', 'l9.math3d-inspect-preview')
    recordAction(checkpointPath, checkpoint, 'previewCancelled', saved.name)
  }
  let previewRun = readAction(checkpoint, 'previewSucceeded')
  if (!previewRun) {
    const before = new Set(readdirSync(runs))
    await panel.getByRole('button', { name: 'Verify and preview' }).click()
    const saved = await completed(before, 'succeeded', 'l9.math3d-inspect-preview')
    previewRun = recordAction(checkpointPath, checkpoint, 'previewSucceeded', saved.name)
    const preview = panel.getByRole('status').filter({ hasText: /selected (?:cgal|vtk)-win-conda/ }).first()
    await preview.waitFor({ timeout: 210_000 })
  }
  assert.ok(previewRun.result.selection?.selectedProvider)
  const automaticProvider = previewRun.result.selection.selectedProvider
  assert.ok(automaticProvider, 'No qualified automatic provider for the accepted class')
  await panel.getByLabel('Inspection OBJ input').fill(fallbackInput)
  const preview = panel.getByRole('status').filter({ hasText: /selected (?:cgal|vtk)-win-conda/ }).first()
  assert.equal(await preview.count(), 0, 'Changing input retained an older recommendation')
  await panel.getByLabel('Inspection OBJ input').fill(acceptedInput)
  const manualProvider = automaticProvider === 'cgal-win-conda' ? 'vtk-win-conda' : 'cgal-win-conda'

  const ids = {}
  for (const [role, input, expected] of [
    ['previewTorus', torusInput, process.env.DEVSHELL_DESKTOP_TORUS_RECOMMENDATION || ''],
    ['previewStar', starInput, process.env.DEVSHELL_DESKTOP_STAR_RECOMMENDATION || ''],
  ]) {
    const prior = readAction(checkpoint, role)
    if (prior) {
      ids[role] = join(runs, prior.name)
      continue
    }
    await ensurePanel()
    await panel.getByLabel('Inspection OBJ input').fill(input)
    await panel.getByLabel('Inspection provider override').selectOption('')
    const before = new Set(readdirSync(runs))
    await panel.getByRole('button', { name: 'Verify and preview' }).click()
    const saved = await completed(before, 'succeeded', 'l9.math3d-inspect-preview')
    assert.equal(saved.result.selection?.selectedProvider, expected || 'math3d-direct')
    assert.equal(saved.result.selection?.state, expected ? 'ranked' : 'fallback')
    recordAction(checkpointPath, checkpoint, role, saved.name)
    ids[role] = join(runs, saved.name)
    console.log(`${role}: ${saved.name}`)
  }

  for (const [role, input, provider, state] of [
    ['automatic', acceptedInput, '', 'succeeded'],
    ['manual', acceptedInput, manualProvider, 'succeeded'],
    ['fallback', fallbackInput, '', 'succeeded'],
    ['cancelled', acceptedInput, '', 'cancelled'],
    ['torusManual', torusInput, 'cgal-win-conda', 'succeeded'],
    ['starManual', starInput, 'vtk-win-conda', 'succeeded'],
  ]) {
    const prior = readAction(checkpoint, role)
    if (prior) {
      ids[role] = join(runs, prior.name)
      console.log(`${role}: ${prior.name} (verified checkpoint)`)
      continue
    }
    await ensurePanel()
    await panel.getByLabel('Inspection OBJ input').fill(input)
    await panel.getByLabel('Inspection provider override').selectOption(provider)
    const before = new Set(readdirSync(runs))
    await panel.getByRole('button', { name: 'Run and reopen in MATH3D' }).click()
    if (role === 'cancelled') {
      await panel.getByRole('button', { name: 'Stop', exact: true }).click()
    }
    const { name, result } = await completed(before, state)
    if (role !== 'cancelled') {
      assert.ok(result.selection?.productFiles?.['read.m3dm'])
      assert.ok(result.selection?.productFiles?.['viewer.json'])
    }
    if (role === 'automatic') assert.equal(result.selection.selectedProvider, automaticProvider)
    if (role === 'manual' || role === 'torusManual' || role === 'starManual')
      assert.equal(result.selection.selectedProvider, provider)
    if (role === 'torusManual' || role === 'starManual') {
      assert.equal(result.selection.recommendedProvider,
        (role === 'torusManual' ? process.env.DEVSHELL_DESKTOP_TORUS_RECOMMENDATION
          : process.env.DEVSHELL_DESKTOP_STAR_RECOMMENDATION) || null)
      assert.equal(result.selection.state, 'manual')
    }
    if (role === 'fallback') assert.equal(result.selection.selectedProvider, 'math3d-direct')
    recordAction(checkpointPath, checkpoint, role, name)
    ids[role] = join(runs, name)
    console.log(`${role}: ${name}`)
  }
  writeFileSync(`${output}.tmp`, JSON.stringify(ids, null, 2))
  renameSync(`${output}.tmp`, output)
} finally {
  await browser.close()
}
