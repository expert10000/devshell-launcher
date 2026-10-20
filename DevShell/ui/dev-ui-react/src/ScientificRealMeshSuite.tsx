import { useEffect, useRef } from 'react'
import type { useScientificRuntime } from './useScientificRuntime'

type OperationEvidence = { operation: string; status: string; durationMs: number; metrics: { volume: number; triangles: number; bounds: number[] }; artifact?: string; artifactSha256?: string }
type CaseEvidence = { name: string; status: string; source: string; sourceSha256?: string; transformB: string; diagnostics: string[]; operations: OperationEvidence[]; invariants?: Record<string, number | boolean>; inputs?: Record<string, { sha256: string }> }
type SuiteEvidence = { worker: { version: string; recordedCgalVersion: string; sha256: string }; limits: { operationSeconds: number; totalSeconds: number; payloadMiB: number }; passed: number; total: number; cases: CaseEvidence[] }

export function ScientificRealMeshSuite({ runtimeId, native, available, repositoryPath }: {
  runtimeId: string; native: ReturnType<typeof useScientificRuntime>; available: boolean; repositoryPath: string | null
}) {
  const requested = useRef<string | null>(null)
  const saved = native.history?.find(item => item.runtimeId === runtimeId && item.recipeId === 'matrix.cgal.real-mesh')
  useEffect(() => { native.send('', 'history') }, [runtimeId])
  useEffect(() => {
    if (saved && !native.historyResults[saved.jobId] && requested.current !== saved.jobId) {
      requested.current = saved.jobId
      native.send(runtimeId, 'history-result', { jobId: saved.jobId })
    }
  }, [saved?.jobId, native.historyResults])
  const live = native.jobs[runtimeId]?.recipeId === 'matrix.cgal.real-mesh' ? native.jobs[runtimeId] : undefined
  const result = live?.result ?? (saved ? native.historyResults[saved.jobId] : undefined)
  const suite = (result as unknown as { realMeshSuite?: SuiteEvidence } | undefined)?.realMeshSuite
  const jobId = live?.jobId ?? saved?.jobId
  return <section aria-label="Real-mesh CGAL qualification" style={{ border: '1px solid #327e91', borderRadius: 8, padding: 12, marginBottom: 18 }}>
    <h3>Real-mesh qualification / opt-in</h3>
    <p>One click runs native CGAL union, intersection, and difference on copied Armadillo and 3DBenchy meshes. Nothing runs when this page opens.</p>
    <button disabled={!available || !repositoryPath || native.busy || native.pending} onClick={() => native.send(runtimeId, 'real-mesh-suite', { repositoryPath })}>Run Armadillo + 3DBenchy suite</button>{' '}
    <button disabled={native.pending} onClick={() => native.send('', 'history')}>Refresh saved evidence</button>
    {!repositoryPath && <p role="alert">Configure the Math3D repository path to enable this suite.</p>}
    {live?.state === 'running' && <p role="status">Running: {live.stage}. Use Stop in the managed-jobs bar to cancel.</p>}
    {suite ? <>
      <p><strong>{suite.passed}/{suite.total} cases passed</strong> / {result?.state ?? live?.state ?? 'recorded'} / recorded CGAL {suite.worker.recordedCgalVersion} / worker {suite.worker.version} / SHA-256 <code>{suite.worker.sha256.slice(0, 16)}</code></p>
      <p>Limits: {suite.limits.operationSeconds}s per operation, {suite.limits.totalSeconds}s total, {suite.limits.payloadMiB} MiB per request/response payload. The payload limit is not a process-RSS limit.</p>
      <div className="scientific-history-scroll"><table><thead><tr><th>Mesh pair / transform</th><th>Outcome</th><th>Operation evidence</th></tr></thead><tbody>
        {suite.cases.map(test => <tr key={test.name}><td><strong>{test.name}</strong><br /><small>{test.transformB}<br />Source SHA-256: <code>{test.sourceSha256?.slice(0, 16) ?? 'unavailable'}</code><br />A/B SHA-256: <code>{test.inputs?.A.sha256.slice(0, 12) ?? '-'}</code> / <code>{test.inputs?.B.sha256.slice(0, 12) ?? '-'}</code></small></td><td><strong>{test.status}</strong>{test.diagnostics.map((diagnostic, index) => <p key={index} role="alert">{diagnostic}</p>)}</td><td>{test.operations.map(operation => <div key={operation.operation}>{operation.operation}: {operation.durationMs} ms / {operation.metrics.triangles.toLocaleString()} triangles / volume {operation.metrics.volume.toPrecision(7)}<br /><small>Output: {operation.artifact ?? '-'} / SHA-256 {operation.artifactSha256?.slice(0, 16) ?? '-'}</small></div>)}{test.invariants && <small>Volume identities: {Number(test.invariants.differencePlusIntersection).toPrecision(7)} vs {Number(test.invariants.expectedA).toPrecision(7)}; {Number(test.invariants.unionPlusIntersection).toPrecision(7)} vs {Number(test.invariants.expectedAPlusB).toPrecision(7)}</small>}</td></tr>)}
      </tbody></table></div>
      {jobId && <div className="scientific-history-actions"><button onClick={() => native.send(runtimeId, 'history-open-output', { jobId })}>Open evidence folder</button><button onClick={() => native.send(runtimeId, 'history-open-log', { jobId })}>Open full log</button></div>}
    </> : <p>No saved real-mesh qualification result loaded. Failed cases retain diagnostics and any completed output meshes.</p>}
  </section>
}
