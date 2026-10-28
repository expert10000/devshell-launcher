// Live WebView2 acceptance check against temporary profiles and a disposable repository.
// Run `prepare`, restart DevShell, then run `verify`. See tests/README.md.
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { existsSync, mkdirSync, writeFileSync, unlinkSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'

const phase = process.argv[2]
assert.ok(['prepare', 'verify'].includes(phase), 'Use prepare or verify')
const root = process.env.DEVSHELL_GROUP2_FIXTURE_ROOT
const profileId = process.env.DEVSHELL_GROUP2_PROFILE_ID
const otherProfileId = process.env.DEVSHELL_GROUP2_OTHER_PROFILE_ID
assert.ok(root && profileId && otherProfileId, 'Set the three DEVSHELL_GROUP2_* fixture variables')
const docs = join(root, 'docs')
const pdfPath = join(docs, 'sample.pdf')
const notePath = join(docs, 'note.txt')
const newPath = join(docs, 'new.txt')

function samplePdf() {
  const stream = page => `BT /F1 18 Tf 72 700 Td (Group 2 acceptance page ${page}) Tj ET\n`
  const one = stream(1), two = stream(2)
  const objects = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 6 0 R >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 7 0 R >>',
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    `<< /Length ${Buffer.byteLength(one)} >>\nstream\n${one}endstream`,
    `<< /Length ${Buffer.byteLength(two)} >>\nstream\n${two}endstream`,
  ]
  let output = '%PDF-1.4\n'
  const offsets = [0]
  for (let i = 0; i < objects.length; i++) {
    offsets.push(Buffer.byteLength(output))
    output += `${i + 1} 0 obj\n${objects[i]}\nendobj\n`
  }
  const xref = Buffer.byteLength(output)
  output += `xref\n0 ${offsets.length}\n0000000000 65535 f \n`
  for (const offset of offsets.slice(1)) output += `${String(offset).padStart(10, '0')} 00000 n \n`
  output += `trailer\n<< /Size ${offsets.length} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`
  return Buffer.from(output, 'ascii')
}

if (phase === 'prepare') {
  mkdirSync(docs, { recursive: true })
  writeFileSync(pdfPath, samplePdf())
  writeFileSync(notePath, 'Group 2 disposable file preview\n')
  if (existsSync(newPath)) unlinkSync(newPath)
}

const require = createRequire(import.meta.url)
const localPlaywright = join(import.meta.dirname, '..', 'DevShell', 'ui', 'dev-ui-react', 'node_modules', 'playwright-core')
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || (existsSync(localPlaywright) ? localPlaywright :
  join(homedir(), '.cache', 'codex-runtimes', 'codex-primary-runtime', 'dependencies', 'node', 'node_modules', 'playwright')))
const browser = await chromium.connectOverCDP(process.env.DEVSHELL_CDP_URL || 'http://127.0.0.1:9237')
const page = browser.contexts().flatMap(context => context.pages()).find(item => item.url().includes('app.local'))
assert.ok(page, 'DevShell UI must be running')
page.setDefaultTimeout(20000)
const errors = []
page.on('pageerror', error => errors.push(error.message))
const profile = page.locator('#workspace-profile-select')
const filesTab = page.getByRole('tab', { name: 'Fixture Files' })
const pdfTab = page.getByRole('tab', { name: 'Fixture / sample.pdf' })
const collectionTab = page.getByRole('tab', { name: 'Fixture / PDF selector' })
const logsTab = page.getByRole('tab', { name: 'Fixture Logs' })
const open = (kind, filePath) => page.evaluate(({ kind, filePath, profileId }) =>
  window.dispatchEvent(new CustomEvent('devshell.workspace.open', {
    detail: { kind, filePath, profileId, projectId: 'acceptance', repositoryId: 'fixture' },
  })), { kind, filePath, profileId })

try {
  await page.evaluate(() => {
    window.__group2Received = []
    window.__group2Listener = event => {
      try { window.__group2Received.push(typeof event.data === 'string' ? JSON.parse(event.data) : event.data) } catch { }
    }
    window.chrome.webview.addEventListener('message', window.__group2Listener)
  })
  if (phase === 'prepare') {
    await profile.selectOption(profileId)
    await page.waitForFunction(id => document.querySelector('#workspace-profile-select')?.value === id, profileId)
    for (const title of ['Fixture Files', 'Fixture / sample.pdf', 'Fixture / PDF selector', 'Fixture Logs']) {
      const close = page.getByRole('button', { name: `Close ${title}` })
      if (await close.count()) await close.click({ force: true })
    }
    await open('files')
    await filesTab.waitFor()
    const files = page.getByRole('tabpanel', { name: 'Fixture Files' })
    await files.locator('.files-row', { hasText: 'docs' }).click()
    await files.locator('.files-row', { hasText: 'sample.pdf' }).waitFor()
    await files.locator('.files-row', { hasText: 'note.txt' }).click()
    await files.getByText('Group 2 disposable file preview').waitFor()
    writeFileSync(newPath, 'Appeared after Refresh files\n')
    await files.getByRole('button', { name: 'Refresh files' }).click()
    await files.locator('.files-row', { hasText: 'new.txt' }).waitFor()
    await files.getByRole('textbox', { name: 'Files relative folder' }).fill('missing-directory')
    await files.getByRole('button', { name: 'Go', exact: true }).click()
    await files.getByRole('alert').filter({ hasText: /Folder is missing/ }).waitFor()
    await files.getByRole('button', { name: 'Root', exact: true }).click()
    await files.locator('.files-row', { hasText: 'docs' }).waitFor()
    await files.locator('.files-row', { hasText: 'docs' }).click()
    await files.locator('.files-row', { hasText: 'sample.pdf' }).click()
    await pdfTab.waitFor()
    const pdf = page.getByRole('tabpanel', { name: 'Fixture / sample.pdf' })
    await pdf.getByRole('button', { name: 'Refresh PDF' }).click()
    await pdf.getByText('PDF loaded / refreshed in the native viewer pane.').waitFor()
    unlinkSync(pdfPath)
    await pdf.getByRole('button', { name: 'Refresh PDF' }).click()
    await pdf.getByRole('alert').filter({ hasText: /PDF is missing/ }).waitFor()
    writeFileSync(pdfPath, samplePdf())
    await pdf.getByRole('button', { name: 'Refresh PDF' }).click()
    await pdf.getByText('PDF loaded / refreshed in the native viewer pane.').waitFor()
    await pdf.getByRole('spinbutton', { name: 'PDF page' }).fill('2')
    await pdf.getByRole('button', { name: 'Go to page' }).click()
    await page.waitForFunction(() => window.__group2Received?.some(message => message.type === 'workspace.pdf.result' && message.action === 'open' && message.page === 2 && !message.error))
    await open('pdf')
    await collectionTab.waitFor()
    const collection = page.getByRole('tabpanel', { name: 'Fixture / PDF selector' })
    await collection.getByText(/1 PDFs available/).waitFor({ timeout: 70000 })
    await collection.getByRole('button', { name: 'Refresh list' }).click()
    await collection.getByText(/1 PDFs available/).waitFor()
    unlinkSync(pdfPath)
    await collection.getByRole('button', { name: 'Refresh list' }).click()
    await collection.getByText(/No collected PDFs yet/).waitFor()
    writeFileSync(pdfPath, samplePdf())
    await collection.getByRole('button', { name: 'Refresh list' }).click()
    await collection.getByText(/1 PDFs available/).waitFor()
    console.log('PASS: Files preview, refresh, missing-folder recovery; PDF open, missing-file recovery, page 2 and collection refresh')

    await page.evaluate(() => window.chrome.webview.postMessage({ type: 'repository.job', action: 'build', projectId: 'acceptance', repositoryId: 'fixture' }))
    await open('logs')
    await logsTab.waitFor()
    const logs = page.getByRole('tabpanel', { name: 'Fixture Logs' })
    await logs.getByText('GROUP2_JOB_READY').waitFor()
    await logs.getByRole('button', { name: 'Stop', exact: true }).click()
    await logs.getByText(/build: stopped/).waitFor()
    const result = await page.evaluate(() => window.__group2Received.filter(message => message.type === 'repository.jobs')
      .flatMap(message => message.jobs ?? []).findLast(job => job.key === `${document.querySelector('#workspace-profile-select')?.value}:acceptance:fixture`))
    assert.equal(result?.state, 'stopped')
    assert.ok(result?.logPath && existsSync(result.logPath), 'Real managed job wrote a persistent log')
    console.log('PASS: Logs Stop cancelled the real disposable managed job; persistent log exists')

    await profile.selectOption(otherProfileId)
    await filesTab.waitFor({ state: 'detached' })
    await pdfTab.waitFor({ state: 'detached' })
    await collectionTab.waitFor({ state: 'detached' })
    await logsTab.waitFor({ state: 'detached' })
    await profile.selectOption(profileId)
    await filesTab.waitFor(); await pdfTab.waitFor(); await collectionTab.waitFor(); await logsTab.waitFor()
    await pdfTab.click()
    assert.equal(await pdf.getByRole('spinbutton', { name: 'PDF page' }).inputValue(), '2')
    assert.deepEqual(errors, [])
    console.log('PASS: PDF/collection/Files/Logs descriptors and explicit PDF page are isolated by profile')
  } else {
    assert.equal(await profile.inputValue(), profileId)
    await filesTab.waitFor(); await pdfTab.waitFor(); await collectionTab.waitFor(); await logsTab.waitFor()
    await pdfTab.click()
    const pdf = page.getByRole('tabpanel', { name: 'Fixture / sample.pdf' })
    await pdf.getByText(/Saved PDF entry/).waitFor()
    assert.equal(await pdf.getByRole('spinbutton', { name: 'PDF page' }).inputValue(), '2')
    await collectionTab.click()
    await page.getByRole('tabpanel', { name: 'Fixture / PDF selector' }).getByText(/Saved PDF entry/).waitFor()
    await logsTab.click()
    await page.getByRole('tabpanel', { name: 'Fixture Logs' }).getByText('No job in this launcher session').waitFor()
    const restoredFiles = page.locator('[role="tabpanel"][aria-label="Fixture Files"]')
    assert.match(await restoredFiles.innerText(), /Saved location only/, 'Files restoration remains passive before selection')
    await filesTab.click()
    const files = page.getByRole('tabpanel', { name: 'Fixture Files' })
    await files.locator('.files-row', { hasText: 'sample.pdf' }).waitFor()
    assert.equal(await files.getByRole('textbox', { name: 'Files relative folder' }).inputValue(), 'docs')
    await profile.selectOption(otherProfileId)
    await filesTab.waitFor({ state: 'detached' })
    await pdfTab.waitFor({ state: 'detached' })
    await collectionTab.waitFor({ state: 'detached' })
    await profile.selectOption(profileId)
    await filesTab.waitFor(); await pdfTab.waitFor(); await collectionTab.waitFor()
    assert.deepEqual(errors, [])
    console.log('PASS: restart restores passive PDF/Files descriptors and saved page, without replaying a job or reopening a document')
  }
} finally {
  await page.evaluate(() => {
    if (window.__group2Listener) window.chrome.webview.removeEventListener('message', window.__group2Listener)
    delete window.__group2Listener
    delete window.__group2Received
  }).catch(() => {})
  await browser.close()
}
