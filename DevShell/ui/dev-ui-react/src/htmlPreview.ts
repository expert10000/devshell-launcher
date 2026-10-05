export type StaticHtmlPreview = { srcDoc: string; omitted: number; limited: boolean }

const allowedTags = new Set(['div', 'span', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'article', 'section', 'header', 'footer', 'main', 'aside', 'nav', 'address', 'blockquote', 'pre', 'code', 'kbd', 'samp', 'var', 'strong', 'b', 'em', 'i', 'u', 's', 'del', 'ins', 'small', 'sub', 'sup', 'mark', 'abbr', 'cite', 'q', 'time', 'br', 'hr', 'wbr', 'ul', 'ol', 'li', 'dl', 'dt', 'dd', 'table', 'caption', 'colgroup', 'col', 'thead', 'tbody', 'tfoot', 'tr', 'th', 'td', 'figure', 'figcaption', 'details', 'summary', 'style'])
const droppedTags = new Set(['script', 'iframe', 'frame', 'frameset', 'object', 'embed', 'meta', 'base', 'link', 'noscript', 'template', 'svg', 'math', 'audio', 'video', 'source', 'track', 'canvas', 'portal', 'fencedframe', 'input', 'textarea', 'select', 'option'])
const allowedAttributes = new Set(['id', 'class', 'style', 'title', 'lang', 'dir', 'colspan', 'rowspan', 'scope', 'width', 'height', 'align', 'valign', 'border', 'cellpadding', 'cellspacing', 'start', 'reversed', 'open', 'aria-label'])
const policy = "default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; img-src 'none'; connect-src 'none'; font-src 'none'; media-src 'none'; object-src 'none'; frame-src 'none'; worker-src 'none'; form-action 'none'; base-uri 'none'"

export function buildStaticHtmlPreview(text: string): StaticHtmlPreview {
  // Parse only in template contents, whose owner document has no browsing context:
  // https://html.spec.whatwg.org/multipage/scripting.html#appropriate-template-contents-owner-document
  // Never attach the source nodes to the launcher DOM. Rebuild a static allowlist
  // in the same inert document before serializing it for an opaque-origin iframe.
  const source = document.createElement('template'); source.innerHTML = text
  const result = document.createElement('template'); const inert = result.content.ownerDocument
  let remaining = 4000; let omitted = 0; let limited = false
  function copy(node: Node, parent: Node, depth: number) {
    if (remaining-- <= 0 || depth > 32) { limited = true; return }
    if (node.nodeType === Node.TEXT_NODE) { parent.appendChild(inert.createTextNode(node.textContent ?? '')); return }
    if (node.nodeType !== Node.ELEMENT_NODE) return
    const original = node as Element; const tag = original.localName.toLowerCase()
    if (original.namespaceURI !== 'http://www.w3.org/1999/xhtml' || droppedTags.has(tag)) { omitted++; return }
    if (tag === 'img') {
      const placeholder = inert.createElement('span'); placeholder.className = 'preview-image-placeholder'
      placeholder.textContent = `[Image omitted${original.getAttribute('alt') ? `: ${original.getAttribute('alt')}` : ''}]`
      parent.appendChild(placeholder); omitted++; return
    }
    // Links and forms retain readable content, but cannot navigate or submit.
    const replacement = tag === 'a' || tag === 'button' || tag === 'label' ? 'span' : tag === 'form' || tag === 'fieldset' ? 'div' : undefined
    if (!allowedTags.has(tag) && !replacement) {
      omitted++
      for (const child of Array.from(original.childNodes)) { if (remaining <= 0) { limited = true; break }; copy(child, parent, depth + 1) }
      return
    }
    const clean = inert.createElement(replacement ?? tag)
    for (const attribute of Array.from(original.attributes)) {
      if (allowedAttributes.has(attribute.name.toLowerCase())) clean.setAttribute(attribute.name, attribute.value)
      else omitted++
    }
    if (tag === 'style') clean.textContent = (original.textContent ?? '').replace(/<\/style/gi, '<\\/style')
    else for (const child of Array.from(original.childNodes)) { if (remaining <= 0) { limited = true; break }; copy(child, clean, depth + 1) }
    parent.appendChild(clean)
  }
  for (const child of Array.from(source.content.childNodes)) { if (remaining <= 0) { limited = true; break }; copy(child, result.content, 0) }
  const srcDoc = `<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="${policy}"><meta name="referrer" content="no-referrer"><style>body{margin:18px;font:16px/1.5 Georgia,serif;color:#182638;background:#fff;overflow-wrap:anywhere}pre{overflow:auto}table{border-collapse:collapse}th,td{padding:6px 10px;border:1px solid #cbd5df}.preview-image-placeholder{display:inline-block;padding:5px 8px;background:#eef2f6;color:#64748b;font:12px/1.5 monospace}</style></head><body>${result.innerHTML}</body></html>`
  return { srcDoc, omitted, limited }
}
