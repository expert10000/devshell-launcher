// Opt-in desktop acceptance: starts one bounded managed recipe per configured backend.
import assert from 'node:assert/strict'
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { createRequire } from 'node:module'
import { join } from 'node:path'
import { setTimeout as delay } from 'node:timers/promises'

const require = createRequire(import.meta.url)
const { chromium } = require(join(import.meta.dirname, '..', 'DevShell', 'ui', 'dev-ui-react', 'node_modules', 'playwright-core'))
const runs = join(import.meta.dirname, '..', '.scientific', 'runs')
const browser = await chromium.connectOverCDP(process.env.DEVSHELL_CDP_URL || 'http://127.0.0.1:9239')
const observed = []

async function newRun(previous, timeoutMs = 180_000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    for (const name of readdirSync(runs)) {
      if (previous.has(name) || !/^[0-9a-f]{32}$/.test(name)) continue
      const folder = join(runs, name)
      const resultPath = join(folder, 'results.json')
      const fingerprintPath = join(folder, 'fingerprint.json')
      if (!existsSync(resultPath) || !existsSync(fingerprintPath)) continue
      try {
        return { folder, result: JSON.parse(readFileSync(resultPath, 'utf8')),
          fingerprint: JSON.parse(readFileSync(fingerprintPath, 'utf8')) }
      } catch { /* Wait for atomic result publication. */ }
    }
    await delay(500)
  }
  throw new Error('Managed recipe did not publish a result and fingerprint before timeout')
}

try {
  const page = browser.contexts().flatMap(context => context.pages()).find(item => item.url().includes('app.local'))
  assert.ok(page, 'DevShell desktop page must be running')
  page.setDefaultTimeout(30_000)
  await page.getByText('RUNTIMES / Scientific', { exact: true }).click()
  const main = page.getByRole('main', { name: 'Scientific Runtimes' })
  const nav = main.getByRole('navigation', { name: 'Scientific runtime sections' })
  const detail = main.getByRole('region', { name: /runtime details/ })
  const choose = async name => main.locator('.scientific-runtime-item').filter({ hasText: name }).first().click()
  const environment = main.getByLabel('Scientific execution environment')

  for (const [name, runtimeId, section, button, recipeId] of [
    ['CGAL', 'cgal-win-conda', 'Commands', 'Version', 'version'],
    ['VTK', 'vtk-win-conda', 'Commands', 'Version', 'version'],
    ['Gmsh', 'gmsh-win-conda', 'Tests', 'Run Gmsh probes', 'lab.probe'],
    ['Python / SciPy', 'python-win-conda', 'Tests', 'Run Python / SciPy probes', 'lab.probe']
  ]) {
    await environment.selectOption('windows-native')
    await choose(name)
    await nav.getByRole('button', { name: section, exact: true }).click()
    const previous = new Set(readdirSync(runs))
    await detail.getByRole('button', { name: button, exact: true }).click()
    const { result, fingerprint } = await newRun(previous)
    assert.equal(result.runtimeId, runtimeId)
    assert.equal(result.recipeId, recipeId)
    assert.equal(result.runFingerprintSha256, fingerprint.sha256)
    assert.equal(fingerprint.components.environment.condaPackageRecords.state, 'recorded')
    assert.equal(fingerprint.components.environment.pythonExecutable.state, 'recorded')
    assert.ok(fingerprint.components.suite.revisionSha256)
    if (runtimeId === 'gmsh-win-conda' && result.state === 'failed')
      assert.ok(result.probeResults?.some(probe => probe.id === 'gmsh.version' && /No module named 'gmsh'/.test(probe.stderr)),
        'A failed Gmsh probe must identify the missing provider package')
    else assert.equal(result.state, 'succeeded', `${runtimeId} managed recipe must succeed`)
    observed.push({ runtimeId, recipeId, state: result.state, runId: result.runId,
      packages: fingerprint.components.environment.condaPackageRecords.count })
    console.log(`${runtimeId}: ${result.state} / ${result.runId} / ${fingerprint.components.environment.condaPackageRecords.count} packages`)
  }

  await environment.selectOption('wsl')
  await choose('SageMath')
  const previous = new Set(readdirSync(runs))
  await detail.getByRole('button', { name: 'Check Sage installation' }).click()
  const { result, fingerprint } = await newRun(previous)
  assert.equal(result.runtimeId, 'sage-wsl')
  assert.equal(result.recipeId, 'sage.version')
  assert.equal(result.runFingerprintSha256, fingerprint.sha256)
  assert.ok(fingerprint.components.suite.revisionSha256)
  assert.equal(result.state, 'succeeded')
  assert.equal(fingerprint.components.environment.wslProviderBinary.state, 'recorded')
  assert.ok(['condaPackageRecords', 'systemPackageRecords'].some(name => fingerprint.components.environment[name]?.state === 'recorded'))
  assert.equal(fingerprint.components.environment.toolchain.wslShell.state, 'recorded')
  assert.equal(fingerprint.components.environment.toolchain.wslTimeout.state, 'recorded')
  observed.push({ runtimeId: result.runtimeId, recipeId: result.recipeId, state: result.state,
    runId: result.runId, wslProvider: fingerprint.components.environment.wslProviderBinary.state ?? 'unavailable' })
  console.log(`sage-wsl: ${result.state} / ${result.runId} / provider ${fingerprint.components.environment.wslProviderBinary.state ?? 'unavailable'}`)

  await nav.getByRole('button', { name: 'History' }).click()
  const history = main.getByRole('region', { name: 'Scientific run history' })
  await history.getByRole('button', { name: /Load history|Refresh history/ }).click()
  const sage = observed.at(-1)
  const row = history.locator(`tr[data-run-id="${sage.runId}"]`)
  await row.waitFor()
  await row.getByRole('button', { name: 'Result' }).click()
  await history.getByText('Current packages and toolchain compared with this saved run:').waitFor()
  console.log(`PASS: ${observed.length} managed desktop runs saved fingerprints; History verified a saved result`)
} finally {
  await browser.close()
}
