import { useEffect, useRef, useState } from 'react'

export type FileSearchHit = { repositoryId: string; repositoryName: string; entry: { name: string; path: string; kind: 'folder' | 'pdf' | 'text' | 'image' | 'code' | 'file'; artifact: boolean; size?: number; modified: string } }
type SearchResult = { entries: FileSearchHit[]; directoriesScanned: number; truncated: boolean; warnings: string[] }
type Bridge = { postMessage: (message: unknown) => void; addEventListener: (name: 'message', handler: (event: MessageEvent) => void) => void; removeEventListener: (name: 'message', handler: (event: MessageEvent) => void) => void }

export function ProjectFileSearch({ profileId, projectId, bridge, onOpen }: { profileId: string; projectId?: string; bridge: Bridge | null; onOpen: (hit: FileSearchHit) => void }) {
  const [query, setQuery] = useState(''); const [result, setResult] = useState<SearchResult>()
  const [pending, setPending] = useState(false); const [error, setError] = useState('')
  const current = useRef(''); const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  useEffect(() => {
    setResult(undefined); setQuery(''); setError(''); setPending(false)
    if (!bridge) return
    const receive = (event: MessageEvent) => {
      let message: { type?: string; profileId?: string; requestId?: string; search?: SearchResult; error?: string }
      try { message = typeof event.data === 'string' ? JSON.parse(event.data) : event.data } catch { return }
      if (message?.type !== 'workspace.files.result' || message.profileId !== profileId || !current.current || message.requestId !== current.current) return
      clearTimeout(timer.current); current.current = ''; setPending(false)
      if (message.error) setError(message.error)
      else if (message.search) setResult(message.search)
    }
    bridge.addEventListener('message', receive)
    return () => { clearTimeout(timer.current); current.current = ''; bridge.removeEventListener('message', receive) }
  }, [bridge, profileId, projectId])
  function search() {
    if (!bridge || !projectId) { setError('Project search requires the DevShell desktop app.'); return }
    current.current = crypto.randomUUID(); setPending(true); setError(''); setResult(undefined)
    clearTimeout(timer.current)
    timer.current = setTimeout(() => { current.current = ''; setPending(false); setError('Search timed out. Try a more specific filename.') }, 30000)
    bridge.postMessage({ type: 'workspace.files', profileId, projectId, requestId: current.current, action: 'search', query: query.trim() })
  }
  return <details className="project-file-search">
    <summary>Search project files</summary>
    <form className="project-file-search-form" onSubmit={event => { event.preventDefault(); if (!pending && query.trim().length >= 2) search() }}>
      <label>Filename or relative path <input aria-label="Project file search" placeholder="Notebook, image, report, or source filename..." maxLength={160} value={query} onChange={event => setQuery(event.target.value)} /></label>
      <button disabled={pending || query.trim().length < 2}>Search repositories</button>
    </form>
    <p className="workspace-view-caption">Searches filenames and relative paths across this project's repositories, not file contents. Dependency folders and symlinks are skipped; terms and results are not saved.</p>
    {pending && <p role="status">Searching project repositories...</p>}
    {error && <p role="alert" className="check-error">{error}</p>}
    {result && <><p role="status">{result.entries.length} matches / {result.directoriesScanned} folders checked{result.truncated ? ' / partial results: scan limits reached' : ''}</p>
      {result.warnings.map((warning, index) => <p className="workspace-view-caption" key={index}>{warning}</p>)}
      <div className="project-file-search-results" aria-label="Project file search results">{result.entries.map(hit => <button key={`${hit.repositoryId}:${hit.entry.path}`} className="project-file-search-result" title={hit.entry.kind === 'file' ? 'Show this file in its folder; no safe preview is available' : 'Open file in its repository'} onClick={() => onOpen(hit)}>
        <span className={`workspace-tab-kind ${hit.entry.kind}`}>{hit.entry.kind}</span><span><strong>{hit.entry.name}</strong><small>{hit.repositoryName} / {hit.entry.path}</small></span>
      </button>)}</div>{!result.entries.length && <p>No matching filenames. Try a shorter term or a relative path.</p>}
    </>}
  </details>
}
