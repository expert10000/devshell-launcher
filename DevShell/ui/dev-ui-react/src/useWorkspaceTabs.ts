import { useEffect, useRef, useState } from 'react'

export type WorkspaceViewTab = {
  id: string; kind: 'logs' | 'diff' | 'browser' | 'jupyter' | 'pdf' | 'files'; projectId?: string; repositoryId?: string;
  filePath?: string; side?: 'working' | 'staged'; url?: string; servicePath?: string; page?: number; restored?: boolean; activationId?: string; revealPath?: string; sourceLine?: number
}
export type WorkspaceTabInput = Omit<WorkspaceViewTab, 'id' | 'restored' | 'activationId'>
type Bridge = { postMessage: (data: unknown) => void; addEventListener: (name: 'message', handler: (event: MessageEvent) => void) => void; removeEventListener: (name: 'message', handler: (event: MessageEvent) => void) => void }
type State = { profileId: string | null; ready: boolean; tabs: WorkspaceViewTab[]; activeId: string | null; error: string }

function identity(tab: WorkspaceTabInput) {
  if (tab.kind === 'pdf') return `pdf:${tab.projectId}:${tab.repositoryId}:${tab.filePath ?? ''}`
  return tab.kind === 'browser' ? `browser:${tab.url}` : tab.kind === 'jupyter' ? `jupyter:${tab.projectId}:${tab.servicePath ?? ''}` : `${tab.kind}:${tab.projectId}:${tab.repositoryId}`
}

function cleanUrl(value?: string) {
  try { const url = new URL(value ?? ''); if (!['http:', 'https:'].includes(url.protocol)) return undefined; url.username = ''; url.password = ''; url.search = ''; url.hash = ''; return url.href } catch { return undefined }
}

export function useWorkspaceTabs(profileId: string | null, bridge: Bridge | null, onActivate: (tab: WorkspaceViewTab) => void) {
  const [state, setState] = useState<State>({ profileId: null, ready: false, tabs: [], activeId: null, error: '' })
  const current = useRef(state)
  const returnTargets = useRef(new Map<string, string>())
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
    const safe = { ...input, url: input.kind === 'browser' ? cleanUrl(input.url) : undefined, activationId: input.kind === 'files' ? crypto.randomUUID() : undefined, revealPath: input.kind === 'files' ? input.revealPath : undefined,
      sourceLine: input.kind === 'files' && typeof input.sourceLine === 'number' && Number.isFinite(input.sourceLine) ? Math.min(1000000, Math.max(1, Math.floor(input.sourceLine))) : undefined }
    if (safe.kind === 'browser' && !safe.url) return
    const existing = previous.tabs.find(tab => identity(tab) === identity(safe))
    if (!existing && previous.tabs.length >= 24) { commit({ ...previous, error: 'Close a workspace tab before opening another (limit: 24).' }); return }
    const tab: WorkspaceViewTab = existing ? { ...existing, ...safe, restored: false } : { ...safe, id: crypto.randomUUID(), restored: false }
    const source = previous.tabs.find(item => item.id === previous.activeId)
    if (tab.kind === 'pdf' && source && source.id !== tab.id && (source.kind === 'files' || source.kind === 'pdf')) {
      returnTargets.current.set(tab.id, source.id)
      // Reopening a selector from its document must not create a Back cycle.
      if (returnTargets.current.get(source.id) === tab.id) returnTargets.current.delete(source.id)
    }
    commit({ ...previous, error: '', activeId: tab.id, tabs: existing ? previous.tabs.map(item => item.id === tab.id ? tab : item) : [...previous.tabs, tab] })
    activation.current(tab)
  }
  const opener = useRef(open)
  opener.current = open

  useEffect(() => {
    returnTargets.current.clear()
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
      if (message.type === 'workspace.files.opened') {
        const tab: WorkspaceTabInput = { kind: 'files', projectId: message.projectId, repositoryId: message.repositoryId, filePath: message.filePath }
        if (loaded) opener.current(tab); else queued.push(tab)
      }
      if (message.type === 'workspace.pdf.opened') {
        if (message.filePath) bridge.postMessage({ type: 'workspace.files', profileId, projectId: message.projectId, repositoryId: message.repositoryId, action: 'remember-pdf', path: message.filePath, requestId: crypto.randomUUID() })
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
    const externalSelect = (event: Event) => {
      const detail = (event as CustomEvent<{ profileId: string; id: string }>).detail
      if (loaded && detail?.profileId === profileId) select(detail.id)
    }
    const restoreLayout = (event: Event) => {
      const detail = (event as CustomEvent<{ profileId: string; requestId: string; tabs: WorkspaceTabInput[]; focused?: string }>).detail
      if (!loaded || detail?.profileId !== profileId) return
      const previous = current.current
      if (!Array.isArray(detail.tabs) || detail.tabs.length !== 2) return
      const next = [...previous.tabs]; const restored: WorkspaceViewTab[] = []
      for (const input of detail.tabs) {
        const existing = next.find(tab => identity(tab) === identity(input))
        const tab: WorkspaceViewTab = existing ? { ...existing, activationId: undefined, revealPath: undefined, sourceLine: undefined } : {
          id: crypto.randomUUID(), kind: input.kind, projectId: input.projectId, repositoryId: input.repositoryId, filePath: input.filePath,
          side: input.side, page: input.page, url: cleanUrl(input.url), servicePath: input.servicePath, restored: true,
        }
        if (existing) next[next.findIndex(item => item.id === tab.id)] = tab
        else next.push(tab)
        restored.push(tab)
      }
      if (next.length > 24 || restored[0].id === restored[1].id) {
        window.dispatchEvent(new CustomEvent('devshell.workspace.layout-restored', { detail: { profileId, requestId: detail.requestId, error: 'Close some workspace tabs before restoring this layout (limit: 24), and use two distinct views.' } }))
        return
      }
      const focused = restored[detail.focused === 'secondary' ? 1 : 0]
      commit({ ...previous, tabs: next, activeId: focused.id, error: '' }); activation.current(focused)
      window.dispatchEvent(new CustomEvent('devshell.workspace.layout-restored', { detail: { profileId, requestId: detail.requestId, primaryId: restored[0].id, secondaryId: restored[1].id } }))
    }
    bridge.addEventListener('message', receive); window.addEventListener('devshell.workspace.open', externalOpen); window.addEventListener('devshell.workspace.select', externalSelect); window.addEventListener('devshell.workspace.layout-restore', restoreLayout)
    bridge.postMessage({ type: 'workspace.tabs', profileId, requestId, action: 'load' })
    return () => { bridge.removeEventListener('message', receive); window.removeEventListener('devshell.workspace.open', externalOpen); window.removeEventListener('devshell.workspace.select', externalSelect); window.removeEventListener('devshell.workspace.layout-restore', restoreLayout) }
  }, [profileId, bridge])

  function select(id: string) {
    if (current.current.profileId !== profileId) return
    const tab = current.current.tabs.find(item => item.id === id); if (!tab) return
    const selected = tab.kind === 'files' ? { ...tab, restored: false, activationId: crypto.randomUUID(), revealPath: undefined, sourceLine: undefined } : tab
    commit({ ...current.current, activeId: id, tabs: current.current.tabs.map(item => item.id === id ? selected : item) }); activation.current(selected)
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
  const backTargetId = state.activeId ? returnTargets.current.get(state.activeId) : undefined
  const backTarget = state.profileId === profileId ? state.tabs.find(tab => tab.id === backTargetId) : undefined
  function back() {
    const targetId = current.current.activeId ? returnTargets.current.get(current.current.activeId) : undefined
    if (targetId) select(targetId)
  }
  return { tabs: state.profileId === profileId ? state.tabs : [], activeId: state.profileId === profileId ? state.activeId : null,
    ready: state.profileId === profileId && state.ready, error: state.profileId === profileId ? state.error : '', open, select, clearActive, close, update, back, backTarget }
}
