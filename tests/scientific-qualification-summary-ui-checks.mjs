// Read-only check of current highest levels and supporting-run links across providers.
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { join } from 'node:path'

const require = createRequire(import.meta.url)
const { chromium } = require(join(import.meta.dirname, '..', 'DevShell', 'ui', 'dev-ui-react', 'node_modules', 'playwright-core'))
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
  for (const [name, backend, capability, level] of [
    ['CGAL', 'windows-native', 'geometry.point3', 'L3'],
    ['CGAL', 'windows-native', 'cgal.cpp.compile-link', 'L4'],
    ['CGAL', 'windows-native', 'mesh.interop.vtk-math3d', 'L9'],
    ['VTK', 'windows-native', 'geometry.polydata', 'L3'],
    ['VTK', 'windows-native', 'vtk.cpp.compile-link', 'L4'],
    ['Python / SciPy', 'windows-native', 'math.linear-algebra', 'L3'],
    ['SageMath', 'wsl', 'math.symbolic', 'L3']
  ]) {
    await environment.selectOption(backend)
    await main.locator('.scientific-runtime-item').filter({ hasText: name }).first().click()
    await nav.getByRole('button', { name: 'History' }).click()
    await history.getByRole('button', { name: /Load history|Refresh history/ }).click()
    const summary = history.locator('section[aria-label="Current qualification summary"]')
    const row = summary.locator('tr').filter({ hasText: capability })
    await row.waitFor()
    assert.match(await row.innerText(), new RegExp(`\\b${level}\\b`))
    const supportingRun = row.getByRole('button').first()
    const runPrefix = await supportingRun.innerText()
    assert.match(runPrefix, /^[0-9a-f]{12}$/)
    await supportingRun.click()
    const resultView = history.locator('.scientific-history-result')
    await resultView.locator('section[aria-label="Qualification records"]').getByText(capability).waitFor()
    console.log(`${name}: ${capability} ${level} / supporting run ${runPrefix}`)
  }
  await environment.selectOption('windows-native')
  await main.locator('.scientific-runtime-item').filter({ hasText: 'Gmsh' }).first().click()
  await nav.getByRole('button', { name: 'History' }).click()
  await history.getByRole('button', { name: /Load history|Refresh history/ }).click()
  await history.locator('section[aria-label="Current qualification summary"]').getByText('mesh.generate').waitFor()
  console.log('PASS: current levels link to supporting runs; Gmsh has scoped mesh.generate L5 evidence')
} finally {
  await browser.close()
}
