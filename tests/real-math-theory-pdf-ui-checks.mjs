// Live host acceptance for existing Math and Theory PDFs. Run prepare, restart, then verify.
import assert from 'node:assert/strict'
import { randomUUID } from 'node:crypto'
import { createRequire } from 'node:module'
import { existsSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'

const phase = process.argv[2]
assert.ok(['prepare', 'verify'].includes(phase))
const root = process.env.DEVSHELL_REAL_PDF_ROOT
assert.ok(root, 'Set DEVSHELL_REAL_PDF_ROOT')
const theoryPath = 'release/v1.0.0/final_pdfs/Master/Theory_of_Quantum_Mechanics_COMPLETE_v1.0.0.pdf'
const mathPath = 'content/theory-of-real-analysis.pdf'
assert.ok(existsSync(join(root, 'theory', ...theoryPath.split('/'))))
assert.ok(existsSync(join(root, 'math', ...mathPath.split('/'))))
const require = createRequire(import.meta.url)
const localPlaywright = join(import.meta.dirname, '..', 'DevShell', 'ui', 'dev-ui-react', 'node_modules', 'playwright-core')
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || (existsSync(localPlaywright) ? localPlaywright :
  join(homedir(), '.cache', 'codex-runtimes', 'codex-primary-runtime', 'dependencies', 'node', 'node_modules', 'playwright')))
const browser = await chromium.connectOverCDP(process.env.DEVSHELL_CDP_URL || 'http://127.0.0.1:9237')
const page = browser.contexts().flatMap(context => context.pages()).find(item => item.url().includes('app.local'))
assert.ok(page, 'DevShell UI must be running')
page.setDefaultTimeout(30000)
const profile = page.locator('#workspace-profile-select')
const theoryTab = page.getByRole('tab', { name: `Theory / ${theoryPath.split('/').at(-1)}` })
const mathTab = page.getByRole('tab', { name: `Math / ${mathPath.split('/').at(-1)}` })
const collectionTab = page.getByRole('tab', { name: 'Math / PDF selector' })
const errors = []
page.on('pageerror', error => errors.push(error.message))

async function pdfRequest(repositoryId, action, filePath, pageNumber = 1) {
  const requestId = randomUUID()
  await page.evaluate(request => window.chrome.webview.postMessage(request), {
    type: 'workspace.pdf', profileId: 'profile-laptop', projectId: 'github', repositoryId,
    action, filePath, page: pageNumber, requestId,
  })
  await page.waitForFunction(requestId => window.__realPdfMessages.some(message =>
    message.type === 'workspace.pdf.result' && message.requestId === requestId), requestId, { timeout: 90000 })
  return page.evaluate(requestId => window.__realPdfMessages.find(message =>
    message.type === 'workspace.pdf.result' && message.requestId === requestId), requestId)
}

try {
  if (await profile.inputValue() !== 'profile-laptop') await profile.selectOption('profile-laptop')
  await page.evaluate(() => {
    window.__realPdfMessages = []
    window.__realPdfReceive = event => {
      try { window.__realPdfMessages.push(typeof event.data === 'string' ? JSON.parse(event.data) : event.data) } catch { }
    }
    window.chrome.webview.addEventListener('message', window.__realPdfReceive)
  })
  if (phase === 'prepare') {
    const configuredTheory = await pdfRequest('theory', 'open', null)
    if (existsSync(join(root, 'theory', 'build', 'main.pdf'))) {
      assert.ok(!configuredTheory.error, configuredTheory.error)
      assert.ok(configuredTheory.size > 100_000)
    } else assert.match(configuredTheory.error ?? '', /PDF is missing/)
    const mathList = await pdfRequest('math', 'list', null)
    assert.ok(!mathList.error, mathList.error)
    assert.ok(Array.isArray(mathList.files) && mathList.files.length <= 256)
    console.log(`PASS: configured Theory output ${configuredTheory.error ? 'is missing' : 'opens'}; Math collection lists ${mathList.files.length} PDFs`)

    const theory = await pdfRequest('theory', 'open', theoryPath, 2)
    assert.ok(!theory.error, theory.error)
    assert.ok(theory.size > 10_000_000, 'Expected the large Theory master PDF')
    await theoryTab.waitFor()
    await theoryTab.click()
    const theoryPane = page.getByRole('tabpanel', { name: `Theory / ${theoryPath.split('/').at(-1)}` })
    await theoryPane.getByText(/PDF (opened|loaded \/ refreshed) in the native viewer pane/).waitFor()
    assert.equal(await theoryPane.getByRole('spinbutton', { name: 'PDF page' }).inputValue(), '2')
    const refresh = await pdfRequest('theory', 'refresh', theoryPath, 2)
    assert.ok(!refresh.error, refresh.error)
    console.log('PASS: large Theory release PDF opens at page 2 and refreshes')

    const math = await pdfRequest('math', 'open', mathPath)
    assert.ok(!math.error, math.error)
    assert.ok(math.size > 100_000)
    await mathTab.waitFor()
    await mathTab.click()
    await page.getByRole('tabpanel', { name: `Math / ${mathPath.split('/').at(-1)}` })
      .getByText(/PDF (opened|loaded \/ refreshed) in the native viewer pane/).waitFor()
    await page.evaluate(() => window.dispatchEvent(new CustomEvent('devshell.workspace.open', {
      detail: { profileId: 'profile-laptop', kind: 'pdf', projectId: 'github', repositoryId: 'math', page: 1 },
    })))
    await collectionTab.waitFor()
    await collectionTab.click()
    const collectionPane = page.getByRole('tabpanel', { name: 'Math / PDF selector' })
    if (mathList.files.length) {
      await collectionPane.getByText(new RegExp(`${mathList.files.length} PDFs available`)).waitFor()
      await collectionPane.getByRole('combobox', { name: 'PDF volume or edition' }).selectOption(mathList.files[0])
      await collectionPane.getByRole('button', { name: 'Open PDF', exact: true }).click()
      await collectionPane.getByText('PDF loaded / refreshed in the native viewer pane.').waitFor()
    } else await collectionPane.getByText(/No collected PDFs yet/).waitFor()
    console.log('PASS: Math real PDF opens and configured selector reflects current build output')
  } else {
    await theoryTab.waitFor(); await mathTab.waitFor(); await collectionTab.waitFor()
    await theoryTab.click()
    const theoryPane = page.getByRole('tabpanel', { name: `Theory / ${theoryPath.split('/').at(-1)}` })
    await theoryPane.getByText(/Saved PDF entry/).waitFor()
    assert.equal(await theoryPane.getByRole('spinbutton', { name: 'PDF page' }).inputValue(), '2')
    await mathTab.click()
    await page.getByRole('tabpanel', { name: `Math / ${mathPath.split('/').at(-1)}` }).getByText(/Saved PDF entry/).waitFor()
    await collectionTab.click()
    await page.getByRole('tabpanel', { name: 'Math / PDF selector' }).getByText(/Saved PDF entry/).waitFor()
    const reopened = await pdfRequest('theory', 'open', theoryPath, 2)
    assert.ok(!reopened.error, reopened.error)
    console.log('PASS: Theory and Math PDF descriptors restore passively; explicit Theory reopen succeeds')
  }
  assert.deepEqual(errors, [])
  const nativeErrors = await page.evaluate(() => window.__realPdfMessages
    .filter(message => message.type === 'workspace.pdf.error')
    .map(message => ({ repositoryId: message.repositoryId, filePath: message.filePath, error: message.error })))
  assert.deepEqual(nativeErrors, [], 'Native PDF viewer reported navigation failures')
} finally {
  await page.evaluate(() => {
    window.chrome.webview.removeEventListener('message', window.__realPdfReceive)
    delete window.__realPdfMessages
    delete window.__realPdfReceive
  }).catch(() => {})
  await browser.close()
}
