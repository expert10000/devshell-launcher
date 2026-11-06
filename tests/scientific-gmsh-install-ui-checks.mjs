// Opt-in desktop check. An existing Gmsh environment is inventoried without updates;
// a missing one is installed in the selected workspace by the managed setup job.
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { join } from 'node:path'

const require = createRequire(import.meta.url)
const { chromium } = require(join(import.meta.dirname, '..', 'DevShell', 'ui', 'dev-ui-react', 'node_modules', 'playwright-core'))
const browser = await chromium.connectOverCDP(process.env.DEVSHELL_CDP_URL || 'http://127.0.0.1:9244')
try {
  const page = browser.contexts().flatMap(context => context.pages()).find(item => item.url().includes('app.local'))
  assert.ok(page, 'DevShell desktop page is unavailable')
  page.setDefaultTimeout(30_000)
  await page.getByText('RUNTIMES / Scientific', { exact: true }).click()
  const main = page.getByRole('main', { name: 'Scientific Runtimes' })
  await main.getByLabel('Scientific execution environment').selectOption('windows-native')
  await main.locator('.scientific-runtime-item').filter({ hasText: 'Gmsh' }).first().click()
  await main.getByRole('button', { name: 'Install / repair Gmsh' }).click()
  const job = main.locator('.scientific-job-summary').filter({ hasText: 'gmsh-win-conda / setup.install' })
  await job.waitFor()
  await page.waitForFunction(() => [...document.querySelectorAll('.scientific-job-summary')]
    .some(item => item.textContent?.includes('gmsh-win-conda / setup.install')
      && item.querySelector('.scientific-job-state')?.textContent?.toLowerCase() === 'running'))
  await page.waitForFunction(() => {
    const job = [...document.querySelectorAll('.scientific-job-summary')]
      .find(item => item.textContent?.includes('gmsh-win-conda / setup.install'))
    return job && !job.textContent?.includes('running')
  }, undefined, { timeout: 1_800_000 })
  assert.match(await job.innerText(), /succeeded/i, 'Gmsh setup failed; open the managed job log')
  await main.getByRole('button', { name: 'Packages' }).click()
  try { await main.getByText('python-gmsh', { exact: true }).waitFor({ timeout: 30_000 }) }
  catch (error) { console.error((await main.innerText()).slice(0, 3000)); throw error }
  console.log('PASS: Gmsh install button runs a managed setup job and reloads the installed package inventory')
} finally {
  await browser.close()
}
