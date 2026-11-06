// Read-only desktop check for evidence-linked scientific runtime matrix verdicts.
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { join } from 'node:path'

const require = createRequire(import.meta.url)
const { chromium } = require(join(import.meta.dirname, '..', 'DevShell', 'ui', 'dev-ui-react', 'node_modules', 'playwright-core'))
const browser = await chromium.connectOverCDP(process.env.DEVSHELL_CDP_URL || 'http://127.0.0.1:9239')
try {
  const page = browser.contexts().flatMap(context => context.pages()).find(item => item.url().includes('app.local'))
  assert.ok(page, 'DevShell desktop page must be running')
  page.setDefaultTimeout(45_000)
  await page.getByText('RUNTIMES / Scientific', { exact: true }).click()
  const main = page.getByRole('main', { name: 'Scientific Runtimes' })
  const nav = main.getByRole('navigation', { name: 'Scientific runtime sections' })
  await nav.getByRole('button', { name: 'Matrix' }).click()
  const matrix = main.getByRole('region', { name: 'Scientific runtime matrix' })
  for (const id of ['cgal-win-conda', 'vtk-win-conda', 'gmsh-win-conda', 'python-win-conda', 'sage-wsl'])
    await matrix.getByText(id, { exact: true }).waitFor()
  const cgal = matrix.locator('tr').filter({ hasText: 'cgal-win-conda' }).first()
  await cgal.getByText('Loading verified levels...').waitFor({ state: 'hidden', timeout: 45_000 })
  const gmsh = matrix.locator('tr').filter({ hasText: 'gmsh-win-conda' }).first()
  await gmsh.getByText('No current qualification').waitFor({ timeout: 45_000 })
  const cgalCapabilities = await cgal.locator('td').nth(2).innerText()
  console.log(`CGAL current capability view: ${cgalCapabilities.replaceAll('\n', ' ')}`)
  const supporting = cgal.locator('td').nth(2).getByRole('button').first()
  if (await supporting.count()) {
    const runId = (await supporting.getAttribute('title'))?.match(/Open run ([0-9a-f]{32})/)?.[1]
    assert.ok(runId, 'Current capability must link to a saved run')
    await supporting.click()
    const history = main.getByRole('region', { name: 'Scientific run history' })
    await history.getByText(runId, { exact: true }).first().waitFor()
    await nav.getByRole('button', { name: 'Matrix' }).click()
  } else {
    assert.match(cgalCapabilities, /No current qualification/)
    const evidence = await cgal.locator('td').nth(3).innerText()
    assert.match(evidence, /[1-9][0-9]* stale/)
    console.log(`CGAL stale evidence: ${evidence.replaceAll('\n', ' ').slice(0, 220)}`)
    const staleLink = cgal.locator('td').nth(3).locator('button[title^="Open run "]').first()
    assert.ok(await staleLink.count(), 'Stale verdict must link to a source run')
    const runId = (await staleLink.getAttribute('title'))?.match(/Open run ([0-9a-f]{32})/)?.[1]
    assert.ok(runId)
    await staleLink.click()
    await main.getByRole('region', { name: 'Scientific run history' }).getByText(runId, { exact: true }).first().waitFor()
    await nav.getByRole('button', { name: 'Matrix' }).click()
  }
  await matrix.locator('tr').filter({ hasText: 'gmsh-win-conda' }).first().getByRole('button', { name: 'State evidence' }).click()
  await main.getByRole('region', { name: /Gmsh runtime details/ }).waitFor()
  console.log('PASS: five providers shown; Gmsh scoped evidence remains below release certification; matrix evidence opens its source view')
} finally {
  await browser.close()
}
