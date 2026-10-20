import { useEffect, useRef } from 'react'
import type { useScientificRuntime } from './useScientificRuntime'

const runtimeId = 'cgal-win-conda'
const recipeId = 'integration.math3d.native-boolean'
const metric = (value: number | null | undefined) => typeof value === 'number' && Number.isFinite(value) ? value.toPrecision(3) : 'unavailable'

type Comparison = {
  verdict: string
  passed: number
  total: number
  checks: { name: string; passed: boolean; expected: unknown; actual: unknown }[]
  cases?: { name: string; reference?: { bounds: number[] | null; volume: number; components: number }; after?: { bounds: number[] | null; volume: number; components: number }; metrics?: { boundsDelta: number | null; areaDelta: number | null; volumeDelta: number | null; sampledSurfaceDeviation: number | null; triangleCountDelta: number }; tolerances?: { bounds: number; area: number; volume: number; sampledSurface: number } }[]
}

export function ScientificMath3DManagedJob({ native, onHistory }: { native: ReturnType<typeof useScientificRuntime>; onHistory: () => void }) {
  const requested = useRef(new Set<string>())
  const refreshed = useRef(new Set<string>())
  const job = native.jobs[runtimeId]?.recipeId === recipeId ? native.jobs[runtimeId] : undefined
  const entry = native.history?.filter(item => item.runtimeId === runtimeId && item.recipeId === recipeId)
    .sort((a, b) => b.finishedAtUtc.localeCompare(a.finishedAtUtc))[0]
  const result = entry ? native.historyResults[entry.jobId] as (typeof native.historyResults[string] & { comparison?: Comparison; scope?: string }) | undefined : undefined

  useEffect(() => { requested.current.clear(); refreshed.current.clear(); native.send('', 'history'); native.send(runtimeId, 'math3d-readiness') }, [native.profileId])
  useEffect(() => {
    if (!job || !['succeeded', 'failed', 'cancelled', 'timed-out'].includes(job.state) || refreshed.current.has(job.jobId)) return
    refreshed.current.add(job.jobId)
    native.send('', 'history')
    native.send(runtimeId, 'math3d-readiness')
  }, [job?.jobId, job?.state, native.send])
  useEffect(() => {
    if (!entry || result || requested.current.has(entry.jobId)) return
    requested.current.add(entry.jobId)
    native.send(runtimeId, 'history-result', { jobId: entry.jobId })
  }, [entry?.jobId, result, native.send])

  return <section aria-label="MATH3D native worker integration" className="scientific-history-result">
    <h3>MATH3D native worker comparison</h3>
    <p className="scientific-runtime-note">Fourteen cases compare tetrahedron/cube self-unions and overlapping, face-touching, disjoint, and contained cube union, intersection, and difference. Checks cover empty intersections, separate shells, cavities, bounds, area, volume, and sampled surface deviation. These fixtures provide bounded integration evidence.</p>
    <div aria-label="Integration prerequisites">
      <h4>Prerequisites: {native.math3dReadiness ? native.math3dReadiness.ready ? 'Ready' : native.math3dReadiness.canPrepare ? 'Preparation needed' : 'Setup needed' : 'Checking...'}</h4>
      {native.math3dReadiness && <>
        {!native.math3dReadiness.ready && <ul>{native.math3dReadiness.checks.filter(check => !check.ready).map(check => <li key={check.id}><strong>{check.canPrepare ? 'Will prepare' : 'Action needed'} / {check.label}</strong>: {check.detail}</li>)}</ul>}
        <details><summary>All prerequisite checks ({native.math3dReadiness.checks.filter(check => check.ready).length}/{native.math3dReadiness.checks.length} ready)</summary>
          <ul>{native.math3dReadiness.checks.map(check => <li key={check.id}><strong>{check.ready ? 'Ready' : check.canPrepare ? 'Will prepare' : 'Action needed'} / {check.label}</strong><br />{check.detail}</li>)}</ul>
        </details>
      </>}
      <p className="scientific-runtime-note">Prepare &amp; Run copies missing fixtures from the workspace MATH3D checkout, builds its native worker, creates missing validation baselines for this profile, then runs the suite. Stop cancels the owned sequence. Missing Node.js, CGAL SDK, or C++ tools must be installed through Environment setup first.</p>
    </div>
    <div className="scientific-inspector-actions">
      <button disabled={native.busy || native.pending || !native.math3dReadiness?.canPrepare} onClick={() => native.send(runtimeId, 'math3d-prepare-run')}>Prepare &amp; Run</button>
      <button disabled={native.busy || native.pending || !native.math3dReadiness?.ready} onClick={() => native.send(runtimeId, 'math3d-integration')}>Run MATH3D integration test</button>
      <button disabled={native.pending} onClick={() => native.send(runtimeId, 'math3d-readiness')}>Check prerequisites</button>
      <button disabled={native.pending} onClick={() => { requested.current.clear(); native.send('', 'history') }}>Refresh saved verdict</button>
    </div>
    {job && <div role="status"><p><strong>Managed job: {job.state}</strong> / {job.stage ?? 'run'} / {job.durationMs} ms</p>
      <div className="scientific-inspector-actions"><button disabled={job.state !== 'running' || native.pending} onClick={() => native.send(runtimeId, 'stop', { jobId: job.jobId })}>Stop</button><button onClick={() => native.send(runtimeId, 'open-log', { jobId: job.jobId })}>Open full log</button><button onClick={() => native.send(runtimeId, 'open-output', { jobId: job.jobId })}>Open output folder</button></div>
      {job.error && <p role="alert">{job.error}</p>}
      <pre>{job.log || 'Waiting for worker output...'}</pre>
    </div>}
    {entry ? <div><h4>Saved verdict: {result?.comparison?.verdict?.toUpperCase() ?? entry.state}</h4>
      <p>{result?.comparison ? `${result.comparison.passed}/${result.comparison.total} checks passed` : 'Load the saved result to see the checks.'} / run <code>{entry.jobId}</code></p>
      {result?.comparison?.cases && <table className="scientific-mesh-statistics"><thead><tr><th>Case</th><th>Expected / actual volume</th><th>Surface shells</th><th>Verdict</th></tr></thead><tbody>{result.comparison.cases.map(item => <tr key={item.name}><th>{item.name}</th><td>{metric(item.reference?.volume)} / {metric(item.after?.volume)}</td><td>{item.after?.components ?? 'unavailable'}</td><td>{result.comparison!.checks.filter(check => check.name.startsWith(item.name + ':')).every(check => check.passed) ? 'PASS' : 'FAIL'}</td></tr>)}</tbody></table>}
      {result?.comparison?.checks && <details><summary>All {result.comparison.total} checks</summary><ul>{result.comparison.checks.map(check => <li key={check.name}>{check.passed ? 'PASS' : 'FAIL'} / {check.name}</li>)}</ul></details>}
      {result?.comparison?.cases && <details><summary>Geometry metrics and tolerances</summary>{result.comparison.cases.map(item => <p key={item.name}>{item.name}: {item.metrics ? `bounds ${metric(item.metrics.boundsDelta)} / ${metric(item.tolerances?.bounds)}, area ${metric(item.metrics.areaDelta)} / ${metric(item.tolerances?.area)}, volume ${metric(item.metrics.volumeDelta)} / ${metric(item.tolerances?.volume)}, sampled surface ${metric(item.metrics.sampledSurfaceDeviation)} / ${metric(item.tolerances?.sampledSurface)}, triangle delta ${item.metrics.triangleCountDelta}` : 'No geometry output'}</p>)}</details>}
      <button onClick={() => { native.send(runtimeId, 'history-result', { jobId: entry.jobId }); onHistory() }}>Open saved History entry</button>
      <p className="scientific-runtime-note">This run is also listed under History. Use its Result, Log, and Folder actions there after Refresh history.</p>
    </div> : <p className="scientific-runtime-note">No saved MATH3D native integration run for this profile. Check prerequisites, then choose Prepare & Run.</p>}
  </section>
}
