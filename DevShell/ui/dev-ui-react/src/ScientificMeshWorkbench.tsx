import { useEffect, useRef, useState } from 'react'
import type { RuntimeProfile } from './scientificRuntimeProfiles'
import type { ScientificDataset } from './useScientificRuntime'
import type { useScientificRuntime } from './useScientificRuntime'
import { ScientificArtifacts } from './ScientificArtifacts'
import './ScientificMeshWorkbench.css'

type Field = { id: string; label: string; kind: 'number' | 'boolean'; value: number | boolean; min?: number; max?: number; step?: number; integer?: boolean }
type Operation = { id: string; label: string; provider: 'cgal' | 'vtk'; description: string; accepts: RegExp; inputNote: string; output: 'obj' | 'vtp'; fields: Field[] }

const operations: Operation[] = [
  { id: 'cgal.validate', label: 'Validate surface', provider: 'cgal', description: 'Read the mesh and record topology and geometry facts.', accepts: /\.(obj|stl|ply|off)$/i, inputNote: 'OBJ, STL, PLY, OFF', output: 'obj', fields: [] },
  { id: 'cgal.remesh', label: 'Isotropic remesh', provider: 'cgal', description: 'Remesh a guarded triangle surface to a target edge length.', accepts: /\.(obj|stl|ply|off)$/i, inputNote: 'OBJ, STL, PLY, OFF; guarded scope', output: 'obj', fields: [
    { id: 'targetEdge', label: 'Target edge length', kind: 'number', value: 0.1, min: 0.000001, max: 1000000 },
    { id: 'iterations', label: 'Iterations', kind: 'number', value: 3, min: 1, max: 10, integer: true },
    { id: 'preserveBoundary', label: 'Protect boundary curve', kind: 'boolean', value: true },
  ] },
  { id: 'cgal.repair-orientation', label: 'Repair orientation', provider: 'cgal', description: 'Orient one closed triangle volume outward; open meshes are rejected.', accepts: /\.obj$/i, inputNote: 'OBJ; one closed triangle volume', output: 'obj', fields: [] },
  { id: 'cgal.fill-bounded-holes', label: 'Fill bounded holes', provider: 'cgal', description: 'Fill 1–8 boundary loops with 3–12 edges each on a guarded OBJ mesh.', accepts: /\.obj$/i, inputNote: 'OBJ; bounded open manifold', output: 'obj', fields: [] },
  { id: 'mesh.inspect', label: 'Inspect surface', provider: 'vtk', description: 'Read the surface and report points, faces, and topology.', accepts: /\.(obj|stl|ply|vtp)$/i, inputNote: 'OBJ, STL, PLY, VTP', output: 'vtp', fields: [] },
  { id: 'mesh.simplify', label: 'Simplify', provider: 'vtk', description: 'Reduce triangle count with optional topology and boundary constraints.', accepts: /\.(obj|stl|ply|vtp)$/i, inputNote: 'OBJ, STL, PLY, VTP', output: 'vtp', fields: [
    { id: 'targetReduction', label: 'Target reduction fraction', kind: 'number', value: 0.5, min: 0, max: 0.95, step: 0.05 },
    { id: 'preserveTopology', label: 'Preserve topology', kind: 'boolean', value: true },
    { id: 'preserveBoundary', label: 'Preserve boundary vertices', kind: 'boolean', value: true },
  ] },
  { id: 'mesh.normals', label: 'Compute normals', provider: 'vtk', description: 'Compute face or vertex normals; automatic orientation requires a closed manifold.', accepts: /\.(obj|stl|ply|vtp)$/i, inputNote: 'OBJ, STL, PLY, VTP', output: 'vtp', fields: [
    { id: 'featureAngle', label: 'Feature angle (degrees)', kind: 'number', value: 30, min: 0, max: 180, step: 1 },
    { id: 'autoOrient', label: 'Auto orient closed mesh', kind: 'boolean', value: false },
  ] },
]

function eligible(dataset: ScientificDataset, operation: Operation) { return operation.accepts.test(dataset.path) }
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

type Props = { runtime: RuntimeProfile; native: ReturnType<typeof useScientificRuntime>; edited: boolean; onHistory: () => void }
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
  const previewRequested = useRef('')
  const currentJob = native.jobs[runtime.id]
  const job = catalog.some(item => item.id === currentJob?.recipeId) ? currentJob : undefined
  const datasets = (native.datasets?.entries ?? []).filter(item => operation && eligible(item, operation))
  const selected = datasets.find(item => item.id === inputId)
  const outputValid = !!operation && new RegExp(`^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}\\.${operation.output}$`).test(outputName)
  const parametersValid = !!operation && validFields(operation, values)
  const ready = !!selected && outputValid && parametersValid && !edited && runtime.execution === 'windows-native'
  const artifact = job?.state === 'succeeded' ? job.result?.artifacts?.find(item => item.role !== 'operand' && /\.(obj|stl|ply|vtp)$/i.test(item.path)) : undefined

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
    if (inputId && !native.datasets?.entries.some(item => item.id === inputId && eligible(item, next))) setInputId('')
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
          <button disabled={native.pending || native.busy} onClick={() => native.send('cgal-win-conda', 'import-meshes')}>Import mesh files…</button></div>
        <p className="scientific-runtime-note">Import copies up to 16 OBJ, STL, PLY, or OFF files (32 MiB each) and currently validates them through CGAL. VTK can use the registered OBJ, STL, or PLY copies. Originals stay untouched.</p>
        <label>Selected object<select aria-label="Workbench object" value={inputId} onChange={event => setInputId(event.target.value)}><option value="">Choose a registered mesh…</option>{datasets.map(item => <option key={item.id} value={item.id}>{item.category} / {item.name}{item.expectedProblem ? ' / expected problem' : ''}</option>)}</select></label>
        {native.datasets && <small>{datasets.length} compatible objects / {native.datasets.entries.length} registered</small>}
        {selected && <p><strong>{selected.name}</strong> · {selected.bytes.toLocaleString()} bytes · <code>SHA-256 {selected.sha256}</code>{selected.validation?.state ? ` · ${selected.validation.state}` : ''}</p>}
      </section>
      <section aria-label="Mesh operation"><h4>2 · Operation</h4>
        <label>Feature<select aria-label="Workbench operation" value={operation.id} onChange={event => changeOperation(event.target.value)}>{catalog.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
        <p>{operation.description}</p><small>Accepted input: {operation.inputNote}. Operation ID: <code>{operation.id}</code></small>
        <div className="scientific-runtime-fields">{operation.fields.map(field => <label key={field.id}>{field.label}{field.kind === 'boolean'
          ? <input type="checkbox" checked={values[field.id] === true} onChange={event => setValues(previous => ({ ...previous, [field.id]: event.target.checked }))} />
          : <input type="number" min={field.min} max={field.max} step={field.step ?? 'any'} value={String(values[field.id] ?? '')} onChange={event => setValues(previous => ({ ...previous, [field.id]: event.target.value }))} />}</label>)}</div>
        <label>Output name<input aria-label="Workbench output name" value={outputName} onChange={event => setOutputName(event.target.value)} spellCheck={false} /></label>
        {!outputValid && <p role="alert">Use a simple .{operation.output} filename.</p>}
        {!parametersValid && <p role="alert">Enter values within the limits shown for this operation.</p>}
        <div className="scientific-inspector-actions"><button disabled={!ready || native.busy || native.pending} onClick={run}>Run {operation.label}</button>
          <button disabled={job?.state !== 'running' || native.pending} onClick={() => job && native.send(runtime.id, 'stop', { jobId: job.jobId })}>Cancel run</button>
          <button onClick={onHistory}>Open History</button></div>
        {edited && <p role="status">This runtime definition is edited. Restore the configured profile before running.</p>}
      </section>
    </div>
    <section aria-label="Mesh result"><h4>3 · Result</h4>
      {job ? <p><strong>{job.recipeId}</strong> · {job.state} · {job.stage ?? 'run'} · {job.durationMs.toLocaleString()} ms · <code>{job.jobId}</code></p> : <p>No mesh operation result in this session. Opening the workbench does not execute an operation. Use History to reopen older results.</p>}
      {job?.error && <p role="alert">{job.error}</p>}
      {job && <ScientificArtifacts runtime={runtime} native={native} />}
    </section>
  </section>
}
