import { useEffect, useState } from 'react'
import type { RuntimeProfile } from './scientificRuntimeProfiles'
import type { useScientificRuntime } from './useScientificRuntime'

export function ScientificBooleanPanel({ runtime, native, edited, onArtifacts, onHistory, onPrepare }: {
  runtime: RuntimeProfile; native: ReturnType<typeof useScientificRuntime>; edited: boolean
  onArtifacts: () => void; onHistory: () => void; onPrepare: () => void
}) {
  const [a, setA] = useState('')
  const [b, setB] = useState('')
  const [operation, setOperation] = useState('union')
  const [scale, setScale] = useState('1')
  const [translation, setTranslation] = useState(['0', '0', '0'])
  const [output, setOutput] = useState('boolean-result.m3dm')
  useEffect(() => { setA(''); setB(''); native.send(runtime.id, 'datasets'); native.send(runtime.id, 'math3d-readiness') }, [native.profileId, runtime.id])
  const inputs = (native.datasets?.entries ?? []).filter(item => /\.(obj|stl|ply|off)$/i.test(item.path))
  const preferred = inputs.find(item => item.id === 'math3d/basic/02_cube.obj')?.id ?? inputs[0]?.id ?? ''
  const inputAId = inputs.some(item => item.id === a) ? a : preferred
  const inputBId = inputs.some(item => item.id === b) ? b : preferred
  const parameters = { inputAId, inputBId, operation, outputName: output, scaleB: Number(scale), translateB: translation.map(Number) }
  const needed = ['node', 'harness', 'environment', 'compiler', 'adapter', 'worker']
  const missing = native.math3dReadiness?.checks.filter(check => needed.includes(check.id) && !check.ready)
  const ready = !!native.math3dReadiness && !missing?.length
  const valid = !!inputAId && !!inputBId && scale.trim() !== '' && Number.isFinite(parameters.scaleB) && parameters.scaleB >= 0.000001 && parameters.scaleB <= 1000
    && translation.every(value => value.trim() !== '' && Number.isFinite(Number(value)) && Math.abs(Number(value)) <= 1000000)
    && /^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}\.m3dm$/.test(output) && !/^operand-[ab]\.m3dm$/i.test(output)
  const canRun = valid && ready && !edited && runtime.id === 'cgal-win-conda' && !native.busy && !native.pending
  const job = native.jobs[runtime.id]?.recipeId === 'cgal.boolean' ? native.jobs[runtime.id] : undefined
  const choices = inputs.map(item => <option key={item.id} value={item.id}>{item.category} / {item.name}{item.expectedProblem ? ' / expected problem' : ''}</option>)
  return <section aria-label="Boolean mesh operation">
    <h3>Boolean operation</h3>
    <p>Choose two registered meshes. Both inputs are validated before the operation; each run saves its result and input snapshots in History.</p>
    {!ready && <div role="status"><p>{native.math3dReadiness ? 'Preparation is needed before running.' : 'Checking prerequisites...'}</p>{missing?.map(check => <p key={check.id}>{check.label}: {check.detail}</p>)}<button type="button" onClick={onPrepare}>Open preparation</button></div>}
    <form onSubmit={event => { event.preventDefault(); if (canRun) native.send(runtime.id, 'boolean-recipe', { parameters }) }}>
      <div className="scientific-runtime-fields">
        <label>Mesh A<select aria-label="Boolean mesh A" value={inputAId} onChange={event => setA(event.target.value)}><option value="">Select mesh A...</option>{choices}</select></label>
        <label>Mesh B<select aria-label="Boolean mesh B" value={inputBId} onChange={event => setB(event.target.value)}><option value="">Select mesh B...</option>{choices}</select></label>
        <label>Operation<select aria-label="Boolean operation" value={operation} onChange={event => setOperation(event.target.value)}><option value="union">Union (A + B)</option><option value="intersection">Intersection (A and B)</option><option value="difference">Difference (A minus B)</option></select></label>
        <label>Output filename<input aria-label="Boolean output filename" value={output} onChange={event => setOutput(event.target.value)} spellCheck={false} /></label>
      </div>
      <details><summary>Mesh B placement: scale {scale || '?'}; offset [{translation.join(', ')}]</summary>
        <div className="scientific-runtime-fields"><label>Uniform scale<input aria-label="Mesh B scale" type="number" min="0.000001" max="1000" step="any" value={scale} onChange={event => setScale(event.target.value)} /></label>
          {['X', 'Y', 'Z'].map((axis, index) => <label key={axis}>Offset {axis}<input aria-label={`Mesh B offset ${axis}`} type="number" min="-1000000" max="1000000" step="any" value={translation[index]} onChange={event => setTranslation(previous => previous.map((value, i) => i === index ? event.target.value : value))} /></label>)}
        </div><p className="scientific-runtime-note">Scale is applied around the origin, then offset. Mesh A keeps its original placement.</p>
      </details>
      <div className="scientific-inspector-actions"><button type="submit" disabled={!canRun}>Run Boolean</button><button type="button" disabled={native.pending} onClick={() => { native.send(runtime.id, 'datasets'); native.send(runtime.id, 'math3d-readiness') }}>Refresh inputs and readiness</button><button type="button" onClick={() => { native.send('', 'history'); onHistory() }}>Open History</button></div>
    </form>
    <p className="scientific-runtime-note">Registered OBJ/STL/PLY/OFF copies only. Inputs must be closed, consistently oriented solids. Nonempty results include an OBJ export; empty results retain a valid M3DM file. Stop cancels validation and computation.</p>
    {job && <div className="scientific-recipe-job" role="status"><h4>{job.request?.parameters.operation as string} / {job.state}</h4><p>{job.stage} / {job.durationMs} ms</p>
      <div className="scientific-inspector-actions"><button disabled={job.state !== 'running'} onClick={() => native.send(runtime.id, 'stop', { jobId: job.jobId })}>Stop</button><button disabled={job.state !== 'succeeded'} onClick={() => { native.send(runtime.id, 'artifacts', { jobId: job.jobId, artifactPath: job.result?.boolean?.outputArtifact }); onArtifacts() }}>Inspect result</button><button onClick={() => native.send(runtime.id, 'open-output', { jobId: job.jobId })}>Open output folder</button></div>
      {job.result?.boolean && <p>{job.result.boolean.empty ? 'Empty result.' : `${job.result.after?.triangles ?? 0} triangles; enclosed volume ${job.result.after?.volume ?? 'unavailable'}.`} Inputs A and B are retained for inspection.</p>}
      {job.error && <p role="alert">{job.error}</p>}<details><summary>Run log</summary><pre>{job.log || 'Waiting for output...'}</pre></details>
    </div>}
  </section>
}
