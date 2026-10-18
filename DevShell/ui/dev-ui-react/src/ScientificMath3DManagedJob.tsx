import { useEffect, useRef } from 'react'
import type { useScientificRuntime } from './useScientificRuntime'

const runtimeId = 'cgal-win-conda'
const recipeId = 'integration.math3d.native-boolean'

type Comparison = {
  verdict: string
  passed: number
  total: number
  checks: { name: string; passed: boolean; expected: unknown; actual: unknown }[]
  cases?: { name: string; reference?: { bounds: number[]; volume: number }; after?: { bounds: number[]; volume: number }; metrics?: { boundsDelta: number; areaDelta: number; volumeDelta: number; sampledSurfaceDeviation: number; triangleCountDelta: number }; tolerances?: { bounds: number; area: number; volume: number; sampledSurface: number } }[]
}

export function ScientificMath3DManagedJob({ native, onHistory }: { native: ReturnType<typeof useScientificRuntime>; onHistory: () => void }) {
  const requested = useRef(new Set<string>())
  const refreshed = useRef(new Set<string>())
  const job = native.jobs[runtimeId]?.recipeId === recipeId ? native.jobs[runtimeId] : undefined
  const entry = native.history?.filter(item => item.runtimeId === runtimeId && item.recipeId === recipeId)
    .sort((a, b) => b.finishedAtUtc.localeCompare(a.finishedAtUtc))[0]
  const result = entry ? native.historyResults[entry.jobId] as (typeof native.historyResults[string] & { comparison?: Comparison; scope?: string }) | undefined : undefined

  useEffect(() => { native.send('', 'history') }, [])
  useEffect(() => {
    if (!job || !['succeeded', 'failed', 'cancelled', 'timed-out'].includes(job.state) || refreshed.current.has(job.jobId)) return
    refreshed.current.add(job.jobId)
    native.send('', 'history')
  }, [job?.jobId, job?.state, native.send])
  useEffect(() => {
    if (!entry || result || requested.current.has(entry.jobId)) return
    requested.current.add(entry.jobId)
    native.send(runtimeId, 'history-result', { jobId: entry.jobId })
  }, [entry?.jobId, result, native.send])

  return <section aria-label="MATH3D native worker integration" className="scientific-history-result">
    <h3>MATH3D native worker comparison</h3>
    <p className="scientific-runtime-note">Run registered tetrahedron and cube self-unions, then union the cube with a second copy translated +1 on X. The overlap has analytic bounds [-1, 2] x [-1, 1] x [-1, 1] and volume 12. Explicit topology and geometry tolerances are checked; this is bounded integration evidence, not broad Boolean correctness.</p>
    <div className="scientific-inspector-actions">
      <button disabled={native.busy || native.pending} onClick={() => native.send(runtimeId, 'math3d-integration')}>Run MATH3D integration test</button>
      <button disabled={native.pending} onClick={() => native.send('', 'history')}>Refresh saved verdict</button>
    </div>
    {job && <div role="status"><p><strong>Managed job: {job.state}</strong> / {job.stage ?? 'run'} / {job.durationMs} ms</p>
      <div className="scientific-inspector-actions"><button disabled={job.state !== 'running' || native.pending} onClick={() => native.send(runtimeId, 'stop', { jobId: job.jobId })}>Stop</button><button onClick={() => native.send(runtimeId, 'open-log', { jobId: job.jobId })}>Open full log</button><button onClick={() => native.send(runtimeId, 'open-output', { jobId: job.jobId })}>Open output folder</button></div>
      {job.error && <p role="alert">{job.error}</p>}
      <pre>{job.log || 'Waiting for worker output...'}</pre>
    </div>}
    {entry ? <div><h4>Saved verdict: {result?.comparison?.verdict?.toUpperCase() ?? entry.state}</h4>
      <p>{result?.comparison ? `${result.comparison.passed}/${result.comparison.total} checks passed` : 'Load the saved result to see the checks.'} / run <code>{entry.jobId}</code></p>
      {result?.comparison?.checks && <ul>{result.comparison.checks.map(check => <li key={check.name}>{check.passed ? 'PASS' : 'FAIL'} / {check.name}</li>)}</ul>}
      {result?.comparison?.cases?.map(item => <p key={item.name}>{item.name}: {item.metrics ? `bounds ${item.metrics.boundsDelta.toPrecision(3)} / ${item.tolerances?.bounds.toPrecision(3)}, area ${item.metrics.areaDelta.toPrecision(3)} / ${item.tolerances?.area.toPrecision(3)}, volume ${item.metrics.volumeDelta.toPrecision(3)} / ${item.tolerances?.volume.toPrecision(3)}, sampled surface ${item.metrics.sampledSurfaceDeviation.toPrecision(3)} / ${item.tolerances?.sampledSurface.toPrecision(3)}, triangle delta ${item.metrics.triangleCountDelta}` : 'No geometry output'}</p>)}
      {result?.comparison?.cases?.find(item => item.name === 'Overlapping cubes')?.reference && <p>Overlapping cubes reference: volume 12, bounds [-1, 2] x [-1, 1] x [-1, 1].</p>}
      <button onClick={() => { native.send(runtimeId, 'history-result', { jobId: entry.jobId }); onHistory() }}>Open saved History entry</button>
      <p className="scientific-runtime-note">This run is also listed under History. Use its Result, Log, and Folder actions there after Refresh history.</p>
    </div> : <p className="scientific-runtime-note">No saved MATH3D native integration run for this profile. The worker must be built in the local Scientific builds folder before running.</p>}
  </section>
}
