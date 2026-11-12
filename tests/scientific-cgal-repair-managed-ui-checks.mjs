// Opt-in live CGAL repair L0-L9 acceptance on a debug-port DevShell session.
import assert from 'node:assert/strict'
import { existsSync, mkdirSync, readFileSync, readdirSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, join } from 'node:path'
import { setTimeout as delay } from 'node:timers/promises'
import { scientificDesktopPage } from './scientific-desktop-page.mjs'

const require = createRequire(import.meta.url)
const { chromium } = require(join(import.meta.dirname, '..', 'DevShell', 'ui', 'dev-ui-react', 'node_modules', 'playwright-core'))
const runs = process.env.DEVSHELL_SCIENTIFIC_RUNS_ROOT || join(import.meta.dirname, '..', '.scientific', 'runs')
const resumeFrom = process.env.DEVSHELL_REPAIR_RESUME_FROM || 'L0'
mkdirSync(runs, { recursive: true })

async function newRun(previous, recipe, level, capability = 'mesh.repair', page, priorAlerts = []) {
  const deadline = Date.now() + 600_000
  while (Date.now() < deadline) {
    for (const name of readdirSync(runs)) {
      if (previous.has(name) || !/^[0-9a-f]{32}$/.test(name)) continue
      const folder = join(runs, name)
      const path = join(folder, 'results.json')
      if (!existsSync(path)) continue
      let result
      try { result = JSON.parse(readFileSync(path, 'utf8')) } catch (error) {
        if (error instanceof SyntaxError) continue
        throw error
      }
      if (result.runtimeId !== 'cgal-win-conda' || result.recipeId !== recipe) continue
      if (result.state && result.state !== 'succeeded')
        throw new Error(`${recipe} ended ${result.state}: ${JSON.stringify(result.diagnostics || result.error)}`)
      if (![join(folder, 'fingerprint.json'), join(folder, 'qualifications.json')].every(existsSync)) continue
      let qualifications
      try { qualifications = JSON.parse(readFileSync(join(folder, 'qualifications.json'), 'utf8')) } catch (error) {
        if (error instanceof SyntaxError) continue
        throw error
      }
      assert.ok(qualifications.records.some(item => item.level === level && item.capabilityId === capability),
        `${recipe} did not issue ${capability}@${level}`)
      return { folder, result, qualifications }
    }
    const alerts = await page.getByRole('alert').allTextContents()
    const fresh = alerts.find(message => message && !priorAlerts.includes(message))
    if (fresh) throw new Error(`${recipe} was rejected before a run started: ${fresh}`)
    await delay(500)
  }
  throw new Error(`${recipe} did not save a managed qualification`)
}

if (!process.env.DEVSHELL_CDP_URL) throw new Error('Set DEVSHELL_CDP_URL to the running DevShell debug endpoint.')
const browser = await chromium.connectOverCDP(process.env.DEVSHELL_CDP_URL)
try {
  const page = await scientificDesktopPage(browser)
  page.setDefaultTimeout(120_000)
  await page.getByText('RUNTIMES / Scientific', { exact: true }).click()
  const main = page.getByRole('main', { name: 'Scientific Runtimes' })
  await main.getByLabel('Scientific execution environment').selectOption('windows-native')
  await main.locator('.scientific-runtime-item').filter({ hasText: 'CGAL' }).first().click()
  const nav = main.getByRole('navigation', { name: 'Scientific runtime sections' })
  await nav.getByRole('button', { name: 'Commands', exact: true }).click()
  const detail = main.getByRole('region', { name: /runtime details/ })
  for (const [button, recipe] of resumeFrom === 'L0'
    ? [['Probe in runtime-lab', 'lab.probe'], ['Compile & link', 'compile-link']] : []) {
    const previous = new Set(readdirSync(runs))
    const priorAlerts = await page.getByRole('alert').allTextContents()
    await detail.getByRole('button', { name: button, exact: true }).click()
    await newRun(previous, recipe, 'L0', 'runtime.inventory', page, priorAlerts)
  }
  await detail.getByRole('button', { name: 'Repair holes', exact: true }).click()
  if (resumeFrom === 'L0' || resumeFrom === 'L5') {
    const beforeFixtureAlerts = await page.getByRole('alert').allTextContents()
    await detail.getByRole('button', { name: 'Load repair fixtures', exact: true }).click()
    const registryPath = join(dirname(runs), 'datasets', 'manifest.json')
    const fixtureDeadline = Date.now() + 60_000
    let fixturesReady = false
    while (Date.now() < fixtureDeadline) {
      if (existsSync(registryPath)) {
        const registry = JSON.parse(readFileSync(registryPath, 'utf8'))
        if (registry.entries?.filter(item => item.id?.startsWith('imported/')).length >= 5) {
          fixturesReady = true
          break
        }
      }
      const alerts = await page.getByRole('alert').allTextContents()
      const fresh = alerts.find(message => message && !beforeFixtureAlerts.includes(message))
      if (fresh) throw new Error(`Repair fixture load failed: ${fresh}`)
      await delay(500)
    }
    assert.ok(fixturesReady, 'Repair fixture registration did not complete')
  }
  const cases = [
    ['Run repair L5 qualification', 'l5.cgal-repair', 'L5'],
    ['Reproduce repair L6', 'l6.cgal-repair', 'L6'],
    ['Check repair L7 consumers', 'l7.cgal-repair', 'L7'],
    ['Test repair L8 resilience', 'l8.cgal-repair', 'L8'],
    ['Run repair L9 products', 'l9.cgal-repair', 'L9']
  ]
  const first = resumeFrom === 'L0' ? 0 : cases.findIndex(item => item[2] === resumeFrom)
  assert.ok(first >= 0, `Unsupported repair resume level: ${resumeFrom}`)
  for (const [button, recipe, level] of cases.slice(first)) {
    const previous = new Set(readdirSync(runs))
    const priorAlerts = await page.getByRole('alert').allTextContents()
    await detail.getByRole('button', { name: button, exact: true }).click()
    const saved = await newRun(previous, recipe, level, 'mesh.repair', page, priorAlerts)
    if (level === 'L9') {
      assert.equal(saved.result.repairProductEvidence.cases.length, 4)
      assert.equal(saved.result.repairProductEvidence.negative.state, 'rejected')
      assert.equal(saved.result.repairProductEvidence.negative.outputAbsent, true)
    }
    console.log(`${recipe}: ${saved.result.runId} / mesh.repair@${level}`)
  }
} finally {
  await browser.close()
}
