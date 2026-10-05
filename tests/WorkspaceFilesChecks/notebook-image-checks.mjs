import assert from 'node:assert/strict'
import { existsSync } from 'node:fs'
import { createRequire } from 'node:module'
import { homedir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const uiRequire = createRequire(new URL('../../DevShell/ui/dev-ui-react/package.json', import.meta.url))
const { build } = uiRequire('esbuild')
const { chromium } = createRequire(import.meta.url)(process.env.PLAYWRIGHT_MODULE || join(homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'))
const executablePath = [process.env.HTML_CHECK_BROWSER, chromium.executablePath(), 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', 'C:/Program Files/Microsoft/Edge/Application/msedge.exe', 'C:/Program Files/Google/Chrome/Application/chrome.exe'].find(path => path && existsSync(path))
assert.ok(executablePath, 'A local browser is available')
const bundle = await build({ stdin: { contents: `
  import React from 'react'; import {createRoot} from 'react-dom/client';
  import {NotebookFilePreview} from './NotebookFilePreview'; import {ImageFilePreview} from './ImageFilePreview';
  const root=createRoot(document.getElementById('root'));
  window.renderNotebook=(notebook)=>root.render(React.createElement(NotebookFilePreview,{key:Math.random(),text:JSON.stringify(notebook)}));
  window.renderImage=(image,paths)=>root.render(React.createElement(ImageFilePreview,{key:image.path,image,paths,onSelect:path=>window.lastImageSelection=path,onError:()=>window.imageFailed=true}));
`, resolveDir: fileURLToPath(new URL('../../DevShell/ui/dev-ui-react/src/', import.meta.url)), loader: 'tsx' }, bundle: true, write: false, format: 'iife', platform: 'browser', jsx: 'automatic', define: { 'process.env.NODE_ENV': '"production"' } })
const browser = await chromium.launch({ executablePath, headless: true })
let checks = 0
const pass = message => { checks++; console.log('PASS: ' + message) }
try {
  const page = await browser.newPage({ viewport: { width: 1000, height: 800 } })
  const errors = []; const requests = []
  page.on('pageerror', error => errors.push(error.message))
  await page.route('**/*', route => { requests.push(route.request().url()); return route.abort() })
  await page.setContent('<div id="root"></div><style>.files-image-preview{width:320px;height:240px;overflow:auto;padding:14px;box-sizing:border-box}.image-pan-canvas{display:grid;place-items:center}.files-image-preview img{max-width:none;max-height:none}</style>')
  await page.addScriptTag({ content: bundle.outputFiles[0].text })
  const png = await page.evaluate(() => { const canvas = document.createElement('canvas'); canvas.width = 900; canvas.height = 600; const context = canvas.getContext('2d'); context.fillStyle = '#2879b5'; context.fillRect(0, 0, 900, 600); return canvas.toDataURL('image/png') })
  const notebook = { nbformat: 4, metadata: { language_info: { name: 'python' } }, cells: [
    { cell_type: 'markdown', source: ['# Notebook fixture\n', '<script>window.notebookCanary=true</script>\n![external](http://127.0.0.1:9/image.png)'] },
    { cell_type: 'code', execution_count: 3, source: ['print("saved")'], outputs: [
      { output_type: 'stream', text: ['saved\n'] },
      { output_type: 'error', ename: 'Error', evalue: 'fixture', traceback: ['\u001b[31mSafe traceback\u001b[0m'] },
      { output_type: 'display_data', data: { 'image/png': png.split(',')[1], 'text/plain': ['Saved plot'] } },
      { output_type: 'display_data', data: { 'text/html': '<img src="http://127.0.0.1:9/output.png" onerror="window.notebookCanary=true">', 'application/javascript': 'window.notebookCanary=true', 'image/svg+xml': '<svg onload="window.notebookCanary=true"></svg>' } }
    ] }, { cell_type: 'raw', source: 'raw text' }
  ] }
  await page.evaluate(value => { window.notebookCanary = false; window.renderNotebook(value) }, notebook)
  await page.getByRole('heading', { name: 'Notebook fixture', exact: true }).waitFor()
  assert.equal(await page.locator('.notebook-cell').count(), 3)
  assert.match(await page.getByLabel('Read-only code preview').innerText(), /print\("saved"\)/)
  pass('Notebook Markdown, code, and raw cells render')
  assert.match(await page.locator('.notebook-outputs').innerText(), /saved\n/)
  assert.match(await page.locator('.notebook-error').innerText(), /Safe traceback/)
  assert.equal((await page.locator('.notebook-error').innerText()).includes('\u001b'), false)
  pass('Saved streams and errors render with ANSI sequences removed')
  await page.waitForFunction(() => { const image = document.querySelector('.notebook-saved-output img'); return image?.naturalWidth === 900 })
  pass('Validated embedded PNG output renders without fetching a URL')
  assert.equal(await page.locator('.notebook-preview script,.notebook-preview iframe,.notebook-preview object,.notebook-preview a,.notebook-preview svg').count(), 0)
  assert.equal(await page.evaluate(() => window.notebookCanary), false)
  assert.deepEqual(requests, [])
  pass('Hostile notebook markup, JavaScript, SVG, and external images remain inert')
  await page.getByRole('checkbox', { name: 'Show saved outputs' }).uncheck()
  assert.equal(await page.locator('.notebook-outputs').count(), 0)
  await page.getByRole('checkbox', { name: 'Show saved outputs' }).check()
  assert.equal(await page.locator('.notebook-outputs').count(), 1)
  pass('Saved outputs toggle without execution')
  await page.evaluate(() => window.renderNotebook({ nbformat: 3, cells: [] }))
  await page.getByRole('alert').waitFor()
  assert.match(await page.getByRole('alert').innerText(), /version 4/)
  pass('Unsupported notebook versions report a readable error')
  await page.evaluate(() => window.renderNotebook({ nbformat: 4, cells: Array.from({ length: 201 }, () => ({ cell_type: 'raw', source: 'bounded' })) }))
  await page.waitForFunction(() => document.querySelectorAll('.notebook-cell').length === 200)
  pass('Notebook cell count is bounded')
  await page.evaluate(value => window.renderImage({ path: 'gallery/b.png', dataUrl: value, mimeType: 'image/png', size: 100 }, ['gallery/a.png', 'gallery/b.png', 'gallery/c.png']), png)
  await page.waitForFunction(() => document.querySelector('.image-pan-canvas img')?.naturalWidth === 900 && document.querySelector('.image-pan-canvas img')?.width < 900)
  const fitWidth = await page.locator('.image-pan-canvas img').evaluate(image => image.width)
  assert.ok(fitWidth <= 292)
  pass('Image defaults to fitting the viewport')
  await page.getByRole('button', { name: '100%', exact: true }).click()
  await page.waitForFunction(() => document.querySelector('.image-pan-canvas img')?.width === 900)
  assert.equal(await page.getByLabel('Image zoom', { exact: true }).innerText(), '100%')
  pass('Actual-size image zoom uses native dimensions')
  await page.getByRole('button', { name: 'Zoom in', exact: true }).click()
  await page.waitForFunction(() => document.querySelector('.image-pan-canvas img')?.width === 1125)
  await page.getByRole('button', { name: 'Zoom out', exact: true }).click()
  await page.waitForFunction(() => document.querySelector('.image-pan-canvas img')?.width === 900)
  pass('Zoom controls update image dimensions')
  const box = await page.locator('.image-pan-viewport').boundingBox()
  await page.mouse.move(box.x + 180, box.y + 160); await page.mouse.down(); await page.mouse.move(box.x + 90, box.y + 80); await page.mouse.up()
  assert.ok(await page.locator('.image-pan-viewport').evaluate(element => element.scrollLeft > 0 && element.scrollTop > 0))
  pass('Pointer dragging pans the zoomed image')
  await page.getByRole('button', { name: 'Previous image', exact: true }).click()
  assert.equal(await page.evaluate(() => window.lastImageSelection), 'gallery/a.png')
  await page.getByRole('button', { name: 'Next image', exact: true }).click()
  assert.equal(await page.evaluate(() => window.lastImageSelection), 'gallery/c.png')
  pass('Previous and next target neighboring folder images')
  await page.locator('.image-pan-viewport').focus(); await page.keyboard.press('Home')
  await page.waitForFunction(() => document.querySelector('.image-pan-viewport').scrollLeft === 0 && document.querySelector('.image-pan-canvas img').width < 900)
  pass('Keyboard Home restores fit and clears pan offset')
  assert.deepEqual(errors, []); assert.deepEqual(requests, [])
  pass('Viewers emit no page errors or external resource requests')
  console.log(`${checks} viewer checks passed`)
} finally { await browser.close() }
