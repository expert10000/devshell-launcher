import { useEffect, useRef, useState } from 'react'

export type FileReference = { projectId: string; repositoryId: string; path: string; kind: 'pdf' | 'image' | 'text' | 'code'; projectName?: string; repositoryName?: string }
type Link = { source: FileReference; output: FileReference }
type Navigation = { recent: FileReference[]; pinned: FileReference[]; links: Link[] }
type Draft = { source?: FileReference; output?: FileReference }
type Bridge = { postMessage: (message: unknown) => void; addEventListener: (name: 'message', handler: (event: MessageEvent) => void) => void; removeEventListener: (name: 'message', handler: (event: MessageEvent) => void) => void }
const drafts = new Map<string, Draft>() // Session-only pairing draft; never serialized.
const identity = (file?: FileReference) => file ? `${file.projectId}:${file.repositoryId}:${file.path.toLowerCase()}` : ''
const caption = (file: FileReference) => `${file.repositoryName ?? file.repositoryId} / ${file.path}`

function changeDraft(profileId: string, value: Draft) {
  if (!drafts.has(profileId) && drafts.size >= 20) drafts.delete(drafts.keys().next().value!)
  drafts.set(profileId, value)
  window.dispatchEvent(new CustomEvent('devshell.workspace.link-draft', { detail: { profileId } }))
}

export function WorkspaceFileNavigation({ profileId, projectId, bridge, selected }: { profileId: string; projectId?: string; bridge: Bridge | null; selected?: FileReference }) {
  const [navigation, setNavigation] = useState<Navigation>({ recent: [], pinned: [], links: [] })
  const [draft, setDraft] = useState<Draft>(() => drafts.get(profileId) ?? {})
  const [pending, setPending] = useState(false); const [error, setError] = useState('')
  const current = useRef<{ id: string; operation: string }>({ id: '', operation: '' })
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  function request(operation: 'load' | 'pin' | 'unpin' | 'link' | 'unlink' | 'clear-recent', data: Record<string, unknown> = {}) {
    if (!bridge) { setError('File shortcuts require the DevShell desktop app.'); return }
    current.current = { id: crypto.randomUUID(), operation }; clearTimeout(timer.current); setPending(true); setError('')
    timer.current = setTimeout(() => { current.current.id = ''; setPending(false); setError('File shortcuts timed out. Click Refresh shortcuts to retry.') }, 30000)
    bridge.postMessage({ type: 'workspace.files', profileId, projectId, requestId: current.current.id, action: 'navigation', operation, ...data })
  }
  useEffect(() => {
    setNavigation({ recent: [], pinned: [], links: [] }); setDraft(drafts.get(profileId) ?? {}); setError(''); setPending(false)
    if (!bridge) return
    const receive = (event: MessageEvent) => {
      let message: { type?: string; profileId?: string; requestId?: string; navigation?: Navigation; error?: string }
      try { message = typeof event.data === 'string' ? JSON.parse(event.data) : event.data } catch { return }
      if (message?.profileId !== profileId) return
      const response = message.type === 'workspace.files.result' && !!current.current.id && message.requestId === current.current.id
      if (!response && message.type !== 'workspace.navigation.changed') return
      if (response) {
        clearTimeout(timer.current); current.current.id = ''; setPending(false)
        if (!message.error && current.current.operation === 'link') changeDraft(profileId, {})
      }
      if (message.error) { setError(message.error); return }
      if (message.navigation) { setNavigation(message.navigation); setError('') }
    }
    const receiveDraft = (event: Event) => { if ((event as CustomEvent<{ profileId: string }>).detail?.profileId === profileId) setDraft(drafts.get(profileId) ?? {}) }
    bridge.addEventListener('message', receive); window.addEventListener('devshell.workspace.link-draft', receiveDraft)
    request('load') // Reference metadata only; does not list folders or reopen any file.
    return () => { clearTimeout(timer.current); current.current.id = ''; bridge.removeEventListener('message', receive); window.removeEventListener('devshell.workspace.link-draft', receiveDraft) }
  }, [bridge, profileId, projectId])
  function open(file: FileReference) {
    if (file.kind === 'pdf') {
      window.dispatchEvent(new CustomEvent('devshell.workspace.open', { detail: { profileId, kind: 'pdf', projectId: file.projectId, repositoryId: file.repositoryId, filePath: file.path, page: 1 } }))
      bridge?.postMessage({ type: 'workspace.pdf', profileId, projectId: file.projectId, repositoryId: file.repositoryId, action: 'open', filePath: file.path, page: 1 })
    } else window.dispatchEvent(new CustomEvent('devshell.workspace.open', { detail: { profileId, kind: 'files', projectId: file.projectId, repositoryId: file.repositoryId, filePath: file.path.split('/').slice(0, -1).join('/'), revealPath: file.path } }))
  }
  const pinned = !!selected && navigation.pinned.some(file => identity(file) === identity(selected))
  const related = selected ? navigation.links.flatMap(link => identity(link.source) === identity(selected) ? [{ file: link.output, label: 'Open output' }] : identity(link.output) === identity(selected) ? [{ file: link.source, label: 'Open source' }] : []) : []
  function fileRow(file: FileReference, pin: boolean) {
    return <div className="file-shortcut-row" key={identity(file)}><button disabled={pending} title={caption(file)} onClick={() => open(file)}><span className={`workspace-tab-kind ${file.kind}`}>{file.kind}</span><span><strong>{file.path.split('/').at(-1)}</strong><small>{file.projectName ?? file.projectId} / {caption(file)}</small></span></button>{pin && <button disabled={pending} aria-label={`Unpin ${file.path}`} onClick={() => request('unpin', { file })}>Unpin</button>}</div>
  }
  return <div className="workspace-file-navigation">
    {selected && <div className="file-shortcut-actions"><button disabled={pending} aria-pressed={pinned} onClick={() => request(pinned ? 'unpin' : 'pin', { file: selected })}>{pinned ? 'Unpin file' : selected.kind === 'pdf' || selected.kind === 'image' ? 'Pin artifact' : 'Pin file'}</button><button disabled={pending} onClick={() => changeDraft(profileId, { ...draft, source: selected })}>Use as source</button><button disabled={pending} onClick={() => changeDraft(profileId, { ...draft, output: selected })}>Use as output</button>{related.slice(0, 8).map(({ file, label }, index) => <button key={`${identity(file)}:${index}`} title={caption(file)} disabled={pending} onClick={() => open(file)}>{label}: {file.path.split('/').at(-1)}</button>)}</div>}
    {(draft.source || draft.output) && <div className="file-link-draft" role="status"><span>Source: {draft.source ? caption(draft.source) : 'choose a file'}</span><span>Output: {draft.output ? caption(draft.output) : 'choose a file'}</span><button disabled={pending || !draft.source || !draft.output || identity(draft.source) === identity(draft.output)} onClick={() => request('link', { source: draft.source, output: draft.output })}>Link files</button><button disabled={pending} onClick={() => changeDraft(profileId, {})}>Cancel pairing</button></div>}
    <details className="file-shortcuts"><summary>Recent files &amp; pinned artifacts ({navigation.recent.length} recent / {navigation.pinned.length} pinned)</summary>
      <div className="file-shortcut-actions"><button disabled={pending} onClick={() => request('load')}>Refresh shortcuts</button><button disabled={pending || !navigation.recent.length} onClick={() => request('clear-recent')}>Clear recents</button></div>
      <div className="file-shortcut-columns"><section><h3>Pinned artifacts &amp; files</h3>{navigation.pinned.map(file => fileRow(file, true))}{!navigation.pinned.length && <p>Open a file or PDF, then click Pin file or Pin artifact.</p>}</section><section><h3>Recently opened files</h3>{navigation.recent.map(file => fileRow(file, false))}{!navigation.recent.length && <p>No recent files in this profile yet.</p>}</section></div>
      <section className="file-link-list"><h3>Source/output links</h3>{navigation.links.map(link => <div className="file-link-row" key={`${identity(link.source)}=>${identity(link.output)}`}><button disabled={pending} title={caption(link.source)} onClick={() => open(link.source)}>Source: {caption(link.source)}</button><button disabled={pending} title={caption(link.output)} onClick={() => open(link.output)}>Output: {caption(link.output)}</button><button disabled={pending} aria-label={`Remove link from ${link.source.path} to ${link.output.path}`} onClick={() => request('unlink', { source: link.source, output: link.output })}>Remove link</button></div>)}{!navigation.links.length && <p>Choose Use as source on one file and Use as output on another, then Link files. Pairing works across repositories and workspace panes.</p>}</section>
      <p className="workspace-view-caption">Per-profile file references only / up to 30 recent files, 40 pins, and 40 links. No preview contents, commands, authentication URLs, or notebook outputs are stored. Opening is explicit; nothing runs on restoration.</p>
    </details>
    {pending && <p className="workspace-view-caption" role="status">Updating file shortcuts...</p>}{error && <p className="check-error" role="alert">{error}</p>}
  </div>
}
