// Keep the parser filename distinct from the React view on Windows.
export type BuildDiagnostic = { file: string; line: number; column: number; severity: 'error' | 'warning'; message: string }
export type DiagnosticScan = { items: BuildDiagnostic[]; truncated: boolean }

export function parseBuildDiagnostics(log: string): DiagnosticScan {
  const bounded = log.slice(-256000).replace(/\x1b\[[0-?]*[ -/]*[@-~]/g, '')
  const all = bounded.split(/\r?\n/); const lines = all.slice(-6000)
  const items: BuildDiagnostic[] = []; const seen = new Set<string>()
  let truncated = bounded.length < log.length || all.length > lines.length
  let context: { severity: 'error' | 'warning'; message: string } | undefined
  for (let index = 0; index < lines.length; index++) {
    const raw = lines[index].trim().replace(/^\[\d+\]\s*/, '')
    const heading = raw.match(/^(error|warning)(?:\[[^\]]+\])?\s*:\s*(.*)$/i)
    if (heading) context = { severity: heading[1].toLowerCase() as 'error' | 'warning', message: heading[2] }
    const source = raw.replace(/^(?:ERROR|WARNING)\s+in\s+/i, '').replace(/^(?:-->|:::)\s*/, '')
    const python = source.match(/^File\s+"([^"]+)",\s+line\s+(\d+)(?:,.*)?$/)
    const parens = source.match(/^(.*?)\((\d+)(?:,\s*(\d+))?\)\s*:\s*(?:(error|warning)\b\s*)?(.*)$/i)
    const colon = source.match(/^(.*?):(\d+)(?::(\d+))?\s*(?::|-)\s*(?:(?:fatal\s+)?(error|warning)\b\s*:?\s*)?(.*)$/i)
    const rust = source.match(/^(.+?):(\d+):(\d+)$/)
    const match = parens ?? colon ?? rust
    if (!python && !match) continue
    const file = (python?.[1] ?? match![1]).trim().replace(/^["'`]|["'`]$/g, '')
    // Require a filename, not a timestamp, port number, URL, or arbitrary log prose.
    if (!/\.[a-z0-9_+-]{1,16}$/i.test(file) || file.length > 2048 || /^[a-z]+:\/\//i.test(file)) continue
    const line = Number(python?.[2] ?? match![2]); const column = Number(python ? 1 : match![3] ?? 1)
    if (!Number.isInteger(line) || line < 1 || line > 1000000 || !Number.isInteger(column) || column < 1 || column > 1000000) continue
    const reported = match?.[4]?.toLowerCase()
    const severity: 'error' | 'warning' = python ? 'error' : reported === 'warning' ? 'warning' : reported === 'error' ? 'error' : context?.severity ?? 'error'
    const message = (python ? `Python traceback: ${lines[index + 1]?.trim() ?? ''}` : match?.[5] || context?.message || 'Build diagnostic').slice(0, 600)
    const key = `${file}:${line}:${column}:${severity}:${message}`
    if (seen.has(key)) continue
    if (items.length >= 100) { truncated = true; break }
    seen.add(key); items.push({ file, line, column, severity, message })
  }
  return { items, truncated }
}
