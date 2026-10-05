import { useEffect, useRef, useState } from 'react'

type Bridge = { postMessage: (message: unknown) => void; addEventListener: (name: 'message', handler: (event: MessageEvent) => void) => void; removeEventListener: (name: 'message', handler: (event: MessageEvent) => void) => void }
type Entry = { name: string; path: string; kind: 'folder' | 'pdf' | 'text' | 'image' | 'file'; artifact: boolean; size?: number; modified: string }
type Overview = { entries: Entry[]; outputDirectory?: string; directoriesScanned: number; truncated: boolean; scannedAt: string; warnings: string[] }
export type ArtifactBuildStatus = { buildState: string; lastBuildFinishedAt?: string; lastBuildState?: string; lastBuildExitCode?: number }
function date(value?: string) { return value ? new Date(value).toLocaleString() : 'Unknown' }

export function ArtifactOverview({ profileId, projectId, repositoryId, bridge, job, onOpen, onFolder }: {
  profileId: string; projectId?: string; repositoryId?: string; bridge: Bridge | null; job?: ArtifactBuildStatus; onOpen: (entry: Entry) => void; onFolder: (path: string) => void
}) {
  const [overview, setOverview] = useState<Overview>(); const [pending, setPending] = useState(false); const [error, setError] = useState('')
  const [filter, setFilter] = useState<'all' | 'pdf' | 'image' | 'text'>('all'); const [query, setQuery] = useState('')
  const requestId = useRef(''); const timeout = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const lastBuild = useRef(job?.lastBuildFinishedAt)
  function refresh() {
    if (!bridge) { setError('Artifacts require the DevShell desktop app.'); return }
    clearTimeout(timeout.current); requestId.current = crypto.randomUUID(); setPending(true); setError('')
    timeout.current = setTimeout(() => { requestId.current = ''; setPending(false); setError('Artifact scan timed out. Refresh to retry.') }, 30000)
    bridge.postMessage({ type: 'workspace.files', profileId, projectId, repositoryId, requestId: requestId.current, action: 'artifacts' })
  }
  useEffect(() => {
    if (!bridge) return
    const receive = (event: MessageEvent) => {
      let message: { type?: string; profileId?: string; requestId?: string; error?: string; artifacts?: Overview }
      try { message = typeof event.data === 'string' ? JSON.parse(event.data) : event.data } catch { return }
      if (message?.type !== 'workspace.files.result' || message.profileId !== profileId || !requestId.current || message.requestId !== requestId.current) return
      clearTimeout(timeout.current); requestId.current = ''; setPending(false)
      if (message.error) setError(message.error); else if (message.artifacts) setOverview(message.artifacts)
    }
    bridge.addEventListener('message', receive); refresh()
    return () => { clearTimeout(timeout.current); requestId.current = ''; bridge.removeEventListener('message', receive) }
  }, [bridge, profileId, projectId, repositoryId])
  useEffect(() => {
    if (pending || !job?.lastBuildFinishedAt || job.lastBuildFinishedAt === lastBuild.current) return
    lastBuild.current = job.lastBuildFinishedAt
    if (job.lastBuildState === 'succeeded') refresh()
  }, [job?.lastBuildFinishedAt, job?.lastBuildState, pending])
  const entries = overview?.entries ?? []
  const visible = entries.filter(entry => (filter === 'all' || entry.kind === filter) && entry.path.toLowerCase().includes(query.toLowerCase()))
  const groups = [{ id: 'all', label: 'All artifacts' }, { id: 'pdf', label: 'PDFs' }, { id: 'image', label: 'Images' }, { id: 'text', label: 'Reports & documents' }] as const
  const newest = entries.reduce<string | undefined>((latest, entry) => !latest || entry.modified > latest ? entry.modified : latest, undefined)
  return <div className="artifact-overview">
    <div className="artifact-build-summary" role="status"><strong>Last managed build</strong><span>{job?.lastBuildFinishedAt ? `${date(job.lastBuildFinishedAt)} / ${job.lastBuildState ?? 'completed'}${job.lastBuildExitCode != null ? ` / exit ${job.lastBuildExitCode}` : ''}` : 'No build recorded in this launcher session.'}</span>{job?.buildState === 'building' && <span>Build currently running...</span>}</div>
    <div className="artifact-groups" aria-label="Artifact categories">{groups.map(group => <button key={group.id} aria-pressed={filter === group.id} onClick={() => setFilter(group.id)}><strong>{entries.filter(entry => group.id === 'all' || entry.kind === group.id).length}</strong><span>{group.label}</span></button>)}</div>
    <div className="artifact-toolbar"><label>Search artifacts <input aria-label="Artifact search" value={query} placeholder="Filter paths across scanned folders..." onChange={event => setQuery(event.target.value)} /></label><button disabled={pending} onClick={refresh}>Refresh overview</button><button disabled={overview?.outputDirectory == null} onClick={() => onFolder(overview!.outputDirectory!)}>Browse output folder</button></div>
    {error && <p className="check-error" role="alert">{error}</p>}
    {pending && <p role="status">Scanning artifact metadata...</p>}
    {overview && <p className="workspace-view-caption">Scanned {overview.directoriesScanned} folders at {date(overview.scannedAt)}. Newest file modification: {date(newest)} / file timestamps are not build completion times.</p>}
    {overview?.truncated && <p className="artifact-scan-warning">Partial overview: scan limits reached. Browse individual folders for remaining files. Limits: 500 artifacts, 200 folders, 10,000 entries, depth 8, and an 8-second scan budget.</p>}
    {!!overview?.warnings.length && <details className="artifact-scan-warning"><summary>Some folders could not be scanned</summary>{overview.warnings.map((warning, index) => <p key={index}>{warning}</p>)}</details>}
    <div className="artifact-list" aria-label="Available artifacts">{visible.map(entry => <div key={entry.path} className="artifact-row"><button className="artifact-open" data-kind={entry.kind} title={`Preview ${entry.path}`} onClick={() => onOpen(entry)}><span className={`workspace-tab-kind ${entry.kind}`}>{entry.kind === 'text' ? 'document' : entry.kind}</span><span><strong>{entry.name}</strong><small>{entry.path}</small></span><span className="artifact-file-meta">{((entry.size ?? 0) / 1024).toFixed(1)} KB<small>{date(entry.modified)}</small></span></button><button title="Browse the containing folder" onClick={() => onFolder(entry.path.split('/').slice(0, -1).join('/'))}>Folder</button></div>)}{overview && !visible.length && <p>No matching artifacts in the scanned folders.</p>}</div>
    <p className="workspace-view-caption">Read-only metadata scan / dependency folders and symlinks are excluded. Files are read only when previewed. Build timestamps are session-only; overview data and search terms are not saved.</p>
  </div>
}
