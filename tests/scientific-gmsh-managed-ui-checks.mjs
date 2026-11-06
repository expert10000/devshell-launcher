// Opt-in live Gmsh L0-L8 acceptance on a debug-port DevShell build.
import assert from 'node:assert/strict'
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs'
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
  page.setDefaultTimeout(120_000)
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
    { button: 'Run L6 reproduction check', recipe: 'l6.reproduce', levels: ['L0', 'L6'] },
    { button: 'Run L7 VTK → MATH3D handoff', recipe: 'l7.gmsh-interop', levels: ['L0', 'L7'] },
    { button: 'Run L8 resilience', recipe: 'l8.gmsh-resilience', levels: ['L0', 'L8'] },
  ]
  const savedRuns = []
  for (const item of process.env.DEVSHELL_GMSH_HISTORY_ONLY ? [] : cases) {
    const previous = new Set(readdirSync(runs))
    await detail.getByRole('button', { name: item.button, exact: true }).click()
    const saved = await newRun(previous, item.recipe, item.levels)
    savedRuns.push(saved)
    console.log(`${item.recipe}: ${saved.result.runId} / ${saved.qualifications.records.map(record => record.level).join(',')}`)
  }
  if (process.env.DEVSHELL_GMSH_HISTORY_ONLY) {
    for (const item of cases.filter(item => !process.env.DEVSHELL_GMSH_HISTORY_TARGET || item.recipe === process.env.DEVSHELL_GMSH_HISTORY_TARGET)) {
      const saved = readdirSync(runs).map(name => join(runs, name)).filter(folder => existsSync(join(folder, 'results.json')))
        .map(folder => ({ folder, result: JSON.parse(readFileSync(join(folder, 'results.json'), 'utf8')) }))
        .filter(entry => entry.result.runtimeId === prefix && entry.result.recipeId === item.recipe && entry.result.state === 'succeeded')
        .sort((a, b) => statSync(b.folder).mtimeMs - statSync(a.folder).mtimeMs)[0]
      assert.ok(saved, `No saved ${item.recipe} run`)
      saved.qualifications = JSON.parse(readFileSync(join(saved.folder, 'qualifications.json'), 'utf8'))
      savedRuns.push(saved)
    }
  }
  await nav.getByRole('button', { name: 'History' }).click()
  const history = main.getByRole('region', { name: 'Scientific run history' })
  await history.getByRole('button', { name: /Load history|Refresh history/ }).click()
  for (const saved of savedRuns.slice(-1)) {
    console.log(`History: ${saved.result.recipeId} / ${saved.result.runId}`)
    const row = history.locator(`tr[data-run-id="${saved.result.runId}"]`)
    await row.waitFor()
    await row.getByRole('button', { name: 'Result' }).click()
    const view = history.locator('section[aria-label="Qualification records"]')
    try { await view.waitFor({ timeout: 20000 }) }
    catch (error) {
      console.error((await main.innerText()).slice(-5000))
      throw error
    }
    assert.equal(await view.locator('tbody tr').count(), saved.qualifications.records.length)
    assert.ok((await view.innerText()).includes('current'), `Gmsh qualification must be current in History: ${await view.innerText()}`)
  }
  const summary = history.getByRole('region', { name: 'Current qualification summary' })
  assert.ok((await summary.innerText()).includes('L8'), 'Highest current Gmsh mesh level must be L8')
  console.log('PASS: Gmsh L0-L8 managed qualification records saved')
} finally {
  await browser.close()
}
