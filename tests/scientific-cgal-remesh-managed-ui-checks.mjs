// Live DevShell qualification acceptance for guarded remesh L5-L9.
import assert from 'node:assert/strict'
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { createRequire } from 'node:module'
import { join } from 'node:path'
import { setTimeout as delay } from 'node:timers/promises'

const require = createRequire(import.meta.url)
const { chromium } = require(join(import.meta.dirname, '..', 'DevShell', 'ui', 'dev-ui-react', 'node_modules', 'playwright-core'))
const runs = process.env.DEVSHELL_SCIENTIFIC_RUNS_ROOT || join(import.meta.dirname, '..', '.scientific', 'runs')
assert.ok(process.env.DEVSHELL_CDP_URL, 'Set DEVSHELL_CDP_URL')

async function completed(before, recipe, level, page, oldAlerts) {
  const deadline = Date.now() + 600_000
  while (Date.now() < deadline) {
    for (const name of readdirSync(runs)) {
      if (before.has(name) || !/^[0-9a-f]{32}$/.test(name)) continue
      const folder = join(runs, name)
      const resultPath = join(folder, 'results.json')
      if (!existsSync(resultPath)) continue
      let result
      try { result = JSON.parse(readFileSync(resultPath, 'utf8')) } catch { continue }
      if (result.recipeId !== recipe) continue
      if (result.state !== 'succeeded') throw new Error(`${recipe}: ${result.state} / ${JSON.stringify(result.diagnostics)}`)
      const recordPath = join(folder, 'qualifications.json')
      if (!existsSync(recordPath)) continue
      let record
      try { record = JSON.parse(readFileSync(recordPath, 'utf8')).records.find(item => item.level === level && item.capabilityId === 'mesh.remesh') } catch { continue }
      assert.ok(record, `${recipe} saved no mesh.remesh@${level} record`)
      assert.ok(result.remeshQualificationEvidence, 'Missing linked evidence')
      assert.ok(existsSync(join(folder, result.remeshQualificationEvidence.reportPath)), 'Missing report')
      return { result, record }
    }
    const alerts = await page.getByRole('alert').allTextContents()
    const fresh = alerts.find(item => item && !oldAlerts.includes(item))
    if (fresh) throw new Error(`${recipe} was rejected: ${fresh}`)
    await delay(500)
  }
  throw new Error(`${recipe} timed out`)
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
  await main.getByRole('navigation', { name: 'Scientific runtime sections' }).getByRole('button', { name: 'Commands', exact: true }).click()
  const detail = main.getByRole('region', { name: /runtime details/ })
  for (const [button, recipe, level, capability] of [['Probe in runtime-lab', 'lab.probe', 'L0', 'runtime.inventory'], ['Compile & link', 'compile-link', 'L4', 'cgal.cpp.compile-link']]) {
    const before = new Set(readdirSync(runs))
    const oldAlerts = await page.getByRole('alert').allTextContents()
    await detail.getByRole('button', { name: button, exact: true }).click()
    // L0-L4 are established by the normal desktop probe/build chain.
    const deadline = Date.now() + 600_000
    let done = false
    while (Date.now() < deadline && !done) {
      for (const name of readdirSync(runs)) {
        if (before.has(name) || !/^[0-9a-f]{32}$/.test(name)) continue
        const folder = join(runs, name)
        if (!existsSync(join(folder, 'qualifications.json')) || !existsSync(join(folder, 'results.json'))) continue
        const result = JSON.parse(readFileSync(join(folder, 'results.json'), 'utf8'))
        if (result.recipeId !== recipe) continue
        assert.equal(result.state, 'succeeded', `${recipe}: ${JSON.stringify(result.diagnostics)}`)
        const records = JSON.parse(readFileSync(join(folder, 'qualifications.json'), 'utf8')).records
        assert.ok(records.some(item => item.level === level && item.capabilityId === capability))
        done = true; break
      }
      if (!done) {
        const alerts = await page.getByRole('alert').allTextContents()
        const fresh = alerts.find(item => item && !oldAlerts.includes(item))
        if (fresh) throw new Error(`${recipe}: ${fresh}`)
        await delay(500)
      }
    }
    assert.ok(done, `${recipe} timed out`)
  }
  await detail.getByRole('button', { name: 'Isotropic Remesh', exact: true }).click()
  for (const level of [5, 6, 7, 8, 9]) {
    const before = new Set(readdirSync(runs))
    const oldAlerts = await page.getByRole('alert').allTextContents()
    await detail.getByRole('button', { name: `Run remesh L${level}`, exact: true }).click()
    const { result } = await completed(before, `l${level}.cgal-remesh`, `L${level}`, page, oldAlerts)
    console.log(`mesh.remesh@L${level}: ${result.runId}`)
  }
  await main.getByRole('navigation', { name: 'Scientific runtime sections' }).getByRole('button', { name: 'History', exact: true }).click()
  await main.getByRole('region', { name: 'Scientific run history' }).getByRole('button', { name: /Load history|Refresh history/ }).click()
  await main.getByText('mesh.remesh', { exact: true }).first().waitFor()
} finally {
  await browser.close()
}
