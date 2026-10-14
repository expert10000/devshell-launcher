import { useEffect, useState } from 'react'
import type { RuntimeProfile } from './scientificRuntimeProfiles'
import type { useScientificRuntime } from './useScientificRuntime'
import { ScientificCgalRecipes } from './ScientificCgalRecipes'

const meshRecipes = [
  { id: 'mesh.inspect', name: 'Inspect mesh', fields: [] },
  { id: 'mesh.simplify', name: 'Simplify', fields: [{ id: 'targetReduction', name: 'Target reduction (fraction)', type: 'number', min: 0, max: 0.95, step: 0.05, value: 0.5 }, { id: 'preserveTopology', name: 'Preserve topology', type: 'boolean', value: true }, { id: 'preserveBoundary', name: 'Preserve boundary vertices', type: 'boolean', value: true }] },
  { id: 'mesh.normals', name: 'Compute normals', fields: [{ id: 'featureAngle', name: 'Feature angle (degrees)', type: 'number', min: 0, max: 180, step: 1, value: 30 }, { id: 'autoOrient', name: 'Auto orient (closed manifold only)', type: 'boolean', value: false }] },
] as const

export function ScientificRecipePanel({ runtime, native, edited, onArtifacts }: { runtime: RuntimeProfile; native: ReturnType<typeof useScientificRuntime>; edited: boolean; onArtifacts: () => void }) {
  const [recipeId, setRecipeId] = useState('mesh.inspect')
  const [inputId, setInputId] = useState('')
  const [outputName, setOutputName] = useState('mesh-output.vtp')
  const [values, setValues] = useState<Record<string, number | boolean | string>>({ targetReduction: 0.5, preserveTopology: true, preserveBoundary: true, featureAngle: 30, autoOrient: false })
  const [copyStatus, setCopyStatus] = useState('')
  useEffect(() => { setRecipeId('mesh.inspect'); setInputId(''); setOutputName('mesh-output.vtp'); setCopyStatus('') }, [runtime.id])
  const executable = runtime.execution === 'windows-native' && ['cgal', 'vtk'].includes(runtime.kind) && !edited
  const recipe = meshRecipes.find(item => item.id === recipeId) ?? meshRecipes[0]
  const parameters = Object.fromEntries(recipe.fields.map(field => [field.id, values[field.id] ?? field.value]))
  const inputs = native.datasets?.entries ?? []
  const selected = inputs.find(item => item.id === inputId)
  const invalidNumbers = recipe.fields.some(field => field.type === 'number' && (typeof values[field.id] !== 'number' || !Number.isFinite(values[field.id]) || Number(values[field.id]) < field.min || Number(values[field.id]) > field.max))
  const valid = !!selected && /^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}\.vtp$/.test(outputName) && !invalidNumbers
  const request = { schemaVersion: 1, runId: '<assigned-by-runner>', runtimeId: runtime.id, recipeId: recipe.id, operation: recipe.id, parameters: { inputId, outputName, ...parameters }, inputArtifacts: selected ? [{ path: selected.path, mediaType: 'application/octet-stream', datasetId: selected.id, sha256: selected.sha256, bytes: selected.bytes, sourceRoot: selected.sourceRoot, sourcePath: selected.sourcePath }] : [], workingDirectory: '<new-owned-run-directory>', datasetRoot: '<registered-dataset-root>', timeoutSeconds: 120, outputArtifacts: [{ path: outputName, mediaType: 'application/vnd.vtk.vtp' }], provenance: { inputPolicy: 'Registered local copies; SHA-256 checked before execution' } }
  const copyRequest = async () => { try { await navigator.clipboard.writeText(JSON.stringify(request, null, 2)); setCopyStatus('Structured invocation copied. RunId and resolved paths are supplied by the native runner.') } catch { setCopyStatus('Clipboard unavailable.') } }
  const job = native.jobs[runtime.id]
  return <section className="scientific-recipe-panel" aria-label="Scientific command recipes">
    <h3>Quick commands / registered recipes</h3>
    <div className="scientific-inspector-actions">{[['version', 'Version'], ['configure', 'Configure'], ['build', 'Build'], ['run', 'Run'], ['test-all', 'Test all']].map(([id, name]) => <button key={id} disabled={!executable || native.busy || native.pending} onClick={() => native.send(runtime.id, 'recipe', { recipeId: id })}>{name}</button>)}</div>
    <p className="scientific-runtime-note">Configure, Build, and Run are separate actions; Test all sequences the shipped smoke test and VTK offscreen check. It is not a complete algorithm test suite. Only registered argv-based commands execute, with owned processes and timeouts.</p>
    <h3>Parameterized mesh operations</h3>
    <button disabled={native.pending} onClick={() => native.send(runtime.id, 'datasets')}>Load duplicated test sets</button>
    {native.datasets && <p className="scientific-runtime-note">{inputs.length} local copies / imported {new Date(native.datasets.importedAt).toLocaleString()}. {native.datasets.note}</p>}
    {runtime.kind === 'vtk' ? <>
      <div className="scientific-runtime-fields">
        <label>Operation<select aria-label="Scientific mesh operation" value={recipeId} onChange={event => { setRecipeId(event.target.value); setCopyStatus('') }}>{meshRecipes.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label>Input dataset<select aria-label="Scientific input dataset" value={inputId} onChange={event => { setInputId(event.target.value); setCopyStatus('') }}><option value="">Select a local copy...</option>{inputs.map(item => <option key={item.id} value={item.id}>{item.category} / {item.name}{item.expectedProblem ? ' / expected problem' : ''}</option>)}</select></label>
        {recipe.fields.map(field => <label key={field.id}>{field.name}{field.type === 'boolean' ? <input aria-label={field.name} type="checkbox" checked={values[field.id] === true} onChange={event => setValues(previous => ({ ...previous, [field.id]: event.target.checked }))} /> : <input aria-label={field.name} type="number" min={field.min} max={field.max} step={field.step} value={typeof values[field.id] === 'number' ? values[field.id] as number : ''} onChange={event => setValues(previous => ({ ...previous, [field.id]: event.target.value === '' ? '' : Number(event.target.value) }))} />}</label>)}
        <label>Output filename<input aria-label="Scientific output filename" value={outputName} onChange={event => setOutputName(event.target.value)} spellCheck={false} /></label>
      </div>
      {selected && <details><summary>Dataset source / hash</summary><p><code>{selected.sourceRoot} / {selected.sourcePath}</code></p><p>{selected.bytes} bytes / SHA-256 <code>{selected.sha256}</code></p></details>}
      <details open><summary>Generated execution contract</summary><pre>{JSON.stringify(request, null, 2)}</pre></details>
      <div className="scientific-inspector-actions"><button disabled={!executable || !valid || native.busy || native.pending} onClick={() => native.send(runtime.id, 'recipe', { recipeId, parameters: request.parameters })}>Run mesh recipe</button><button onClick={copyRequest}>Copy invocation</button></div>
      <p className="scientific-runtime-note">Only OBJ/STL/PLY/VTP local copies are read; each run writes a new VTP and result JSON in its own folder. Topology/boundary constraints can prevent the requested reduction. Auto orientation is rejected for open/non-manifold surfaces. Inspect reports basic statistics, not full mesh validity or self-intersections.</p>
    </> : runtime.kind === 'cgal' ? <ScientificCgalRecipes runtime={runtime} native={native} edited={edited} /> : <p>Select an installed Windows Native CGAL or VTK profile to use mesh recipes.</p>}
    {job && <section className="scientific-recipe-job" aria-label="Scientific job output"><h3>{job.recipeId} / {job.state}</h3><p>{job.stage ?? 'run'} / {job.durationMs} ms / <code>{job.outputDirectory}</code></p><div className="scientific-inspector-actions"><button disabled={job.state !== 'running' || native.pending} onClick={() => native.send(runtime.id, 'stop', { jobId: job.jobId })}>Stop</button><button onClick={() => native.send(runtime.id, 'open-log', { jobId: job.jobId })}>Open full log</button><button onClick={() => native.send(runtime.id, 'open-output', { jobId: job.jobId })}>Open output folder</button><button disabled={!job.result} onClick={onArtifacts}>View artifacts / compare</button></div><pre>{job.log || 'Waiting for output...'}</pre>{job.error && <p role="alert">{job.error}</p>}</section>}
    {copyStatus && <p role="status">{copyStatus}</p>}
  </section>
}
