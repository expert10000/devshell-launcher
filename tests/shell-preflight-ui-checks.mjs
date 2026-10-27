// Live WebView2 check. Launch DevShell with WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=9237.
// Simulates an unavailable PowerShell 7 profile without changing the machine or starting an installer.
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { homedir } from 'node:os'
import { join } from 'node:path'

const require = createRequire(import.meta.url)
const { chromium } = require(process.env.PLAYWRIGHT_MODULE ||
  join(homedir(), '.cache', 'codex-runtimes', 'codex-primary-runtime', 'dependencies', 'node', 'node_modules', 'playwright'))
const browser = await chromium.connectOverCDP(process.env.DEVSHELL_CDP_URL || 'http://127.0.0.1:9237')
const page = browser.contexts().flatMap(context => context.pages()).find(item => item.url().includes('app.local'))
assert.ok(page, 'DevShell UI must be running')
page.setDefaultTimeout(30000)
const errors = []
page.on('pageerror', error => errors.push(error.message))

await page.evaluate(() => {
  window.__shellCheckMessages = []
  window.__shellCheckSent = []
  window.__shellCheckOriginalPost = window.chrome.webview.postMessage.bind(window.chrome.webview)
  window.chrome.webview.addEventListener('message', event => {
    const message = typeof event.data === 'string' ? JSON.parse(event.data) : event.data
    window.__shellCheckMessages.push(message)
  })
  window.chrome.webview.postMessage = message => {
    window.__shellCheckSent.push(message)
    if (message?.type !== 'shell.setup') window.__shellCheckOriginalPost(message)
  }
  window.__shellCheckOriginalPost({ type: 'profiles.request' })
})

let realProfiles
try {
  await page.waitForFunction(() => window.__shellCheckMessages.some(message => message.type === 'profiles.list'))
  realProfiles = await page.evaluate(() => window.__shellCheckMessages.find(message => message.type === 'profiles.list').profiles)
  assert.ok(realProfiles.some(profile => profile.id === 'pwsh'))
  assert.equal(await page.locator('#workspace-profile-select').inputValue(), 'profile-laptop')
  await page.getByRole('button', { name: /Jupyter Studio D:/ }).click()
  await page.locator('.tab-strip .tab').filter({ hasText: 'Shell' }).click()
  await page.evaluate(profiles => window.chrome.webview.dispatchEvent(new MessageEvent('message', {
    data: JSON.stringify({ type: 'profiles.list', profiles: profiles.map(profile =>
      profile.id === 'pwsh' ? { ...profile, isAvailable: false } : profile) })
  })), realProfiles)

  const task = page.locator('.task-panel-row').filter({ has: page.locator('.row-title', { hasText: 'Jupyter - Environment Check' }) })
  const tabsBefore = await page.locator('.tab-strip .tab').count()
  const startsBefore = await page.evaluate(() => window.__shellCheckSent.filter(message => message.type === 'start').length)
  await task.getByRole('button', { name: 'New tab' }).click()
  await page.getByRole('alert', { name: 'Missing terminal shell' }).waitFor()
  assert.equal(await page.locator('.tab-strip .tab').count(), tabsBefore)
  assert.equal(await page.evaluate(() => window.__shellCheckSent.filter(message => message.type === 'start').length), startsBefore)
  console.log('PASS: Missing PowerShell 7 blocks a task before creating a failed tab')

  await page.getByRole('button', { name: 'Install PowerShell 7' }).click()
  assert.ok(await page.evaluate(() => window.__shellCheckSent.some(message => message.type === 'shell.setup' && message.profileId === 'pwsh')))
  console.log('PASS: Warning offers a PowerShell 7 setup action')

  await page.getByRole('button', { name: 'Recheck shells' }).click()
  await page.waitForFunction(() => window.__shellCheckMessages.filter(message => message.type === 'profiles.list').length >= 2)
  await page.getByRole('alert', { name: 'Missing terminal shell' }).waitFor({ state: 'hidden' })
  console.log('PASS: Recheck clears the warning when PowerShell 7 is available')

  assert.deepEqual(errors, [])
  console.log('PASS: No page errors')
} finally {
  await page.evaluate(profiles => {
    window.chrome.webview.postMessage = window.__shellCheckOriginalPost
    if (profiles) window.chrome.webview.dispatchEvent(new MessageEvent('message', {
      data: JSON.stringify({ type: 'profiles.list', profiles })
    }))
  }, realProfiles).catch(() => {})
}
process.exit(0)
