import { useMemo, useState } from 'react'
import { CodeFilePreview } from './DataFilePreview'
import { MarkdownPreview } from './MarkdownPreview'

function object(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}
function text(value: unknown): string {
  return (typeof value === 'string' ? value : Array.isArray(value) ? value.filter(item => typeof item === 'string').join('') : '').slice(0, 32768)
}
function clean(value: unknown) { return text(value).replace(/\x1b\[[0-?]*[ -/]*[@-~]/g, '') }

function savedImage(data: Record<string, unknown>): string | undefined {
  // Only raster data stored in the notebook is allowed. Never load a URL, SVG,
  // HTML, widget, attachment, or executable MIME representation.
  for (const mime of ['image/png', 'image/jpeg']) {
    const raw = data[mime]
    const encoded = (typeof raw === 'string' ? raw : Array.isArray(raw) ? raw.filter(item => typeof item === 'string').join('') : '').replace(/\s/g, '')
    if (!encoded || encoded.length > 1400000 || !/^[A-Za-z0-9+/]+={0,2}$/.test(encoded)) continue
    try {
      const bytes = atob(encoded)
      const valid = mime === 'image/png' ? bytes.startsWith('\x89PNG\r\n\x1a\n') : bytes.startsWith('\xff\xd8\xff')
      if (valid) return `data:${mime};base64,${encoded}`
    } catch { /* Invalid saved image remains inert. */ }
  }
  return undefined
}

function NotebookOutput({ value }: { value: unknown }) {
  const output = object(value); const data = object(output.data)
  const image = useMemo(() => savedImage(data), [value])
  const [imageFailed, setImageFailed] = useState(false)
  if (output.output_type === 'stream') return <pre className={output.name === 'stderr' ? 'notebook-output notebook-error' : 'notebook-output'}>{clean(output.text)}</pre>
  if (output.output_type === 'error') return <pre className="notebook-output notebook-error">{clean(output.traceback) || `${text(output.ename)}: ${text(output.evalue)}`}</pre>
  const plain = text(data['text/plain']); const markdown = text(data['text/markdown'])
  return <div className="notebook-saved-output">
    {image && !imageFailed && <img src={image} alt="Saved notebook output" onError={() => setImageFailed(true)} />}
    {imageFailed && <p role="status">The saved image could not be decoded.</p>}
    {plain ? <pre className="notebook-output">{clean(plain)}</pre> : markdown ? <MarkdownPreview text={markdown} /> : !image && <p className="workspace-view-caption">Unsupported rich output omitted. HTML, SVG, JavaScript, and widgets are never loaded.</p>}
    {data['text/latex'] !== undefined && <pre className="notebook-output" aria-label="Saved LaTeX output">{text(data['text/latex'])}</pre>}
  </div>
}

export function NotebookFilePreview({ text: source }: { text: string }) {
  const [outputsVisible, setOutputsVisible] = useState(true)
  const parsed = useMemo(() => {
    try {
      const notebook = object(JSON.parse(source))
      if (notebook.nbformat !== 4 || !Array.isArray(notebook.cells)) return { error: 'Only version 4 notebooks with a cells array are supported.', cells: [], language: '' }
      const metadata = object(notebook.metadata)
      return { error: '', cells: notebook.cells as unknown[], language: text(object(metadata.language_info).name) || 'code' }
    } catch { return { error: 'Notebook JSON is incomplete or invalid. Large notebooks may exceed the 128K-character file preview limit; use View source or Jupyter.', cells: [], language: '' } }
  }, [source])
  return <div className="notebook-preview" tabIndex={0} aria-label="Read-only notebook preview">
    <div className="notebook-toolbar"><strong>{parsed.cells.length} cells{parsed.language && ` / ${parsed.language}`}</strong><label><input type="checkbox" checked={outputsVisible} onChange={event => setOutputsVisible(event.target.checked)} /> Show saved outputs</label></div>
    <p className="workspace-view-caption">Read-only notebook / no kernel, cell execution, external resources, or active outputs. Markdown links and images remain inert.</p>
    {parsed.error && <p role="alert">{parsed.error}</p>}
    {parsed.cells.slice(0, 200).map((value, index) => {
      const cell = object(value); const kind = text(cell.cell_type); const source = text(cell.source)
      const outputs = Array.isArray(cell.outputs) ? cell.outputs : []
      return <section className={`notebook-cell ${kind === 'code' ? 'notebook-code-cell' : ''}`} key={index}>
        <header><strong>Cell {index + 1} / {kind || 'raw'}</strong>{kind === 'code' && <span>In [{typeof cell.execution_count === 'number' ? cell.execution_count : ' '}]: saved execution count</span>}</header>
        {kind === 'markdown' ? <MarkdownPreview text={source} /> : kind === 'code' ? <CodeFilePreview text={source} filename={`cell.${parsed.language}`} /> : <pre className="notebook-output">{source}</pre>}
        {kind === 'code' && outputsVisible && outputs.length > 0 && <div className="notebook-outputs" aria-label={`Saved outputs for cell ${index + 1}`}>{outputs.slice(0, 20).map((output, outputIndex) => <NotebookOutput value={output} key={outputIndex} />)}{outputs.length > 20 && <p>Additional saved outputs omitted.</p>}</div>}
      </section>
    })}
    {parsed.cells.length > 200 && <p>Showing the first 200 cells. View source or open Jupyter for the full notebook.</p>}
    <p className="workspace-view-caption">Up to 20 outputs per cell and 32K characters per text field are shown. Preview content and output visibility are not saved.</p>
  </div>
}
