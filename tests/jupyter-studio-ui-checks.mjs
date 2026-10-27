// Live DevShell check. Launch the app with WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=9237.
// Uses the laptop profile's prepared Jupyter environment and stops the service on completion.
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { homedir } from 'node:os'
import { join } from 'node:path'
import { existsSync } from 'node:fs'

const require = createRequire(import.meta.url)
const localPlaywright = join(import.meta.dirname, '..', 'DevShell', 'ui', 'dev-ui-react', 'node_modules', 'playwright-core')
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || (existsSync(localPlaywright) ? localPlaywright :
  join(homedir(), '.cache', 'codex-runtimes', 'codex-primary-runtime', 'dependencies', 'node', 'node_modules', 'playwright')))
const browser = await chromium.connectOverCDP(process.env.DEVSHELL_CDP_URL || 'http://127.0.0.1:9237')
const page = browser.contexts().flatMap(context => context.pages()).find(item => item.url().includes('app.local'))
assert.ok(page, 'DevShell UI must be running')
page.setDefaultTimeout(30000)
const errors = []
page.on('pageerror', error => errors.push(error.message))

await page.evaluate(() => {
  window.__jupyterCheckMessages = []
  window.chrome.webview.addEventListener('message', event => {
    const message = typeof event.data === 'string' ? JSON.parse(event.data) : event.data
    window.__jupyterCheckMessages.push(message)
  })
})

const waitForMessage = (type, detail) => page.waitForFunction(({ type, detail }) =>
  window.__jupyterCheckMessages.some(message => message.type === type &&
    (detail == null || message.servicePath === detail)), { type, detail }, { timeout: 90000 })
const service = page.locator('.task-sidebar .service-card')
const waitForState = state => page.waitForFunction(state =>
  document.querySelector('.service-card .service-state')?.textContent?.trim() === state,
  state, { timeout: 90000 })

try {
  assert.equal(await page.locator('#workspace-profile-select').inputValue(), 'profile-laptop')
  await page.getByRole('button', { name: /Jupyter Studio D:/ }).click()
  await page.locator('.tab-strip .tab').filter({ hasText: 'Shell' }).click()
  await service.waitFor()
  console.log('PASS: Jupyter Studio service controls visible in laptop profile')

  await page.getByRole('button', { name: 'Jupyter - Environment Check', exact: true }).click()
  await page.waitForFunction(() => window.__jupyterCheckMessages
    .filter(message => message.type === 'output').map(message => message.data ?? '').join('').includes('JupyterLab '))
  const output = await page.evaluate(() => window.__jupyterCheckMessages
    .filter(message => message.type === 'output').map(message => message.data ?? '').join(''))
  assert.match(output, /JupyterLab\s+\d/)
  assert.doesNotMatch(output, /Command not found for profile/)
  console.log('PASS: Environment Check runs in a DevShell terminal')

  await service.getByRole('button', { name: 'Start', exact: true }).click()
  await waitForState('running')
  await waitForMessage('workspace.browser.opened', null)
  console.log('PASS: Lab starts and opens inside DevShell')

  await page.getByRole('button', { name: 'Jupyter - Open Start Here', exact: true }).click()
  await waitForMessage('workspace.browser.opened', 'notebooks/00_start_here.ipynb')
  console.log('PASS: Start Here notebook opens inside DevShell')

  await service.getByRole('button', { name: 'Restart', exact: true }).click()
  await waitForState('running')
  console.log('PASS: Lab restarts')

  await service.getByRole('button', { name: 'Stop', exact: true }).click()
  await waitForState('stopped')
  console.log('PASS: Lab stops')
  assert.deepEqual(errors, [])
  console.log('PASS: No page errors')
} finally {
  if (await service.count() && await service.getByRole('button', { name: 'Stop', exact: true }).isEnabled().catch(() => false)) {
    await service.getByRole('button', { name: 'Stop', exact: true }).click().catch(() => {})
    await waitForState('stopped').catch(() => {})
  }
}
process.exit(0)
