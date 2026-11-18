// Opt-in live DevShell journey. Run against a clean committed checkout and pulled MATH3D.
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { createRequire } from 'node:module'
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { setTimeout as delay } from 'node:timers/promises'
import { scientificDesktopPage } from './scientific-desktop-page.mjs'

const require = createRequire(import.meta.url)
const root = process.env.DEVSHELL_TYPED_WORKTREE_ROOT || join(import.meta.dirname, '..')
const { chromium } = require(join(root, 'DevShell', 'ui', 'dev-ui-react', 'node_modules', 'playwright-core'))
const dataRoot = join(root, '.scientific')
const runs = join(dataRoot, 'runs')
const datasets = join(dataRoot, 'datasets')
const sha = bytes => createHash('sha256').update(bytes).digest('hex')
assert.ok(process.env.DEVSHELL_CDP_URL, 'Set DEVSHELL_CDP_URL to the owned DevShell CDP endpoint.')
mkdirSync(runs, { recursive: true }); mkdirSync(datasets, { recursive: true })

// Known, outward closed primitive and an independent scaled source copy.
const original = readFileSync(join(root, 'scientific', 'fixtures', 'cgal-repair-quad', 'cube-closed.obj'), 'utf8')
const smaller = original.split(/\r?\n/).map(line => line.startsWith('v ')
  ? `v ${line.slice(2).split(' ').map(value => String(Number(value) / 2)).join(' ')}` : line).join('\n')
const entries = [original, smaller].map((content, index) => {
  const bytes = Buffer.from(content)
  const hash = sha(bytes)
  const name = index ? 'cube-half.obj' : 'cube-full.obj'
  const id = `imported/${hash}/mesh-${name}`
  const path = join(datasets, ...id.split('/'))
  mkdirSync(join(datasets, 'imported', hash), { recursive: true })
  if (existsSync(path)) assert.equal(sha(readFileSync(path)), hash)
  else writeFileSync(path, bytes)
  return { id, path: id, name, category: 'Imported', bytes: bytes.length, sha256: hash,
    sourcePath: name, sourceRoot: 'authored test fixture', expectedProblem: false, validation: { state: 'not-checked' } }
})
assert.notEqual(entries[0].sha256, entries[1].sha256)
const manifestPath = join(datasets, 'manifest.json')
const existing = existsSync(manifestPath) ? JSON.parse(readFileSync(manifestPath, 'utf8')) : { schemaVersion: 1, entries: [] }
assert.equal(existing.schemaVersion, 1)
assert.ok(Array.isArray(existing.entries))
writeFileSync(manifestPath, JSON.stringify({ ...existing,
  entries: [...existing.entries.filter(item => !entries.some(entry => entry.id === item.id)), ...entries] }))

async function completed(before, recipeId, expected = 'succeeded', timeoutMs = 600_000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    for (const name of readdirSync(runs)) {
      if (before.has(name) || !/^[0-9a-f]{32}$/.test(name)) continue
      const folder = join(runs, name)
      const path = join(folder, 'results.json')
      if (!existsSync(path) || !existsSync(join(folder, 'fingerprint.json'))) continue
      let result
      try { result = JSON.parse(readFileSync(path, 'utf8')) } catch { continue }
      if (result.recipeId !== recipeId) continue
      assert.equal(result.state, expected, `${recipeId}: ${result.state} / ${JSON.stringify(result.diagnostics)}`)
      return { name, result, folder }
    }
    await delay(500)
  }
  throw new Error(`Managed ${recipeId} did not save a completed History record.`)
}

const browser = await chromium.connectOverCDP(process.env.DEVSHELL_CDP_URL)
try {
  const page = await scientificDesktopPage(browser)
  page.setDefaultTimeout(120_000)
  await page.getByText('RUNTIMES / Scientific', { exact: true }).click()
  const main = page.getByRole('main', { name: 'Scientific Runtimes' })
  await main.getByLabel('Scientific execution environment').selectOption('windows-native')
  await main.locator('.scientific-runtime-item').filter({ hasText: 'CGAL' }).first().click()
  const nav = main.getByRole('navigation', { name: 'Scientific runtime sections' })
  await nav.getByRole('button', { name: 'Boolean', exact: true }).click()
  const panel = main.getByRole('region', { name: 'Boolean mesh operation' })
  await panel.getByRole('button', { name: 'Refresh inputs and readiness' }).click()
  await delay(1000)
  if (await panel.getByRole('button', { name: 'Open preparation' }).isVisible()) {
    await panel.getByRole('button', { name: 'Open preparation' }).click()
    const preparation = main.getByRole('region', { name: 'MATH3D native worker integration' })
    const beforePreparation = new Set(readdirSync(runs))
    await preparation.getByRole('button', { name: 'Prepare & Run' }).click()
    const prepared = await completed(beforePreparation, 'integration.math3d.native-boolean', 'succeeded', 900_000)
    assert.equal(prepared.result.comparison.verdict, 'pass')
    await nav.getByRole('button', { name: 'Boolean', exact: true }).click()
    await panel.getByRole('button', { name: 'Refresh inputs and readiness' }).click()
  }
  await panel.getByLabel('Boolean mesh A').selectOption(entries[0].id)
  await panel.getByLabel('Boolean mesh B').selectOption(entries[1].id)
  await panel.getByLabel('Boolean operation').selectOption('union')
  await panel.locator('details').filter({ hasText: 'Mesh B placement' }).locator('summary').click()
  await panel.getByLabel('Offset X').fill('0.75')
  const beforeBoolean = new Set(readdirSync(runs))
  await panel.getByRole('button', { name: 'Run Boolean' }).click()
  const boolean = await completed(beforeBoolean, 'cgal.boolean')
  assert.equal(boolean.result.boolean.empty, false)
  assert.notEqual(boolean.result.inputArtifacts[0].sha256, boolean.result.inputArtifacts[1].sha256)
  await panel.getByRole('button', { name: 'Continue through Gmsh, VTK, SciPy and MATH3D' }).waitFor()
  const beforeJourney = new Set(readdirSync(runs))
  await panel.getByRole('button', { name: 'Continue through Gmsh, VTK, SciPy and MATH3D' }).click()
  const journey = await completed(beforeJourney, 'scientific.typed-journey')
  assert.equal(journey.result.sourceRunId, boolean.result.runId)
  assert.equal(journey.result.typedJourney.verification.verdict, 'verified-typed-product-relations')
  assert.equal(journey.result.typedJourney.coldReopen.newProcess, true)
  assert.equal(journey.result.typedJourney.scipy.measurement.unit, 'mm2')
  assert.equal(journey.result.typedJourney.gmsh.dimension, 3)
  assert.ok(journey.result.artifacts.some(item => item.path === 'vtk/preview.png'))
  await nav.getByRole('button', { name: 'History', exact: true }).click()
  await main.getByRole('button', { name: /Refresh history|Load history/ }).click()
  await main.locator(`[data-run-id="${journey.result.runId}"]`).getByRole('button', { name: 'Result' }).click()
  await main.getByRole('region', { name: 'Saved typed scientific journey' }).getByText('verified-typed-product-relations').waitFor()
  await main.locator(`[data-run-id="${boolean.result.runId}"]`).getByRole('button', { name: 'Result' }).click()
  const surface = join(boolean.folder, boolean.result.boolean.outputArtifact.replace(/\.m3dm$/, '.obj'))
  const originalSurface = readFileSync(surface)
  try {
    writeFileSync(surface, Buffer.concat([originalSurface, Buffer.from('\n# tampered\n')]))
    await main.getByRole('button', { name: /Continue typed Gmsh/ }).click()
    await main.getByRole('alert').filter({ hasText: /artifact changed/i }).waitFor()
  } finally { writeFileSync(surface, originalSurface) }
  const beforeCancelled = new Set(readdirSync(runs))
  await main.getByRole('button', { name: /Continue typed Gmsh/ }).click()
  await nav.getByRole('button', { name: 'Boolean', exact: true }).click()
  await panel.getByRole('button', { name: 'Stop journey' }).click()
  const cancelled = await completed(beforeCancelled, 'scientific.typed-journey', 'cancelled')
  assert.equal(cancelled.result.artifacts.length, 0)
  console.log(JSON.stringify({ verdict: 'managed-typed-journey-passed', booleanRunId: boolean.result.runId,
    journeyRunId: journey.result.runId, cancelledRunId: cancelled.result.runId,
    sourceCommit: journey.result.typedJourney.verification.sourceCommit,
    consumerCommit: journey.result.typedJourney.product.consumerCommit,
    documentId: journey.result.typedJourney.product.documentId }))
} finally { await browser.close() }
