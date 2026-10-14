import { useEffect, useState } from 'react'
import type { RuntimeProfile } from './scientificRuntimeProfiles'
import type { useScientificRuntime } from './useScientificRuntime'

const shellQuote = (value: string) => `'${value.replaceAll("'", "''")}'`

export function ScientificCgalRecipes({ runtime, native, edited }: {
  runtime: RuntimeProfile; native: ReturnType<typeof useScientificRuntime>; edited: boolean
}) {
  const [operation, setOperation] = useState('validate')
  const [inputId, setInputId] = useState('')
  const [targetEdge, setTargetEdge] = useState('0.1')
  const [iterations, setIterations] = useState('3')
  const [preserveBoundary, setPreserveBoundary] = useState(true)
  const [outputName, setOutputName] = useState('mesh-result.obj')
  const [notice, setNotice] = useState('')
  useEffect(() => { setInputId(''); setNotice('') }, [runtime.id])
  const inputs = (native.datasets?.entries ?? []).filter(item => /\.(obj|stl|ply|off)$/i.test(item.path))
  const selected = inputs.find(item => item.id === inputId)
  const edge = Number(targetEdge), count = Number(iterations)
  const parameters = { inputId, outputName, ...(operation === 'remesh' ? { targetEdge: edge, iterations: count, preserveBoundary } : {}) }
  const valid = !!selected && /^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}\.obj$/.test(outputName) &&
    (operation !== 'remesh' || (targetEdge.trim() !== '' && iterations.trim() !== '' && Number.isFinite(edge) && edge > 0 && edge <= 1000000 && Number.isInteger(count) && count >= 1 && count <= 10))
  const executable = runtime.execution === 'windows-native' && runtime.id === 'cgal-win-conda' && !edited
  const argv = [operation, selected?.path ?? '<input fixture>', `<new-run-folder>/${outputName}`, operation === 'remesh' ? targetEdge : '0.1', operation === 'remesh' ? iterations : '1', operation === 'remesh' && preserveBoundary ? '1' : '0']
  const command = `& 'devshell_cgal_worker.exe' ${argv.map(shellQuote).join(' ')}`
  const recipe = {
    schemaVersion: 1, id: `cgal.${operation}`, runtime: runtime.id,
    steps: [{ executable: 'cmake', argv: ['-S', '<shipped cgal-worker>', '-B', '<profile build cache>', '-G', 'Visual Studio 17 2022', '-A', 'x64', '-DCMAKE_PREFIX_PATH=<installed CGAL prefix>/Library'] },
      { executable: 'cmake', argv: ['--build', '<profile build cache>', '--config', 'Release', '--parallel', '1'] },
      { executable: '<profile build cache>/Release/devshell_cgal_worker.exe', argv }],
    parameters, artifacts: [outputName, 'results.json', 'invocation.json', 'full.log'],
    timeoutSecondsPerStep: [180, 180, 120], execution: 'owned argv-based processes; paths resolved by the native runner',
  }
  const request = { schemaVersion: 1, runId: '<assigned-by-runner>', runtimeId: runtime.id, recipeId: `cgal.${operation}`, operation: `cgal.${operation}`, parameters,
    workingDirectory: '<new-owned-run-directory>', datasetRoot: '<registered-dataset-root>', timeoutSeconds: 120,
    inputArtifacts: selected ? [{ path: selected.path, mediaType: 'application/octet-stream', datasetId: selected.id, sha256: selected.sha256, bytes: selected.bytes, sourceRoot: selected.sourceRoot, sourcePath: selected.sourcePath }] : [],
    outputArtifacts: [{ path: outputName, mediaType: 'model/obj' }], provenance: { inputPolicy: 'Registered local copies; SHA-256 checked before execution' } }
  const copy = async (value: string) => { try { await navigator.clipboard.writeText(value); setNotice('Copied. Placeholder paths are resolved by the runner, not by the clipboard command.') } catch { setNotice('Clipboard unavailable.') } }
  return <section aria-label="CGAL parameterized recipes">
    <h4>Mesh / CGAL worker recipes</h4>
    <div className="scientific-inspector-actions">
      <button aria-pressed={operation === 'validate'} onClick={() => setOperation('validate')}>Validate</button>
      <button aria-pressed={operation === 'remesh'} onClick={() => setOperation('remesh')}>Isotropic Remesh</button>
      {['Repair', 'Boolean', 'Simplify', 'AABB', 'Distance', 'Intersection'].map(name => <button key={name} disabled title="This CGAL worker operation is not implemented">{name}</button>)}
    </div>
    <div className="scientific-runtime-fields">
      <label>Input dataset<select aria-label="CGAL input dataset" value={inputId} onChange={event => setInputId(event.target.value)}><option value="">Load and select a duplicated mesh...</option>{inputs.map(item => <option key={item.id} value={item.id}>{item.category} / {item.name}{item.expectedProblem ? ' / expected problem' : ''}</option>)}</select></label>
      {operation === 'remesh' && <>
        <label>Target edge length (mesh units)<input aria-label="CGAL target edge length" type="number" min="0.000001" max="1000000" step="any" value={targetEdge} onChange={event => setTargetEdge(event.target.value)} /></label>
        <label>Iterations<input aria-label="CGAL iterations" type="number" min="1" max="10" step="1" value={iterations} onChange={event => setIterations(event.target.value)} /></label>
        <label>Protect boundary curve<input aria-label="CGAL preserve boundary" type="checkbox" checked={preserveBoundary} onChange={event => setPreserveBoundary(event.target.checked)} /></label>
      </>}
      <label>Output filename<input aria-label="CGAL output filename" value={outputName} onChange={event => setOutputName(event.target.value)} spellCheck={false} /></label>
    </div>
    {selected && <details><summary>Dataset provenance</summary><p><code>{selected.sourceRoot} / {selected.sourcePath}</code></p><p>SHA-256 <code>{selected.sha256}</code></p></details>}
    <details><summary>Engine command / positional arguments</summary><pre>{command}</pre><p className="scientific-runtime-note">The registered JSON adapter resolves the copied input and fresh output directory, then invokes the C++ engine with argv. This text is never passed to a shell.</p></details>
    <details open><summary>Shared JSON request contract</summary><pre>{JSON.stringify(request, null, 2)}</pre></details>
    <details><summary>Registered build recipe</summary><pre>{JSON.stringify(recipe, null, 2)}</pre></details>
    <div className="scientific-inspector-actions">
      <button disabled={!executable || !valid || native.busy || native.pending} onClick={() => native.send(runtime.id, 'cgal-recipe', { recipeId: `cgal.${operation}`, parameters })}>Run {operation === 'remesh' ? 'remesh' : 'validation'} recipe</button>
      <button onClick={() => copy(command)}>Copy command template</button>
      <button onClick={() => copy(JSON.stringify(recipe, null, 2))}>Copy recipe</button>
      <button onClick={() => copy(JSON.stringify(request, null, 2))}>Copy invocation</button>
    </div>
    <p className="scientific-runtime-note">Validation rejects unreadable/non-manifold inputs, degenerate triangles, and self-intersections. Polygon faces are triangulated explicitly. Open surfaces are allowed; no implicit soup repair is performed. Protected boundaries can gain vertices from edge splitting. Inputs are limited to 100,000 faces and 32 MiB; very small edge targets are rejected by a conservative geometry budget. Local validation/remesh acceptance cases have passed; each new run records its own evidence rather than claiming every CGAL capability is ready.</p>
    {notice && <p role="status">{notice}</p>}
  </section>
}
