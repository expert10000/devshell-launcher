import { useEffect, useRef, useState } from 'react'
import type { RuntimeProfile } from './scientificRuntimeProfiles'
import type { ScientificDataset } from './useScientificRuntime'
import type { useScientificRuntime } from './useScientificRuntime'
import { ScientificArtifacts } from './ScientificArtifacts'
import { MeshCanvas } from './ScientificMeshViewer'
import { initialCamera } from './scientificCamera'
import operationCatalog from '../../../../schemas/scientific-workbench-operations.v1.json'
import './ScientificMeshWorkbench.css'

type Field = { id: string; label: string; kind: 'number' | 'boolean'; value: number | boolean; min?: number; max?: number; step?: number; integer?: boolean }
type Operation = { id: string; label: string; provider: 'cgal' | 'vtk'; description: string; inputExtensions: string[]; inputNote: string; output: 'obj' | 'vtp'; fields: Field[] }
const operations = operationCatalog.operations as Operation[]

function eligible(dataset: ScientificDataset, operation: Operation) { return operation.inputExtensions.includes(dataset.path.split('.').pop()?.toLowerCase() ?? '') }
function validFields(operation: Operation, values: Record<string, string | boolean>) {
  return operation.fields.every(field => {
    const value = values[field.id]
    if (field.kind === 'boolean') return typeof value === 'boolean'
    if (typeof value !== 'string' || value.trim() === '') return false
    const number = Number(value)
    return Number.isFinite(number) && (field.min === undefined || number >= field.min) &&
      (field.max === undefined || number <= field.max) && (!field.integer || Number.isInteger(number))
  })
}

function WorkbenchResultSummary({ result }: { result: NonNullable<ReturnType<typeof useScientificRuntime>['jobs'][string]['result']> }) {
  if (result.state !== 'succeeded') return null
  const before = result.before ?? {}, after = result.after ?? {}
  const count = (value: number | boolean | undefined) => typeof value === 'number' ? value.toLocaleString() : 'unavailable'
  const delta = (key: string) => typeof before[key] === 'number' && typeof after[key] === 'number'
    ? ((after[key] as number) - (before[key] as number)).toLocaleString() : 'unavailable'
  const trianglesBefore = typeof before.triangles === 'number' ? before.triangles : typeof before.faces === 'number' ? before.faces : undefined
  const trianglesAfter = typeof after.triangles === 'number' ? after.triangles : typeof after.faces === 'number' ? after.faces : undefined
  const reduction = result.recipeId === 'mesh.simplify' && trianglesBefore && typeof trianglesAfter === 'number'
    ? `${((1 - trianglesAfter / trianglesBefore) * 100).toFixed(1)}% observed triangle reduction` : null
  return <section aria-label="Workbench result summary" className="scientific-workbench-summary">
    <h5>{result.recipeId} / recorded result</h5>
    <p>{reduction ?? `${count(trianglesAfter)} output triangles`}. {count(after.points ?? after.vertices)} output points.</p>
    <p>Triangle change: {trianglesBefore !== undefined && trianglesAfter !== undefined ? (trianglesAfter - trianglesBefore).toLocaleString() : delta('triangles')}. Boundary edges: {count(after.boundaryEdges)}; non-manifold edges: {count(after.nonManifoldEdges)}.</p>
    {typeof after.closed === 'boolean' && <p>Closed surface: {after.closed ? 'yes' : 'no'}.</p>}
    {typeof after.surfaceArea === 'number' && <p>Surface area: {after.surfaceArea.toPrecision(6)}.</p>}
    {typeof after.signedVolume === 'number' && <p>Signed volume: {after.signedVolume.toPrecision(6)}.</p>}
    {result.recipeId === 'mesh.normals' && <p>Normals were written to the saved VTP. Review the artifact hash before handoff.</p>}
    <small>Counts and topology are worker facts for the full output. The 3D view may sample triangles.</small>
  </section>
}

type Props = { runtime: RuntimeProfile; native: ReturnType<typeof useScientificRuntime>; edited: boolean; onHistory: (jobId?: string) => void }
export function ScientificMeshWorkbench(props: Props) {
  return <ScientificMeshWorkbenchContent key={props.runtime.id} {...props} />
}

function ScientificMeshWorkbenchContent({ runtime, native, edited, onHistory }: Props) {
  const catalog = operations.filter(item => item.provider === runtime.kind)
  const [operationId, setOperationId] = useState(catalog[0]?.id ?? '')
  const operation = catalog.find(item => item.id === operationId) ?? catalog[0]
  const [inputId, setInputId] = useState('')
  const [values, setValues] = useState<Record<string, string | boolean>>(() => Object.fromEntries((operation?.fields ?? []).map(field => [field.id, field.kind === 'boolean' ? field.value === true : String(field.value)])))
  const [outputName, setOutputName] = useState(() => `mesh-result.${operation?.output ?? 'obj'}`)
  const [inputCamera, setInputCamera] = useState(initialCamera)
  const previewRequested = useRef('')
  const importRefreshed = useRef('')
  const historyRequested = useRef(false)
  const datasetsRequested = useRef(false)
  const currentJob = native.jobs[runtime.id]
  const job = catalog.some(item => item.id === currentJob?.recipeId) ? currentJob : undefined
  const datasets = native.datasets?.entries ?? []
  const selected = datasets.find(item => item.id === inputId)
  const formatAccepted = !!selected && !!operation && eligible(selected, operation)
  const inputPreview = selected && native.datasetPreview?.inputId === selected.id && native.datasetPreview.sha256 === selected.sha256
    ? native.datasetPreview.geometry : null
  const outputValid = !!operation && new RegExp(`^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}\\.${operation.output}$`).test(outputName)
  const parametersValid = !!operation && validFields(operation, values)
  const ready = formatAccepted && outputValid && parametersValid && !edited && runtime.execution === 'windows-native'
  const artifact = job?.state === 'succeeded' ? job.result?.artifacts?.find(item => item.role !== 'operand' && /\.(obj|stl|ply|vtp)$/i.test(item.path)) : undefined
  const importJob = currentJob?.recipeId === 'datasets.import' ? currentJob : undefined
  const lastSaved = native.history?.find(item => item.runtimeId === runtime.id && catalog.some(entry => entry.id === item.recipeId))
  const lastSuccessful = native.history?.find(item => item.runtimeId === runtime.id && item.state === 'succeeded' && catalog.some(entry => entry.id === item.recipeId))

  useEffect(() => {
    if (!native.history && !native.pending && !historyRequested.current) {
      historyRequested.current = true
      native.send('', 'history')
    }
    // History is read once when the workbench opens; a run never starts on restore.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runtime.id, native.history, native.pending])

  useEffect(() => {
    if (!native.datasets && !native.pending && !datasetsRequested.current) {
      datasetsRequested.current = true
      native.send(runtime.id, 'datasets')
    }
    // Loading registered metadata is read-only and does not run an operation.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runtime.id, native.datasets, native.pending])

  useEffect(() => {
    if (!importJob || importJob.state === 'running' || native.pending || importRefreshed.current === importJob.jobId) return
    importRefreshed.current = importJob.jobId
    native.send(runtime.id, 'datasets')
  }, [importJob, native, runtime.id])

  useEffect(() => {
    if (!job || !artifact || native.pending || previewRequested.current === job.jobId ||
        native.previews[runtime.id]?.jobId === job.jobId) return
    previewRequested.current = job.jobId
    native.send(runtime.id, 'artifacts', { jobId: job.jobId, artifactPath: artifact.path })
  }, [artifact, job, native, runtime.id])

  const changeOperation = (id: string) => {
    const next = catalog.find(item => item.id === id)
    if (!next) return
    setOperationId(id)
    setValues(Object.fromEntries(next.fields.map(field => [field.id, field.kind === 'boolean' ? field.value === true : String(field.value)])))
    setOutputName(`mesh-result.${next.output}`)
  }
  const run = () => {
    if (!ready || !operation) return
    const parameters = { inputId, outputName, ...Object.fromEntries(operation.fields.map(field => [field.id, field.kind === 'number' ? Number(values[field.id]) : values[field.id]])) }
    native.send(runtime.id, runtime.kind === 'cgal' ? 'cgal-recipe' : 'recipe', { recipeId: operation.id, parameters })
  }

  if (!operation) return null
  return <section className="scientific-mesh-workbench" aria-label="Scientific mesh workbench">
    <header><h3>Mesh workbench</h3><p>Open a registered mesh, choose a {runtime.name} operation, and inspect the managed result in 3D and as recorded facts.</p></header>
    <div className="scientific-workbench-steps">
      <section aria-label="Mesh input"><h4>1 · Object</h4>
        <div className="scientific-inspector-actions"><button disabled={native.pending} onClick={() => native.send(runtime.id, 'datasets')}>Load registered objects</button>
          <button disabled={native.pending || native.busy} onClick={() => native.send(runtime.id, 'import-meshes')}>Import mesh files…</button></div>
        {importJob && <div role="status"><strong>Last import: {importJob.state}</strong>{importJob.result?.imports?.map(item =>
          <p key={item.name}>{item.name}: {item.state}{item.message ? ` · ${item.message}` : ''}</p>)}</div>}
        <p className="scientific-runtime-note">Import copies up to 16 {runtime.kind === 'vtk' ? 'OBJ, STL, PLY, or VTP' : 'OBJ, STL, PLY, or OFF'} files (32 MiB each). VTP registration accepts local XML/base64 PolyData only, with no DTD or external references. CGAL validates its copies. VTK geometry is checked when an operation runs. Originals stay untouched.</p>
        <label>Selected object<select aria-label="Workbench object" value={inputId} onChange={event => { setInputId(event.target.value); setInputCamera(initialCamera) }}><option value="">Choose a registered mesh…</option>{datasets.map(item => <option key={item.id} value={item.id}>{item.category} / {item.name}{item.expectedProblem ? ' / expected problem' : ''}</option>)}</select></label>
        {native.datasets && <small>{datasets.filter(item => eligible(item, operation)).length} compatible objects / {datasets.length} registered</small>}
        {selected && <p><strong>{selected.name}</strong> · {selected.bytes.toLocaleString()} bytes · <code>SHA-256 {selected.sha256}</code>{selected.validation?.state ? ` · ${selected.validation.state}` : ''}</p>}
        {selected && !formatAccepted && <p role="alert">{selected.name} cannot be used for {operation.label}. This operation accepts {operation.inputNote}.</p>}
        {selected && <div className="scientific-workbench-input-preview">
          <button disabled={native.pending || !/\.(obj|stl|ply|vtp)$/i.test(selected.path)} onClick={() => native.send(runtime.id, 'dataset-preview', { inputId: selected.id })}>Load input 3D preview</button>
          {inputPreview && <MeshCanvas key={selected.id} mesh={inputPreview} camera={inputCamera} setCamera={setInputCamera} bounds={inputPreview.bounds} after={false} label="INPUT / registered copy" />}
          {!/\.(obj|stl|ply|vtp)$/i.test(selected.path) && <p>OFF has no 3D preview in this Workbench. CGAL can still run on the verified registered copy; review its output and recorded metrics afterward.</p>}
          <small>Preview reads the copied bytes with VTK and verifies their hash. A run checks the copy again.</small>
        </div>}
      </section>
      <section aria-label="Mesh operation"><h4>2 · Operation</h4>
        <label>Feature<select aria-label="Workbench operation" value={operation.id} onChange={event => changeOperation(event.target.value)}>{catalog.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
        <p>{operation.description}</p><small>Accepted input: {operation.inputNote}. Operation ID: <code>{operation.id}</code>. Catalog v{operationCatalog.schemaVersion}.</small>
        <div className="scientific-runtime-fields">{operation.fields.map(field => <label key={field.id}>{field.label}{field.kind === 'boolean'
          ? <input type="checkbox" checked={values[field.id] === true} onChange={event => setValues(previous => ({ ...previous, [field.id]: event.target.checked }))} />
          : <input type="number" min={field.min} max={field.max} step={field.step ?? 'any'} value={String(values[field.id] ?? '')} onChange={event => setValues(previous => ({ ...previous, [field.id]: event.target.value }))} />}</label>)}</div>
        <label>Output name<input aria-label="Workbench output name" value={outputName} onChange={event => setOutputName(event.target.value)} spellCheck={false} /></label>
        {!outputValid && <p role="alert">Use a simple .{operation.output} filename.</p>}
        {!parametersValid && <p role="alert">Enter values within the limits shown for this operation.</p>}
        <div className="scientific-inspector-actions"><button disabled={!ready || native.busy || native.pending} onClick={run}>Run {operation.label}</button>
          <button disabled={job?.state !== 'running' || native.pending} onClick={() => job && native.send(runtime.id, 'stop', { jobId: job.jobId })}>Cancel run</button>
          <button onClick={() => onHistory()}>Open History</button></div>
        {edited && <p role="status">This runtime definition is edited. Restore the configured profile before running.</p>}
      </section>
    </div>
    <section aria-label="Mesh result"><h4>3 · Result</h4>
      {job ? <p><strong>{job.recipeId}</strong> · {job.state} · {job.stage ?? 'run'} · {job.durationMs.toLocaleString()} ms · <code>{job.jobId}</code></p> : <p>No mesh operation result in this session. Opening the workbench does not execute an operation.</p>}
      {!job && lastSaved && <button onClick={() => onHistory(lastSaved.jobId)}>Reopen last saved result · {lastSaved.recipeId} / {lastSaved.state}</button>}
      {!job && lastSuccessful && lastSuccessful.jobId !== lastSaved?.jobId && <button onClick={() => onHistory(lastSuccessful.jobId)}>Reopen last successful result · {lastSuccessful.recipeId}</button>}
      {job?.error && <p role="alert">{job.error}</p>}
      {job?.result && <WorkbenchResultSummary result={job.result} />}
      {job && <ScientificArtifacts runtime={runtime} native={native} />}
    </section>
  </section>
}
