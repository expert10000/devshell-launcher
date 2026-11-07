// Opt-in live desktop check. Start BatchLauncher with WebView2 CDP port 9247.
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'

const require = createRequire(import.meta.url)
const root = join(import.meta.dirname, '..')
const localPlaywright = join(root, 'DevShell', 'ui', 'dev-ui-react', 'node_modules', 'playwright-core')
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || (existsSync(localPlaywright) ? localPlaywright :
  join(homedir(), '.cache', 'codex-runtimes', 'codex-primary-runtime', 'dependencies', 'node', 'node_modules', 'playwright')))
const browser = await chromium.connectOverCDP(process.env.DEVSHELL_CDP_URL || 'http://127.0.0.1:9247')
try {
  const page = browser.contexts().flatMap(context => context.pages()).find(item => item.url().includes('app.local'))
  assert.ok(page, 'DevShell desktop page must be running')
  page.setDefaultTimeout(30_000)
  await page.getByText('RUNTIMES / Scientific', { exact: true }).click()
  await page.getByLabel('Scientific execution environment').selectOption('wsl')
  await page.locator('.scientific-runtime-item').filter({ hasText: 'SageMath' }).click()
  await page.getByRole('navigation', { name: 'Scientific runtime sections' }).getByRole('button', { name: 'Tests' }).click()
  await page.getByRole('button', { name: 'Qualify exact Sage cases' }).click()
  const job = page.locator('.scientific-job-summary').filter({ hasText: 'sage-wsl / sage.qualify-exact' })
  await job.locator('.scientific-job-state').getByText('running', { exact: true }).waitFor()
  await job.locator('.scientific-job-state').getByText('succeeded', { exact: true }).waitFor({ timeout: 600_000 })
  await page.getByText('[pass] prime-rejection', { exact: false }).waitFor()

  const runs = join(root, '.scientific', 'runs')
  const saved = readdirSync(runs).map(id => ({ id, path: join(runs, id, 'results.json') }))
    .filter(item => existsSync(item.path))
    .map(item => ({ ...item, result: JSON.parse(readFileSync(item.path, 'utf8')) }))
    .filter(item => item.result.recipeId === 'sage.qualify-exact' && item.result.state === 'succeeded'
      && existsSync(join(runs, item.id, 'qualifications.json')))
    .sort((a, b) => statSync(b.path).mtimeMs - statSync(a.path).mtimeMs)
  assert.ok(saved.length, 'Managed Sage result must be saved')
  const latest = saved[0]
  assert.equal(latest.result.sageExactEvidence.verdict, 'passed')
  assert.equal(latest.result.sageExactEvidence.cases.length, 9)
  const records = JSON.parse(readFileSync(join(runs, latest.id, 'qualifications.json'), 'utf8')).records
  const exact = records.filter(item => item.evidenceId === 'sage.exact-suite')
  assert.deepEqual(exact.map(item => item.capabilityId).sort(),
    ['math.matrix.solve', 'math.number-field.quadratic', 'math.polynomial.factor', 'math.rational.add'])
  assert.ok(exact.every(item => item.level === 'L3' && item.evidenceSha256?.length === 64))
  await page.getByRole('navigation', { name: 'Scientific runtime sections' }).getByRole('button', { name: 'History' }).click()
  await page.getByRole('button', { name: /^(Load|Refresh) history$/ }).click()
  const summary = page.getByRole('region', { name: 'Current qualification summary' })
  await summary.getByText('math.number-field.quadratic', { exact: true }).waitFor({ timeout: 180_000 })
  await summary.getByRole('button', { name: latest.result.runId.slice(0, 12), exact: false }).first().click()
  const verified = page.getByRole('region', { name: 'Qualification records' })
  await verified.getByText('math.number-field.quadratic', { exact: true }).waitFor({ timeout: 180_000 })
  console.log(`PASS: managed Sage button saved nine cases and four L3 records (${latest.id})`)
} finally {
  await browser.close()
}
