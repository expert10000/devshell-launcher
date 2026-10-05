import { useMemo, useState, type ReactNode } from 'react'
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

export function CodeFilePreview({ text, filename }: { text: string; filename: string }) {
  const lines = useMemo(() => text.replace(/\r\n?/g, '\n').split('\n'), [text])
  return <div className="code-preview" tabIndex={0} aria-label="Read-only code preview"><p className="workspace-view-caption">{filename.split('.').at(-1)?.toUpperCase()} source / read-only, never executed</p><div className="code-lines">{lines.slice(0, 2000).map((line, index) => <div className="code-line" key={index}><span aria-hidden="true">{index + 1}</span><code>{line || ' '}</code></div>)}</div>{lines.length > 2000 && <p>Showing the first 2000 lines. View source for the bounded text.</p>}</div>
}
