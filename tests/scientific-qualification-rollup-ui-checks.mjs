// Opt-in desktop acceptance for current cross-run levels and fresh native L4 evidence.
import assert from 'node:assert/strict'
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { createRequire } from 'node:module'
import { join } from 'node:path'
import { setTimeout as delay } from 'node:timers/promises'

const require = createRequire(import.meta.url)
const { chromium } = require(join(import.meta.dirname, '..', 'DevShell', 'ui', 'dev-ui-react', 'node_modules', 'playwright-core'))
const runs = join(import.meta.dirname, '..', '.scientific', 'runs')

async function newRun(previous) {
  const deadline = Date.now() + 360_000
  while (Date.now() < deadline) {
    for (const name of readdirSync(runs)) {
      if (previous.has(name) || !/^[0-9a-f]{32}$/.test(name)) continue
      const folder = join(runs, name)
      if (!existsSync(join(folder, 'results.json')) || !existsSync(join(folder, 'qualifications.json'))) continue
      try {
        return { result: JSON.parse(readFileSync(join(folder, 'results.json'), 'utf8')),
          qualification: JSON.parse(readFileSync(join(folder, 'qualifications.json'), 'utf8')) }
      } catch { /* Wait for atomic publication. */ }
    }
    await delay(1000)
  }
  throw new Error('Compile and link did not publish qualification evidence before timeout')
}

const browser = await chromium.connectOverCDP(process.env.DEVSHELL_CDP_URL || 'http://127.0.0.1:9239')
try {
  const page = browser.contexts().flatMap(context => context.pages()).find(item => item.url().includes('app.local'))
  assert.ok(page, 'DevShell desktop page must be running')
  page.setDefaultTimeout(30_000)
  await page.getByText('RUNTIMES / Scientific', { exact: true }).click()
  const main = page.getByRole('main', { name: 'Scientific Runtimes' })
  const detail = main.getByRole('region', { name: /runtime details/ })
  const nav = main.getByRole('navigation', { name: 'Scientific runtime sections' })
  const environment = main.getByLabel('Scientific execution environment')
  const history = main.getByRole('region', { name: 'Scientific run history' })
  await environment.selectOption('windows-native')
  const completed = []
  for (const [name, id, capability] of [
    ['CGAL', 'cgal-win-conda', 'cgal.cpp.compile-link'],
    ['VTK', 'vtk-win-conda', 'vtk.cpp.compile-link']
  ]) {
    await main.locator('.scientific-runtime-item').filter({ hasText: name }).first().click()
    await nav.getByRole('button', { name: 'Commands' }).click()
    const previous = new Set(readdirSync(runs))
    await detail.getByRole('button', { name: 'Compile & link' }).click()
    const { result, qualification } = await newRun(previous)
    assert.equal(result.runtimeId, id)
    assert.equal(result.recipeId, 'compile-link')
    assert.equal(result.state, 'succeeded')
    assert.equal(result.steps?.length, 2)
    assert.deepEqual(result.steps.map(step => step.stage), ['configure', 'build'])
    const l4 = qualification.records.find(record => record.level === 'L4' && record.capabilityId === capability)
    assert.ok(l4, `${id} must produce a named L4 record`)
    assert.equal(l4.evidenceSha256, result.compileLink.sha256)
    completed.push({ name, id, capability, runId: result.runId })
    console.log(`${id}: L4 / ${result.runId} / ${l4.evidenceSha256.slice(0, 12)}`)
  }
  for (const item of completed) {
    await main.locator('.scientific-runtime-item').filter({ hasText: item.name }).first().click()
    await nav.getByRole('button', { name: 'History' }).click()
    await history.getByRole('button', { name: /Load history|Refresh history/ }).click()
    const summary = history.locator('section[aria-label="Current qualification summary"]')
    const capabilityRow = summary.locator('tr').filter({ hasText: item.capability })
    await capabilityRow.waitFor()
    assert.match(await capabilityRow.innerText(), /L4/)
    await capabilityRow.getByRole('button', { name: item.runId.slice(0, 12) }).click()
    const resultView = history.locator('.scientific-history-result')
    await resultView.getByText(item.runId).waitFor()
    await resultView.locator('section[aria-label="Qualification records"]').getByText(item.capability).waitFor()
  }
  await main.locator('.scientific-runtime-item').filter({ hasText: 'Gmsh' }).first().click()
  await nav.getByRole('button', { name: 'History' }).click()
  await history.getByRole('button', { name: /Load history|Refresh history/ }).click()
  await history.locator('section[aria-label="Current qualification summary"]').getByText('No current qualifications for this provider.').waitFor()
  console.log('PASS: CGAL and VTK L4 levels link to fresh runs; Gmsh remains unqualified')
} finally {
  await browser.close()
}
