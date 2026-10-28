// Opt-in desktop check. Launch DevShell with WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=9237.
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { existsSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'

const require = createRequire(import.meta.url)
const localPlaywright = join(import.meta.dirname, '..', 'DevShell', 'ui', 'dev-ui-react', 'node_modules', 'playwright-core')
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || (existsSync(localPlaywright) ? localPlaywright :
  join(homedir(), '.cache', 'codex-runtimes', 'codex-primary-runtime', 'dependencies', 'node', 'node_modules', 'playwright')))
const browser = await chromium.connectOverCDP(process.env.DEVSHELL_CDP_URL || 'http://127.0.0.1:9237')
try {
  const page = browser.contexts().flatMap(context => context.pages()).find(item => item.url().includes('app.local'))
  assert.ok(page, 'DevShell desktop page must be running')
  page.setDefaultTimeout(30_000)
  await page.getByText('RUNTIMES / Scientific', { exact: true }).click()
  await page.getByLabel('Scientific execution environment').selectOption('wsl')
  await page.locator('.scientific-runtime-item').filter({ hasText: 'SageMath' }).click()
  await page.getByRole('navigation', { name: 'Scientific runtime sections' }).getByRole('button', { name: 'Tests' }).click()
  const coverage = page.getByRole('region', { name: 'SageMath capability coverage' })
  await coverage.getByRole('button', { name: 'Run SageMath probes' }).click()
  await page.waitForFunction(() => /sage-wsl \/ lab\.probe/.test(document.querySelector('.scientific-job-bar')?.textContent ?? '') &&
    /RUNNING/i.test(document.querySelector('.scientific-job-bar')?.textContent ?? ''))
  await page.waitForFunction(() => /sage-wsl \/ lab\.probe/.test(document.querySelector('.scientific-job-bar')?.textContent ?? '') &&
    /SUCCEEDED/i.test(document.querySelector('.scientific-job-bar')?.textContent ?? ''), undefined, { timeout: 120_000 })
  assert.match(await coverage.innerText(), /Probe evidence: 5\/5 passed/)
  await coverage.getByRole('button', { name: 'Refresh saved evidence' }).click()
  await coverage.getByRole('button', { name: 'Load saved result' }).waitFor()
  await coverage.getByRole('button', { name: 'Load saved result' }).click()
  assert.match(await coverage.innerText(), /Probe evidence: 5\/5 passed/)
  console.log('PASS: SageMath button starts a visible managed job and loads saved 5/5 evidence')
} finally {
  await browser.close()
}
