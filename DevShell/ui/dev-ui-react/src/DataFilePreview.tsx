import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { parseDelimited, parseJsonPreview } from './filePreviewParsers'

function jsonNode(value: unknown, name: string, depth: number, budget: { remaining: number }): ReactNode {
  if (budget.remaining-- <= 0) return <span>Node limit reached; view source for more.</span>
  if (value === null || typeof value !== 'object') {
    const text = JSON.stringify(value) ?? String(value)
    return <div className="json-value"><strong>{name}</strong>: <code className={`json-${value === null ? 'null' : typeof value}`}>{text.length > 4096 ? `${text.slice(0, 4096)}...` : text}</code></div>
  }
  const children = Object.entries(value); const array = Array.isArray(value)
  const summary = <summary><strong>{name}</strong><span>{array ? 'Array' : 'Object'} / {children.length} {array ? 'items' : 'fields'}</span></summary>
  if (depth >= 12) return <details>{summary}<p>Depth limit reached; view source for more.</p></details>
  const nodes: ReactNode[] = []
  for (const [key, child] of children) {
    if (nodes.length >= 100 || budget.remaining <= 0) { nodes.push(<li key="remaining">More fields omitted from the tree; view source for the bounded document.</li>); break }
    nodes.push(<li key={`field:${key}`}>{jsonNode(child, array ? `[${key}]` : key, depth + 1, budget)}</li>)
  }
  return <details open={depth === 0}>{summary}<ul>{nodes}</ul></details>
}

export function JsonFilePreview({ text, notebook }: { text: string; notebook: boolean }) {
  const parsed = useMemo(() => parseJsonPreview(text), [text])
  const tree = useMemo(() => parsed.error ? null : jsonNode(parsed.value, notebook ? 'Notebook JSON' : 'JSON', 0, { remaining: 2000 }), [parsed, notebook])
  return <div className="json-preview" tabIndex={0} aria-label="Read-only JSON preview">{parsed.error ? <p role="alert">{parsed.error}</p> : tree}{notebook && <p className="workspace-view-caption">Notebook source only. Cells and outputs are not executed; use Jupyter for the notebook UI.</p>}</div>
}

export function TableFilePreview({ text, delimiter }: { text: string; delimiter: ',' | '\t' }) {
  const parsed = useMemo(() => parseDelimited(text, delimiter), [text, delimiter]); const [header, setHeader] = useState(true)
  const width = parsed.rows.reduce((largest, row) => Math.max(largest, row.length), 0)
  const headers = Array.from({ length: width }, (_, index) => header ? parsed.rows[0]?.[index] || `Column ${index + 1}` : `Column ${index + 1}`)
  const rows = header ? parsed.rows.slice(1) : parsed.rows
  return <div className="table-preview" aria-label="Read-only table preview"><label><input type="checkbox" checked={header} onChange={event => setHeader(event.target.checked)} /> First row contains headers</label><div className="table-preview-scroll" tabIndex={0}><table><thead><tr>{headers.map((name, index) => <th key={index}>{name}</th>)}</tr></thead><tbody>{rows.map((row, rowIndex) => <tr key={rowIndex}>{headers.map((_, index) => <td key={index}>{row[index] ?? ''}</td>)}</tr>)}</tbody></table></div><p className="workspace-view-caption">{rows.length} visible rows / {width} columns. Up to 201 total rows, 50 columns, and 4096 characters per cell are displayed.</p>{parsed.truncated && <p>Table preview limits reached. View source for the bounded text.</p>}{parsed.warning && <p role="alert">{parsed.warning}</p>}</div>
}

export function CodeFilePreview({ text, filename, line }: { text: string; filename: string; line?: number }) {
  const lines = useMemo(() => text.replace(/\r\n?/g, '\n').split('\n'), [text])
  const container = useRef<HTMLDivElement>(null); const highlighted = useRef<HTMLDivElement>(null)
  const requested = Math.max(1, Math.floor(line ?? 1)); const available = !!line && requested <= lines.length
  const start = available && requested > 2000 ? Math.max(0, requested - 1000) : 0
  const end = Math.min(lines.length, start + 2000)
  useEffect(() => {
    const target = highlighted.current; const element = container.current
    if (target && element) element.scrollTop += target.getBoundingClientRect().top - element.getBoundingClientRect().top - element.clientHeight / 2
  }, [text, filename, line])
  return <div ref={container} className="code-preview" tabIndex={0} aria-label="Read-only code preview"><p className="workspace-view-caption">{filename.split('.').at(-1)?.toUpperCase()} source / read-only, never executed{line ? ` / diagnostic line ${requested}` : ''}</p><div className="code-lines">{lines.slice(start, end).map((source, index) => <div ref={available && start + index + 1 === requested ? highlighted : undefined} className={`code-line ${available && start + index + 1 === requested ? 'diagnostic-line' : ''}`} aria-current={available && start + index + 1 === requested ? true : undefined} key={start + index}><span aria-hidden="true">{start + index + 1}</span><code>{source || ' '}</code></div>)}</div>{line && !available && <p role="status">Reported line is outside the available preview. The file may have changed or the preview may be truncated.</p>}{lines.length > 2000 && <p>Showing lines {start + 1}-{end} of the bounded preview. View source for more.</p>}</div>
}
