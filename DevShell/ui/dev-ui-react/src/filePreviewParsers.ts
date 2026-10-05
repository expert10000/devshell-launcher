export type DelimitedPreview = { rows: string[][]; truncated: boolean; warning?: string }

export function parseDelimited(text: string, delimiter: ',' | '\t', maxRows = 201, maxColumns = 50, maxCellChars = 4096): DelimitedPreview {
  if (maxRows < 1 || maxColumns < 1 || maxCellChars < 1) throw new Error('Table limits must be positive.')
  const rows: string[][] = []; let row: string[] = []; let cell = ''; let quoted = false; let truncated = false
  function append(value: string) { if (cell.length < maxCellChars) cell += value.slice(0, maxCellChars - cell.length); else truncated = true }
  function finishCell() { if (row.length < maxColumns) row.push(cell); else truncated = true; cell = '' }
  function finishRow() { rows.push(row); row = [] }
  for (let i = 0; i < text.length; i++) {
    const char = text[i]
    if (quoted) {
      if (char === '"' && text[i + 1] === '"') { append('"'); i++ }
      else if (char === '"') quoted = false
      else append(char)
    } else if (char === '"' && !cell.length) quoted = true
    else if (char === delimiter) finishCell()
    else if (char === '\n' || char === '\r') {
      if (char === '\r' && text[i + 1] === '\n') i++
      finishCell(); finishRow()
      if (rows.length >= maxRows && i + 1 < text.length) return { rows, truncated: true }
    } else append(char)
  }
  if (cell.length || row.length || quoted || text.endsWith(delimiter)) {
    finishCell()
    if (rows.length < maxRows) finishRow(); else truncated = true
  }
  return { rows, truncated, warning: quoted ? 'An unclosed quoted field was found. The source may be incomplete or truncated.' : undefined }
}

export function parseJsonPreview(text: string): { value?: unknown; error?: string } {
  try { return { value: JSON.parse(text) as unknown } }
  catch { return { error: 'JSON is invalid or incomplete. View source to inspect the bounded text preview.' } }
}
