import { useEffect, useRef, useState } from 'react'
import type { WorkspaceViewTab } from './useWorkspaceTabs'
import type { WorkspaceSplitState } from './workspaceSplit'

type SavedLayout = { id: string; name: string; direction: 'right' | 'below'; ratio: number; focused: 'primary' | 'secondary'; tabs: WorkspaceViewTab[] }
type Bridge = { postMessage: (message: unknown) => void; addEventListener: (name: 'message', handler: (event: MessageEvent) => void) => void; removeEventListener: (name: 'message', handler: (event: MessageEvent) => void) => void }
type Restored = { profileId: string; requestId: string; primaryId?: string; secondaryId?: string; error?: string }

export function NamedWorkspaceLayouts({ profileId, bridge, layout, tabs, onRestore }: { profileId: string; bridge: Bridge | null; layout: WorkspaceSplitState; tabs: WorkspaceViewTab[]; onRestore: (layout: WorkspaceSplitState) => void }) {
  const [saved, setSaved] = useState<SavedLayout[]>([]); const [selected, setSelected] = useState(''); const [name, setName] = useState('')
  const [pending, setPending] = useState(false); const [error, setError] = useState('')
  const current = useRef<{ id: string; operation: string; layout?: SavedLayout }>({ id: '', operation: '' })
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const latest = useRef(onRestore); latest.current = onRestore
  function begin(operation: string, restored?: SavedLayout) {
    clearTimeout(timer.current); current.current = { id: crypto.randomUUID(), operation, layout: restored }; setPending(true); setError('')
    timer.current = setTimeout(() => { current.current.id = ''; setPending(false); setError('Layout request timed out. Refresh layouts to retry.') }, 30000)
    return current.current.id
  }
  function request(action: 'layouts-load' | 'layouts-save' | 'layouts-delete', extra: Record<string, unknown> = {}) {
    if (!bridge) { setError('Named layouts require the DevShell desktop app.'); return }
    bridge.postMessage({ type: 'workspace.tabs', profileId, requestId: begin(action), action, ...extra })
  }
  useEffect(() => {
    setSaved([]); setSelected(''); setName(''); setPending(false); setError('')
    if (!bridge) return
    const receive = (event: MessageEvent) => {
      let message: { type?: string; profileId?: string; requestId?: string; layouts?: SavedLayout[]; savedId?: string; error?: string }
      try { message = typeof event.data === 'string' ? JSON.parse(event.data) : event.data } catch { return }
      if (message?.type !== 'workspace.layouts.result' || message.profileId !== profileId || !current.current.id || message.requestId !== current.current.id) return
      clearTimeout(timer.current); current.current.id = ''; setPending(false)
      if (message.error) { setError(message.error); return }
      if (message.layouts) setSaved(message.layouts)
      if (message.savedId) setSelected(message.savedId)
      if (current.current.operation === 'layouts-delete') { setSelected(''); setName('') }
    }
    const restored = (event: Event) => {
      const detail = (event as CustomEvent<Restored>).detail
      if (detail?.profileId !== profileId || !current.current.id || detail.requestId !== current.current.id) return
      const preset = current.current.layout
      clearTimeout(timer.current); current.current.id = ''; setPending(false)
      if (detail.error) { setError(detail.error); return }
      if (preset && detail.primaryId && detail.secondaryId) latest.current({ profileId, direction: preset.direction, ratio: preset.ratio, focused: preset.focused, primaryId: detail.primaryId, secondaryId: detail.secondaryId })
    }
    bridge.addEventListener('message', receive); window.addEventListener('devshell.workspace.layout-restored', restored)
    request('layouts-load')
    return () => { clearTimeout(timer.current); current.current.id = ''; bridge.removeEventListener('message', receive); window.removeEventListener('devshell.workspace.layout-restored', restored) }
  }, [bridge, profileId])
  function save() {
    const primary = tabs.find(tab => tab.id === layout.primaryId); const secondary = tabs.find(tab => tab.id === layout.secondaryId)
    if (!layout.direction || !primary || !secondary || !name.trim()) return
    const descriptors = [primary, secondary].map(tab => ({ id: tab.id, kind: tab.kind, projectId: tab.projectId, repositoryId: tab.repositoryId, filePath: tab.filePath, side: tab.side, page: tab.page, url: tab.url, servicePath: tab.servicePath }))
    request('layouts-save', { layout: { name: name.trim(), direction: layout.direction, ratio: layout.ratio, focused: layout.focused, tabs: descriptors } })
  }
  function restore() {
    const preset = saved.find(item => item.id === selected); if (!preset) return
    const requestId = begin('restore', preset)
    window.dispatchEvent(new CustomEvent('devshell.workspace.layout-restore', { detail: { profileId, requestId, tabs: preset.tabs, focused: preset.focused } }))
  }
  return <details className="named-workspace-layouts"><summary>Named layouts</summary><div className="named-layout-controls">
    <label>Layout name <input aria-label="Layout name" maxLength={48} value={name} placeholder="Code and build logs" onChange={event => setName(event.target.value)} /></label>
    <button disabled={pending || !layout.direction || !name.trim()} onClick={save}>Save layout</button>
    <label>Saved layout <select aria-label="Saved workspace layout" value={selected} disabled={pending} onChange={event => { setSelected(event.target.value); setName(saved.find(item => item.id === event.target.value)?.name ?? '') }}><option value="">Choose saved layout...</option>{saved.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
    <button disabled={pending || !selected} onClick={restore}>Restore layout</button><button disabled={pending || !selected} onClick={() => request('layouts-delete', { layoutId: selected })}>Delete layout</button><button disabled={pending} onClick={() => request('layouts-load')}>Refresh layouts</button>
  </div><p className="workspace-view-caption">Up to 12 named layouts per profile. Same-name saves replace that layout. Restore reuses open tabs or creates passive descriptors: no commands, file reads, browser navigation, or service starts. Existing previews stay open; new restored views require Refresh/Open.</p>{pending && <p role="status">Updating workspace layouts...</p>}{error && <p role="alert" className="check-error">{error}</p>}</details>
}
