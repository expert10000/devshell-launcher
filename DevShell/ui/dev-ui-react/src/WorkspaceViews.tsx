import { useEffect, useRef, useState } from 'react'
import type { WorkspaceViewTab } from './useWorkspaceTabs'
import { PdfWorkspaceView } from './PdfWorkspaceView'
import { FilesWorkspaceView } from './FilesWorkspaceView'
import { chooseWorkspacePane, resizeWorkspacePanes, resolveWorkspaceSplit, singleWorkspacePane, splitWorkspacePane } from './workspaceSplit'
import { WorkspaceFileNavigation } from './WorkspaceFileNavigation'
import { NamedWorkspaceLayouts } from './NamedWorkspaceLayouts'
import { BuildDiagnostics } from './BuildDiagnostics'
import { ArtifactComparison } from './ArtifactComparison'
import { WorkspaceCommandPalette } from './WorkspaceCommandPalette'

type Project = { id: string; name: string; repositories?: { id: string; name: string; pdfDirectory?: string; buildTask?: string; runTask?: string; url?: string }[] }
type Job = { key: string; state: string; buildState: string; exitCode?: number; log: string; logPath: string; action?: string; lastBuildFinishedAt?: string; lastBuildState?: string; lastBuildExitCode?: number }
type Bridge = { postMessage: (message: unknown) => void; addEventListener: (name: 'message', handler: (event: MessageEvent) => void) => void; removeEventListener: (name: 'message', handler: (event: MessageEvent) => void) => void }
type ChangedFile = { path: string; staged: boolean; unstaged: boolean; conflicted: boolean }
type Snapshot = { path: string; files: ChangedFile[]; blockedReason?: string }
type Diff = { path: string; side: string; text: string; truncated: boolean }

export function workspaceTabTitle(tab: WorkspaceViewTab, projects: Project[]) {
  const project = projects.find(item => item.id === tab.projectId)
  const repo = project?.repositories?.find(item => item.id === tab.repositoryId)
  if (tab.kind === 'logs') return `${repo?.name ?? 'Repository'} Logs`
  if (tab.kind === 'diff') return `${repo?.name ?? 'Repository'} Diff`
  if (tab.kind === 'files') return `${repo?.name ?? 'Project'} Files`
  if (tab.kind === 'pdf') return `${repo?.name ?? 'Document'} / ${tab.filePath?.split('/').at(-1) ?? 'PDF selector'}`
  if (tab.kind === 'jupyter') return `${project?.name ?? 'Jupyter'}${tab.servicePath ? ` / ${tab.servicePath.split('/').at(-1)}` : ''}`
  try { return `${repo?.name ?? new URL(tab.url ?? '').hostname} Browser` } catch { return 'Browser' }
}

export function WorkspaceTabButtons({ tabs, activeId, projects, onSelect, onClose }: { tabs: WorkspaceViewTab[]; activeId: string | null; projects: Project[]; onSelect: (id: string) => void; onClose: (id: string) => void }) {
  return <>{tabs.map(tab => <div key={tab.id} className={`workspace-tab-entry ${activeId === tab.id ? 'active' : ''}`}>
    <button className={`tab ${activeId === tab.id ? 'active' : ''}`} role="tab" aria-selected={activeId === tab.id} onClick={() => onSelect(tab.id)} title={workspaceTabTitle(tab, projects)}><span className={`workspace-tab-kind ${tab.kind}`}>{tab.kind}</span><span>{workspaceTabTitle(tab, projects)}</span></button>
    <button className="workspace-tab-close" aria-label={`Close ${workspaceTabTitle(tab, projects)}`} title="Close view only; running jobs and browser pages are not stopped" onClick={() => onClose(tab.id)}>x</button>
  </div>)}</>
}

function LogsView({ job, error, onStop, onFullLog, onRefresh, onOutputFolder }: { job?: Job; error?: string; onStop: () => void; onFullLog: () => void; onRefresh: () => void; onOutputFolder: () => void }) {
  const [follow, setFollow] = useState(true); const output = useRef<HTMLPreElement>(null)
  useEffect(() => { if (follow && output.current) output.current.scrollTop = output.current.scrollHeight }, [job?.log, follow])
  const running = !!job && ['queued', 'building', 'running'].includes(job.state)
  const built = !!job && ['build', 'launch'].includes(job.action ?? '') && (job.buildState === 'succeeded' || job.action === 'build' && job.state === 'succeeded')
  return <>
    <div className="workspace-view-toolbar"><strong role="status">{job ? `${job.action ?? 'Job'}: ${job.state}${job.exitCode != null ? ` / exit ${job.exitCode}` : ''}` : 'No job in this launcher session'}</strong><div className="service-actions">
      <label><input type="checkbox" checked={follow} onChange={event => setFollow(event.target.checked)} /> Follow output</label>
      <button onClick={onRefresh}>Refresh</button><button disabled={!running} onClick={onStop}>Stop</button><button disabled={!job?.logPath} onClick={onFullLog}>Open full log</button>
      <button disabled={!built} title={built ? 'Browse the configured output directory or an existing dist, build, or bin folder' : 'Available after a successful managed build in this launcher session'} onClick={onOutputFolder}>Show output folder</button>
    </div></div>
    {error && <p className="check-error" role="alert">{error}</p>}
    <pre ref={output} className="workspace-output" tabIndex={0} aria-label="Job output">{job?.log || (job ? 'Waiting for output...' : 'This tab remembers the repository, not a job or its output. Nothing was restarted. Run a repository action to view its live output here.')}</pre>
    {job?.logPath && <p className="workspace-view-caption">{job.logPath} / closing this tab does not stop the job.</p>}
  </>
}

function DiffView({ tab, profileId, bridge, active, busy, onChange }: { tab: WorkspaceViewTab; profileId: string; bridge: Bridge | null; active: boolean; busy: boolean; onChange: (changes: Pick<WorkspaceViewTab, 'filePath' | 'side'>) => void }) {
  const [snapshot, setSnapshot] = useState<Snapshot>(); const [diff, setDiff] = useState<Diff>()
  const [filePath, setFilePath] = useState(tab.filePath ?? ''); const [side, setSide] = useState<'working' | 'staged'>(tab.side ?? 'working')
  const [pending, setPending] = useState(false); const [error, setError] = useState('')
  const current = useRef<{ id: string; action: string; filePath?: string; side?: 'working' | 'staged' }>({ id: '', action: '' })
  const timeout = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const latest = useRef({ tab, onChange }); latest.current = { tab, onChange }
  function request(action: 'changes' | 'file-diff', path?: string, targetSide?: 'working' | 'staged') {
    if (!bridge) { setError('Diff previews require the DevShell desktop app.'); return }
    clearTimeout(timeout.current)
    const id = crypto.randomUUID(); current.current = { id, action, filePath: path, side: targetSide }
    setPending(true); setError(''); setDiff(undefined)
    timeout.current = setTimeout(() => { current.current.id = ''; setPending(false); setError('Git timed out. Refresh to retry.') }, 65000)
    bridge.postMessage({ type: 'repository.job', action, profileId, projectId: tab.projectId, repositoryId: tab.repositoryId, requestId: id, path, side: targetSide })
  }
  useEffect(() => {
    if (!bridge) return
    const receive = (event: MessageEvent) => {
      let message: { type?: string; profileId?: string; requestId?: string; snapshot?: Snapshot; diff?: Diff; error?: string }
      try { message = typeof event.data === 'string' ? JSON.parse(event.data) : event.data } catch { return }
      if (message?.type !== 'repository.changes' || message.profileId !== profileId || message.requestId !== current.current.id) return
      clearTimeout(timeout.current); setPending(false)
      if (message.error) { setError(message.error); return }
      if (message.snapshot) setSnapshot(message.snapshot)
      if (message.diff) { setDiff(message.diff); return }
      if (current.current.action === 'changes' && message.snapshot) {
        const desired = latest.current.tab.filePath
        const selected = message.snapshot.files.find(file => file.path === desired) ?? message.snapshot.files[0]
        if (!selected) { setFilePath(''); setDiff(undefined); return }
        const targetSide = latest.current.tab.side ?? (selected.unstaged ? 'working' : 'staged')
        setFilePath(selected.path); setSide(targetSide); latest.current.onChange({ filePath: selected.path, side: targetSide })
        request('file-diff', selected.path, targetSide)
      }
    }
    bridge.addEventListener('message', receive)
    if (!tab.restored && active && !busy) request('changes')
    return () => { clearTimeout(timeout.current); current.current.id = ''; bridge.removeEventListener('message', receive) }
  }, [bridge, profileId, tab.id])
  useEffect(() => {
    if (!active || busy || pending || !tab.filePath || tab.filePath === filePath && (tab.side ?? 'working') === side) return
    setFilePath(tab.filePath); setSide(tab.side ?? 'working')
    request('file-diff', tab.filePath, tab.side ?? 'working')
  }, [tab.filePath, tab.side, active, busy, pending])
  function choose(path: string, targetSide: 'working' | 'staged') {
    setFilePath(path); setSide(targetSide); onChange({ filePath: path, side: targetSide }); if (path) request('file-diff', path, targetSide)
  }
  return <>
    <div className="workspace-view-toolbar"><div className="workspace-diff-controls">
      <label>File <select aria-label="Diff file" value={filePath} disabled={pending || busy || !snapshot?.files.length} onChange={event => choose(event.target.value, side)}><option value="">Select a changed file</option>{snapshot?.files.map(file => <option key={file.path} value={file.path}>{file.path}{file.conflicted ? ' (conflict)' : ''}{file.staged ? ' [staged]' : ''}{file.unstaged ? ' [working]' : ''}</option>)}</select></label>
      <label>Compare <select aria-label="Diff side" value={side} disabled={pending || busy} onChange={event => choose(filePath, event.target.value as 'working' | 'staged')}><option value="working">Working tree vs index</option><option value="staged">Staged vs HEAD</option></select></label>
      <button disabled={pending || busy} onClick={() => request('changes')}>{pending ? 'Reading Git...' : 'Refresh'}</button>
    </div><span className="workspace-view-caption">Read-only / no staging, commits, or task execution</span></div>
    {snapshot && <p className="workspace-view-caption">{snapshot.path} / {snapshot.files.length} changed files</p>}
    {busy && <p role="status">This checkout has an active job or Update All reservation. Refresh is available when it finishes.</p>}
    {error && <p className="check-error" role="alert">{error}</p>}
    <pre className="workspace-output workspace-diff-output" tabIndex={0} aria-label="File diff">{diff?.text ?? (pending ? 'Reading current Git state...' : snapshot ? snapshot.files.length ? 'Select a file and comparison side.' : 'Clean checkout: no changed files.' : 'Restored descriptor only. Click Refresh to read the current changes; no command was replayed.')}</pre>
    {diff?.truncated && <p className="workspace-view-caption">Preview truncated at 240 KB. Use VS Code for the full diff.</p>}
  </>
}

export function WorkspaceViews({ tabs, activeId, profileId, projects, jobs, errors, reservedKeys, bridge, onChange, onClose, onBack, backTarget }: {
  tabs: WorkspaceViewTab[]; activeId: string | null; profileId: string; projects: Project[]; jobs: Job[]; errors: Record<string, string>; reservedKeys: Set<string>; bridge: Bridge | null;
  onChange: (id: string, changes: Pick<WorkspaceViewTab, 'filePath' | 'side' | 'page'>) => void; onClose: (id: string) => void; onBack: () => void; backTarget?: WorkspaceViewTab
}) {
  const [split, setSplit] = useState(() => singleWorkspacePane(profileId, activeId))
  const [compact, setCompact] = useState(false)
  const [resizing, setResizing] = useState(false)
  const grid = useRef<HTMLDivElement>(null)
  const drag = useRef<{ id: number; direction: 'right' | 'below' } | null>(null)
  const ids = tabs.map(tab => tab.id)
  const layout = resolveWorkspaceSplit(split, profileId, ids, activeId)
  const direction = layout.direction === 'right' && compact ? 'below' : layout.direction
  const busyKeys = new Set([...reservedKeys, ...jobs.filter(job => ['queued', 'building', 'running'].includes(job.state)).map(job => job.key)])
  useEffect(() => { setSplit(previous => resolveWorkspaceSplit(previous, profileId, tabs.map(tab => tab.id), activeId)) }, [profileId, tabs, activeId])
  useEffect(() => {
    const element = grid.current; if (!element) return
    const observer = new ResizeObserver(() => setCompact(element.clientWidth < 760))
    observer.observe(element); return () => observer.disconnect()
  }, [])
  useEffect(() => { drag.current = null; setResizing(false) }, [profileId, direction])
  function focusPane(id: string) {
    if (activeId !== id) window.dispatchEvent(new CustomEvent('devshell.workspace.select', { detail: { profileId, id } }))
  }
  function choosePane(pane: 'primary' | 'secondary', id: string) {
    setSplit(chooseWorkspacePane(layout, pane, id)); focusPane(id)
  }
  function closeTab(id: string) {
    const survivor = layout.direction && (id === layout.primaryId ? layout.secondaryId : id === layout.secondaryId ? layout.primaryId : null)
    onClose(id)
    if (survivor) { setSplit(singleWorkspacePane(profileId, survivor)); focusPane(survivor) }
  }
  function releaseDivider() { drag.current = null; setResizing(false) }
  function repositoryAction(tab: WorkspaceViewTab, action: string) { bridge?.postMessage({ type: 'repository.job', projectId: tab.projectId, repositoryId: tab.repositoryId, action }) }
  return <div className="workspace-content workspace-split-content" style={{ display: activeId ? undefined : 'none' }}>
    <div className="workspace-split-toolbar" aria-label="Workspace layout">
      <WorkspaceCommandPalette profileId={profileId} bridge={bridge} projects={projects} tabs={tabs} activeId={activeId} busyKeys={busyKeys} />
      <button disabled={tabs.length < 2} aria-pressed={layout.direction === 'right'} title={tabs.length < 2 ? 'Open a second workspace tab first' : 'Keep two workspace views side by side'} onClick={() => setSplit(splitWorkspacePane(layout, 'right', ids, activeId))}>Split right</button>
      <button disabled={tabs.length < 2} aria-pressed={layout.direction === 'below'} title={tabs.length < 2 ? 'Open a second workspace tab first' : 'Keep two workspace views above and below'} onClick={() => setSplit(splitWorkspacePane(layout, 'below', ids, activeId))}>Split below</button>
      {layout.direction && <>
        <button onClick={() => setSplit(singleWorkspacePane(profileId, activeId))}>Single pane</button>
        <label>First pane <select aria-label="First workspace pane" value={layout.primaryId ?? ''} onChange={event => choosePane('primary', event.target.value)}>{tabs.map(tab => <option key={tab.id} value={tab.id}>{workspaceTabTitle(tab, projects)}</option>)}</select></label>
        <label>Second pane <select aria-label="Second workspace pane" value={layout.secondaryId ?? ''} onChange={event => choosePane('secondary', event.target.value)}>{tabs.map(tab => <option key={tab.id} value={tab.id}>{workspaceTabTitle(tab, projects)}</option>)}</select></label>
        <span className="workspace-view-caption">{compact && layout.direction === 'right' ? 'Stacked to fit this window. ' : ''}Choose a tab for each pane; new views replace the focused pane. Layout is session-only.</span>
      </>}
      {!layout.direction && tabs.length < 2 && <span className="workspace-view-caption">Open another Files, Logs, Diff, or viewer tab to split.</span>}
    </div>
    <NamedWorkspaceLayouts profileId={profileId} bridge={bridge} layout={layout} tabs={tabs} onRestore={setSplit} />
    <ArtifactComparison profileId={profileId} bridge={bridge} />
    <div ref={grid} className={`workspace-split-grid ${direction ? `split split-${direction}` : ''} ${resizing ? 'resizing' : ''}`} style={{ gridTemplateColumns: direction === 'right' ? `minmax(0, ${layout.ratio}fr) 10px minmax(0, ${100 - layout.ratio}fr)` : 'minmax(0, 1fr)', gridTemplateRows: direction === 'below' ? `minmax(0, ${layout.ratio}fr) 10px minmax(0, ${100 - layout.ratio}fr)` : 'minmax(0, 1fr)' }}>{tabs.map(tab => {
    const key = `${profileId}:${tab.projectId}:${tab.repositoryId}`; const job = jobs.find(item => item.key === key)
    const busy = reservedKeys.has(key) || !!job && ['queued', 'building', 'running'].includes(job.state)
    const secondary = !!direction && tab.id === layout.secondaryId
    const visible = tab.id === layout.primaryId || secondary
    return <section key={tab.id} role="tabpanel" aria-label={workspaceTabTitle(tab, projects)} data-workspace-pane={visible ? secondary ? 'secondary' : 'primary' : undefined} className={`workspace-view ${activeId === tab.id ? 'pane-focused' : ''}`} style={{ display: visible ? undefined : 'none', gridColumn: secondary && direction === 'right' ? 3 : 1, gridRow: secondary && direction === 'below' ? 3 : 1 }} onPointerDownCapture={() => visible && focusPane(tab.id)} onFocusCapture={() => visible && focusPane(tab.id)}>
      <header className="workspace-view-heading"><div>{tab.kind === 'pdf' && activeId === tab.id && backTarget && <button className="workspace-back" onClick={onBack} title={`Return to ${workspaceTabTitle(backTarget, projects)} without closing this PDF`}>{backTarget.kind === 'files' ? 'Back to files' : 'Back to PDF selector'}</button>}<span className={`workspace-tab-kind ${tab.kind}`}>{tab.kind}</span><h2>{workspaceTabTitle(tab, projects)}</h2></div><div className="workspace-pane-actions">{direction && <button aria-label={`Focus ${secondary ? 'second' : 'first'} workspace pane`} aria-pressed={activeId === tab.id} onClick={() => focusPane(tab.id)}>Focus pane</button>}<button onClick={() => closeTab(tab.id)}>Close tab</button></div></header>
      {tab.kind === 'logs' && <LogsView job={job} error={errors[key]} onStop={() => repositoryAction(tab, 'stop')} onFullLog={() => repositoryAction(tab, 'log')} onRefresh={() => bridge?.postMessage({ type: 'repository.job', action: 'status' })} onOutputFolder={() => bridge?.postMessage({ type: 'workspace.files', action: 'output', profileId, projectId: tab.projectId, repositoryId: tab.repositoryId, requestId: crypto.randomUUID() })} />}
      {tab.kind === 'logs' && <BuildDiagnostics log={job?.log ?? ''} profileId={profileId} projectId={tab.projectId} repositoryId={tab.repositoryId} bridge={bridge} />}
      {tab.kind === 'diff' && <DiffView tab={tab} profileId={profileId} bridge={bridge} active={visible && !!activeId} busy={busy} onChange={changes => onChange(tab.id, changes)} />}
      {tab.kind === 'files' && <FilesWorkspaceView tab={tab} profileId={profileId} bridge={bridge} repos={projects.find(project => project.id === tab.projectId)?.repositories ?? []} active={visible && !!activeId} onFolder={path => onChange(tab.id, { filePath: path })} job={job} />}
      {tab.kind === 'pdf' && <><WorkspaceFileNavigation profileId={profileId} projectId={tab.projectId} bridge={bridge} selected={tab.filePath && tab.projectId && tab.repositoryId ? { projectId: tab.projectId, repositoryId: tab.repositoryId, path: tab.filePath, kind: 'pdf' } : undefined} /><PdfWorkspaceView tab={tab} profileId={profileId} bridge={bridge} job={job} directory={projects.find(project => project.id === tab.projectId)?.repositories?.find(repo => repo.id === tab.repositoryId)?.pdfDirectory} onPage={page => onChange(tab.id, { page })} /></>}
      {(tab.kind === 'browser' || tab.kind === 'jupyter') && <div className="workspace-browser-entry"><h3>{tab.kind === 'jupyter' ? 'Jupyter in the native browser pane' : 'Browser page in the native pane'}</h3><p>{tab.kind === 'jupyter' ? tab.servicePath ?? 'JupyterLab workspace' : tab.url}</p>
        <p>Workspace navigation is linked to the existing browser pane. Restoring this entry does not navigate, start a service, or replay a task.</p>
        <button onClick={() => tab.kind === 'jupyter' ? bridge?.postMessage({ type: 'service.control', projectId: tab.projectId, action: 'open', path: tab.servicePath }) : bridge?.postMessage({ type: 'browser.open', projectId: tab.projectId, url: tab.url })}>{tab.kind === 'jupyter' ? 'Open Jupyter' : 'Open / focus browser page'}</button>
        <p className="workspace-view-caption">Use Show/hide browser to toggle the native pane. Closing this workspace entry does not close the page.{tab.kind === 'browser' ? ' Saved links omit credentials, query strings, and fragments; use the original task when parameters are required.' : ' Notebook access is reopened through the service controller; authentication URLs are never stored here.'}</p>
      </div>}
    </section>
  })}
    {direction && <div className="workspace-split-divider" role="separator" tabIndex={0} aria-label="Resize workspace panes" aria-orientation={direction === 'right' ? 'vertical' : 'horizontal'} aria-valuemin={20} aria-valuemax={80} aria-valuenow={Math.round(layout.ratio)} style={{ gridColumn: direction === 'right' ? 2 : 1, gridRow: direction === 'below' ? 2 : 1 }}
      onPointerDown={event => { if (event.button !== 0) return; drag.current = { id: event.pointerId, direction }; event.currentTarget.setPointerCapture(event.pointerId); setResizing(true); event.currentTarget.focus(); event.preventDefault() }}
      onPointerMove={event => { const origin = drag.current; const bounds = grid.current?.getBoundingClientRect(); if (!origin || origin.id !== event.pointerId || !bounds) return; const length = origin.direction === 'right' ? bounds.width : bounds.height; const offset = origin.direction === 'right' ? event.clientX - bounds.left : event.clientY - bounds.top; if (length > 0) setSplit(previous => resizeWorkspacePanes(previous, offset / length * 100)) }}
      onPointerUp={event => { if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId); releaseDivider() }} onPointerCancel={releaseDivider} onLostPointerCapture={releaseDivider}
      onDoubleClick={() => setSplit(previous => resizeWorkspacePanes(previous, 50))}
      onKeyDown={event => { const backward = direction === 'right' ? 'ArrowLeft' : 'ArrowUp'; const forward = direction === 'right' ? 'ArrowRight' : 'ArrowDown'; if (event.key === backward || event.key === forward || event.key === 'Home') { event.preventDefault(); setSplit(previous => resizeWorkspacePanes(previous, event.key === 'Home' ? 50 : previous.ratio + (event.key === forward ? 5 : -5))) } }} />}
    </div>
  </div>
}
