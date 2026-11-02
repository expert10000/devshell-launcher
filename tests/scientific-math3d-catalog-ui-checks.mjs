// Opt-in desktop acceptance: launch DevShell with WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=9238.
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { join } from 'node:path'

const require = createRequire(import.meta.url)
const { chromium } = require(join(import.meta.dirname, '..', 'DevShell', 'ui', 'dev-ui-react', 'node_modules', 'playwright-core'))
const browser = await chromium.connectOverCDP(process.env.DEVSHELL_CDP_URL || 'http://127.0.0.1:9238')
try {
  const page = browser.contexts().flatMap(context => context.pages()).find(item => item.url().includes('app.local'))
  assert.ok(page, 'DevShell desktop page must be running')
  page.setDefaultTimeout(30_000)
  await page.getByText('RUNTIMES / Scientific', { exact: true }).click()
  await page.getByRole('navigation', { name: 'Scientific runtime sections' }).getByRole('button', { name: 'Catalog' }).click()
  const catalog = page.getByRole('region', { name: 'Math3D test catalog' })
  const cards = catalog.locator('.scientific-test-catalog-card')
  assert.equal(await cards.count(), 6)
  const version = cards.filter({ hasText: 'SageMath installation' })
  const factor = cards.filter({ hasText: 'Exact factorization' })
  await version.getByText(/Saved: succeeded/).waitFor()
  await factor.getByText(/Saved: cancelled/).waitFor()
  await version.getByRole('button', { name: 'Latest result' }).click()
  await version.getByText('SUCCEEDED', { exact: true }).waitFor()
  assert.match(await version.innerText(), /10\.9/)
  await factor.getByRole('button', { name: 'Latest result' }).click()
  const previousRun = await factor.locator('.scientific-test-catalog-result code').innerText()

  await factor.getByRole('button', { name: 'Run test' }).click()
  await factor.getByText(/Current: running/).waitFor()
  await factor.getByRole('button', { name: 'Stop' }).click()
  await factor.getByText(/Current: cancelled/).waitFor({ timeout: 30_000 })
  await catalog.getByRole('button', { name: 'Refresh saved results' }).click()
  await factor.getByText(/Saved: cancelled/).waitFor()
  await factor.getByRole('button', { name: 'Latest result' }).click()
  await factor.locator('.scientific-test-catalog-result code').filter({ hasNotText: previousRun }).waitFor()
  assert.notEqual(await factor.locator('.scientific-test-catalog-result code').innerText(), previousRun)
  await catalog.getByRole('button', { name: 'Open full History' }).click()
  assert.match(await page.getByRole('main', { name: 'Scientific Runtimes' }).innerText(), /sage\.factor-smoke/)
  console.log('PASS: Math3D catalog restores saved results, opens evidence, starts and stops Sage, and links History')
} finally {
  await browser.close()
}
