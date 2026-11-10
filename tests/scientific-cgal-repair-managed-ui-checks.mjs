// Opt-in live CGAL repair L0-L9 acceptance on a debug-port DevShell session.
import assert from 'node:assert/strict'
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { createRequire } from 'node:module'
import { join } from 'node:path'
import { setTimeout as delay } from 'node:timers/promises'

const require = createRequire(import.meta.url)
const { chromium } = require(join(import.meta.dirname, '..', 'DevShell', 'ui', 'dev-ui-react', 'node_modules', 'playwright-core'))
const runs = join(import.meta.dirname, '..', '.scientific', 'runs')

async function newRun(previous, recipe, level, capability = 'mesh.repair') {
  const deadline = Date.now() + 600_000
  while (Date.now() < deadline) {
    for (const name of readdirSync(runs)) {
      if (previous.has(name) || !/^[0-9a-f]{32}$/.test(name)) continue
      const folder = join(runs, name)
      const path = join(folder, 'results.json')
      if (!existsSync(path)) continue
      const result = JSON.parse(readFileSync(path, 'utf8'))
      if (result.runtimeId !== 'cgal-win-conda' || result.recipeId !== recipe) continue
      if (result.state && result.state !== 'succeeded')
        throw new Error(`${recipe} ended ${result.state}: ${JSON.stringify(result.diagnostics || result.error)}`)
      if (![join(folder, 'fingerprint.json'), join(folder, 'qualifications.json')].every(existsSync)) continue
      const qualifications = JSON.parse(readFileSync(join(folder, 'qualifications.json'), 'utf8'))
      assert.ok(qualifications.records.some(item => item.level === level && item.capabilityId === capability),
        `${recipe} did not issue ${capability}@${level}`)
      return { folder, result, qualifications }
    }
    await delay(500)
  }
  throw new Error(`${recipe} did not save a managed qualification`)
}

if (!process.env.DEVSHELL_CDP_URL) throw new Error('Set DEVSHELL_CDP_URL to the running DevShell debug endpoint.')
const browser = await chromium.connectOverCDP(process.env.DEVSHELL_CDP_URL)
try {
  const page = browser.contexts().flatMap(context => context.pages()).find(item => item.url().includes('app.local'))
  assert.ok(page, 'DevShell app page is unavailable')
  page.setDefaultTimeout(120_000)
  await page.getByText('RUNTIMES / Scientific', { exact: true }).click()
  const main = page.getByRole('main', { name: 'Scientific Runtimes' })
  await main.getByLabel('Scientific execution environment').selectOption('windows-native')
  await main.locator('.scientific-runtime-item').filter({ hasText: 'CGAL' }).first().click()
  const nav = main.getByRole('navigation', { name: 'Scientific runtime sections' })
  await nav.getByRole('button', { name: 'Commands', exact: true }).click()
  const detail = main.getByRole('region', { name: /runtime details/ })
  for (const [button, recipe] of [['Probe in runtime-lab', 'lab.probe'], ['Compile & link', 'compile-link']]) {
    const previous = new Set(readdirSync(runs))
    await detail.getByRole('button', { name: button, exact: true }).click()
    await newRun(previous, recipe, 'L0', 'runtime.inventory')
  }
  await nav.getByRole('button', { name: 'Recipes', exact: true }).click()
  await detail.getByRole('button', { name: 'Repair holes', exact: true }).click()
  await detail.getByRole('button', { name: 'Load repair fixtures', exact: true }).click()
  const cases = [
    ['Run repair L5 qualification', 'l5.cgal-repair', 'L5'],
    ['Reproduce repair L6', 'l6.cgal-repair', 'L6'],
    ['Check repair L7 consumers', 'l7.cgal-repair', 'L7'],
    ['Test repair L8 resilience', 'l8.cgal-repair', 'L8'],
    ['Run repair L9 products', 'l9.cgal-repair', 'L9']
  ]
  for (const [button, recipe, level] of cases) {
    const previous = new Set(readdirSync(runs))
    await detail.getByRole('button', { name: button, exact: true }).click()
    const saved = await newRun(previous, recipe, level)
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
