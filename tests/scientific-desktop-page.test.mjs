import assert from 'node:assert/strict'
import test from 'node:test'
import { scientificDesktopPage } from './scientific-desktop-page.mjs'

test('waits for an app target to attach after CDP reports readiness', async () => {
  const pages = []
  const browser = { contexts: () => [{ pages: () => pages }] }
  const app = { isClosed: () => false, url: () => 'https://app.local/' }
  setTimeout(() => pages.push(app), 20)
  assert.equal(await scientificDesktopPage(browser, 500), app)
})

test('refuses to begin qualification when the app target never attaches', async () => {
  const browser = { contexts: () => [{ pages: () => [] }] }
  await assert.rejects(scientificDesktopPage(browser, 20), /did not attach/)
})
