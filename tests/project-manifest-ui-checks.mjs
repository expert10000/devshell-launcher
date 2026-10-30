import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { join } from 'node:path'

const require = createRequire(import.meta.url)
const { chromium } = require(join(import.meta.dirname, '..', 'DevShell', 'ui', 'dev-ui-react', 'node_modules', 'playwright-core'))
const browser = await chromium.connectOverCDP(process.env.DEVSHELL_CDP_URL || 'http://127.0.0.1:9237')
const page = browser.contexts().flatMap(context => context.pages()).find(item => item.url().includes('app.local'))
assert.ok(page, 'DevShell UI must be running')
page.setDefaultTimeout(15000)

await page.getByRole('button', { name: 'Manage', exact: true }).click()
await page.getByRole('button', { name: 'Import manifest…' }).waitFor()
await page.getByRole('button', { name: 'Import folder…' }).waitFor()
await page.evaluate(() => window.chrome.webview.dispatchEvent(new MessageEvent('message', { data: JSON.stringify({
  type: 'project.manifest.preview',
  preview: { manifestPath: 'C:\\sample\\devshell.project.json', project: { id: 'sample', name: 'Sample', root: 'C:\\sample' }, errors: ['Invalid version'], warnings: [] },
}) })))
const preview = page.getByRole('dialog', { name: 'Import project preview' })
await preview.getByText('Invalid version').waitFor()
assert.equal(await preview.getByRole('button', { name: 'Import project' }).isDisabled(), true)
await preview.getByRole('button', { name: 'Cancel' }).click()
assert.equal(await preview.count(), 0)
await page.evaluate(() => {
  const webview = window.chrome.webview
  window.__manifestPosted = []
  const originalPost = webview.postMessage.bind(webview)
  webview.postMessage = message => {
    if (['project.manifest.overrides.save', 'project.manifest.refresh.preview', 'project.manifest.refresh.apply'].includes(message.type)) {
      window.__manifestPosted.push(message)
      return
    }
    originalPost(message)
  }
  webview.dispatchEvent(new MessageEvent('message', { data: JSON.stringify({ type: 'projects.list', workspace: { version: 2, projects: [{
    id: 'managed-sample', name: 'Managed sample', root: 'C:\\source', manifestSource: 'C:\\source\\devshell.project.json',
    manifestOverrides: {}, repositories: [{ id: 'source', name: 'Source', path: 'C:\\source' }], service: { name: 'Lab', kind: 'jupyter', python: '' }, tasks: {},
  }] } }) }))
})
await page.locator('.project-editor-item').filter({ hasText: 'Managed sample' }).click()
await page.getByRole('button', { name: 'Local settings' }).click()
const settings = page.getByRole('dialog', { name: 'Local project settings' })
await settings.getByRole('textbox', { name: 'Project root override' }).fill('D:\\managed')
await settings.getByRole('textbox', { name: 'Python environment override' }).fill('D:\\.venv')
await settings.getByRole('button', { name: 'Save local settings' }).click()
assert.ok((await page.evaluate(() => window.__manifestPosted)).some(message => message.type === 'project.manifest.overrides.save' && message.overrides.root === 'D:\\managed'))
await settings.getByRole('button', { name: 'Cancel' }).click()
await page.getByRole('button', { name: 'Refresh manifest' }).click()
assert.ok((await page.evaluate(() => window.__manifestPosted)).some(message => message.type === 'project.manifest.refresh.preview' && message.projectId === 'managed-sample'))
await page.evaluate(() => window.chrome.webview.dispatchEvent(new MessageEvent('message', { data: JSON.stringify({
  type: 'project.manifest.preview', preview: { mode: 'refresh', targetProjectId: 'managed-sample', manifestPath: 'C:\\source\\devshell.project.json',
    project: { id: 'managed-sample', name: 'Managed sample', root: 'D:\\managed', tasks: { Test: {} } }, changes: ["Task 'Test' added"], errors: [], warnings: [] },
}) })))
const refresh = page.getByRole('dialog', { name: 'Refresh project preview' })
await refresh.getByText("Task 'Test' added", { exact: true }).waitFor()
await refresh.getByRole('button', { name: 'Apply refresh' }).click()
assert.ok((await page.evaluate(() => window.__manifestPosted)).some(message => message.type === 'project.manifest.refresh.apply'))
console.log('PASS: manifest import validation, local overrides, and refresh preview')
await browser.close()
