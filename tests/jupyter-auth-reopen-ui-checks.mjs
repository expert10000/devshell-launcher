// Run `prepare`, restart the desktop process, then run `verify`.
// The runner backs up profile state and leaves an existing Jupyter server running.
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { createHash, randomUUID } from 'node:crypto'
import { createRequire } from 'node:module'
import { existsSync, readFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'

const phase = process.argv[2]
assert.ok(['prepare', 'verify'].includes(phase), 'Use prepare or verify')
const python = process.env.DEVSHELL_JUPYTER_PYTHON
const root = process.env.DEVSHELL_JUPYTER_ROOT
const controller = join(import.meta.dirname, '..', 'BatchLauncher', 'service_control.py')
assert.ok(python && root, 'Jupyter Python and workspace root are required')
const profileHash = createHash('sha256').update('profile-laptop').digest('hex').toUpperCase()
const stateRoot = join(process.env.LOCALAPPDATA, 'DevShellLauncher')
const workspaceState = join(stateRoot, 'workspace-tabs', `${profileHash}.json`)
const browserState = join(stateRoot, 'browser', profileHash, 'tabs.json')
const require = createRequire(import.meta.url)
const localPlaywright = join(import.meta.dirname, '..', 'DevShell', 'ui', 'dev-ui-react', 'node_modules', 'playwright-core')
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || (existsSync(localPlaywright) ? localPlaywright :
  join(homedir(), '.cache', 'codex-runtimes', 'codex-primary-runtime', 'dependencies', 'node', 'node_modules', 'playwright')))
const browser = await chromium.connectOverCDP(process.env.DEVSHELL_CDP_URL || 'http://127.0.0.1:9237')
const page = browser.contexts().flatMap(context => context.pages()).find(item => item.url().includes('app.local'))
assert.ok(page, 'DevShell UI must be running')
page.setDefaultTimeout(30000)
const profile = page.locator('#workspace-profile-select')
const jupyterTab = page.locator('.workspace-tab-entry .tab[title="Jupyter Studio"]')
const errors = []
page.on('pageerror', error => errors.push(error.message))

async function authenticatedContents() {
  // The controller discovers the running server's token, as it does for Open.
  // Never print or persist the authenticated URL.
  const result = JSON.parse(execFileSync(python, [controller, 'open', '--root', root, '--port', '8890', '--no-open'],
    { encoding: 'utf8', timeout: 90000 }))
  assert.equal(result.state, 'running', result.message)
  const lab = new URL(result.url)
  assert.equal(lab.hostname, '127.0.0.1')
  assert.equal(lab.port, '8890')
  assert.ok(lab.searchParams.has('token'), 'Open must reacquire the authentication token')
  const contents = new URL('/api/contents', lab)
  contents.searchParams.set('token', lab.searchParams.get('token'))
  const response = await fetch(contents, { signal: AbortSignal.timeout(15000) })
  assert.equal(response.status, 200, 'Authenticated Jupyter contents request failed')
  assert.equal((await response.json()).type, 'directory')
}

async function centerMode() {
  return page.evaluate(requestId => new Promise((resolve, reject) => {
    const timer = setTimeout(() => { window.chrome.webview.removeEventListener('message', receive); reject(new Error('Browser slot status timed out')) }, 5000)
    const receive = event => {
      const message = typeof event.data === 'string' ? JSON.parse(event.data) : event.data
      if (message.type !== 'workspace.browser.slot.state' || message.requestId !== requestId) return
      clearTimeout(timer)
      window.chrome.webview.removeEventListener('message', receive)
      resolve(message.mode)
    }
    window.chrome.webview.addEventListener('message', receive)
    window.chrome.webview.postMessage({ type: 'workspace.browser.slot', action: 'status', profileId: 'profile-laptop', requestId })
  }), randomUUID())
}

async function waitForCenter() {
  for (let attempt = 0; attempt < 80; attempt++) {
    if (await centerMode() === 'center') return
    await new Promise(resolve => setTimeout(resolve, 250))
  }
  throw new Error('Jupyter browser did not appear in the center workspace')
}

async function openAndCheck(action) {
  const marker = await page.evaluate(() => window.__jupyterReopenMessages.length)
  await action()
  try {
    await page.waitForFunction(marker => window.__jupyterReopenMessages.slice(marker).some(message =>
      message.type === 'workspace.browser.opened' && message.kind === 'jupyter' && message.projectId === 'jupyter-studio'),
    marker, { timeout: 90000 })
  } catch (error) {
    const events = await page.evaluate(marker => window.__jupyterReopenMessages.slice(marker)
      .filter(message => message.type === 'service.status' || message.type === 'workspace.browser.opened')
      .map(message => ({ type: message.type, state: message.state, message: message.message, kind: message.kind })), marker)
    console.error('Jupyter reopen events:', events)
    throw error
  }
  const event = await page.evaluate(marker => window.__jupyterReopenMessages.slice(marker)
    .find(message => message.type === 'workspace.browser.opened' && message.kind === 'jupyter'), marker)
  assert.ok(event.url == null, 'The bridge must not expose the authenticated URL')
  await jupyterTab.waitFor()
  await page.getByRole('tabpanel', { name: 'Jupyter Studio' }).getByRole('heading', { name: 'Jupyter workspace' }).waitFor()
  await waitForCenter()
  await authenticatedContents()
  await new Promise(resolve => setTimeout(resolve, 700))
  assert.ok(existsSync(workspaceState) && existsSync(browserState), 'Both tab stores must be saved')
  for (const path of [workspaceState, browserState]) {
    assert.doesNotMatch(readFileSync(path, 'utf8'), /[?&]token=/i, 'Saved tabs must not contain Jupyter tokens')
  }
}

try {
  if (await profile.inputValue() !== 'profile-laptop') await profile.selectOption('profile-laptop')
  await page.evaluate(() => {
    window.__jupyterReopenMessages = []
    window.__jupyterReopenReceive = event => {
      try { window.__jupyterReopenMessages.push(typeof event.data === 'string' ? JSON.parse(event.data) : event.data) } catch { }
    }
    window.chrome.webview.addEventListener('message', window.__jupyterReopenReceive)
  })
  if (phase === 'prepare') {
    await openAndCheck(() => page.evaluate(() => window.chrome.webview.postMessage({
      type: 'service.control', projectId: 'jupyter-studio', action: 'open',
    })))
    console.log('PASS: authenticated Jupyter is open before desktop restart')
  } else {
    await jupyterTab.waitFor()
    await jupyterTab.click()
    await page.getByRole('tabpanel', { name: 'Jupyter Studio' }).getByText(/Restored tabs wait for an explicit Open/).waitFor()
    const passive = await page.evaluate(() => window.__jupyterReopenMessages.some(message =>
      message.type === 'workspace.browser.opened'))
    assert.equal(passive, false, 'Selecting a restored Jupyter tab must stay passive')
    await openAndCheck(() => page.getByRole('tabpanel', { name: 'Jupyter Studio' })
      .getByRole('button', { name: 'Open Jupyter' }).click())
    console.log('PASS: after desktop restart, explicit Open reacquires a valid Jupyter token and reopens the center tab')
  }
  assert.deepEqual(errors, [])
} finally {
  await page.evaluate(() => {
    window.chrome.webview.removeEventListener('message', window.__jupyterReopenReceive)
    delete window.__jupyterReopenMessages
    delete window.__jupyterReopenReceive
  }).catch(() => {})
  await browser.close()
}
