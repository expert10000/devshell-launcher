// Record live class selection, MATH3D reload, and managed cancellation in DevShell.
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, join } from 'node:path'
import { setTimeout as delay } from 'node:timers/promises'

const require = createRequire(import.meta.url)
const { chromium } = require(join(import.meta.dirname, '..', 'DevShell', 'ui', 'dev-ui-react', 'node_modules', 'playwright-core'))
const runs = process.env.DEVSHELL_SCIENTIFIC_RUNS_ROOT
const releasePath = process.env.DEVSHELL_INSPECT_RELEASE_RECORD
const classPath = process.env.DEVSHELL_INSPECT_CLASS_RECORD
const inputPath = process.env.DEVSHELL_INSPECT_INPUT
const outputPath = process.env.DEVSHELL_INSPECT_DESKTOP_RECORD
for (const value of [runs, releasePath, classPath, inputPath, outputPath, process.env.DEVSHELL_CDP_URL]) assert.ok(value, 'Desktop selection evidence environment is incomplete')
const sha = path => createHash('sha256').update(readFileSync(path)).digest('hex')
const release = JSON.parse(readFileSync(releasePath, 'utf8'))
const sourceRoot = dirname(dirname(runs))
assert.equal(execFileSync('git', ['-C', sourceRoot, 'rev-parse', 'HEAD'], { encoding: 'utf8' }).trim(), release.sourceCommit)

async function finished(before, expectedState) {
  const deadline = Date.now() + 600_000
  while (Date.now() < deadline) {
    for (const name of readdirSync(runs)) {
      if (before.has(name) || !/^[0-9a-f]{32}$/.test(name)) continue
      const path = join(runs, name, 'results.json')
      if (!existsSync(path)) continue
      let result
      try { result = JSON.parse(readFileSync(path, 'utf8')) } catch { continue }
      if (result.recipeId !== 'l9.math3d-inspect-selection') continue
      if (!['succeeded', 'cancelled', 'failed', 'timed-out'].includes(result.state)) continue
      assert.equal(result.state, expectedState, `${result.state}: ${JSON.stringify(result.diagnostics)}`)
      return { runId: name, resultPath: path, resultSha256: sha(path), result }
    }
    await delay(250)
  }
  throw new Error(`Managed inspection ${expectedState} timed out`)
}

const browser = await chromium.connectOverCDP(process.env.DEVSHELL_CDP_URL)
try {
  const page = browser.contexts().flatMap(context => context.pages()).find(item => item.url().includes('app.local'))
  assert.ok(page, 'DevShell app page is unavailable')
  page.setDefaultTimeout(120_000)
  await page.getByText('RUNTIMES / Scientific', { exact: true }).click()
  const main = page.getByRole('main', { name: 'Scientific Runtimes' })
  await main.getByLabel('Scientific execution environment').selectOption('windows-native')
  await main.locator('.scientific-runtime-item').filter({ hasText: 'CGAL' }).first().click()
  await main.getByRole('navigation', { name: 'Scientific runtime sections' }).getByRole('button', { name: 'Integration', exact: true }).click()
  const panel = main.getByRole('region', { name: 'MATH3D inspection backend selection' })
  await panel.getByLabel('Inspection OBJ input').fill(inputPath)
  await panel.getByLabel('Bounded inspection class record').fill(classPath)
  await panel.getByRole('button', { name: 'Verify and preview' }).click()
  await panel.getByRole('status').first().getByText(/selected/).waitFor()
  const automaticText = await panel.getByRole('status').first().innerText()
  assert.match(automaticText, /tetra-uniform-4|octa-uniform-8|cube-uniform-12/)
  assert.match(automaticText, /selected (cgal-win-conda|vtk-win-conda)/)

  await panel.getByLabel('Inspection provider override').selectOption('vtk-win-conda')
  await panel.getByRole('button', { name: 'Verify and preview' }).click()
  await panel.getByRole('status').first().getByText(/selected vtk-win-conda/).waitFor()
  const manualText = await panel.getByRole('status').first().innerText()
  assert.match(manualText, /manual/i)
  await panel.getByLabel('Inspection provider override').selectOption('')

  const beforeSuccess = new Set(readdirSync(runs))
  await panel.getByRole('button', { name: 'Run and reopen in MATH3D' }).click()
  const success = await finished(beforeSuccess, 'succeeded')
  const selectionPath = join(runs, success.runId, 'product-selection', 'selection.json')
  assert.ok(existsSync(selectionPath))
  const selection = JSON.parse(readFileSync(selectionPath, 'utf8'))
  assert.equal(selection.classRecordSha256, sha(classPath))
  assert.equal(selection.inputSha256, sha(inputPath))
  assert.ok(selection.productFiles?.['read.m3dm'] && selection.productFiles?.['viewer.png'])
  assert.equal(success.result.selection?.classId, selection.classId)
  await panel.getByRole('status').last().getByText(/succeeded/).waitFor()

  const beforeCancel = new Set(readdirSync(runs))
  await panel.getByRole('button', { name: 'Run and reopen in MATH3D' }).click()
  await panel.getByRole('button', { name: 'Stop', exact: true }).click()
  const cancelled = await finished(beforeCancel, 'cancelled')
  assert.deepEqual(cancelled.result.artifacts, [])
  assert.deepEqual(cancelled.result.validatedCapabilities, [])
  await panel.getByRole('status').last().getByText(/cancelled/).waitFor()

  const record = { schemaVersion: 1, kind: 'scientific.live-desktop-inspect-selection',
    sourceCommit: release.sourceCommit, releaseRecordSha256: sha(releasePath),
    classRecordSha256: sha(classPath), inputSha256: sha(inputPath),
    automaticText, manualText, success: { runId: success.runId, resultPath: success.resultPath,
      resultSha256: success.resultSha256, selectionPath, selectionSha256: sha(selectionPath) },
    cancellation: { runId: cancelled.runId, resultPath: cancelled.resultPath,
      resultSha256: cancelled.resultSha256 } }
  mkdirSync(dirname(outputPath), { recursive: true })
  writeFileSync(outputPath, JSON.stringify(record, null, 2))
  writeFileSync(`${outputPath}.sha256`, sha(outputPath))
  console.log(`LIVE_DESKTOP_RECORD=${outputPath}`)
} finally {
  await browser.close()
}
