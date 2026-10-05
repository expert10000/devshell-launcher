import { useEffect, useRef, useState } from 'react'
import type { WorkspaceViewTab } from './useWorkspaceTabs'
import { MarkdownPreview } from './MarkdownPreview'
import { ArtifactOverview, type ArtifactBuildStatus } from './ArtifactOverview'
import { CodeFilePreview, JsonFilePreview, TableFilePreview } from './DataFilePreview'
import { HtmlFilePreview } from './HtmlFilePreview'

type Repo = { id: string; name: string }
type Bridge = { postMessage: (message: unknown) => void; addEventListener: (name: 'message', handler: (event: MessageEvent) => void) => void; removeEventListener: (name: 'message', handler: (event: MessageEvent) => void) => void }
type Entry = { name: string; path: string; kind: 'folder' | 'pdf' | 'text' | 'image' | 'code' | 'file'; artifact: boolean; size?: number; modified: string }
type Listing = { path: string; entries: Entry[]; truncated: boolean }
type Preview = { path: string; text: string; truncated: boolean }
type ImagePreview = { path: string; mimeType: string; dataUrl: string; size: number }

export function FilesWorkspaceView({ tab, profileId, bridge, repos, active, onFolder, job }: {
  tab: WorkspaceViewTab; profileId: string; bridge: Bridge | null; repos: Repo[]; active: boolean; onFolder: (path: string) => void; job?: ArtifactBuildStatus
}) {
  const [listing, setListing] = useState<Listing>(); const [preview, setPreview] = useState<Preview>()
  const [image, setImage] = useState<ImagePreview>(); const [showSource, setShowSource] = useState(false)
  const [overview, setOverview] = useState(false)
  const [path, setPath] = useState(tab.filePath ?? ''); const [query, setQuery] = useState(''); const [artifacts, setArtifacts] = useState(false)
  const [pending, setPending] = useState(false); const [error, setError] = useState('')
  const [selectedPath, setSelectedPath] = useState('')
  const [previewKind, setPreviewKind] = useState<Entry['kind']>('text')
  const [history, setHistory] = useState<{ paths: string[]; index: number }>({ paths: [], index: -1 })
  const requestedHistoryIndex = useRef<number | undefined>(undefined)
  const handledActivation = useRef(tab.activationId)
  const current = useRef(''); const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const latest = useRef({ onFolder }); latest.current = { onFolder }
  function request(action: 'list' | 'preview' | 'image', target: string, historyIndex?: number) {
    if (!bridge) { setError('Files require the DevShell desktop app.'); return }
    if (action === 'list') setOverview(false)
    requestedHistoryIndex.current = action === 'list' ? historyIndex : undefined
    clearTimeout(timer.current); current.current = crypto.randomUUID(); setPending(true); setError(''); setPreview(undefined); setImage(undefined); setShowSource(false)
    timer.current = setTimeout(() => { current.current = ''; setPending(false); setError('File request timed out. Refresh to retry.') }, 30000)
    bridge.postMessage({ type: 'workspace.files', profileId, projectId: tab.projectId, repositoryId: tab.repositoryId, requestId: current.current, action, path: target })
  }
  useEffect(() => {
    if (!bridge) return
    const receive = (event: MessageEvent) => {
      let message: { type?: string; profileId?: string; projectId?: string; repositoryId?: string; requestId?: string; error?: string; listing?: Listing; preview?: Preview; image?: ImagePreview }
      try { message = typeof event.data === 'string' ? JSON.parse(event.data) : event.data } catch { return }
      const outputOpened = message?.type === 'workspace.files.opened' && message.projectId === tab.projectId && message.repositoryId === tab.repositoryId
      if (message?.profileId !== profileId || !(outputOpened || message.type === 'workspace.files.result' && !!current.current && message.requestId === current.current)) return
      clearTimeout(timer.current); current.current = ''; setPending(false)
      if (outputOpened) { requestedHistoryIndex.current = undefined; setPreview(undefined); setImage(undefined); setShowSource(false); setOverview(false); setError('') }
      if (message.error) { setError(message.error); return }
      if (message.listing) {
        const result = message.listing; const historyIndex = requestedHistoryIndex.current
        setHistory(previous => {
          if (historyIndex !== undefined && previous.paths[historyIndex] === result.path) return { ...previous, index: historyIndex }
          if (previous.paths[previous.index] === result.path) return previous
          const paths = [...previous.paths.slice(0, previous.index + 1), result.path].slice(-100)
          return { paths, index: paths.length - 1 }
        })
        setListing(result); setPath(result.path); setQuery(''); setSelectedPath(previous => result.entries.some(entry => entry.path === previous) ? previous : ''); latest.current.onFolder(result.path)
      }
      if (message.preview) setPreview(message.preview)
      if (message.image) setImage(message.image)
    }
    bridge.addEventListener('message', receive)
    if (!tab.restored) request('list', tab.filePath ?? '')
    return () => { clearTimeout(timer.current); current.current = ''; bridge.removeEventListener('message', receive) }
  }, [bridge, profileId, tab.id])
  useEffect(() => {
    if (active && !pending && (tab.filePath ?? '') !== (listing?.path ?? path)) request('list', tab.filePath ?? '')
  }, [tab.filePath, active, pending])
  useEffect(() => {
    if (!active || pending || !tab.activationId || handledActivation.current === tab.activationId) return
    handledActivation.current = tab.activationId
    // Explicit selection may load a restored location, but restoration itself
    // never creates an activation token. Keep loaded lists and PDF-return filters.
    if (!listing && !overview) request('list', tab.filePath ?? '')
  }, [active, pending, tab.activationId, overview])
  function open(entry: Entry) {
    setSelectedPath(entry.path)
    setPreviewKind(entry.kind)
    if (entry.kind === 'folder') { request('list', entry.path); return }
    if (entry.kind === 'text' || entry.kind === 'code') { request('preview', entry.path); return }
    if (entry.kind === 'image') { request('image', entry.path); return }
    if (entry.kind === 'pdf') {
      window.dispatchEvent(new CustomEvent('devshell.workspace.open', { detail: { profileId, kind: 'pdf', projectId: tab.projectId, repositoryId: tab.repositoryId, filePath: entry.path, page: 1 } }))
      bridge?.postMessage({ type: 'workspace.pdf', profileId, projectId: tab.projectId, repositoryId: tab.repositoryId, action: 'open', filePath: entry.path, page: 1 })
    }
  }
  const entries = listing?.entries.filter(entry => (!artifacts || entry.kind === 'folder' || entry.artifact) && entry.name.toLowerCase().includes(query.toLowerCase())) ?? []
  const folder = listing?.path ?? tab.filePath ?? ''
  const segments = folder.split('/').filter(Boolean)
  const markdown = !!preview && /\.(md|markdown)$/i.test(preview.path)
  const html = !!preview && /\.html?$/i.test(preview.path)
  const json = !!preview && /\.(json|ipynb)$/i.test(preview.path)
  const table = !!preview && /\.(csv|tsv)$/i.test(preview.path)
  const structured = !html && (markdown || json || table || previewKind === 'code')
  const renderedPreview = preview && !showSource ? html ? <HtmlFilePreview key={preview.path} text={preview.text} filename={preview.path} /> : markdown ? <MarkdownPreview text={preview.text} /> : json ? <JsonFilePreview key={preview.path} text={preview.text} notebook={/\.ipynb$/i.test(preview.path)} /> : table ? <TableFilePreview key={preview.path} text={preview.text} delimiter={/\.tsv$/i.test(preview.path) ? '\t' : ','} /> : previewKind === 'code' ? <CodeFilePreview text={preview.text} filename={preview.path} /> : undefined : undefined
  return <div className="files-workspace">
    <div className="workspace-view-toolbar files-toolbar">
      <label>Repository <select aria-label="Files repository" value={tab.repositoryId} onChange={event => window.dispatchEvent(new CustomEvent('devshell.workspace.open', { detail: { profileId, kind: 'files', projectId: tab.projectId, repositoryId: event.target.value } }))}>{repos.map(repo => <option key={repo.id} value={repo.id}>{repo.name}</option>)}</select></label>
      <button aria-pressed={!overview} onClick={() => { setOverview(false); if (!listing && !pending) request('list', tab.filePath ?? '') }}>Folder browser</button>
      <button aria-pressed={overview} onClick={() => { setOverview(true); setPreview(undefined); setImage(undefined); setError('') }}>Artifact overview</button>
      <button disabled={pending || history.index <= 0} title={history.index > 0 ? `Back to ${history.paths[history.index - 1] || 'repository root'}` : 'No previous folder'} onClick={() => request('list', history.paths[history.index - 1], history.index - 1)}>Back</button>
      <button disabled={pending || history.index < 0 || history.index >= history.paths.length - 1} title={history.index < history.paths.length - 1 ? `Forward to ${history.paths[history.index + 1] || 'repository root'}` : 'No next folder'} onClick={() => request('list', history.paths[history.index + 1], history.index + 1)}>Forward</button>
      <button disabled={pending} onClick={() => request('list', '')}>Root</button>
      <button disabled={pending || !listing?.path} onClick={() => request('list', listing!.path.split('/').slice(0, -1).join('/'))}>Up</button>
      <button disabled={pending} onClick={() => request('list', listing?.path ?? tab.filePath ?? '')}>Refresh files</button>
    </div>
    <form className="files-path-form" style={{ display: overview ? 'none' : undefined }} onSubmit={event => { event.preventDefault(); request('list', path) }}><label>Relative folder <input aria-label="Files relative folder" value={path} placeholder="Repository root" onChange={event => setPath(event.target.value)} /></label><button disabled={pending}>Go</button></form>
    <nav className="files-location files-breadcrumbs" aria-label="Folder breadcrumbs" style={{ display: overview ? 'none' : undefined }}>
      <button disabled={pending} aria-label="Repository root" aria-current={!folder ? 'location' : undefined} title="Browse repository root" onClick={() => request('list', '')}>{repos.find(repo => repo.id === tab.repositoryId)?.name ?? 'Repository'}</button>
      {segments.map((segment, index) => { const target = segments.slice(0, index + 1).join('/'); return <span className="files-breadcrumb" key={target}><span aria-hidden="true">/</span><button disabled={pending} aria-current={index === segments.length - 1 ? 'location' : undefined} title={target} onClick={() => request('list', target)}>{segment}</button></span> })}
    </nav>
    <div className="files-filters" style={{ display: overview ? 'none' : undefined }}><label>Search <input aria-label="File search" value={query} placeholder="Filter this folder..." onChange={event => setQuery(event.target.value)} /></label><label className={artifacts ? 'files-artifact-filter active' : 'files-artifact-filter'}><input type="checkbox" checked={artifacts} onChange={event => setArtifacts(event.target.checked)} /> Artifacts only</label></div>
    {selectedPath && <p className="files-selection" role="status">Selected: {selectedPath}</p>}
    {error && <p className="check-error" role="alert">{error}</p>}
    {pending && <p role="status">Reading files...</p>}
    {!overview && !listing && !pending && <p>Saved location only. Click Refresh files to list the repository; no document or command was reopened.</p>}
    {listing?.truncated && <p className="workspace-view-caption">Showing the first 1000 entries. Navigate to a smaller folder to see more.</p>}
    <div className={`files-body ${preview || image ? 'has-preview' : ''}`}><div className="files-list" aria-label="Repository files">
      {overview && <ArtifactOverview profileId={profileId} projectId={tab.projectId} repositoryId={tab.repositoryId} bridge={bridge} job={job} onOpen={open} onFolder={target => request('list', target)} />}
      {!overview && <>
      {entries.map(entry => <button key={entry.path} className={`files-row ${selectedPath === entry.path ? 'selected' : ''}`} aria-pressed={selectedPath === entry.path} data-kind={entry.kind} disabled={pending || entry.kind === 'file'} title={entry.kind === 'file' ? 'No safe preview for this file type' : `${entry.path} / ${entry.kind === 'folder' ? 'Browse folder' : entry.kind === 'pdf' ? 'Open PDF' : entry.kind === 'image' ? 'Read-only image preview' : 'Read-only text preview'}`} onClick={() => open(entry)}><span className={`workspace-tab-kind ${entry.kind}`}>{entry.kind}</span><strong>{entry.name}</strong><span>{entry.kind === 'folder' ? 'Folder' : `${((entry.size ?? 0) / 1024).toFixed(1)} KB`}</span></button>)}
      {listing && !entries.length && <p>No matching files or folders.</p>}
      </>}
    </div>{preview && <section className="files-preview"><header><strong>{preview.path}</strong><div className="files-preview-actions">{structured && <button aria-pressed={showSource} onClick={() => setShowSource(previous => !previous)}>{showSource ? 'Formatted preview' : 'View source'}</button>}<button onClick={() => setPreview(undefined)}>Close preview</button></div></header>{renderedPreview ?? <pre className="workspace-output" tabIndex={0} aria-label="Read-only file preview">{preview.text}</pre>}{markdown && <p className="workspace-view-caption">Safe Markdown preview / HTML is text; links and embedded images are not opened or loaded.</p>}{preview.truncated && <p>Preview truncated at 128K characters.</p>}</section>}{image && <section className="files-preview"><header><strong>{image.path}</strong><button onClick={() => setImage(undefined)}>Close preview</button></header><div className="files-image-preview"><img src={image.dataUrl} alt={image.path} onError={() => { setImage(undefined); setError('The image could not be decoded. Only PNG, JPEG, GIF, and WebP up to 8 MiB are previewed.') }} /></div><p className="workspace-view-caption">{image.mimeType} / {(image.size / 1024).toFixed(1)} KB / read-only local preview</p></section>}</div>
    <p className="workspace-view-caption">Read-only / no terminal session required. Folder locations are remembered; Back/Forward history stays in this session only. Previews, file contents, and search terms are not saved. PDFs open in the native viewer. Other file types are never executed.</p>
  </div>
}
