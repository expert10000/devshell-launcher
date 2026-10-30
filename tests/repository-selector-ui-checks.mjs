// Live WebView2 check: selecting a repository from an open Shell tab focuses its Files workspace.
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
page.setDefaultTimeout(15000)

await page.locator('.project-row-main').filter({ hasText: 'GitHub Repos' }).click()
await page.locator('.tab-strip > .tab').filter({ hasText: 'Shell' }).first().click()
const selector = page.getByRole('group', { name: 'Select repository' })
const filesTab = page.locator('.workspace-tab-entry .tab[title="Math3D Files"]')
const filesBefore = await filesTab.count()
await selector.getByRole('button', { name: /Math3D/ }).click()
await filesTab.waitFor()
assert.equal(await filesTab.getAttribute('aria-selected'), 'true')
await page.getByRole('tabpanel', { name: 'Math3D Files' }).waitFor({ state: 'visible' })

await page.locator('.tab-strip > .tab').filter({ hasText: 'Shell' }).first().click()
await selector.getByRole('button', { name: /Math3D/ }).click()
assert.equal(await filesTab.count(), 1, 'Selecting the repository again should reuse its Files tab')
assert.equal(await filesTab.getAttribute('aria-selected'), 'true')
console.log('PASS: Math3D selector switches from Shell to one reusable Files tab')

await page.evaluate(() => {
  const webview = window.chrome.webview
  window.__toolSetupSent = []
  window.__toolCloneSent = []
  window.__toolSetupOriginalPost = webview.postMessage.bind(webview)
  webview.addEventListener('message', event => {
    const message = typeof event.data === 'string' ? JSON.parse(event.data) : event.data
    if (message?.type === 'workspace.tools.refreshed' && !window.__toolSetupWorkspace) window.__toolSetupWorkspace = message.workspace
  })
  webview.postMessage = message => {
    const parsed = typeof message === 'string' ? JSON.parse(message) : message
    if (parsed?.type === 'tool.setup') { window.__toolSetupSent.push(parsed); return }
    if (parsed?.type === 'repository.job' && parsed.action === 'clone') { window.__toolCloneSent.push(parsed); return }
    if (window.__toolSetupHoldDashboard && parsed?.type === 'dashboard.request') return
    window.__toolSetupOriginalPost(message)
  }
  window.__toolSetupOriginalPost({ type: 'workspace.tools.refresh' })
})
try {
  await page.waitForFunction(() => !!window.__toolSetupWorkspace)
  await page.evaluate(() => {
    const workspace = structuredClone(window.__toolSetupWorkspace)
    delete workspace.globals.tools.git
    delete workspace.globals.tools.pwsh
    delete workspace.globals.tools.node
    delete workspace.globals.tools.npm
    delete workspace.globals.tools.python
    delete workspace.globals.tools.dotnet
    window.chrome.webview.dispatchEvent(new MessageEvent('message', { data: JSON.stringify({ type: 'workspace.tools.refreshed', workspace }) }))
  })
  await page.locator('.tab-strip > .tab').filter({ hasText: 'Repositories' }).click()
  const requiredTools = page.getByRole('region', { name: 'Required tools' })
  await requiredTools.getByRole('button', { name: 'Install Git' }).click()
  await requiredTools.getByRole('button', { name: 'Install PowerShell 7' }).click()
  await requiredTools.getByRole('button', { name: 'Install Node.js and npm' }).click()
  await requiredTools.getByRole('button', { name: 'Install Python' }).click()
  await requiredTools.getByRole('button', { name: 'Install .NET SDK' }).click()
  assert.equal(await page.getByRole('button', { name: 'Update All' }).isDisabled(), true)
  const sent = await page.evaluate(() => window.__toolSetupSent)
  assert.ok(sent.some(message => message.toolId === 'git' && message.action === 'install'))
  assert.ok(sent.some(message => message.toolId === 'pwsh' && message.action === 'install'))
  assert.ok(sent.some(message => message.toolId === 'node' && message.action === 'install'))
  assert.ok(sent.some(message => message.toolId === 'python' && message.action === 'install'))
  assert.ok(sent.some(message => message.toolId === 'dotnet' && message.action === 'install'))
  console.log('PASS: Declared project/repository tools show install actions before cloning; Update All waits for Git')
  await page.getByRole('button', { name: 'General setup' }).click()
  const setup = page.getByRole('dialog', { name: 'General setup' })
  await setup.getByRole('region', { name: 'Required tools' }).getByRole('button', { name: 'Install PowerShell 7' }).click()
  assert.ok((await page.evaluate(() => window.__toolSetupSent)).filter(message => message.toolId === 'pwsh').length >= 2)
  await page.evaluate(() => {
    window.__toolSetupHoldDashboard = true
    window.chrome.webview.dispatchEvent(new MessageEvent('message', { data: JSON.stringify({
      type: 'workspace.tools.refreshed', workspace: window.__toolSetupWorkspace
    }) }))
  })
  await page.waitForTimeout(1000)
  await page.evaluate(() => {
    const profileId = document.querySelector('#workspace-profile-select').value
    window.chrome.webview.dispatchEvent(new MessageEvent('message', { data: JSON.stringify({ type: 'dashboard.result', profileId,
      checkedAt: new Date().toISOString(), repositories: [{ projectId: 'github', id: 'math3d', path: 'D:\\masters\\Math3D', changed: 0, files: [], error: 'Repository folder is missing.' }],
      checks: [{ projectId: 'github', repositoryId: 'math3d', name: 'Repository folder', state: 'error', detail: 'Missing D:\\masters\\Math3D', fixTarget: 'clone', fixLabel: 'Clone repository' }]
    }) }))
  })
  await setup.getByRole('article', { name: 'Math3D setup' }).getByRole('button', { name: 'Clone repository' }).click()
  assert.ok((await page.evaluate(() => window.__toolCloneSent)).some(message => message.projectId === 'github' && message.repositoryId === 'math3d'))
  console.log('PASS: General setup exposes missing PowerShell and repository clone actions')
  await setup.getByRole('button', { name: 'Close' }).click()
} finally {
  await page.evaluate(() => {
    window.chrome.webview.postMessage = window.__toolSetupOriginalPost
    if (window.__toolSetupWorkspace) window.chrome.webview.dispatchEvent(new MessageEvent('message', {
      data: JSON.stringify({ type: 'workspace.tools.refreshed', workspace: window.__toolSetupWorkspace })
    }))
  }).catch(() => {})
}
if (!filesBefore) await page.getByRole('button', { name: 'Close Math3D Files' }).click()
process.exit(0)
