import { useState } from 'react'
import type { useScientificRuntime, ScientificHistoryEntry } from './useScientificRuntime'
import { MeshCanvas, initialCamera } from './ScientificArtifacts'
import type { Camera } from './ScientificArtifacts'
import { ScientificComparisonPresets } from './ScientificComparisonPresets'

export function ScientificHistory({ native }: { native: ReturnType<typeof useScientificRuntime> }) {
  const entries = native.history
  const result = native.historyResult
  const [comparisonIds, setComparisonIds] = useState<string[]>([])
  const [paths, setPaths] = useState<Record<string, string>>({})
  const [camera, setCamera] = useState<Camera>(initialCamera)
  const meshArtifacts = (items: { path: string }[] = []) => items.filter(item => /\.(obj|stl|ply|vtp)$/i.test(item.path))
  const toggleComparison = (entry: ScientificHistoryEntry) => {
    setComparisonIds(current => current.includes(entry.jobId) ? current.filter(id => id !== entry.jobId) : [...current.slice(-1), entry.jobId])
    setCamera(initialCamera)
    if (!native.historyResults[entry.jobId]) native.send(entry.runtimeId, 'history-result', { jobId: entry.jobId })
  }
  const loadPreview = (jobId: string, runtimeId: string, path: string) => {
    setPaths(previous => ({ ...previous, [jobId]: path }))
    setComparisonIds(current => current.includes(jobId) ? current : [...current.slice(-1), jobId])
    native.send(runtimeId, 'history-preview', { jobId, artifactPath: path })
  }
  const comparison = comparisonIds.map(jobId => {
    const entry = entries?.find(item => item.jobId === jobId)
    const saved = native.historyResults[jobId]
    const artifacts = meshArtifacts(saved?.artifacts)
    const path = artifacts.some(item => item.path === paths[jobId]) ? paths[jobId] : artifacts[0]?.path ?? ''
    return { jobId, entry, artifacts, path, preview: native.historyPreviews[`${jobId}|${path}`] }
  })
  const meshes = comparison.flatMap(item => item.preview ? [item.preview.geometry.after] : [])
  const bounds = meshes.length ? [0, 1, 2].flatMap(axis => [Math.min(...meshes.map(mesh => mesh.bounds[axis * 2])), Math.max(...meshes.map(mesh => mesh.bounds[axis * 2 + 1]))]) : [0, 1, 0, 1, 0, 1]
  return <section className="scientific-history" aria-label="Scientific run history">
    <h3>Run history</h3>
    <ScientificComparisonPresets native={native} />
    <p className="scientific-runtime-note">Completed runs for this profile are read from local result files. Loading history never starts a recipe.</p>
    <button disabled={native.pending} onClick={() => native.send('', 'history')}>{entries ? 'Refresh history' : 'Load history'}</button>
    {entries && (entries.length ? <div className="scientific-history-scroll"><table><thead><tr><th>Finished</th><th>Runtime / recipe</th><th>State</th><th>Duration</th><th>Artifacts</th><th>Actions</th></tr></thead><tbody>{entries.map(entry => <tr key={entry.jobId}>
      <td>{new Date(entry.finishedAtUtc).toLocaleString()}</td><td>{entry.runtimeId}<br /><strong>{entry.recipeId}</strong></td><td>{entry.state}</td><td>{(entry.durationMs / 1000).toFixed(1)} s</td><td>{entry.artifactCount}</td>
      <td><div className="scientific-history-actions"><button onClick={() => native.send(entry.runtimeId, 'history-result', { jobId: entry.jobId })}>Result</button><button onClick={() => native.send(entry.runtimeId, 'history-open-log', { jobId: entry.jobId })}>Log</button><button onClick={() => native.send(entry.runtimeId, 'history-open-output', { jobId: entry.jobId })}>Folder</button><button disabled={entry.state !== 'succeeded' || !entry.artifactCount} aria-pressed={comparisonIds.includes(entry.jobId)} onClick={() => toggleComparison(entry)}>{comparisonIds.includes(entry.jobId) ? 'Selected' : 'Compare'}</button></div></td>
    </tr>)}</tbody></table></div> : <p>No completed runs found for this profile.</p>)}
    {result && <div className="scientific-history-result"><h4>{result.runtimeId} / {result.recipeId} / {result.state}</h4><p><code>{result.runId}</code> / {result.durationMs} ms</p>
      <h5>Artifacts</h5>{result.artifacts?.length ? <ul>{result.artifacts.map(artifact => <li key={artifact.path}><code>{artifact.path}</code> <button onClick={() => native.send(result.runtimeId, 'history-reveal-artifact', { jobId: result.runId, artifactPath: artifact.path })}>Reveal</button> {meshArtifacts([artifact]).length > 0 && <button disabled={native.pending} onClick={() => loadPreview(result.runId, result.runtimeId, artifact.path)}>Preview</button>}</li>)}</ul> : <p>No output artifacts recorded.</p>}
      <details><summary>Result contract</summary><pre>{JSON.stringify(result, null, 2)}</pre></details>
    </div>}
    {comparison.length > 0 && <div className="scientific-history-result"><h4>Compare saved outputs</h4><p className="scientific-runtime-note">Select up to two successful runs. Previews use the same camera and bounds; this is visual comparison, not mesh registration or a numeric geometry diff.</p><button onClick={() => { setComparisonIds([]); setCamera(initialCamera) }}>Clear comparison</button><button onClick={() => setCamera(initialCamera)}>Reset camera</button>
      <div className="scientific-history-compare-grid">{comparison.map((item, index) => <div className="scientific-history-compare-card" key={item.jobId}>
        <h5>Run {index + 1}: {item.entry?.runtimeId} / {item.entry?.recipeId}</h5><small>{item.jobId}</small>
        {item.artifacts.length ? <><label>Output mesh<select value={item.path} onChange={event => setPaths(previous => ({ ...previous, [item.jobId]: event.target.value }))}>{item.artifacts.map(artifact => <option key={artifact.path} value={artifact.path}>{artifact.path}</option>)}</select></label><button disabled={!item.path || native.pending} onClick={() => loadPreview(item.jobId, item.entry?.runtimeId ?? '', item.path)}>{item.preview ? 'Reload preview' : 'Load preview'}</button></> : <p>{item.entry ? 'Load the run result to see its mesh outputs.' : 'Run is no longer in the current history list.'}</p>}
        {item.preview && <MeshCanvas mesh={item.preview.geometry.after} camera={camera} setCamera={setCamera} bounds={bounds} after={index === 1} label={`Run ${index + 1} / output`} />}
      </div>)}</div>
    </div>}
  </section>
}
