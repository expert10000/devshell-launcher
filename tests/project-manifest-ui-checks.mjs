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
console.log('PASS: project manifest preview shows validation and blocks invalid import')
await browser.close()
