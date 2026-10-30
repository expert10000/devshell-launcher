// Live WebView2 UI check with a disposable declared worker and intercepted bridge actions.
// The backend process lifecycle is exercised separately by ProcessServiceChecks.
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
await page.locator('.tab-strip .tab').filter({ hasText: 'Shell' }).first().click()
await page.locator('.inspector-tabs').waitFor()
const card = page.locator('.services-list .service-card[aria-label="Disposable Worker service controls"]')

await page.evaluate(() => {
  const webview = window.chrome.webview
  window.__workerOriginalPost = webview.postMessage.bind(webview)
  window.__workerActions = []
  window.__workerState = 'stopped'
  webview.addEventListener('message', event => {
    const message = typeof event.data === 'string' ? JSON.parse(event.data) : event.data
    if (message.type === 'workspace.tools.refreshed' && !window.__workerOriginalWorkspace) window.__workerOriginalWorkspace = message.workspace
  })
  window.__workerOriginalPost({ type: 'workspace.tools.refresh' })
})
try {
  await page.waitForFunction(() => !!window.__workerOriginalWorkspace)
  await page.evaluate(() => {
    const webview = window.chrome.webview
    const workspace = structuredClone(window.__workerOriginalWorkspace)
    workspace.projects.push({ id: 'disposable-worker', name: 'Disposable Worker Project', root: 'C:\\Temp',
      service: { kind: 'process', name: 'Disposable Worker', command: 'pwsh', arguments: ['-NoProfile'], cwd: 'C:\\Temp' } })
    const profileId = document.querySelector('#workspace-profile-select').value
    window.__workerProfileId = profileId
    webview.postMessage = message => {
      const request = typeof message === 'string' ? JSON.parse(message) : message
      if (window.__workerSetupMode && request.type === 'dashboard.request') return
      if (request.type === 'repository.job' && request.action === 'create-workspace') {
        window.__workerActions.push('create-workspace')
        queueMicrotask(() => webview.dispatchEvent(new MessageEvent('message', { data: JSON.stringify({
          type: 'repository.jobs', jobs: [{ key: `${profileId}:${request.projectId}:${request.repositoryId}`,
            action: 'create-workspace', state: 'succeeded', buildState: 'not-run', log: '', logPath: '' }], batches: []
        }) })))
        return
      }
      if (request.type === 'repository.job' && request.action === 'fix' && request.projectId === 'jupyter-studio') {
        window.__workerActions.push(`fix:${request.targets?.join(',')}`)
        return
      }
      if (request.projectId === 'disposable-worker' && request.type === 'service.control') {
        window.__workerActions.push(request.action)
        if (request.action === 'start' || request.action === 'restart') window.__workerState = 'running'
        if (request.action === 'stop') window.__workerState = 'stopped'
        queueMicrotask(() => webview.dispatchEvent(new MessageEvent('message', { data: JSON.stringify({
          type: 'service.status', projectId: 'disposable-worker', profileId,
          state: window.__workerState, message: window.__workerState === 'running' ? 'Running in this DevShell session' : 'Stopped'
        }) })))
        return
      }
      if (request.projectId === 'disposable-worker' && request.type === 'service.log') {
        window.__workerActions.push('logs')
        queueMicrotask(() => webview.dispatchEvent(new MessageEvent('message', { data: JSON.stringify({
          type: 'service.log.result', projectId: 'disposable-worker', profileId, data: 'WORKER_LOG'
        }) })))
        return
      }
      window.__workerOriginalPost(message)
    }
    webview.dispatchEvent(new MessageEvent('message', { data: JSON.stringify({ type: 'workspace.tools.refreshed', workspace }) }))
  })
  await page.locator('.inspector-tabs button').filter({ hasText: 'Services' }).click()
  await card.waitFor()
  assert.equal((await card.locator('.service-state').innerText()).toLowerCase(), 'stopped')
  assert.equal(await card.getByRole('button', { name: 'Open' }).isDisabled(), true)
  await card.getByRole('button', { name: 'Start', exact: true }).click()
  await card.locator('.service-state.running').waitFor()
  await card.getByRole('button', { name: 'Logs' }).click()
  await card.locator('.service-log-panel pre').filter({ hasText: 'WORKER_LOG' }).waitFor()
  await card.getByRole('button', { name: 'Restart', exact: true }).click()
  await card.locator('.service-state.running').waitFor()
  await card.getByRole('button', { name: 'Stop' }).click()
  await card.locator('.service-state.stopped').waitFor()
  const actions = await page.evaluate(() => window.__workerActions)
  for (const action of ['start', 'logs', 'restart', 'stop']) assert.ok(actions.includes(action), `${action} was not sent`)
  console.log('PASS: declared worker uses unified Start, status, Logs, Restart, Stop controls')
  await page.evaluate(() => { window.__workerSetupMode = true; window.chrome.webview.dispatchEvent(new MessageEvent('message', { data: JSON.stringify({
    type: 'dashboard.result', profileId: window.__workerProfileId, repositories: [], checkedAt: new Date().toISOString(),
    checks: [{ name: 'Jupyter workspace folder', state: 'error', detail: 'Missing JupyterWorkspace',
      projectId: 'jupyter-studio', repositoryId: 'environment', fixTarget: 'clone', fixLabel: 'Create workspace' }]
  }) })) })
  await page.locator('.services-list .service-card[aria-label="Jupyter Lab service controls"]')
    .getByRole('button', { name: 'Setup / Fix' }).click()
  const setup = page.locator('.services-list .service-card[aria-label="Jupyter Lab service controls"] .project-environment')
  await setup.waitFor()
  if (!await setup.getByRole('button', { name: 'Create workspace' }).count()) {
    console.error('Jupyter setup diagnostic:', await setup.innerText(), JSON.stringify(await page.evaluate(() =>
      window.__workerOriginalWorkspace.projects.filter(project => project.id === 'jupyter-studio' || project.id === 'github')
        .map(project => ({ id: project.id, root: project.root, repos: project.repositories?.map(repo => ({ id: repo.id, path: repo.path, url: repo.url })) }))), null, 2))
  }
  await setup.getByRole('button', { name: 'Create workspace' }).click()
  assert.equal(await page.getByRole('main', { name: 'Repositories' }).isVisible(), false)
  assert.ok((await page.evaluate(() => window.__workerActions)).includes('create-workspace'))
  await page.evaluate(() => window.chrome.webview.dispatchEvent(new MessageEvent('message', { data: JSON.stringify({
    type: 'dashboard.result', profileId: window.__workerProfileId, repositories: [], checkedAt: new Date().toISOString(),
    checks: [{ name: 'Python environment', state: 'error', detail: 'Missing devshell-jupyter\\Scripts\\python.exe',
      projectId: 'jupyter-studio', repositoryId: 'environment', fixTarget: 'python', fixLabel: 'Create Python environment' }]
  }) })))
  await setup.getByRole('button', { name: 'Create Python environment' }).click()
  assert.ok((await page.evaluate(() => window.__workerActions)).includes('fix:python'))
  assert.equal(await page.getByRole('main', { name: 'Repositories' }).isVisible(), false)
  console.log('PASS: Jupyter Setup / Fix keeps folder creation and Python installation beside the service')
} finally {
  await page.evaluate(() => {
    window.chrome.webview.postMessage = window.__workerOriginalPost
    if (window.__workerOriginalWorkspace) window.chrome.webview.dispatchEvent(new MessageEvent('message', {
      data: JSON.stringify({ type: 'workspace.tools.refreshed', workspace: window.__workerOriginalWorkspace })
    }))
  })
}
process.exit(0)
