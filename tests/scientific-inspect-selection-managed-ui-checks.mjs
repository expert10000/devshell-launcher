// Live four-role product journey in DevShell's managed Scientific Integration panel.
import assert from 'node:assert/strict'
import { existsSync, readFileSync, readdirSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { join } from 'node:path'
import { setTimeout as delay } from 'node:timers/promises'
import { scientificDesktopPage } from './scientific-desktop-page.mjs'

const require = createRequire(import.meta.url)
const { chromium } = require(join(import.meta.dirname, '..', 'DevShell', 'ui', 'dev-ui-react', 'node_modules', 'playwright-core'))
const runs = process.env.DEVSHELL_SCIENTIFIC_RUNS_ROOT
const classRecord = process.env.DEVSHELL_DESKTOP_CLASS_RECORD
const acceptedInput = process.env.DEVSHELL_DESKTOP_INSPECT_INPUT
const fallbackInput = process.env.DEVSHELL_DESKTOP_FALLBACK_INPUT
const output = process.env.DEVSHELL_DESKTOP_JOURNEY_RUNS
for (const [name, value] of Object.entries({ runs, classRecord, acceptedInput, fallbackInput, output }))
  assert.ok(value, `Set ${name} for the managed inspection journey`)

async function completed(before, expectedState, timeoutMs = 600_000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    for (const name of readdirSync(runs)) {
      if (before.has(name) || !/^[0-9a-f]{32}$/.test(name)) continue
      const path = join(runs, name, 'results.json')
      if (!existsSync(path)) continue
      let result
      try { result = JSON.parse(readFileSync(path, 'utf8')) } catch { continue }
      if (result.recipeId !== 'l9.math3d-inspect-selection') continue
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
  await panel.getByLabel('Bounded inspection class record').fill(classRecord)
  await panel.getByLabel('Inspection OBJ input').fill(acceptedInput)
  await panel.getByRole('button', { name: 'Verify and preview' }).click()
  await panel.getByRole('status').filter({ hasText: /selected cgal-win-conda/ }).first().waitFor()

  const ids = {}
  for (const [role, input, provider, state] of [
    ['automatic', acceptedInput, '', 'succeeded'],
    ['manual', acceptedInput, 'vtk-win-conda', 'succeeded'],
    ['fallback', fallbackInput, '', 'succeeded'],
    ['cancelled', acceptedInput, '', 'cancelled'],
  ]) {
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
    if (role === 'automatic') assert.equal(result.selection.selectedProvider, 'cgal-win-conda')
    if (role === 'manual') assert.equal(result.selection.selectedProvider, provider)
    if (role === 'fallback') assert.equal(result.selection.selectedProvider, 'math3d-direct')
    ids[role] = join(runs, name)
    console.log(`${role}: ${name}`)
  }
  writeFileSync(output, JSON.stringify(ids, null, 2))
} finally {
  await browser.close()
}
