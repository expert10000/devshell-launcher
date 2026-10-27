// Live managed-web-service check. Requires the prepared laptop Math3D repository and free ports 5180/8787.
// Launch DevShell with WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=9237.
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
const page = browser.contexts().flatMap(context => context.pages()).find(item => item.url().includes('app.local'))
assert.ok(page, 'DevShell UI must be running')
page.setDefaultTimeout(30000)
const card = page.locator('.services-list .service-card[aria-label="Math3D service controls"]')

await page.evaluate(() => {
  window.__managedServiceMessages = []
  window.__managedServiceSent = []
  const originalPost = window.chrome.webview.postMessage.bind(window.chrome.webview)
  window.chrome.webview.postMessage = message => {
    window.__managedServiceSent.push(message)
    originalPost(message)
  }
  window.chrome.webview.addEventListener('message', event => {
    const message = typeof event.data === 'string' ? JSON.parse(event.data) : event.data
    if (message.type === 'repository.jobs') {
      const job = message.jobs?.find(item => item.key.endsWith(':math3d'))
      window.__managedServiceMessages.push(job ? {
        state: job.state, browserState: job.browserState, logPath: job.logPath
      } : null)
    }
  })
})

const latestJob = () => page.evaluate(() => window.__managedServiceMessages.at(-1))
const waitForJob = async (predicate, timeout = 360000) => {
  await page.waitForFunction(predicate, null, { timeout })
  return latestJob()
}

try {
  assert.equal(await page.locator('#workspace-profile-select').inputValue(), 'profile-laptop')
  await page.locator('.tab-strip .tab').filter({ hasText: 'Shell' }).click()
  await page.getByRole('tab', { name: /Services/ }).click()
  await card.waitFor()
  await card.getByRole('button', { name: 'Start', exact: true }).click()
  const started = await waitForJob(() => {
    const job = window.__managedServiceMessages.at(-1)
    return job?.browserState === 'ready' || job?.state === 'failed'
  })
  assert.equal(started.browserState, 'ready', 'Math3D failed to become ready')
  assert.equal(started.state, 'running')
  console.log('PASS: Managed web service starts and becomes ready in Services')

  await card.getByRole('button', { name: 'Open' }).click()
  assert.ok(await page.evaluate(() => window.__managedServiceSent.some(message => message.type === 'browser.open' && message.repositoryId === 'math3d')))
  await card.getByRole('button', { name: 'Logs' }).click()
  console.log('PASS: Open and Logs actions are available')

  await card.getByRole('button', { name: 'Restart' }).click()
  const restarted = await waitForJob(() => {
    const job = window.__managedServiceMessages.at(-1)
    const first = window.__managedServiceMessages.find(item => item?.browserState === 'ready')
    return job?.logPath !== first?.logPath && (job?.browserState === 'ready' || job?.state === 'failed')
  })
  assert.equal(restarted.browserState, 'ready', 'Math3D restart failed')
  assert.notEqual(restarted.logPath, started.logPath)
  console.log('PASS: Restart stops the previous owned job and starts a new one')

  await card.getByRole('button', { name: 'Stop' }).click()
  const stopped = await waitForJob(() => window.__managedServiceMessages.at(-1)?.state === 'stopped', 90000)
  assert.equal(stopped.state, 'stopped')
  console.log('PASS: Stop ends the managed web service')
} finally {
  if (await card.count() && await card.getByRole('button', { name: 'Stop' }).isEnabled().catch(() => false)) {
    await card.getByRole('button', { name: 'Stop' }).click().catch(() => {})
    await waitForJob(() => window.__managedServiceMessages.at(-1)?.state === 'stopped', 90000).catch(() => {})
  }
}
process.exit(0)
