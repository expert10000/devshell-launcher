// Explicit live UI regression check. Launch DevShell with a loopback CDP port first.
// Browses existing Theory/Math fixtures; never launches tasks. Removes its test layout.
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
const require = createRequire(import.meta.url)
const { chromium } = require('C:/Users/janko/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright')
const browser = await chromium.connectOverCDP(process.env.DEVSHELL_CDP_URL || 'http://127.0.0.1:9237')
const page = browser.contexts().flatMap(context => context.pages()).find(item => item.url().includes('app.local'))
assert.ok(page, 'DevShell UI must be running')
page.setDefaultTimeout(10000)
let checks = 0
const pass = name => { checks++; console.log(`PASS: ${name}`) }
const errors = []
page.on('pageerror', error => errors.push(error.message))
const comparison = page.locator('details').filter({ has: page.locator('summary').filter({ hasText: 'Artifact comparison' }) })
const layouts = page.locator('details').filter({ has: page.locator('summary').filter({ hasText: 'Named layouts' }) })
const files = () => page.locator('.workspace-view:visible').filter({ has: page.getByRole('combobox', { name: 'Files repository', exact: true }) })
const openPalette = async () => {
  await page.keyboard.press('Control+Alt+p')
  await page.locator('dialog[open]').waitFor()
}
const chooseFile = async name => {
  await files().locator('.files-row').filter({ has: page.getByText(name, { exact: true }) }).click()
  await files().getByRole('button', { name: 'Compare as A', exact: true }).waitFor()
}
const setFolder = async path => {
  await files().getByRole('textbox', { name: 'Files relative folder', exact: true }).fill(path)
  await files().getByRole('button', { name: 'Go', exact: true }).click()
}
const nativeCount = () => page.evaluate(() => window.__workflowMessages.length)
const since = start => page.evaluate(start => window.__workflowMessages.slice(start), start)
const forbidden = messages => messages.filter(message => {
  const raw = JSON.stringify(message)
  return /repository\.job|task\.run|service\.control|browser\.open/.test(raw)
})
const previewRequests = messages => messages.filter(message => {
  const raw = JSON.stringify(message)
  return raw.includes('workspace.files') && /"action":"(preview|image|list|locate|diagnostic)"/.test(raw.replace(/\s/g, ''))
})
await page.evaluate(() => {
  window.__workflowMessages = []
  window.__workflowOriginalPost = window.chrome.webview.postMessage
  window.chrome.webview.postMessage = function (message) {
    const parsed = typeof message === 'string' ? JSON.parse(message) : message
    window.__workflowMessages.push(parsed)
    // Test safety guard: no accidental confirmation can launch a real task.
    if (/repository\.job|task\.run|service\.control|browser\.open/.test(JSON.stringify(parsed))) return
    return window.__workflowOriginalPost.call(window.chrome.webview, message)
  }
})
let testLayoutCreated = false
try {
  await openPalette()
  await page.getByRole('combobox', { name: 'Workspace command search' }).fill('Build Math3D')
  await page.getByRole('option').filter({ hasText: 'Build Math3D' }).click()
  await page.getByRole('button', { name: 'Run task', exact: true }).waitFor()
  assert.equal(forbidden(await since(0)).length, 0)
  pass('Palette task selection requires confirmation and starts no job')
  await page.getByRole('button', { name: 'Cancel task', exact: true }).click()
  await page.keyboard.press('Escape')
  await openPalette()
  await page.getByRole('combobox', { name: 'Workspace command search' }).fill('Open Theory files')
  await page.keyboard.press('ArrowDown')
  await page.keyboard.press('Enter')
  await files().getByRole('heading', { name: 'Theory Files', exact: true }).waitFor()
  pass('Palette keyboard navigation focuses the requested repository')
  if (await page.getByRole('button', { name: 'Single pane', exact: true }).count()) {
    await page.getByRole('button', { name: 'Single pane', exact: true }).click()
  }
  await page.getByRole('button', { name: 'Split right', exact: true }).click()
  assert.equal(await page.locator('.workspace-view:visible').count(), 2)
  pass('Split shows two distinct workspace views')
  await setFolder('bibliography')
  await chooseFile('reference_catalog.json')
  let start = await nativeCount()
  await files().getByRole('button', { name: 'Compare as A', exact: true }).click()
  assert.equal(previewRequests(await since(start)).length, 0)
  pass('Assigning comparison A reads no file')
  await files().getByRole('button', { name: 'Root', exact: true }).click()
  await chooseFile('main.tex')
  start = await nativeCount()
  await files().getByRole('button', { name: 'Compare as B', exact: true }).click()
  assert.equal(previewRequests(await since(start)).length, 0)
  pass('Assigning comparison B reads no file')
  await comparison.getByRole('button', { name: 'Compare artifacts', exact: true }).click()
  await comparison.locator('summary').filter({ hasText: 'Line-position differences' }).waitFor()
  assert.match(await comparison.innerText(), /JSONObject/)
  assert.match(await comparison.innerText(), /TEX source/)
  pass('Structured JSON and source report render side by side with differences')
  const separator = page.getByRole('separator', { name: 'Resize workspace panes', exact: true })
  await separator.focus()
  await separator.press('Home')
  await separator.press('ArrowRight')
  assert.equal(await separator.getAttribute('aria-valuenow'), '55')
  pass('Keyboard divider resizing is accessible')
  if (!(await layouts.evaluate(element => element.open))) await layouts.locator('summary').click()
  const layoutName = `Workflow UI ${Date.now()}`
  await layouts.getByRole('textbox', { name: 'Layout name', exact: true }).fill(layoutName)
  await layouts.getByRole('button', { name: 'Save layout', exact: true }).click()
  await layouts.getByRole('combobox', { name: 'Saved workspace layout', exact: true }).selectOption({ label: layoutName })
  testLayoutCreated = true
  await separator.press('Home')
  start = await nativeCount()
  await layouts.getByRole('button', { name: 'Restore layout', exact: true }).click()
  await page.waitForFunction(() => document.querySelector('[role="separator"]')?.getAttribute('aria-valuenow') === '55')
  const restoreMessages = await since(start)
  assert.equal(previewRequests(restoreMessages).length, 0)
  assert.equal(forbidden(restoreMessages).length, 0)
  assert.match(await files().innerText(), /TEX source/)
  pass('Named layout restores sizing passively and preserves existing preview')
  await layouts.getByRole('button', { name: 'Delete layout', exact: true }).click()
  testLayoutCreated = false
  await files().getByRole('combobox', { name: 'Files repository', exact: true }).selectOption({ label: 'Math' })
  await files().getByRole('heading', { name: 'Math Files', exact: true }).waitFor()
  await setFolder('chapters/figures')
  await chooseFile('Downloads_.figs_cayley_lines_w.png')
  await files().getByRole('button', { name: 'Compare as A', exact: true }).click()
  await chooseFile('Downloads_.figs_cayley_lines_z.png')
  await files().getByRole('button', { name: 'Compare as B', exact: true }).click()
  await comparison.getByRole('button', { name: 'Compare artifacts', exact: true }).click()
  await comparison.getByRole('img').nth(1).waitFor()
  assert.equal(await comparison.getByRole('img').count(), 2)
  pass('Repository switching scopes image comparison to the new checkout')
  await comparison.getByRole('button', { name: 'Actual size', exact: true }).first().click()
  assert.equal(await comparison.getByRole('img').count(), 2)
  pass('Image comparison exposes independent image controls')
  assert.deepEqual(errors, [])
  assert.equal(forbidden(await since(0)).length, 0)
  pass('Workflow emits no page errors and launches no tasks or services')
  console.log(`${checks} live workflow checks passed`)
} finally {
  if (testLayoutCreated) await layouts.getByRole('button', { name: 'Delete layout', exact: true }).click().catch(() => {})
  await page.evaluate(() => {
    window.chrome.webview.postMessage = window.__workflowOriginalPost
    delete window.__workflowOriginalPost
    delete window.__workflowMessages
  }).catch(() => {})
  // Disconnect from the native app without closing its WebView or user window.
}
process.exit(0)
