import { createElement, useMemo, type ReactNode } from 'react'

// Render a small, read-only Markdown subset as React nodes. Never interpret HTML,
// execute content, navigate links, or fetch embedded resources from a repository.
function inline(text: string, prefix: string): ReactNode[] {
  const nodes: ReactNode[] = []
  const pattern = /(`[^`\n]+`|\*\*[^*\n]+\*\*|__[^_\n]+__|\*[^*\n]+\*|~~[^~\n]+~~|!\[[^\]]*\]\([^)\n]*\)|\[[^\]]+\]\([^)\n]*\))/g
  let offset = 0
  for (const match of text.matchAll(pattern)) {
    const index = match.index!; const token = match[0]; const key = `${prefix}:${index}`
    if (index > offset) nodes.push(text.slice(offset, index))
    if (token.startsWith('`')) nodes.push(<code key={key}>{token.slice(1, -1)}</code>)
    else if (token.startsWith('**') || token.startsWith('__')) nodes.push(<strong key={key}>{token.slice(2, -2)}</strong>)
    else if (token.startsWith('~~')) nodes.push(<del key={key}>{token.slice(2, -2)}</del>)
    else if (token.startsWith('*')) nodes.push(<em key={key}>{token.slice(1, -1)}</em>)
    else {
      const close = token.indexOf(']('); const image = token.startsWith('!')
      const label = token.slice(image ? 2 : 1, close); const target = token.slice(close + 2, -1)
      nodes.push(<span key={key} className="markdown-reference" title={target}>{image ? `Image: ${label || 'embedded image'} (not loaded)` : label}<small> ({target})</small></span>)
    }
    offset = index + token.length
  }
  if (offset < text.length) nodes.push(text.slice(offset))
  return nodes
}

const tableDivider = /^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$/
const listItem = /^\s*([-+*]|\d+[.)])\s+(.*)$/
const fenceStart = /^ {0,3}(`{3,}|~{3,})(.*)$/
const horizontalRule = /^ {0,3}([-*_])(?:\s*\1){2,}\s*$/
function cells(line: string) { return line.trim().replace(/^\||\|$/g, '').split('|').map(cell => cell.trim()) }
function startsBlock(line: string) { return /^ {0,3}(#{1,6}\s|>|`{3,}|~{3,})/.test(line) || listItem.test(line) || horizontalRule.test(line) }

function blocks(text: string): ReactNode[] {
  const lines = text.replace(/\r\n?/g, '\n').split('\n'); const nodes: ReactNode[] = []
  let i = 0
  while (i < lines.length) {
    if (!lines[i].trim()) { i++; continue }
    const key = `block:${i}`; const fence = lines[i].match(fenceStart)
    if (fence) {
      const code: string[] = []; const marker = fence[1]; const language = fence[2].trim(); i++
      while (i < lines.length) {
        const closing = lines[i].match(/^ {0,3}(`{3,}|~{3,})\s*$/)
        if (closing && closing[1][0] === marker[0] && closing[1].length >= marker.length) { i++; break }
        code.push(lines[i++])
      }
      nodes.push(<section key={key} className="markdown-code">{language && <small>{language}</small>}<pre><code>{code.join('\n')}</code></pre></section>); continue
    }
    const heading = lines[i].match(/^ {0,3}(#{1,6})\s+(.+?)\s*#*\s*$/)
    if (heading) { nodes.push(createElement(`h${heading[1].length}`, { key }, ...inline(heading[2], key))); i++; continue }
    if (horizontalRule.test(lines[i])) { nodes.push(<hr key={key} />); i++; continue }
    if (i + 1 < lines.length && lines[i].includes('|') && tableDivider.test(lines[i + 1])) {
      const headers = cells(lines[i]); const rows: string[][] = []; i += 2
      while (i < lines.length && lines[i].trim() && lines[i].includes('|')) rows.push(cells(lines[i++]))
      nodes.push(<div className="markdown-table" key={key}><table><thead><tr>{headers.map((cell, column) => <th key={column}>{inline(cell, `${key}:h:${column}`)}</th>)}</tr></thead><tbody>{rows.map((row, rowIndex) => <tr key={rowIndex}>{headers.map((_, column) => <td key={column}>{inline(row[column] ?? '', `${key}:${rowIndex}:${column}`)}</td>)}</tr>)}</tbody></table></div>); continue
    }
    if (/^ {0,3}>/.test(lines[i])) {
      const quote: string[] = []
      while (i < lines.length && /^ {0,3}>/.test(lines[i])) quote.push(lines[i++].replace(/^ {0,3}> ?/, ''))
      nodes.push(<blockquote key={key}>{inline(quote.join('\n'), key)}</blockquote>); continue
    }
    const item = lines[i].match(listItem)
    if (item) {
      const ordered = /^\d/.test(item[1]); const items: ReactNode[] = []
      while (i < lines.length) {
        const next = lines[i].match(listItem)
        if (!next || /^\d/.test(next[1]) !== ordered || horizontalRule.test(lines[i])) break
        const task = next[2].match(/^\[([ xX])\]\s+(.*)$/)
        items.push(<li key={i}>{task ? <><input type="checkbox" disabled checked={task[1].toLowerCase() === 'x'} aria-label={task[1] === ' ' ? 'Incomplete task' : 'Completed task'} /> {inline(task[2], `${key}:${i}`)}</> : inline(next[2], `${key}:${i}`)}</li>); i++
      }
      nodes.push(ordered ? <ol key={key} start={parseInt(item[1], 10)}>{items}</ol> : <ul key={key}>{items}</ul>); continue
    }
    const paragraph: string[] = [lines[i++]]
    while (i < lines.length && lines[i].trim() && !startsBlock(lines[i]) && !(lines[i].includes('|') && tableDivider.test(lines[i + 1] ?? ''))) paragraph.push(lines[i++])
    nodes.push(<p key={key}>{inline(paragraph.join('\n'), key)}</p>)
  }
  return nodes
}

export function MarkdownPreview({ text }: { text: string }) {
  const content = useMemo(() => blocks(text), [text])
  return <article className="markdown-preview" tabIndex={0} aria-label="Read-only Markdown preview">{content}</article>
}
