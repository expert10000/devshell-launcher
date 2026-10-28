// Live WebView2 acceptance check. Run `prepare`, restart DevShell, then run `verify`.
// Back up and restore profile/browser tab state around the two phases. This check never
// starts a repository job, mutates Git, or starts Jupyter.
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { existsSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'

const phase = process.argv[2]
assert.ok(['prepare', 'verify'].includes(phase), 'Use prepare or verify')
const require = createRequire(import.meta.url)
const localPlaywright = join(import.meta.dirname, '..', 'DevShell', 'ui', 'dev-ui-react', 'node_modules', 'playwright-core')
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || (existsSync(localPlaywright) ? localPlaywright :
  join(homedir(), '.cache', 'codex-runtimes', 'codex-primary-runtime', 'dependencies', 'node', 'node_modules', 'playwright')))
const browser = await chromium.connectOverCDP(process.env.DEVSHELL_CDP_URL || 'http://127.0.0.1:9237')
const page = browser.contexts().flatMap(context => context.pages()).find(item => item.url().includes('app.local'))
assert.ok(page, 'DevShell UI must be running')
page.setDefaultTimeout(20000)
const profile = page.locator('#workspace-profile-select')
const profileId = 'profile-laptop'
const logTab = page.locator('.workspace-tab-entry .tab[title="DevShell Logs"]')
const diffTab = page.locator('.workspace-tab-entry .tab[title="DevShell Diff"]')
const errors = []
page.on('pageerror', error => errors.push(error.message))
const open = kind => page.evaluate(({ kind, profileId }) => window.dispatchEvent(new CustomEvent('devshell.workspace.open', {
  detail: { kind, profileId, projectId: 'github', repositoryId: 'devshell' }
})), { kind, profileId })

try {
  assert.equal(await profile.inputValue(), profileId)
  if (phase === 'prepare') {
    assert.equal(await logTab.count(), 0, 'DevShell Logs must be absent before preparation')
    assert.equal(await diffTab.count(), 0, 'DevShell Diff must be absent before preparation')
    await open('diff')
    await diffTab.waitFor()
    await page.getByRole('tabpanel', { name: 'DevShell Diff' }).getByText(/Clean checkout|Select a file and comparison side/).waitFor()
    await open('logs')
    await logTab.waitFor()
    await page.getByRole('tabpanel', { name: 'DevShell Logs' }).getByText('No job in this launcher session').waitFor()
    assert.equal(await logTab.getAttribute('aria-selected'), 'true')
    assert.deepEqual(errors, [])
    console.log('PASS: Logs and Diff descriptors prepared; Logs active before process restart')
  } else {
    await logTab.waitFor()
    await diffTab.waitFor()
    assert.equal(await logTab.getAttribute('aria-selected'), 'true', 'Active Logs tab restores after restart')
    await page.getByRole('tabpanel', { name: 'DevShell Logs' }).getByText('No job in this launcher session').waitFor()
    const journal = await page.evaluate(() => {
      const webview = window.chrome.webview
      const sent = [], received = []
      const originalPost = webview.postMessage.bind(webview)
      const listener = event => { try { received.push(typeof event.data === 'string' ? JSON.parse(event.data) : event.data) } catch { } }
      webview.addEventListener('message', listener)
      webview.postMessage = message => {
        const parsed = typeof message === 'string' ? JSON.parse(message) : message
        sent.push(parsed)
        originalPost(message)
      }
      window.__tabAcceptance = { sent, received, originalPost, listener }
      return true
    })
    assert.ok(journal)
    const sent = () => page.evaluate(() => window.__tabAcceptance.sent)
    const forbidden = messages => messages.filter(message => message.type === 'task.run' || message.type === 'browser.open' ||
      message.type === 'repository.job' && message.action !== 'status' ||
      message.type === 'service.control' && message.action !== 'status')
    try {
      await diffTab.click()
      const diff = page.getByRole('tabpanel', { name: 'DevShell Diff' })
      await diff.getByText(/Restored descriptor only/).waitFor()
      assert.equal(forbidden(await sent()).length, 0)
      assert.equal((await sent()).filter(message => message.type === 'repository.job' && message.action === 'changes').length, 0)
      console.log('PASS: restored Logs/Diff are passive; no job or Git action replayed')

      await profile.selectOption('profile-portable')
      await page.waitForFunction(() => document.querySelector('#workspace-profile-select')?.value === 'profile-portable')
      assert.equal(await logTab.count(), 0)
      assert.equal(await diffTab.count(), 0)
      await profile.selectOption(profileId)
      await page.waitForFunction(() => document.querySelector('#workspace-profile-select')?.value === 'profile-laptop')
      await logTab.waitFor(); await diffTab.waitFor()
      assert.equal(forbidden(await sent()).length, 0)
      console.log('PASS: workspace tab descriptors stay isolated across profiles')

      const jupyterTab = page.locator('.workspace-tab-entry .tab[title="Jupyter Studio"]')
      const browserTab = page.locator('.workspace-tab-entry .tab[title="Math3D Browser"]')
      await jupyterTab.waitFor(); await browserTab.waitFor()
      const beforeSelection = (await sent()).length
      await jupyterTab.click()
      await page.getByRole('tabpanel', { name: 'Jupyter Studio', exact: true }).getByRole('heading', { name: 'Jupyter workspace' }).waitFor()
      await browserTab.click()
      const browserEntry = page.getByRole('tabpanel', { name: 'Math3D Browser' })
      await browserEntry.getByRole('heading', { name: 'Browser workspace' }).waitFor()
      assert.equal(forbidden((await sent()).slice(beforeSelection)).length, 0)
      console.log('PASS: selecting Jupyter/Browser entries does not start a service or navigate')

      // Exercise a malformed destination through the native guard; it must not
      // create a browser tab or prevent further workspace navigation.
      const beforeInvalid = await page.evaluate(() => window.__tabAcceptance.received.length)
      await page.evaluate(() => window.chrome.webview.postMessage({ type: 'browser.open', projectId: 'github', url: 'file:///not-a-web-page' }))
      await page.waitForFunction(before => window.__tabAcceptance.received.slice(before).some(message =>
        message.type === 'error' && /HTTP or HTTPS/.test(message.message ?? '')), beforeInvalid)
      await logTab.click()
      await page.getByRole('tabpanel', { name: 'DevShell Logs' }).getByText('No job in this launcher session').waitFor()
      assert.deepEqual(errors, [])
      console.log('PASS: invalid browser navigation is rejected; workspace remains usable')

      await browserTab.click()
      const beforeOpen = await page.evaluate(() => window.__tabAcceptance.received.length)
      await browserEntry.getByRole('button', { name: 'Open / focus browser page' }).click()
      await page.waitForFunction(before => window.__tabAcceptance.received.slice(before).some(message =>
        message.type === 'workspace.browser.opened' && message.url === 'http://127.0.0.1:5180/'), beforeOpen)
      await browserTab.waitFor()
      await logTab.click()
      await page.getByRole('tabpanel', { name: 'DevShell Logs' }).getByText('No job in this launcher session').waitFor()
      assert.deepEqual(errors, [])
      console.log('PASS: failed local navigation preserves the repository browser entry and workspace remains usable')
    } finally {
      await page.evaluate(() => {
        const state = window.__tabAcceptance
        if (!state) return
        window.chrome.webview.postMessage = state.originalPost
        window.chrome.webview.removeEventListener('message', state.listener)
        delete window.__tabAcceptance
      }).catch(() => {})
    }
  }
} finally {
  await browser.close()
}
