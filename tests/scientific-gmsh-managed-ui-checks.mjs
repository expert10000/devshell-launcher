// Opt-in live Gmsh L0-L5 acceptance on a debug-port DevShell build.
import assert from 'node:assert/strict'
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { createRequire } from 'node:module'
import { join } from 'node:path'
import { setTimeout as delay } from 'node:timers/promises'

const require = createRequire(import.meta.url)
const { chromium } = require(join(import.meta.dirname, '..', 'DevShell', 'ui', 'dev-ui-react', 'node_modules', 'playwright-core'))
const runs = join(import.meta.dirname, '..', '.scientific', 'runs')
const prefix = 'gmsh-win-conda'

async function newRun(previous, recipe, expectedLevels) {
  const deadline = Date.now() + 180_000
  while (Date.now() < deadline) {
    for (const name of readdirSync(runs)) {
      if (previous.has(name) || !/^[0-9a-f]{32}$/.test(name)) continue
      const folder = join(runs, name)
      const resultPath = join(folder, 'results.json')
      const fingerprintPath = join(folder, 'fingerprint.json')
      const qualificationPath = join(folder, 'qualifications.json')
      if (![resultPath, fingerprintPath, qualificationPath].every(existsSync)) continue
      try {
        const result = JSON.parse(readFileSync(resultPath, 'utf8'))
        const fingerprint = JSON.parse(readFileSync(fingerprintPath, 'utf8'))
        const qualifications = JSON.parse(readFileSync(qualificationPath, 'utf8'))
        if (result.runtimeId !== prefix || result.recipeId !== recipe) continue
        assert.equal(result.state, 'succeeded', JSON.stringify(result.diagnostics))
        assert.equal(result.runFingerprintSha256, fingerprint.sha256)
        assert.deepEqual([...new Set(qualifications.records.map(item => item.level))].sort(), expectedLevels)
        return { folder, result, qualifications }
      } catch (error) {
        if (error?.name === 'AssertionError') throw error
      }
    }
    await delay(500)
  }
  throw new Error(`${recipe} did not save managed qualification before timeout`)
}

const browser = await chromium.connectOverCDP(process.env.DEVSHELL_CDP_URL || 'http://127.0.0.1:9244')
try {
  const page = browser.contexts().flatMap(context => context.pages()).find(item => item.url().includes('app.local'))
  assert.ok(page, 'DevShell app page is unavailable')
  page.setDefaultTimeout(30_000)
  await page.getByText('RUNTIMES / Scientific', { exact: true }).click()
  const main = page.getByRole('main', { name: 'Scientific Runtimes' })
  await main.getByLabel('Scientific execution environment').selectOption('windows-native')
  await main.locator('.scientific-runtime-item').filter({ hasText: 'Gmsh' }).first().click()
  const nav = main.getByRole('navigation', { name: 'Scientific runtime sections' })
  await nav.getByRole('button', { name: 'Commands', exact: true }).click()
  const detail = main.getByRole('region', { name: /runtime details/ })
  const cases = [
    { button: 'Probe in runtime-lab', recipe: 'lab.probe', levels: ['L0', 'L1', 'L2', 'L3'] },
    { button: 'Compile & link', recipe: 'compile-link', levels: ['L0', 'L4'] },
    { button: 'Run L5 worker check', recipe: 'l5.worker', levels: ['L0', 'L5'] },
  ]
  const savedRuns = []
  for (const item of cases) {
    const previous = new Set(readdirSync(runs))
    await detail.getByRole('button', { name: item.button, exact: true }).click()
    const saved = await newRun(previous, item.recipe, item.levels)
    savedRuns.push(saved)
    console.log(`${item.recipe}: ${saved.result.runId} / ${saved.qualifications.records.map(record => record.level).join(',')}`)
  }
  await nav.getByRole('button', { name: 'History' }).click()
  const history = main.getByRole('region', { name: 'Scientific run history' })
  await history.getByRole('button', { name: /Load history|Refresh history/ }).click()
  for (const saved of savedRuns) {
    const row = history.locator(`tr[data-run-id="${saved.result.runId}"]`)
    await row.waitFor()
    await row.getByRole('button', { name: 'Result' }).click()
    const view = history.locator('section[aria-label="Qualification records"]')
    await view.waitFor()
    assert.equal(await view.locator('tbody tr').count(), saved.qualifications.records.length)
    assert.ok((await view.innerText()).includes('current'), 'Gmsh qualification must be current in History')
  }
  console.log('PASS: Gmsh L0-L5 managed qualification records saved')
} finally {
  await browser.close()
}
