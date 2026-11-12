import { setTimeout as delay } from 'node:timers/promises'

// CDP can report the WebView2 target before Playwright attaches its page.
export async function waitForScientificPage(browser, timeoutMs = 45_000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const page = browser.contexts().flatMap(context => context.pages())
      .find(item => !item.isClosed() && item.url().includes('app.local'))
    if (page) return page
    await delay(250)
  }
  throw new Error('DevShell app page is unavailable after CDP attachment wait')
}
