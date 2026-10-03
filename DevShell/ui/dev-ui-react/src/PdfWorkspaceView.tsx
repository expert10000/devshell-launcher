import { useEffect, useRef, useState } from 'react'
import type { WorkspaceViewTab } from './useWorkspaceTabs'

type Bridge = { postMessage: (message: unknown) => void; addEventListener: (name: 'message', handler: (event: MessageEvent) => void) => void; removeEventListener: (name: 'message', handler: (event: MessageEvent) => void) => void }
type Job = { state: string; buildState: string; action?: string; logPath: string }

export function PdfWorkspaceView({ tab, profileId, bridge, directory, job, onPage }: { tab: WorkspaceViewTab; profileId: string; bridge: Bridge | null; directory?: string; job?: Job; onPage: (page: number) => void }) {
  const collection = !tab.filePath && !!directory
  const [files, setFiles] = useState<string[]>([]); const [selectedFile, setSelectedFile] = useState(tab.filePath ?? '')
  const [listed, setListed] = useState(false)
  const [page, setPage] = useState(String(tab.page ?? 1))
  const [pending, setPending] = useState(false); const [error, setError] = useState('')
  const [metadata, setMetadata] = useState<{ size: number; modified: string }>()
  const [status, setStatus] = useState(tab.restored ? 'Saved PDF entry. Refresh to load the current file list or Open PDF to view the saved document; nothing was rebuilt or reopened.' : collection ? 'Choose a volume or edition, then Open PDF.' : 'PDF opened in the native viewer pane.')
  const requestId = useRef(''); const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  // Do not replay a completed build merely because this tab was restored or mounted.
  const lastCompletedBuild = useRef(job?.state === 'succeeded' && job.action === 'build' ? job.logPath : '')
  useEffect(() => { setPage(String(tab.page ?? 1)) }, [tab.page])
  useEffect(() => {
    if (!bridge) return
    const receive = (event: MessageEvent) => {
      let message: { type?: string; profileId?: string; projectId?: string; repositoryId?: string; filePath?: string; requestId?: string; error?: string; action?: string; size?: number; modified?: string; files?: string[] }
      try { message = typeof event.data === 'string' ? JSON.parse(event.data) : event.data } catch { return }
      if (message?.profileId !== profileId || message.projectId !== tab.projectId || message.repositoryId !== tab.repositoryId) return
      if (message.type === 'workspace.pdf.error' && message.filePath === tab.filePath) { setError(message.error ?? 'PDF could not be displayed.'); return }
      if (message.type !== 'workspace.pdf.result') return
      const requested = !!requestId.current && message.requestId === requestId.current
      if (!requested && (message.requestId || message.filePath !== tab.filePath)) return
      if (requested) { clearTimeout(timer.current); requestId.current = ''; setPending(false) }
      if (message.error) { setError(message.error); return }
      setError('')
      if (message.action === 'list' && message.files) {
        setFiles(message.files); setListed(true)
        setSelectedFile(previous => message.files!.includes(previous) ? previous : message.files![0] ?? '')
        setStatus(message.files.length ? `${message.files.length} PDFs available. Choose a volume or edition, then Open PDF.` : 'No collected PDFs yet. Use Math > Build PDFs, then Refresh list.')
        return
      }
      if (message.size != null && message.modified) setMetadata({ size: message.size, modified: message.modified })
      setStatus(message.action === 'external' ? 'Opened in the external PDF application.' : 'PDF loaded / refreshed in the native viewer pane.')
    }
    bridge.addEventListener('message', receive)
    if (collection && !tab.restored) request('list')
    return () => { clearTimeout(timer.current); requestId.current = ''; bridge.removeEventListener('message', receive) }
  }, [bridge, profileId, tab.id, tab.filePath])
  useEffect(() => {
    if (!collection || !bridge || pending || job?.action !== 'build' || job.state !== 'succeeded' ||
        job.buildState !== 'succeeded' || !job.logPath || job.logPath === lastCompletedBuild.current) return
    lastCompletedBuild.current = job.logPath
    request('list')
  }, [collection, bridge, pending, job?.action, job?.state, job?.buildState, job?.logPath])
  function request(action: 'open' | 'refresh' | 'external' | 'list') {
    if (!bridge) { setError('PDF viewing requires the DevShell desktop app.'); return }
    const selectedPage = Number(page)
    if (!Number.isInteger(selectedPage) || selectedPage < 1 || selectedPage > 1000000) { setError('Enter a page between 1 and 1000000.'); return }
    const filePath = collection ? selectedFile : tab.filePath
    if (action !== 'list' && !filePath) { setError('Choose a PDF first. Build PDFs if the list is empty.'); return }
    clearTimeout(timer.current); requestId.current = crypto.randomUUID(); setPending(true); setError('')
    if (action !== 'external' && action !== 'list') onPage(selectedPage)
    timer.current = setTimeout(() => { requestId.current = ''; setPending(false); setError('PDF viewer timed out. Open or Refresh to retry.') }, 65000)
    bridge.postMessage({ type: 'workspace.pdf', profileId, projectId: tab.projectId, repositoryId: tab.repositoryId, filePath: action === 'list' ? undefined : filePath, page: selectedPage, action, requestId: requestId.current })
  }
  return <div className="workspace-pdf-entry">
    <div className="workspace-view-toolbar workspace-pdf-controls">
      {collection && <label>Volume / edition <select aria-label="PDF volume or edition" value={selectedFile} disabled={pending || !files.length} onChange={event => setSelectedFile(event.target.value)}><option value="">Select a PDF</option>{files.map(path => <option key={path} value={path}>{path.split('/').at(-1)}</option>)}</select></label>}
      {collection && <button disabled={pending} onClick={() => request('list')}>Refresh list</button>}
      <button disabled={pending || collection && !selectedFile} onClick={() => request('open')}>Open PDF</button>
      <label>Page <input type="number" min="1" max="1000000" aria-label="PDF page" value={page} onChange={event => setPage(event.target.value)} /></label>
      <button disabled={pending || collection && !selectedFile} onClick={() => request('open')}>Go to page</button>
      {!collection && <button disabled={pending} onClick={() => request('refresh')}>{pending ? 'Opening...' : 'Refresh PDF'}</button>}
      <button disabled={pending || collection && !selectedFile} onClick={() => request('external')}>Open externally</button>
    </div>
    <h3>{tab.filePath ?? `${directory} / PDF collection`}</h3><p role="status">{pending ? 'Reading PDF selection...' : status}</p>
    {collection && listed && !files.length && <p>Build PDFs compiles the canonical volumes and available editions using BUILD_ALL.ps1, including document QA. Nothing is built when this selector opens.</p>}
    {error && <p className="check-error" role="alert">{error}</p>}
    {metadata && <p className="workspace-view-caption">{(metadata.size / 1048576).toFixed(1)} MB / modified {new Date(metadata.modified).toLocaleString()}</p>}
    <div className="workspace-pdf-help"><h3>Document controls</h3><p>The PDF appears in the native pane beside this workspace. Its toolbar provides page navigation, zoom, and search. Use Show/hide browser to hide or reveal the pane.</p>
      <p>A successful managed build refreshes the currently visible PDF. The repository's Open PDF after successful build option opens the result even if no PDF is currently visible.</p>
      <p className="workspace-view-caption">Only the relative file path and the page set with Go to page are remembered. Scrolling inside the native viewer does not update the saved page. Restoring a tab does not read the document or run a build. Document links and downloads are blocked here; Open externally is the explicit alternative.</p>
    </div>
  </div>
}
