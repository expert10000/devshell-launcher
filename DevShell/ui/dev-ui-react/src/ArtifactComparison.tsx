import { useEffect, useMemo, useRef, useState } from 'react'
import { comparisonPair, compareTextLines, setComparisonPair } from './artifactComparisonState'
import type { ComparisonPair } from './artifactComparisonState'
import type { FileReference } from './WorkspaceFileNavigation'
import { CodeFilePreview, JsonFilePreview, TableFilePreview } from './DataFilePreview'
import { ImageFilePreview } from './ImageFilePreview'

type Bridge = { postMessage: (message: unknown) => void; addEventListener: (name: 'message', handler: (event: MessageEvent) => void) => void; removeEventListener: (name: 'message', handler: (event: MessageEvent) => void) => void }
type Side = { file?: FileReference; text?: string; truncated?: boolean; image?: { path: string; mimeType: string; dataUrl: string; size: number }; error?: string; pending?: boolean }
const empty = { left: {} as Side, right: {} as Side }
export function ArtifactComparison({ profileId, bridge }: { profileId: string; bridge: Bridge | null }) {
  const [pair, setPair] = useState<ComparisonPair>(() => comparisonPair(profileId)); const [open, setOpen] = useState(false)
  const [sides, setSides] = useState(empty); const current = useRef(new Map<string, 'left' | 'right'>())
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const pending = !!sides.left.pending || !!sides.right.pending
  useEffect(() => {
    setPair(comparisonPair(profileId)); setOpen(false); setSides(empty)
    const selected = (event: Event) => {
      if ((event as CustomEvent<{ profileId: string }>).detail?.profileId !== profileId) return
      clearTimeout(timer.current); current.current.clear(); setPair(comparisonPair(profileId)); setSides(empty); setOpen(true)
    }
    const receive = (event: MessageEvent) => {
      let message: { type?: string; profileId?: string; requestId?: string; error?: string; preview?: { text: string; truncated: boolean }; image?: Side['image'] }
      try { message = typeof event.data === 'string' ? JSON.parse(event.data) : event.data } catch { return }
      const side = message.requestId ? current.current.get(message.requestId) : undefined
      if (!side || message.type !== 'workspace.files.result' || message.profileId !== profileId) return
      current.current.delete(message.requestId!)
      if (!current.current.size) clearTimeout(timer.current)
      setSides(previous => ({ ...previous, [side]: { ...previous[side], pending: false, error: message.error, text: message.preview?.text, truncated: message.preview?.truncated, image: message.image } }))
    }
    window.addEventListener('devshell.workspace.comparison', selected); bridge?.addEventListener('message', receive)
    return () => { clearTimeout(timer.current); current.current.clear(); window.removeEventListener('devshell.workspace.comparison', selected); bridge?.removeEventListener('message', receive) }
  }, [profileId, bridge])
  const difference = useMemo(() => sides.left.text !== undefined && sides.right.text !== undefined ? compareTextLines(sides.left.text, sides.right.text) : undefined, [sides.left.text, sides.right.text])
  function compare() {
    if (!bridge || !pair.left || !pair.right) return
    clearTimeout(timer.current); current.current.clear()
    setSides({ left: { file: pair.left, pending: true }, right: { file: pair.right, pending: true } })
    for (const side of ['left', 'right'] as const) {
      const file = pair[side]!; const requestId = crypto.randomUUID(); current.current.set(requestId, side)
      bridge.postMessage({ type: 'workspace.files', profileId, projectId: file.projectId, repositoryId: file.repositoryId, requestId, action: file.kind === 'image' ? 'image' : 'preview', path: file.path })
    }
    timer.current = setTimeout(() => { current.current.clear(); setSides(previous => ({ left: previous.left.pending ? { ...previous.left, pending: false, error: 'Comparison read timed out.' } : previous.left, right: previous.right.pending ? { ...previous.right, pending: false, error: 'Comparison read timed out.' } : previous.right })) }, 30000)
  }
  function render(side: 'left' | 'right') {
    const value = sides[side]
    return <section className="artifact-comparison-side" aria-label={`Comparison ${side === 'left' ? 'A' : 'B'}`}><h3>{side === 'left' ? 'A' : 'B'} / {value.file?.path ?? pair[side]?.path ?? 'Choose an artifact'}</h3>
      {value.pending && <p role="status">Reading comparison artifact...</p>}{value.error && <p role="alert" className="check-error">{value.error}</p>}
      {value.image && <ImageFilePreview key={`${side}:${value.image.path}`} image={value.image} paths={[value.image.path]} onSelect={() => {}} onError={() => setSides(previous => ({ ...previous, [side]: { ...previous[side], image: undefined, error: 'Comparison image could not be decoded.' } }))} />}
      {value.text !== undefined && (/\.(csv|tsv)$/i.test(value.file?.path ?? '') ? <TableFilePreview key={value.file?.path} text={value.text} delimiter={/\.tsv$/i.test(value.file?.path ?? '') ? '\t' : ','} /> : /\.json$/i.test(value.file?.path ?? '') ? <JsonFilePreview key={value.file?.path} text={value.text} notebook={false} /> : <CodeFilePreview text={value.text} filename={value.file?.path ?? 'report.txt'} />)}
      {value.truncated && <p className="workspace-view-caption">File preview truncated at 128K characters.</p>}
      {!value.file && <p>Select Compare as A/B on a file, then click Compare artifacts. No file is read by assigning it.</p>}
    </section>
  }
  return <details className="artifact-comparison" open={open} onToggle={event => setOpen(event.currentTarget.open)}><summary>Artifact comparison</summary><div className="artifact-comparison-controls"><span>A: {pair.left?.path ?? 'not selected'}</span><span>B: {pair.right?.path ?? 'not selected'}</span><button disabled={pending || !bridge || !pair.left || !pair.right} onClick={compare}>Compare artifacts</button><button disabled={pending || !pair.left && !pair.right} onClick={() => setComparisonPair(profileId, { left: pair.right, right: pair.left })}>Swap A/B</button><button onClick={() => setComparisonPair(profileId, {})}>Clear comparison</button></div>
    <div className="artifact-comparison-grid">{render('left')}{render('right')}</div>
    {difference && <details className="artifact-comparison-diff"><summary>Line-position differences / {difference.changed} changed positions</summary><p>Compared {difference.linesCompared} line positions; this is not an aligned Git diff.</p><div className="artifact-comparison-diff-scroll"><table><thead><tr><th>Line</th><th>A</th><th>B</th></tr></thead><tbody>{difference.rows.map(row => <tr key={row.line}><th>{row.line}</th><td><pre>{row.left ?? '(no line)'}</pre></td><td><pre>{row.right ?? '(no line)'}</pre></td></tr>)}</tbody></table></div>{difference.truncated && <p>Showing up to 100 changed positions from the first 5000 lines.</p>}</details>}
    <p className="workspace-view-caption">Read-only PNG/JPEG/GIF/WebP and text/report comparison. Each image has independent zoom/pan. PDF comparison remains in the native viewer. Selections and contents are session-only, not restored or saved.</p>
  </details>
}
