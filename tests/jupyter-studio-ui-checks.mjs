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
const service = page.locator('.services-list .service-card[aria-label="Jupyter Lab service controls"]')
const waitForState = state => page.waitForFunction(state =>
  document.querySelector('[aria-label="Jupyter Lab service controls"] .service-state')?.textContent?.trim() === state,
  state, { timeout: 90000 })

try {
  assert.equal(await page.locator('#workspace-profile-select').inputValue(), 'profile-laptop')
  await page.getByRole('button', { name: /Jupyter Studio D:/ }).click()
  await page.locator('.tab-strip .tab').filter({ hasText: 'Shell' }).click()
  await page.getByRole('tab', { name: /Services/ }).click()
  await service.waitFor()
  assert.ok(await page.locator('.services-list .service-card').count() > 1, 'Services view should include other configured projects')
  console.log('PASS: Jupyter Studio service controls visible in laptop profile')

  await page.getByRole('tab', { name: 'Tasks' }).click()
  await page.getByRole('searchbox', { name: 'Search project tasks' }).fill('Environment Check')
  await page.locator('.task-panel-row').filter({ hasText: 'Jupyter - Environment Check' }).getByRole('button', { name: 'Run' }).click()
  try {
    // Cold scientific imports can take 25 seconds; terminal startup adds more time.
    await page.waitForFunction(() => window.__jupyterCheckMessages
      .filter(message => message.type === 'output').map(message => message.data ?? '').join('').includes('JupyterLab '),
    null, { timeout: 120000 })
  } catch (error) {
    const output = await page.evaluate(() => window.__jupyterCheckMessages
      .filter(message => message.type === 'output').map(message => message.data ?? '').join(''))
    console.error('Environment Check terminal output:', output.slice(-4000))
    throw error
  }
  const output = await page.evaluate(() => window.__jupyterCheckMessages
    .filter(message => message.type === 'output').map(message => message.data ?? '').join(''))
  assert.match(output, /JupyterLab\s+\d/)
  assert.doesNotMatch(output, /Command not found for profile/)
  console.log('PASS: Environment Check runs in a DevShell terminal')

  await page.getByRole('tab', { name: /Services/ }).click()
  await service.getByRole('button', { name: 'Start', exact: true }).click()
  try {
    await waitForState('running')
    await waitForMessage('workspace.browser.opened', null)
  } catch (error) {
    const messages = await page.evaluate(() => window.__jupyterCheckMessages
      .filter(message => message.type === 'service.status' || message.type === 'workspace.browser.opened')
      .map(message => ({ type: message.type, state: message.state, message: message.message,
        kind: message.kind, projectId: message.projectId, servicePath: message.servicePath })))
    console.error('Jupyter service/browser events:', messages)
    console.error('Service card:', await service.innerText())
    throw error
  }
  console.log('PASS: Lab starts and opens inside DevShell')

  await service.getByRole('button', { name: 'Logs', exact: true }).click()
  await service.locator('.service-log-panel pre').filter({ hasText: /ServerApp|No service log/ }).waitFor()
  const log = await service.locator('.service-log-panel pre').innerText()
  assert.doesNotMatch(log, /[?&]token=[a-f0-9]{20,}/i)
  console.log('PASS: Service log opens with authentication tokens redacted')

  await page.getByRole('tab', { name: 'Tasks' }).click()
  await page.getByRole('searchbox', { name: 'Search project tasks' }).fill('Open Start Here')
  await page.locator('.task-panel-row').filter({ hasText: 'Jupyter - Open Start Here' }).getByRole('button', { name: 'Run' }).click()
  await waitForMessage('workspace.browser.opened', 'notebooks/00_start_here.ipynb')
  console.log('PASS: Start Here notebook opens inside DevShell')

  await page.getByRole('tab', { name: /Services/ }).click()
  const restartMarker = await page.evaluate(() => window.__jupyterCheckMessages.length)
  await service.getByRole('button', { name: 'Restart', exact: true }).click()
  try {
    await page.waitForFunction(marker => {
      const statuses = window.__jupyterCheckMessages.slice(marker).filter(message => message.type === 'service.status')
      const busyIndex = statuses.findIndex(message => message.state === 'busy' && message.message?.startsWith('restart'))
      return busyIndex >= 0 && statuses.slice(busyIndex + 1).some(message => message.state === 'running')
    }, restartMarker, { timeout: 90000 })
    await waitForState('running')
  }
  catch (error) {
    const statuses = await page.evaluate(() => window.__jupyterCheckMessages
      .filter(message => message.type === 'service.status')
      .map(message => `${message.state}: ${message.message}`)
      .filter((value, index, values) => index === 0 || value !== values[index - 1]))
    console.error('Service status transitions:', statuses)
    console.error('Service card:', await service.innerText())
    throw error
  }
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
