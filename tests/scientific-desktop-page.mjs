import { setTimeout as delay } from 'node:timers/promises'

// CDP can publish the WebView target before Playwright attaches it to a context.
// Qualification actions must wait for that attachment, not just /json/list.
export async function scientificDesktopPage(browser, timeoutMs = 20_000) {
  const deadline = Date.now() + timeoutMs
  do {
    const pages = browser.contexts().flatMap(context => context.pages())
    const page = pages.find(item => !item.isClosed() && item.url().includes('app.local'))
    if (page) return page
    await delay(Math.min(250, Math.max(1, deadline - Date.now())))
  } while (Date.now() < deadline)
  throw new Error('DevShell app page did not attach to Playwright after CDP became ready')
}
