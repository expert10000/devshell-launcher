import { useEffect, useRef, useState } from 'react'

export type WorkspaceViewTab = {
  id: string; kind: 'logs' | 'diff' | 'browser' | 'jupyter' | 'pdf'; projectId?: string; repositoryId?: string;
  filePath?: string; side?: 'working' | 'staged'; url?: string; servicePath?: string; page?: number; restored?: boolean
}
export type WorkspaceTabInput = Omit<WorkspaceViewTab, 'id' | 'restored'>
type Bridge = { postMessage: (data: unknown) => void; addEventListener: (name: 'message', handler: (event: MessageEvent) => void) => void; removeEventListener: (name: 'message', handler: (event: MessageEvent) => void) => void }
type State = { profileId: string | null; ready: boolean; tabs: WorkspaceViewTab[]; activeId: string | null; error: string }

function identity(tab: WorkspaceTabInput) {
  if (tab.kind === 'pdf') return `pdf:${tab.projectId}:${tab.repositoryId}:${tab.filePath}`
  return tab.kind === 'browser' ? `browser:${tab.url}` : tab.kind === 'jupyter' ? `jupyter:${tab.projectId}:${tab.servicePath ?? ''}` : `${tab.kind}:${tab.projectId}:${tab.repositoryId}`
}

function cleanUrl(value?: string) {
  try { const url = new URL(value ?? ''); if (!['http:', 'https:'].includes(url.protocol)) return undefined; url.username = ''; url.password = ''; url.search = ''; url.hash = ''; return url.href } catch { return undefined }
}

export function useWorkspaceTabs(profileId: string | null, bridge: Bridge | null, onActivate: (tab: WorkspaceViewTab) => void) {
  const [state, setState] = useState<State>({ profileId: null, ready: false, tabs: [], activeId: null, error: '' })
  const current = useRef(state)
  const activation = useRef(onActivate)
  activation.current = onActivate
  function commit(next: State) {
    current.current = next; setState(next)
    if (next.ready && next.profileId === profileId) bridge?.postMessage({ type: 'workspace.tabs', action: 'save', profileId,
      state: { version: 1, activeId: next.activeId, tabs: next.tabs.map(tab => ({ id: tab.id, kind: tab.kind, projectId: tab.projectId, repositoryId: tab.repositoryId,
        filePath: tab.filePath, side: tab.side, url: cleanUrl(tab.url), servicePath: tab.servicePath, page: tab.page })) } })
  }
  function open(input: WorkspaceTabInput) {
    const previous = current.current
    if (!profileId || previous.profileId !== profileId || !previous.ready) return
    const safe = { ...input, url: input.kind === 'browser' ? cleanUrl(input.url) : undefined }
    if (safe.kind === 'browser' && !safe.url) return
    const existing = previous.tabs.find(tab => identity(tab) === identity(safe))
    if (!existing && previous.tabs.length >= 24) { commit({ ...previous, error: 'Close a workspace tab before opening another (limit: 24).' }); return }
    const tab: WorkspaceViewTab = existing ? { ...existing, ...safe, restored: false } : { ...safe, id: crypto.randomUUID(), restored: false }
    commit({ ...previous, error: '', activeId: tab.id, tabs: existing ? previous.tabs.map(item => item.id === tab.id ? tab : item) : [...previous.tabs, tab] })
    activation.current(tab)
  }
  const opener = useRef(open)
  opener.current = open

  useEffect(() => {
    const empty: State = { profileId, ready: false, tabs: [], activeId: null, error: '' }
    current.current = empty; setState(empty)
    if (!bridge || !profileId) return
    const requestId = crypto.randomUUID()
    let loaded = false
    const queued: WorkspaceTabInput[] = []
    const receive = (event: MessageEvent) => {
      let message: { type?: string; profileId?: string; requestId?: string; message?: string; state?: { version?: number; tabs?: WorkspaceViewTab[]; activeId?: string }; kind?: WorkspaceViewTab['kind']; projectId?: string; repositoryId?: string; url?: string; servicePath?: string; filePath?: string; page?: number }
      try { message = typeof event.data === 'string' ? JSON.parse(event.data) : event.data } catch { return }
      if (message?.profileId !== profileId) return
      if (message.type === 'workspace.tabs.loaded' && message.requestId === requestId && !loaded) {
        loaded = true
        const tabs = (message.state?.tabs ?? []).map(tab => ({ ...tab, restored: true }))
        const activeId = tabs.some(tab => tab.id === message.state?.activeId) ? message.state?.activeId ?? null : null
        const next: State = { profileId, ready: true, tabs, activeId, error: '' }; current.current = next; setState(next)
        const active = tabs.find(tab => tab.id === activeId); if (active) activation.current(active)
        for (const tab of queued) opener.current(tab)
      }
      if (message.type === 'workspace.tabs.error') setState(previous => ({ ...previous, error: message.message ?? 'Could not save workspace tabs.' }))
      if (message.type === 'workspace.pdf.opened') {
        const tab: WorkspaceTabInput = { kind: 'pdf', projectId: message.projectId, repositoryId: message.repositoryId, filePath: message.filePath, page: message.page ?? 1 }
        if (loaded) opener.current(tab); else queued.push(tab)
      }
      if (message.type === 'workspace.browser.opened' && (message.kind === 'browser' || message.kind === 'jupyter')) {
        const tab: WorkspaceTabInput = { kind: message.kind, projectId: message.projectId ?? undefined, repositoryId: message.repositoryId ?? undefined,
          url: message.url ?? undefined, servicePath: message.servicePath ?? undefined }
        if (loaded) opener.current(tab); else queued.push(tab)
      }
    }
    const externalOpen = (event: Event) => {
      const detail = (event as CustomEvent<WorkspaceTabInput & { profileId: string }>).detail
      if (detail?.profileId === profileId) { if (loaded) opener.current(detail); else queued.push(detail) }
    }
    bridge.addEventListener('message', receive); window.addEventListener('devshell.workspace.open', externalOpen)
    bridge.postMessage({ type: 'workspace.tabs', profileId, requestId, action: 'load' })
    return () => { bridge.removeEventListener('message', receive); window.removeEventListener('devshell.workspace.open', externalOpen) }
  }, [profileId, bridge])

  function select(id: string) {
    if (current.current.profileId !== profileId) return
    const tab = current.current.tabs.find(item => item.id === id); if (!tab) return
    commit({ ...current.current, activeId: id }); activation.current(tab)
  }
  function clearActive() {
    if (current.current.profileId === profileId && current.current.activeId) commit({ ...current.current, activeId: null })
  }
  function close(id: string) {
    if (current.current.profileId !== profileId) return
    const previous = current.current; const tabs = previous.tabs.filter(tab => tab.id !== id)
    const activeId = previous.activeId === id ? tabs.at(-1)?.id ?? null : previous.activeId
    commit({ ...previous, tabs, activeId }); const active = tabs.find(tab => tab.id === activeId); if (active) activation.current(active)
  }
  function update(id: string, changes: Pick<WorkspaceViewTab, 'filePath' | 'side' | 'page'>) {
    if (current.current.profileId === profileId) commit({ ...current.current, tabs: current.current.tabs.map(tab => tab.id === id ? { ...tab, ...changes } : tab) })
  }
  return { tabs: state.profileId === profileId ? state.tabs : [], activeId: state.profileId === profileId ? state.activeId : null,
    ready: state.profileId === profileId && state.ready, error: state.profileId === profileId ? state.error : '', open, select, clearActive, close, update }
}
