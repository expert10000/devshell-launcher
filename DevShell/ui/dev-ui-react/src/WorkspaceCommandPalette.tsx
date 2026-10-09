import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import type { WorkspaceViewTab } from './useWorkspaceTabs'
import type { FileReference } from './WorkspaceFileNavigation'

type Project = { id: string; name: string; repositories?: { id: string; name: string; buildTask?: string; runTask?: string; url?: string }[] }
type Bridge = { postMessage: (message: unknown) => void; addEventListener: (name: 'message', handler: (event: MessageEvent) => void) => void; removeEventListener: (name: 'message', handler: (event: MessageEvent) => void) => void }
type Command = { id: string; label: string; detail: string; run: () => void; task?: { projectId: string; repositoryId: string; action: 'build' | 'run' }; blocked?: boolean }
type Hit = { repositoryId: string; repositoryName: string; entry: { name: string; path: string; kind: string } }
export function WorkspaceCommandPalette({ profileId, bridge, projects, tabs, activeId, busyKeys }: { profileId: string; bridge: Bridge | null; projects: Project[]; tabs: WorkspaceViewTab[]; activeId: string | null; busyKeys: Set<string> }) {
  const [open, setOpen] = useState(false); const [query, setQuery] = useState(''); const [highlight, setHighlight] = useState(0)
  const [projectId, setProjectId] = useState(projects[0]?.id ?? ''); const [hits, setHits] = useState<Hit[]>([])
  const [layouts, setLayouts] = useState<{ id: string; name: string }[]>([]); const [files, setFiles] = useState<FileReference[]>([])
  const [confirmation, setConfirmation] = useState<Command>(); const [pending, setPending] = useState(false); const [error, setError] = useState('')
  const dialog = useRef<HTMLDialogElement>(null); const input = useRef<HTMLInputElement>(null); const previousFocus = useRef<HTMLElement | null>(null)
  const requests = useRef(new Map<string, { kind: 'layouts' | 'navigation' | 'search'; projectId?: string }>()); const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  function close() { setOpen(false); setConfirmation(undefined); setQuery(''); setHits([]); setError(''); requests.current.clear(); clearTimeout(timer.current); setPending(false) }
  function show() {
    previousFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    setProjectId(tabs.find(tab => tab.id === activeId)?.projectId ?? projects[0]?.id ?? ''); setOpen(true); setQuery(''); setHits([]); setConfirmation(undefined); setHighlight(0)
    if (!bridge) return
    for (const kind of ['layouts', 'navigation'] as const) {
      const requestId = crypto.randomUUID(); requests.current.set(requestId, { kind })
      bridge.postMessage(kind === 'layouts' ? { type: 'workspace.tabs', profileId, requestId, action: 'layouts-load' } : { type: 'workspace.files', profileId, projectId: projects[0]?.id, requestId, action: 'navigation', operation: 'load' })
    }
  }
  useEffect(() => {
    if (open && !dialog.current?.open) { dialog.current?.showModal(); input.current?.focus() }
    else if (!open && dialog.current?.open) { dialog.current.close(); if (previousFocus.current?.isConnected) previousFocus.current.focus() }
  }, [open])
  const showRef = useRef(show); showRef.current = show
  useEffect(() => {
    close(); setLayouts([]); setFiles([])
    const keyboard = (event: KeyboardEvent) => { if (event.ctrlKey && event.altKey && event.key.toLowerCase() === 'p') { event.preventDefault(); showRef.current() } }
    const receive = (event: MessageEvent) => {
      let message: { type?: string; profileId?: string; requestId?: string; layouts?: { id: string; name: string }[]; navigation?: { pinned: FileReference[]; recent: FileReference[] }; search?: { entries: Hit[]; truncated: boolean }; error?: string }
      try { message = typeof event.data === 'string' ? JSON.parse(event.data) : event.data } catch { return }
      if (message?.profileId !== profileId || !message.requestId) return
      const request = requests.current.get(message.requestId); if (!request) return
      requests.current.delete(message.requestId)
      if (request.kind === 'search') { clearTimeout(timer.current); setPending(false) }
      if (message.error) { setError(message.error); return }
      if (message.layouts) setLayouts(message.layouts)
      if (message.navigation) {
        const unique = new Map<string, FileReference>(); for (const file of [...message.navigation.pinned, ...message.navigation.recent]) unique.set(`${file.projectId}:${file.repositoryId}:${file.path}`, file)
        setFiles([...unique.values()])
      }
      if (message.search && request.projectId) { setHits(message.search.entries); setError(message.search.truncated ? 'File search is partial: scan limits reached.' : ''); setHighlight(0) }
    }
    window.addEventListener('keydown', keyboard); bridge?.addEventListener('message', receive)
    return () => { clearTimeout(timer.current); requests.current.clear(); window.removeEventListener('keydown', keyboard); bridge?.removeEventListener('message', receive) }
  }, [profileId, bridge])
  function openFile(file: FileReference) {
    if (file.kind === 'pdf') {
      window.dispatchEvent(new CustomEvent('devshell.workspace.open', { detail: { profileId, kind: 'pdf', projectId: file.projectId, repositoryId: file.repositoryId, filePath: file.path, page: 1 } }))
      bridge?.postMessage({ type: 'workspace.pdf', profileId, projectId: file.projectId, repositoryId: file.repositoryId, action: 'open', filePath: file.path, page: 1 })
    } else window.dispatchEvent(new CustomEvent('devshell.workspace.open', { detail: { profileId, kind: 'files', projectId: file.projectId, repositoryId: file.repositoryId, filePath: file.path.split('/').slice(0, -1).join('/'), revealPath: file.path } }))
  }
  const commands = useMemo(() => {
    const items: Command[] = []
    for (const tab of tabs) items.push({ id: `tab:${tab.id}`, label: `Focus ${tab.kind} tab`, detail: `${projects.find(project => project.id === tab.projectId)?.name ?? ''} / ${projects.flatMap(project => project.repositories ?? []).find(repo => repo.id === tab.repositoryId)?.name ?? tab.url ?? tab.filePath ?? ''}`, run: () => window.dispatchEvent(new CustomEvent('devshell.workspace.select', { detail: { profileId, id: tab.id } })) })
    for (const project of projects) for (const repo of project.repositories ?? []) {
      for (const kind of ['files', 'logs', 'diff'] as const) items.push({ id: `${project.id}:${repo.id}:${kind}`, label: `Open ${repo.name} ${kind}`, detail: project.name, run: () => window.dispatchEvent(new CustomEvent('devshell.workspace.open', { detail: { profileId, kind, projectId: project.id, repositoryId: repo.id } })) })
      for (const action of ['build', 'run'] as const) if (action === 'build' ? repo.buildTask : repo.runTask) items.push({ id: `task:${project.id}:${repo.id}:${action}`, label: `${action === 'build' ? 'Build' : 'Run'} ${repo.name}`, detail: `${project.name} / ${action === 'build' ? repo.buildTask : repo.runTask}`, run: () => {}, task: { projectId: project.id, repositoryId: repo.id, action }, blocked: busyKeys.has(`${profileId}:${project.id}:${repo.id}`) })
    }
    for (const file of files) items.push({ id: `file:${file.projectId}:${file.repositoryId}:${file.path}`, label: `Open ${file.path.split('/').at(-1)}`, detail: `${file.repositoryName ?? file.repositoryId} / ${file.path}`, run: () => openFile(file) })
    for (const layout of layouts) items.push({ id: `layout:${layout.id}`, label: `Restore layout ${layout.name}`, detail: 'Passive pane arrangement; no commands replayed', run: () => window.dispatchEvent(new CustomEvent('devshell.workspace.named-layout', { detail: { profileId, layoutId: layout.id } })) })
    for (const hit of hits) items.push({ id: `search:${hit.repositoryId}:${hit.entry.path}`, label: `Open ${hit.entry.name}`, detail: `${hit.repositoryName} / ${hit.entry.path}`, run: () => openFile({ projectId, repositoryId: hit.repositoryId, path: hit.entry.path, kind: hit.entry.kind === 'pdf' ? 'pdf' : hit.entry.kind === 'image' ? 'image' : hit.entry.kind === 'code' ? 'code' : 'text' }) })
    const words = query.trim().toLowerCase().split(/\s+/).filter(Boolean)
    return items.filter(item => words.every(word => `${item.label} ${item.detail}`.toLowerCase().includes(word))).slice(0, 60)
  }, [tabs, projects, profileId, files, layouts, hits, projectId, query, busyKeys])
  useEffect(() => setHighlight(0), [query, projectId])
  function choose(command?: Command) {
    if (!command || command.blocked) return
    if (command.task) { setConfirmation(command); return }
    close(); command.run()
  }
  function search() {
    if (!bridge || !projectId || query.trim().length < 2 || pending) return
    for (const [id, request] of requests.current) if (request.kind === 'search') requests.current.delete(id)
    const requestId = crypto.randomUUID(); requests.current.set(requestId, { kind: 'search', projectId }); setPending(true); setError(''); setHits([])
    bridge.postMessage({ type: 'workspace.files', profileId, projectId, requestId, action: 'search', query: query.trim().slice(0, 160) })
    clearTimeout(timer.current); timer.current = setTimeout(() => { requests.current.delete(requestId); setPending(false); setError('File search timed out.') }, 30000)
  }
  return <><button className="workspace-palette-button" onClick={show} title="Workspace palette (Ctrl+Alt+P)">Workspace palette</button>{createPortal(<dialog ref={dialog} className="workspace-command-dialog" aria-label="Workspace command palette" onCancel={event => { event.preventDefault(); close() }} onClose={() => setOpen(false)}>
    <header><strong>Workspace palette</strong><span>Ctrl+Alt+P</span><button onClick={close}>Close palette</button></header>
    {confirmation ? <section className="workspace-task-confirmation"><h3>{confirmation.label}</h3><p>{confirmation.detail}</p><p>This explicitly starts a managed repository task. It is not run by searching or restoring a layout.</p><button disabled={!bridge || !!confirmation.blocked || busyKeys.has(`${profileId}:${confirmation.task?.projectId}:${confirmation.task?.repositoryId}`)} onClick={() => { const task = confirmation.task!; close(); bridge?.postMessage({ type: 'repository.job', projectId: task.projectId, repositoryId: task.repositoryId, action: task.action }) }}>Run task</button><button onClick={() => { setConfirmation(undefined); input.current?.focus() }}>Cancel task</button></section> : <>
      <input ref={input} className="workspace-command-query" aria-label="Workspace command search" role="combobox" aria-expanded={open} aria-controls="workspace-command-options" aria-activedescendant={commands[highlight] ? `workspace-command-${highlight}` : undefined} value={query} placeholder="Repository, file, task, or saved layout..." onChange={event => { setQuery(event.target.value); setHits([]) }} onKeyDown={event => { if (event.key === 'ArrowDown' || event.key === 'ArrowUp') { event.preventDefault(); setHighlight(previous => commands.length ? (previous + (event.key === 'ArrowDown' ? 1 : -1) + commands.length) % commands.length : 0) } else if (event.key === 'Enter') { event.preventDefault(); choose(commands[highlight]) } }} />
      <div className="workspace-command-file-search"><label>Search project <select aria-label="Palette search project" value={projectId} onChange={event => { setProjectId(event.target.value); setHits([]) }}>{projects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label><button disabled={pending || query.trim().length < 2} onClick={search}>Search filenames</button></div>
      <div id="workspace-command-options" className="workspace-command-results" role="listbox" aria-label="Workspace commands">{commands.map((command, index) => <button id={`workspace-command-${index}`} role="option" aria-selected={highlight === index} disabled={command.blocked} className={highlight === index ? 'selected' : ''} key={command.id} onMouseMove={() => setHighlight(index)} onClick={() => choose(command)}><strong>{command.label}</strong><small>{command.detail}{command.blocked ? ' / checkout busy' : ''}</small></button>)}</div>{!commands.length && <p>No matching command. Use Search filenames to scan the selected project's repositories.</p>}
    </>}{pending && <p role="status">Searching filenames...</p>}{error && <p role="status">{error}</p>}<p className="workspace-view-caption">Arrow keys + Enter to select / Escape to close. Queries and results are not saved. Managed Build/Run tasks require confirmation.</p>
  </dialog>, document.body)}</>
}
