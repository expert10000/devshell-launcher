import { useEffect, useMemo, useRef, useState } from 'react'
import { parseBuildDiagnostics } from './diagnosticParser'
import type { BuildDiagnostic } from './diagnosticParser'

type Bridge = { postMessage: (message: unknown) => void; addEventListener: (name: 'message', handler: (event: MessageEvent) => void) => void; removeEventListener: (name: 'message', handler: (event: MessageEvent) => void) => void }
export function BuildDiagnostics({ log, profileId, projectId, repositoryId, bridge }: { log: string; profileId: string; projectId?: string; repositoryId?: string; bridge: Bridge | null }) {
  const scan = useMemo(() => parseBuildDiagnostics(log), [log])
  const [filter, setFilter] = useState<'all' | 'error' | 'warning'>('all'); const [pending, setPending] = useState(false); const [error, setError] = useState('')
  const current = useRef(''); const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  useEffect(() => {
    if (!bridge) return
    const receive = (event: MessageEvent) => {
      let message: { type?: string; profileId?: string; requestId?: string; error?: string; location?: { path: string; line: number; column: number } }
      try { message = typeof event.data === 'string' ? JSON.parse(event.data) : event.data } catch { return }
      if (message?.type !== 'workspace.files.result' || message.profileId !== profileId || !current.current || message.requestId !== current.current) return
      clearTimeout(timer.current); current.current = ''; setPending(false)
      if (message.error) { setError(message.error); return }
      if (message.location) window.dispatchEvent(new CustomEvent('devshell.workspace.open', { detail: { profileId, kind: 'files', projectId, repositoryId, filePath: message.location.path.split('/').slice(0, -1).join('/'), revealPath: message.location.path, sourceLine: message.location.line } }))
    }
    bridge.addEventListener('message', receive)
    return () => { clearTimeout(timer.current); current.current = ''; bridge.removeEventListener('message', receive) }
  }, [bridge, profileId, projectId, repositoryId])
  function open(diagnostic: BuildDiagnostic) {
    if (!bridge) { setError('Diagnostic navigation requires the DevShell desktop app.'); return }
    current.current = crypto.randomUUID(); clearTimeout(timer.current); setPending(true); setError('')
    timer.current = setTimeout(() => { current.current = ''; setPending(false); setError('Diagnostic navigation timed out. Retry the file link.') }, 30000)
    bridge.postMessage({ type: 'workspace.files', profileId, projectId, repositoryId, requestId: current.current, action: 'diagnostic', file: diagnostic.file, line: diagnostic.line, column: diagnostic.column })
  }
  if (!scan.items.length) return null
  const errors = scan.items.filter(item => item.severity === 'error').length; const warnings = scan.items.length - errors
  return <details className="build-diagnostics"><summary>Build diagnostics / {errors} errors / {warnings} warnings</summary><div className="build-diagnostic-filters">{(['all', 'error', 'warning'] as const).map(value => <button key={value} aria-pressed={filter === value} onClick={() => setFilter(value)}>{value === 'all' ? 'All diagnostics' : value === 'error' ? 'Errors' : 'Warnings'}</button>)}</div><div className="build-diagnostic-list" aria-label="Build diagnostics">
    {scan.items.filter(item => filter === 'all' || item.severity === filter).map((item, index) => <button className={`build-diagnostic ${item.severity}`} key={`${item.file}:${item.line}:${index}`} disabled={pending} title={`Open ${item.file}:${item.line}:${item.column} in the read-only source viewer`} onClick={() => open(item)}><span className="build-diagnostic-location">{item.severity.toUpperCase()} / {item.file}:{item.line}:{item.column}</span><span>{item.message}</span></button>)}
  </div><p className="workspace-view-caption">Recognized .NET, TypeScript, C/C++, Go, Rust, TeX file-line messages, and Python traceback locations. Paths must stay inside this build's repository. Click opens read-only source; no command runs. Up to 100 diagnostics from the latest 256K characters / 6000 log lines.</p>{scan.truncated && <p className="workspace-view-caption">Diagnostic scan is partial. Open full log for earlier output.</p>}{pending && <p role="status">Resolving diagnostic file...</p>}{error && <p role="alert" className="check-error">{error}</p>}</details>
}
