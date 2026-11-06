// Opt-in L0-L3 acceptance through the running desktop app and its saved History.
import assert from 'node:assert/strict'
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { createRequire } from 'node:module'
import { join } from 'node:path'
import { setTimeout as delay } from 'node:timers/promises'

const require = createRequire(import.meta.url)
const { chromium } = require(join(import.meta.dirname, '..', 'DevShell', 'ui', 'dev-ui-react', 'node_modules', 'playwright-core'))
const runs = join(import.meta.dirname, '..', '.scientific', 'runs')

async function newRun(previous) {
  const deadline = Date.now() + 180_000
  while (Date.now() < deadline) {
    for (const name of readdirSync(runs)) {
      if (previous.has(name) || !/^[0-9a-f]{32}$/.test(name)) continue
      const folder = join(runs, name)
      if (!existsSync(join(folder, 'results.json')) || !existsSync(join(folder, 'fingerprint.json'))) continue
      try {
        const result = JSON.parse(readFileSync(join(folder, 'results.json'), 'utf8'))
        const fingerprint = JSON.parse(readFileSync(join(folder, 'fingerprint.json'), 'utf8'))
        const qualifications = existsSync(join(folder, 'qualifications.json'))
          ? JSON.parse(readFileSync(join(folder, 'qualifications.json'), 'utf8')) : null
        return { result, fingerprint, qualifications }
      } catch { /* Wait for atomic publication. */ }
    }
    await delay(500)
  }
  throw new Error('Managed run did not publish evidence before timeout')
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
  const records = []
  const cases = [
    { name: 'CGAL', id: 'cgal-win-conda', backend: 'windows-native', section: 'Commands', button: 'Probe in runtime-lab', levels: ['L0', 'L1', 'L2', 'L3'] },
    { name: 'VTK', id: 'vtk-win-conda', backend: 'windows-native', section: 'Commands', button: 'Probe in runtime-lab', levels: ['L0', 'L1', 'L2', 'L3'] },
    { name: 'Python / SciPy', id: 'python-win-conda', backend: 'windows-native', section: 'Tests', button: 'Run Python / SciPy probes', levels: ['L0', 'L1', 'L2', 'L3'] },
    { name: 'SageMath', id: 'sage-wsl', backend: 'wsl', section: 'State', button: 'Check Sage installation', levels: ['L0', 'L1'] },
    { name: 'SageMath', id: 'sage-wsl', backend: 'wsl', section: 'State', button: 'Test exact factorization', levels: ['L0', 'L2', 'L3'] },
    { name: 'Gmsh', id: 'gmsh-win-conda', backend: 'windows-native', section: 'Commands', button: 'Probe in runtime-lab', levels: ['L0', 'L1', 'L2', 'L3'] }
  ]
  for (const item of cases) {
    await environment.selectOption(item.backend)
    await main.locator('.scientific-runtime-item').filter({ hasText: item.name }).first().click()
    await nav.getByRole('button', { name: item.section, exact: true }).click()
    const previous = new Set(readdirSync(runs))
    await detail.getByRole('button', { name: item.button, exact: true }).click()
    const saved = await newRun(previous)
    assert.equal(saved.result.runtimeId, item.id)
    assert.equal(saved.result.runFingerprintSha256, saved.fingerprint.sha256)
    if (item.levels.length) {
      assert.equal(saved.result.state, 'succeeded')
      assert.equal(saved.result.qualificationReference, 'qualifications.json')
      assert.ok(saved.result.qualificationSha256 && saved.qualifications)
      assert.equal(saved.qualifications.runId, saved.result.runId)
      assert.deepEqual([...new Set(saved.qualifications.records.map(record => record.level))].sort(), item.levels.slice().sort())
      assert.ok(saved.qualifications.records.every(record => record.runFingerprintSha256 === saved.result.runFingerprintSha256
        && record.suiteRevisionSha256 === saved.fingerprint.components.suite.revisionSha256
        && record.contract.providerRegistryVersion === saved.fingerprint.components.contract.providerRegistryVersion))
    } else {
      assert.equal(saved.result.state, 'failed')
      assert.equal(saved.qualifications, null)
      assert.equal(saved.result.qualificationSha256, undefined)
      assert.ok(saved.result.probeResults?.some(probe => probe.id === 'gmsh.version' && /No module named 'gmsh'/.test(probe.stderr)))
    }
    records.push({ ...item, runId: saved.result.runId, state: saved.result.state, count: saved.qualifications?.records.length ?? 0 })
    console.log(`${item.id} / ${item.button}: ${saved.result.state} / ${saved.result.runId} / ${saved.qualifications?.records.length ?? 0} qualifications`)
  }

  for (const item of records.filter(record => record.levels.length)) {
    await environment.selectOption(item.backend)
    await main.locator('.scientific-runtime-item').filter({ hasText: item.name }).first().click()
    await nav.getByRole('button', { name: 'History' }).click()
    await history.getByRole('button', { name: /Load history|Refresh history/ }).click()
    const row = history.locator(`tr[data-run-id="${item.runId}"]`)
    await row.waitFor()
    await row.getByRole('button', { name: 'Result' }).click()
    const view = history.locator('section[aria-label="Qualification records"]')
    await view.waitFor()
    assert.equal(await view.locator('tbody tr').count(), item.count)
    assert.ok((await view.innerText()).includes('current'), `${item.id} qualifications must be current immediately after the run`)
  }
  console.log('PASS: five providers saved scoped L0-L3 qualifications; History verified current records')
} finally {
  await browser.close()
}
