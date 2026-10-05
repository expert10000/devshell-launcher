import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { homedir } from 'node:os';
import { join } from 'node:path';

const require = createRequire(import.meta.url);
const uiRequire = createRequire(new URL('../../DevShell/ui/dev-ui-react/package.json', import.meta.url));
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || join(homedir(), '.cache', 'codex-runtimes', 'codex-primary-runtime', 'dependencies', 'node', 'node_modules', 'playwright'));
const ts = uiRequire('typescript');
const source = readFileSync(new URL('../../DevShell/ui/dev-ui-react/src/htmlPreview.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText;
const candidates = [process.env.HTML_CHECK_BROWSER, chromium.executablePath(), 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe', 'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe', 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'].filter(Boolean);
const executablePath = candidates.find(path => existsSync(path));
if (!executablePath) throw new Error('No test browser found. Set HTML_CHECK_BROWSER to a Chromium-based browser executable.');
const browser = await chromium.launch({ executablePath, headless: true });
const page = await browser.newPage();
const attemptedResources = [];
await page.route('**/*', route => { attemptedResources.push(route.request().url()); return route.abort(); });
await page.setContent('<!doctype html><html><body></body></html>');
await page.addScriptTag({ content: `(() => { const exports = {}; ${compiled}\nwindow.htmlPreviewChecks = exports; window.__htmlCanary = false; })();` });
const pass = label => console.log(`PASS: ${label}`);
async function render(srcDoc) {
  await page.evaluate(doc => {
    document.getElementById('html-check-frame')?.remove();
    const frame = document.createElement('iframe'); frame.id = 'html-check-frame'; frame.setAttribute('sandbox', ''); frame.referrerPolicy = 'no-referrer'; frame.srcdoc = doc; document.body.appendChild(frame);
  }, srcDoc);
  const handle = await page.locator('#html-check-frame').elementHandle();
  assert.ok(handle, 'Preview iframe is attached');
  const frame = await handle.contentFrame();
  assert.ok(frame, 'Preview browsing context is available');
  await frame.locator('meta[http-equiv="Content-Security-Policy"]').waitFor({ state: 'attached' });
  return frame;
}
try {
  const hostile = `<script>window.__htmlCanary=true;parent.__htmlCanary=true</script><script src="http://127.0.0.1:9/preview-script"></script><style>@import url("http://127.0.0.1:9/preview-style");.fixture{color:rgb(1,2,3);background-image:url("http://127.0.0.1:9/preview-background")}</style><link rel="stylesheet" href="http://127.0.0.1:9/preview-link"><base href="http://127.0.0.1:9/"><meta http-equiv="refresh" content="0;url=http://127.0.0.1:9/preview-refresh"><h1 class="fixture" onclick="window.__htmlCanary=true">Static fixture</h1><a href="http://127.0.0.1:9/preview-navigation" ping="http://127.0.0.1:9/preview-ping" target="_top">Inert link</a><form action="http://127.0.0.1:9/preview-form"><input name="secret" value="fixture"><button>Submit</button></form><img src="http://127.0.0.1:9/preview-image" onerror="window.__htmlCanary=true" alt="Blocked image"><iframe src="http://127.0.0.1:9/preview-frame"></iframe><object data="http://127.0.0.1:9/preview-object"></object><svg onload="window.__htmlCanary=true"><script>window.__htmlCanary=true</script></svg><math><mtext>Foreign markup</mtext></math><table><tr><th>Safe heading</th><td>Safe cell</td></tr></table>`;
  const preview = await page.evaluate(text => window.htmlPreviewChecks.buildStaticHtmlPreview(text), hostile);
  await page.waitForTimeout(250);
  assert.equal(await page.evaluate(() => window.__htmlCanary), false);
  assert.deepEqual(attemptedResources, []);
  pass('inert template parsing executes no scripts and starts no resource requests');
  let frame = await render(preview.srcDoc);
  await frame.getByRole('heading', { name: 'Static fixture', exact: true }).waitFor();
  assert.equal(await frame.getByText('Safe cell', { exact: true }).count(), 1);
  assert.equal(await frame.locator('.fixture').evaluate(element => getComputedStyle(element).color), 'rgb(1, 2, 3)');
  pass('static headings, tables, and inline CSS render');
  assert.equal(await frame.locator('script,iframe,object,embed,svg,math,form,input,button,base,link,meta[http-equiv="refresh"]').count(), 0);
  pass('executable, embedded, navigation, and form elements are removed');
  assert.equal(await frame.locator('[onclick],[onerror],[src],[href],[action],[ping],[srcdoc]').count(), 0);
  assert.equal(await frame.getByText('Inert link', { exact: true }).count(), 1);
  pass('active attributes are removed while link text stays readable');
  assert.equal(await frame.locator('img').count(), 0);
  assert.ok((await frame.locator('.preview-image-placeholder').innerText()).includes('Blocked image'));
  pass('images become inert placeholders');
  assert.equal(await page.locator('#html-check-frame').getAttribute('sandbox'), '');
  const isolation = await frame.evaluate(() => {
    let parentBlocked = false; let storageBlocked = false;
    try { void parent.document.body; } catch { parentBlocked = true; }
    try { void localStorage.length; } catch { storageBlocked = true; }
    return { parentBlocked, storageBlocked };
  });
  assert.deepEqual(isolation, { parentBlocked: true, storageBlocked: true });
  pass('opaque-origin sandbox blocks parent DOM and storage access');
  await page.waitForTimeout(250); assert.deepEqual(attemptedResources, []);
  pass('CSS imports, backgrounds, and external resources produce no requests');
  const defense = preview.srcDoc.replace('</body>', '<script>window.__htmlCanary=true</script><img src="http://127.0.0.1:9/defense"><form action="http://127.0.0.1:9/defense-form"></form></body>');
  frame = await render(defense); await frame.locator('script').waitFor({ state: 'attached' });
  assert.equal(await frame.evaluate(() => window.__htmlCanary), undefined);
  await frame.locator('form').evaluate(form => form.submit());
  await page.waitForTimeout(250); assert.deepEqual(attemptedResources, []);
  assert.equal(await frame.getByRole('heading', { name: 'Static fixture', exact: true }).count(), 1);
  pass('sandbox and CSP still block scripts, requests, and forms if filtering is bypassed');
  const mutation = '<math><mtext><table><mglyph><style><!--</style><img title="--><img src=http://127.0.0.1:9/mutation onerror=window.__htmlCanary=true>">';
  const sanitizedMutation = await page.evaluate(text => window.htmlPreviewChecks.buildStaticHtmlPreview(text), mutation);
  frame = await render(sanitizedMutation.srcDoc);
  assert.equal(await frame.locator('script,svg,math,img,[onerror],[src]').count(), 0);
  pass('foreign-content mutation fixture cannot introduce active markup');
  const escaped = await page.evaluate(() => window.htmlPreviewChecks.buildStaticHtmlPreview('<p>&lt;script&gt;literal&lt;/script&gt;</p>'));
  frame = await render(escaped.srcDoc); assert.equal(await frame.locator('p').innerText(), '<script>literal</script>');
  assert.equal(await frame.locator('script').count(), 0);
  pass('escaped markup remains text after serialization');
  const deep = await page.evaluate(() => window.htmlPreviewChecks.buildStaticHtmlPreview('<div>'.repeat(80) + 'depth fixture' + '</div>'.repeat(80)));
  assert.equal(deep.limited, true); pass('HTML nesting depth is bounded');
  const large = await page.evaluate(() => window.htmlPreviewChecks.buildStaticHtmlPreview('<span>node</span>'.repeat(5000)));
  assert.equal(large.limited, true); frame = await render(large.srcDoc);
  assert.ok(await frame.locator('body *').count() <= 4000);
  assert.deepEqual(attemptedResources, []); pass('HTML node count is bounded');
} finally { await browser.close(); }
