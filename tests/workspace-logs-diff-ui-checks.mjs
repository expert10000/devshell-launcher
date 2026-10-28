// Live WebView2 UI check. Run against a built DevShell with DEVSHELL_CDP_URL set.
// Native Git reads and job controls for the fixture repository are simulated;
// this check never starts a job or writes to a repository.
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

const profileId = await page.locator('#workspace-profile-select').inputValue()
assert.equal(profileId, 'profile-laptop', 'The laptop profile contains the DevShell repository fixture')
const projectId = 'github', repositoryId = 'devshell'
const key = `${profileId}:${projectId}:${repositoryId}`
const logTitle = 'DevShell Logs', diffTitle = 'DevShell Diff'
assert.equal(await page.getByRole('tab', { name: logTitle }).count(), 0, 'Test log tab must be absent before the check')
assert.equal(await page.getByRole('tab', { name: diffTitle }).count(), 0, 'Test diff tab must be absent before the check')
const terminalCount = await page.locator('.tab-strip > .tab').count()
const pageErrors = []
page.on('pageerror', error => pageErrors.push(error.message))

await page.evaluate(({ profileId, projectId, repositoryId, key }) => {
  const webview = window.chrome.webview
  window.__logsDiffSent = []
  window.__logsDiffOriginalPost = webview.postMessage.bind(webview)
  window.__logsDiffEmit = message => webview.dispatchEvent(new MessageEvent('message', { data: JSON.stringify(message) }))
  webview.postMessage = message => {
    const parsed = typeof message === 'string' ? JSON.parse(message) : message
    window.__logsDiffSent.push(parsed)
    if (parsed?.type === 'workspace.tabs' && parsed.action === 'save') return
    if (parsed?.type === 'repository.job' && parsed.action === 'status') return
    if (parsed?.type === 'repository.job' && parsed.projectId === projectId && parsed.repositoryId === repositoryId) {
      if (parsed.action === 'changes' || parsed.action === 'file-diff') {
        const snapshot = { path: 'D:\\fixture', files: [{ path: 'sample.txt', staged: true, unstaged: true, conflicted: false }] }
        const diff = parsed.action === 'file-diff' ? { path: 'sample.txt', side: parsed.side,
          text: parsed.side === 'staged' ? 'STAGED DIFF FIXTURE' : 'WORKING DIFF FIXTURE', truncated: false } : undefined
        setTimeout(() => window.__logsDiffEmit({ type: 'repository.changes', profileId, requestId: parsed.requestId, snapshot, diff }), 0)
        return
      }
      if (parsed.action === 'stop' || parsed.action === 'log') return
    }
    window.__logsDiffOriginalPost(message)
  }
  window.__logsDiffEmit({ type: 'repository.jobs', jobs: [{ key, action: 'build', state: 'running', buildState: 'running',
    log: 'LIVE LOG FIXTURE', logPath: 'D:\\fixture\\job.log' }], batches: [] })
}, { profileId, projectId, repositoryId, key })

const open = kind => page.evaluate(({ profileId, projectId, repositoryId, kind }) =>
  window.dispatchEvent(new CustomEvent('devshell.workspace.open', { detail: { profileId, projectId, repositoryId, kind } })),
{ profileId, projectId, repositoryId, kind })
const sent = () => page.evaluate(() => window.__logsDiffSent)
let logOpened = false, diffOpened = false
try {
  await open('logs'); logOpened = true
  const logs = page.getByRole('tabpanel', { name: logTitle })
  await logs.getByText('LIVE LOG FIXTURE').waitFor()
  await logs.locator('[role="status"]').filter({ hasText: 'build: running' }).waitFor()
  await logs.getByRole('button', { name: 'Stop', exact: true }).click()
  await logs.getByRole('button', { name: 'Open full log' }).click()
  assert.ok((await sent()).some(message => message.type === 'repository.job' && message.action === 'stop' && message.repositoryId === repositoryId))
  assert.ok((await sent()).some(message => message.type === 'repository.job' && message.action === 'log' && message.repositoryId === repositoryId))
  const stopsBeforeClose = (await sent()).filter(message => message.type === 'repository.job' && message.action === 'stop').length
  await page.getByRole('button', { name: `Close ${logTitle}` }).click(); logOpened = false
  assert.equal((await sent()).filter(message => message.type === 'repository.job' && message.action === 'stop').length, stopsBeforeClose)
  console.log('PASS: Logs show live output and status; Stop/full-log controls send the intended actions; closing the view does not stop the job')

  await page.evaluate(() => window.__logsDiffEmit({ type: 'repository.jobs', jobs: [], batches: [] }))
  await open('diff'); diffOpened = true
  const diff = page.getByRole('tabpanel', { name: diffTitle })
  await diff.getByText('WORKING DIFF FIXTURE').waitFor()
  await diff.getByRole('combobox', { name: 'Diff side' }).selectOption('staged')
  await diff.getByText('STAGED DIFF FIXTURE').waitFor()
  await diff.getByRole('combobox', { name: 'Diff side' }).selectOption('working')
  await diff.getByText('WORKING DIFF FIXTURE').waitFor()
  await diff.getByRole('button', { name: 'Refresh' }).click()
  await diff.getByText('WORKING DIFF FIXTURE').waitFor()
  const gitRequests = (await sent()).filter(message => message.type === 'repository.job' && ['changes', 'file-diff'].includes(message.action))
  assert.ok(gitRequests.some(message => message.action === 'changes'))
  assert.ok(gitRequests.some(message => message.action === 'file-diff' && message.side === 'staged'))
  assert.ok(gitRequests.some(message => message.action === 'file-diff' && message.side === 'working'))
  assert.equal((await sent()).filter(message => message.type === 'repository.job' && ['stage', 'unstage', 'commit', 'push'].includes(message.action)).length, 0)
  assert.equal(await page.locator('.tab-strip > .tab').count(), terminalCount)
  assert.equal((await sent()).filter(message => message.type === 'start').length, 0)
  assert.deepEqual(pageErrors, [])
  console.log('PASS: Diff switches working/staged sides and Refresh rereads without Git writes or terminal replay')
} finally {
  if (diffOpened) {
    await page.getByRole('button', { name: `Close ${diffTitle}` }).click({ force: true }).catch(() => {})
    await page.getByRole('tab', { name: diffTitle }).waitFor({ state: 'detached' }).catch(() => {})
  }
  if (logOpened) {
    await page.getByRole('button', { name: `Close ${logTitle}` }).click({ force: true }).catch(() => {})
    await page.getByRole('tab', { name: logTitle }).waitFor({ state: 'detached' }).catch(() => {})
  }
  await page.evaluate(() => {
    const webview = window.chrome.webview
    webview.postMessage = window.__logsDiffOriginalPost
    webview.postMessage({ type: 'repository.job', action: 'status' })
    delete window.__logsDiffSent
    delete window.__logsDiffOriginalPost
    delete window.__logsDiffEmit
  }).catch(() => {})
  await page.getByRole('button', { name: 'Repositories', exact: true }).click().catch(() => {})
  await browser.close()
}
