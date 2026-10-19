import { useEffect, useState } from 'react'
import type { useScientificRuntime } from './useScientificRuntime'
import type { RuntimeProfile } from './scientificRuntimeProfiles'
import { ScientificMeshInspection } from './ScientificMeshViewer'
export { MeshCanvas, initialCamera, ScientificMeshInspection } from './ScientificMeshViewer'
export type { Camera } from './ScientificMeshViewer'
import './ScientificArtifacts.css'

type CaseMeshStats = { vertices: number; faces: number; boundaryEdges: number; nonManifoldEdges: number; closed: boolean; volume: number; bounds: number[] | null }

export function ScientificArtifacts({ runtime, native }: { runtime: RuntimeProfile; native: ReturnType<typeof useScientificRuntime> }) {
  const job = native.jobs[runtime.id]
  const [selected, setSelected] = useState('')
  useEffect(() => { setSelected('') }, [runtime.id, job?.jobId])
  const artifacts = (job?.result?.artifacts ?? []).filter(item => item.role !== 'operand' && /\.(obj|stl|ply|vtp|m3dm)$/i.test(item.path))
  const path = artifacts.some(item => item.path === selected) ? selected : artifacts[0]?.path ?? ''
  const cached = native.previews[runtime.id]
  const preview = cached?.jobId === job?.jobId && cached?.artifactPath === path ? cached : null
  const result = job?.result
  const selectedCase = result?.recipeId === 'integration.math3d.native-boolean'
    ? (result as typeof result & { comparison?: { cases?: { name: string; outputArtifact: string | null; before: CaseMeshStats; reference?: { volume: number; bounds: number[] | null }; after?: CaseMeshStats }[] } }).comparison?.cases?.find(item => item.outputArtifact === path)
    : undefined
  const beforeStats: Record<string, number | boolean> | undefined = selectedCase ? {
    points: selectedCase.before.vertices, triangles: selectedCase.before.faces,
    boundaryEdges: selectedCase.before.boundaryEdges, nonManifoldEdges: selectedCase.before.nonManifoldEdges,
    closed: selectedCase.before.closed,
  } : result?.before
  const afterStats: Record<string, number | boolean> | undefined = selectedCase?.after ? {
    points: selectedCase.after.vertices, triangles: selectedCase.after.faces,
    boundaryEdges: selectedCase.after.boundaryEdges, nonManifoldEdges: selectedCase.after.nonManifoldEdges,
    closed: selectedCase.after.closed,
  } : result?.after
  return <section className="scientific-artifacts" aria-label="Scientific mesh artifacts">
    <h3>Mesh comparison / run artifacts</h3>
    {!job ? <p>No managed run in this session. Use Commands to run a mesh recipe; opening this page does not execute anything.</p> : <>
      <p><strong>{job.recipeId} / {job.state}</strong> / {job.durationMs} ms / <code>{job.jobId}</code></p>
      <div className="scientific-artifact-toolbar"><label>Output artifact<select aria-label="Scientific output artifact" value={path} onChange={event => { setSelected(event.target.value) }}><option value="">Select geometry...</option>{artifacts.map(item => <option key={item.path} value={item.path}>{item.path}</option>)}</select></label>
        <button disabled={!path || job.state !== 'succeeded' || native.pending} onClick={() => native.send(runtime.id, 'artifacts', { jobId: job.jobId, artifactPath: path })}>{native.pending ? 'Loading...' : 'Load comparison'}</button>
        <button onClick={() => native.send(runtime.id, 'open-output', { jobId: job.jobId })}>Open output folder</button><button onClick={() => native.send(runtime.id, 'open-log', { jobId: job.jobId })}>Open full log</button>
      </div>
      {!artifacts.length && <p>No previewable geometry in this run. Failed, cancelled, and timed-out runs do not advertise successful output artifacts.</p>}
      {preview && <>
        {selectedCase?.reference && <div className="scientific-mesh-target"><strong>{selectedCase.name}: expected versus actual</strong><span>Volume: {selectedCase.reference.volume.toPrecision(6)} / {selectedCase.after?.volume.toPrecision(6) ?? 'not recorded'}</span><span>Bounds: [{selectedCase.reference.bounds?.join(', ') ?? 'empty'}] / [{selectedCase.after?.bounds?.join(', ') ?? (selectedCase.after ? 'empty' : 'not recorded')}]</span></div>}
        <ScientificMeshInspection key={`${preview.jobId}|${preview.artifactPath}`} geometry={preview.geometry} />
      </>}
      {result && <><table className="scientific-mesh-statistics"><thead><tr><th>Recorded statistic</th><th>Before</th><th>After</th><th>Change</th></tr></thead><tbody>{['points', 'triangles', 'boundaryEdges', 'nonManifoldEdges', 'closed'].map(name => {
        const before = beforeStats?.[name], after = afterStats?.[name]
        if (before === undefined && after === undefined) return null
        return <tr key={name}><th>{name}</th><td>{String(before ?? 'Not recorded')}</td><td>{String(after ?? 'Not recorded')}</td><td>{typeof before === 'number' && typeof after === 'number' ? (after - before).toLocaleString() : 'Not applicable'}</td></tr>
      })}</tbody></table><p className="scientific-runtime-note">{result.scope}</p>
        {result.diagnostics.length > 0 && <ul>{result.diagnostics.map((item, index) => <li key={index}>{item.severity}: {item.message}</li>)}</ul>}
        <details><summary>Artifact hashes and input provenance</summary><pre>{JSON.stringify({ inputArtifacts: result.inputArtifacts, artifacts: result.artifacts, provenance: result.provenance }, null, 2)}</pre></details>
        <details><summary>Shared request / result contract</summary><h4>Request</h4><pre>{JSON.stringify(job.request, null, 2)}</pre><h4>Result</h4><pre>{JSON.stringify(result, null, 2)}</pre></details></>}
    </>}
    <p className="scientific-runtime-note">Read-only OBJ/STL/PLY/VTP/M3DM previews require the dedicated VTK environment. At most 12,000 sampled triangles per view; statistics describe the full worker geometry. No file content is executed, no external resources are fetched, and meshes are not saved in profile restoration.</p>
  </section>
}
