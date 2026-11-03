// Read-only desktop acceptance for the latest fingerprinted result of each provider.
import assert from 'node:assert/strict'
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs'
import { createRequire } from 'node:module'
import { join } from 'node:path'

const require = createRequire(import.meta.url)
const { chromium } = require(join(import.meta.dirname, '..', 'DevShell', 'ui', 'dev-ui-react', 'node_modules', 'playwright-core'))
const runs = join(import.meta.dirname, '..', '.scientific', 'runs')
const latest = new Map()
for (const name of readdirSync(runs)) {
  if (!/^[0-9a-f]{32}$/.test(name)) continue
  const path = join(runs, name, 'results.json')
  if (!existsSync(path)) continue
  try {
    const result = JSON.parse(readFileSync(path, 'utf8'))
    if (!result.runFingerprintSha256) continue
    const time = statSync(path).mtimeMs
    if (time > (latest.get(result.runtimeId)?.time ?? -1)) latest.set(result.runtimeId, { result, time })
  } catch { /* Ignore incomplete or legacy evidence. */ }
}

const browser = await chromium.connectOverCDP(process.env.DEVSHELL_CDP_URL || 'http://127.0.0.1:9239')
try {
  const page = browser.contexts().flatMap(context => context.pages()).find(item => item.url().includes('app.local'))
  assert.ok(page, 'DevShell desktop page must be running')
  page.setDefaultTimeout(30_000)
  await page.getByText('RUNTIMES / Scientific', { exact: true }).click()
  const main = page.getByRole('main', { name: 'Scientific Runtimes' })
  const nav = main.getByRole('navigation', { name: 'Scientific runtime sections' })
  const environment = main.getByLabel('Scientific execution environment')
  const history = main.getByRole('region', { name: 'Scientific run history' })
  for (const [name, id, backend] of [
    ['CGAL', 'cgal-win-conda', 'windows-native'], ['VTK', 'vtk-win-conda', 'windows-native'],
    ['Gmsh', 'gmsh-win-conda', 'windows-native'], ['Python / SciPy', 'python-win-conda', 'windows-native'],
    ['SageMath', 'sage-wsl', 'wsl']
  ]) {
    const saved = latest.get(id)?.result
    assert.ok(saved, `A fingerprinted ${id} result is required`)
    await environment.selectOption(backend)
    await main.locator('.scientific-runtime-item').filter({ hasText: name }).first().click()
    await nav.getByRole('button', { name: 'History' }).click()
    await history.getByRole('button', { name: /Load history|Refresh history/ }).click()
    const row = history.locator(`tr[data-run-id="${saved.runId}"]`)
    await row.waitFor()
    await row.getByRole('button', { name: 'Result' }).click()
    const resultView = history.locator('.scientific-history-result')
    await resultView.getByText('Verified run fingerprint:', { exact: false }).waitFor()
    const source = resultView.getByText('Current source compared with this saved run:', { exact: false })
    await source.waitFor()
    assert.match(await source.innerText(), /\bcurrent\b/, `${id} source must be current immediately after its run`)
    const drift = resultView.getByText('Current packages and toolchain compared with this saved run:', { exact: false })
    await drift.waitFor()
    const line = await drift.innerText()
    assert.match(line, /\b(current|unknown)\b/, `${id} must not be stale immediately after its run`)
    console.log(`${id}: ${saved.state} / ${line}`)
  }
  console.log('PASS: History verified five fingerprinted results and showed package/toolchain drift')
} finally {
  await browser.close()
}
