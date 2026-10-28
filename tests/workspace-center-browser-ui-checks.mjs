// Live WebView2 center-browser acceptance. Run `live`, restart DevShell, then `verify`.
// Back up and restore profile-laptop workspace/browser tabs around both phases.
import assert from 'node:assert/strict'
import { createHash, randomUUID } from 'node:crypto'
import { createRequire } from 'node:module'
import { existsSync, readFileSync } from 'node:fs'
import { createServer } from 'node:http'
import { homedir } from 'node:os'
import { join } from 'node:path'

const phase = process.argv[2]
assert.ok(['live', 'verify'].includes(phase), 'Use live or verify')
const profileId = 'profile-laptop'
const marker = 'fixture-secret-center-browser-314159'
const hash = createHash('sha256').update(profileId).digest('hex').toUpperCase()
const local = join(process.env.LOCALAPPDATA, 'DevShellLauncher')
const workspaceState = join(local, 'workspace-tabs', `${hash}.json`)
const nativeState = join(local, 'browser', hash, 'tabs.json')
const require = createRequire(import.meta.url)
const localPlaywright = join(import.meta.dirname, '..', 'DevShell', 'ui', 'dev-ui-react', 'node_modules', 'playwright-core')
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || (existsSync(localPlaywright) ? localPlaywright :
  join(homedir(), '.cache', 'codex-runtimes', 'codex-primary-runtime', 'dependencies', 'node', 'node_modules', 'playwright')))
let server, url
if (phase === 'live') {
  server = createServer((_request, response) => {
    response.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' })
    response.end('<!doctype html><title>Center Browser Fixture</title><main id="center-browser-ok">CENTER_BROWSER_OK</main>')
  })
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
  url = `http://127.0.0.1:${server.address().port}/center?token=${marker}&view=grid#section`
}
const browser = await chromium.connectOverCDP(process.env.DEVSHELL_CDP_URL || 'http://127.0.0.1:9237')
const page = browser.contexts().flatMap(context => context.pages()).find(item => item.url().includes('app.local'))
assert.ok(page, 'DevShell UI must be running')
page.setDefaultTimeout(30000)
const profile = page.locator('#workspace-profile-select')
const logs = page.getByRole('tab', { name: 'DevShell Logs' })
const browserTab = page.getByRole('tab', { name: '127.0.0.1 Browser' })
const jupyterTab = page.locator('.workspace-tab-entry .tab[title="Jupyter Studio"]')
const errors = []
page.on('pageerror', error => errors.push(error.message))

async function slotState() {
  const currentProfileId = await profile.inputValue()
  return page.evaluate(({ profileId, requestId }) => new Promise((resolve, reject) => {
    const timeout = setTimeout(() => { window.chrome.webview.removeEventListener('message', receive); reject(new Error('slot status timed out')) }, 5000)
    const receive = event => {
      let message
      try { message = typeof event.data === 'string' ? JSON.parse(event.data) : event.data } catch { return }
      if (message.type !== 'workspace.browser.slot.state' || message.requestId !== requestId) return
      clearTimeout(timeout); window.chrome.webview.removeEventListener('message', receive); resolve(message)
    }
    window.chrome.webview.addEventListener('message', receive)
    window.chrome.webview.postMessage({ type: 'workspace.browser.slot', action: 'status', profileId, requestId })
  }), { profileId: currentProfileId, requestId: randomUUID() })
}
async function waitMode(mode, timeoutMs = 20000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const state = await slotState()
    if (state.mode === mode) return state
    await new Promise(resolve => setTimeout(resolve, 250))
  }
  throw new Error(`Native browser never reached ${mode}; last mode was ${(await slotState()).mode}`)
}

try {
  if (await profile.inputValue() !== profileId) {
    await profile.selectOption(profileId)
    await page.waitForFunction(id => document.querySelector('#workspace-profile-select')?.value === id, profileId)
  }
  await page.evaluate(() => {
    window.__centerMessages = []
    window.__centerReceive = event => {
      try { window.__centerMessages.push(typeof event.data === 'string' ? JSON.parse(event.data) : event.data) } catch { }
    }
    window.chrome.webview.addEventListener('message', window.__centerReceive)
    window.__centerSent = []
    window.__centerOriginalPost = window.chrome.webview.postMessage.bind(window.chrome.webview)
    window.chrome.webview.postMessage = message => {
      window.__centerSent.push(message)
      window.__centerOriginalPost(message)
    }
  })
  if (phase === 'live') {
    await page.evaluate(url => window.chrome.webview.postMessage({ type: 'browser.open', projectId: 'github', url }), url)
    await browserTab.waitFor()
    await page.getByRole('tabpanel', { name: '127.0.0.1 Browser' }).getByRole('heading', { name: 'Browser workspace' }).waitFor()
    assert.equal((await waitMode('center')).mode, 'center')
    const nativePages = browser.contexts().flatMap(context => context.pages())
    const fixture = nativePages.find(item => item.url().startsWith(url.split('?')[0]))
    if (fixture) await fixture.locator('#center-browser-ok').waitFor()
    await page.evaluate(() => window.dispatchEvent(new CustomEvent('devshell.workspace.open', {
      detail: { profileId: 'profile-laptop', kind: 'logs', projectId: 'github', repositoryId: 'devshell' },
    })))
    await logs.click()
    await waitMode('hidden')
    const before = await page.evaluate(() => window.__centerSent.length)
    await browserTab.click()
    await waitMode('center')
    const selectionActions = await page.evaluate(before => window.__centerSent.slice(before).filter(message =>
      message.type === 'browser.open' || message.type === 'service.control' && message.action !== 'status'), before)
    assert.deepEqual(selectionActions, [])
    console.log('PASS: existing native browser displays in the center slot; switching tabs hides/restores it without navigating')

    await page.evaluate(() => window.chrome.webview.postMessage({ type: 'service.control', projectId: 'jupyter-studio', action: 'open' }))
    await page.waitForFunction(() => window.__centerMessages.some(message => message.type === 'workspace.browser.opened' && message.kind === 'jupyter'), null, { timeout: 90000 })
    await jupyterTab.waitFor()
    await waitMode('center', 90000)
    const beforeJupyterSelection = await page.evaluate(() => window.__centerSent.length)
    await browserTab.click(); await waitMode('center')
    await jupyterTab.click(); await waitMode('center')
    const jupyterSelectionActions = await page.evaluate(before => window.__centerSent.slice(before).filter(message =>
      message.type === 'browser.open' || message.type === 'service.control' && message.action !== 'status'), beforeJupyterSelection)
    assert.deepEqual(jupyterSelectionActions, [])
    assert.ok(existsSync(workspaceState) && existsSync(nativeState))
    await new Promise(resolve => setTimeout(resolve, 1000))
    const savedWorkspace = readFileSync(workspaceState, 'utf8')
    const savedNative = readFileSync(nativeState, 'utf8')
    assert.ok(savedWorkspace.includes('127.0.0.1') && savedWorkspace.includes('jupyter'))
    assert.ok(!savedWorkspace.includes(marker) && !savedNative.includes(marker))
    assert.ok(!savedWorkspace.includes('?token=') && !savedNative.includes('?token='))
    console.log('PASS: Browser/Jupyter center switching is passive; workspace and native saved URLs omit tokens')
    await page.evaluate(() => window.chrome.webview.postMessage({ type: 'service.control', projectId: 'jupyter-studio', action: 'stop' }))
    await page.waitForFunction(() => window.__centerMessages.some(message => message.type === 'service.status' && message.projectId === 'jupyter-studio' && message.state === 'stopped'), null, { timeout: 30000 })
  } else {
    await browserTab.waitFor(); await jupyterTab.waitFor()
    await browserTab.click()
    await page.getByRole('tabpanel', { name: '127.0.0.1 Browser' }).getByText(/Restored tabs wait for an explicit Open/).waitFor()
    await waitMode('hidden')
    await jupyterTab.click()
    await waitMode('hidden')
    const passiveActions = await page.evaluate(() => window.__centerSent.filter(message =>
      message.type === 'browser.open' || message.type === 'service.control' && message.action !== 'status'))
    assert.deepEqual(passiveActions, [])
    console.log('PASS: restart restores Browser/Jupyter center descriptors without navigation or service startup')
    await profile.selectOption('profile-portable')
    await page.waitForFunction(() => document.querySelector('#workspace-profile-select')?.value === 'profile-portable')
    await browserTab.waitFor({ state: 'detached' })
    await jupyterTab.waitFor({ state: 'detached' })
    await waitMode('hidden')
    await profile.selectOption(profileId)
    await page.waitForFunction(id => document.querySelector('#workspace-profile-select')?.value === id, profileId)
    await browserTab.waitFor(); await jupyterTab.waitFor()
    await browserTab.click()
    await waitMode('hidden')
    const profileActions = await page.evaluate(() => window.__centerSent.filter(message =>
      message.type === 'browser.open' || message.type === 'service.control' && message.action !== 'status'))
    assert.deepEqual(profileActions, [])
    console.log('PASS: Browser/Jupyter center tabs remain isolated across profiles and restore passively')
    await browserTab.click()
    await page.getByRole('tabpanel', { name: '127.0.0.1 Browser' }).getByRole('button', { name: 'Open / focus browser page' }).click()
    await waitMode('center')
    await logs.click()
    await waitMode('hidden')
    assert.deepEqual(errors, [])
    console.log('PASS: failed local navigation after restart leaves the center workspace usable')
  }
  assert.deepEqual(errors, [])
} finally {
  await page.evaluate(() => {
    if (window.__centerReceive) window.chrome.webview.removeEventListener('message', window.__centerReceive)
    if (window.__centerOriginalPost) window.chrome.webview.postMessage = window.__centerOriginalPost
    delete window.__centerMessages; delete window.__centerReceive; delete window.__centerSent; delete window.__centerOriginalPost
  }).catch(() => {})
  await browser.close()
  if (server) await new Promise(resolve => server.close(resolve))
}
