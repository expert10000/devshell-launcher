import { useEffect, useRef, useState } from 'react'

type ChangedFile = { path: string; originalPath?: string; index: string; worktree: string; conflicted: boolean; staged: boolean; unstaged: boolean }
type Snapshot = { path: string; head: string; token: string; files: ChangedFile[]; blockedReason?: string }
type Diff = { path: string; side: string; text: string; truncated: boolean }
type Bridge = { postMessage: (message: unknown) => void; addEventListener: (name: 'message', handler: (event: MessageEvent) => void) => void; removeEventListener: (name: 'message', handler: (event: MessageEvent) => void) => void }
type Reply = { type: string; requestId?: string; profileId?: string; snapshot?: Snapshot; diff?: Diff; error?: string }

export function RepositoryChangesPanel({ profileId, projectId, repositoryId, name, blocked, onClose, onCommit }: {
  profileId: string; projectId: string; repositoryId: string; name: string; blocked: boolean; onClose: () => void; onCommit: () => void
}) {
  const bridge = (window as unknown as { chrome?: { webview?: Bridge } }).chrome?.webview
  const [snapshot, setSnapshot] = useState<Snapshot>()
  const [diff, setDiff] = useState<Diff>()
  const [error, setError] = useState('')
  const [pending, setPending] = useState(true)
  const [stagedSelection, setStagedSelection] = useState<string[]>([])
  const [workingSelection, setWorkingSelection] = useState<string[]>([])
  const requestId = useRef('')
  const timeout = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  function request(action: string, extra: Record<string, unknown> = {}) {
    if (!bridge) { setError('Changes requires the DevShell desktop app.'); setPending(false); return }
    clearTimeout(timeout.current)
    requestId.current = crypto.randomUUID()
    setPending(true); setError('')
    timeout.current = setTimeout(() => { requestId.current = ''; setPending(false); setError('Git request timed out. Refresh to check its result before retrying.') }, 65000)
    bridge.postMessage({ type: 'repository.job', profileId, projectId, repositoryId, requestId: requestId.current, action, ...extra })
  }
  useEffect(() => {
    if (!bridge) return
    const receive = (event: MessageEvent) => {
      let message: Reply
      try { message = typeof event.data === 'string' ? JSON.parse(event.data) as Reply : event.data as Reply } catch { return }
      if (message?.type !== 'repository.changes' || message.profileId !== profileId || message.requestId !== requestId.current) return
      clearTimeout(timeout.current); setPending(false)
      if (message.error) { setError(message.error); return }
      if (message.snapshot) { setSnapshot(message.snapshot); setStagedSelection([]); setWorkingSelection([]) }
      setDiff(message.diff)
      bridge.postMessage({ type: 'dashboard.request' })
    }
    bridge.addEventListener('message', receive)
    const id = crypto.randomUUID(); requestId.current = id
    bridge.postMessage({ type: 'repository.job', profileId, projectId, repositoryId, requestId: id, action: 'changes' })
    timeout.current = setTimeout(() => { requestId.current = ''; setPending(false); setError('Git request timed out. Refresh to retry.') }, 65000)
    return () => { clearTimeout(timeout.current); bridge.removeEventListener('message', receive) }
  }, [bridge, profileId, projectId, repositoryId])

  const locked = pending || blocked || !!snapshot?.blockedReason
  const staged = snapshot?.files.filter(file => file.staged) ?? []
  const working = snapshot?.files.filter(file => file.unstaged) ?? []
  function fileList(files: ChangedFile[], side: 'staged' | 'working') {
    const selection = side === 'staged' ? stagedSelection : workingSelection
    const setSelection = side === 'staged' ? setStagedSelection : setWorkingSelection
    return <ul className="changes-files">{files.map(file => <li key={file.path}>
      <input type="checkbox" aria-label={`Select ${side} ${file.path}`} disabled={locked} checked={selection.includes(file.path)} onChange={event => setSelection(current => event.target.checked ? [...current, file.path] : current.filter(path => path !== file.path))} />
      <button disabled={pending || blocked} title={file.originalPath ? `${file.originalPath} -> ${file.path}` : file.path} onClick={() => request('file-diff', { path: file.path, side })}>
        <code>{side === 'staged' ? file.index : file.worktree}</code> {file.path}{file.conflicted ? ' (conflict)' : ''}
      </button>
    </li>)}</ul>
  }
  return <div className="project-editor-overlay" onClick={onClose}>
    <section className="health-dialog changes-dialog" role="dialog" aria-modal="true" aria-label={`${name} changes`} onClick={event => event.stopPropagation()} onKeyDown={event => { if (event.key === 'Escape') { event.stopPropagation(); onClose() } }}>
      <div className="service-heading"><h2>{name} changes</h2><button autoFocus onClick={onClose}>Close</button></div>
      <p className="repo-path">{snapshot?.path}</p>
      <p>Select files, then stage or unstage. Staging includes the whole file as it exists when clicked. Unstaging keeps your working files. No automatic stage-all or discard.</p>
      <div className="service-actions"><button disabled={pending || blocked} onClick={() => { setDiff(undefined); request('changes') }}>Refresh</button><button disabled={locked || !staged.length || snapshot?.head === undefined} onClick={onCommit}>Commit staged files...</button></div>
      {pending && <p role="status">Reading Git state...</p>}
      {error && <p className="check-error" role="alert">{error}</p>}
      {snapshot?.blockedReason && <p className="check-error" role="alert">{snapshot.blockedReason}</p>}
      <div className="changes-columns">
        <section aria-label="Working tree files"><h3>Changes ({working.length})</h3>{fileList(working, 'working')}{!pending && !working.length && <p>No working-tree changes.</p>}<button disabled={locked || !workingSelection.length || workingSelection.length > 200} onClick={() => request('stage', { token: snapshot?.token, paths: workingSelection })}>Stage selected ({workingSelection.length})</button></section>
        <section aria-label="Staged files"><h3>Staged ({staged.length})</h3>{fileList(staged, 'staged')}{!pending && !staged.length && <p>No staged changes.</p>}<button disabled={locked || !stagedSelection.length || stagedSelection.length > 200} onClick={() => request('unstage', { token: snapshot?.token, paths: stagedSelection })}>Unstage selected ({stagedSelection.length})</button></section>
      </div>
      {diff && <section aria-label="File diff"><h3>{diff.path} ({diff.side === 'staged' ? 'staged' : 'working tree'})</h3><pre className="repository-log changes-diff">{diff.text}</pre>{diff.truncated && <p>Preview truncated at 240 KB. Use VS Code for the complete file.</p>}</section>}
    </section>
  </div>
}
