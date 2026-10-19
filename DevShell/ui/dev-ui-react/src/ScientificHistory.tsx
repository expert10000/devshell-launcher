import { useEffect, useRef, useState } from 'react'
import type { useScientificRuntime, ScientificHistoryEntry } from './useScientificRuntime'
import { MeshCanvas, initialCamera, ScientificMeshInspection } from './ScientificArtifacts'
import type { Camera } from './ScientificArtifacts'
import { ScientificComparisonPresets } from './ScientificComparisonPresets'

const metric = (value: number | null | undefined) => typeof value === 'number' && Number.isFinite(value) ? value.toPrecision(4) : 'unavailable'

function HistoryThumbnail({ entry, native, onPreview }: { entry: ScientificHistoryEntry; native: ReturnType<typeof useScientificRuntime>; onPreview: () => void }) {
  const button = useRef<HTMLButtonElement>(null)
  const send = useRef(native.send); send.current = native.send
  const key = `${entry.jobId}|${entry.thumbnailPath}`
  const thumbnail = native.historyThumbnails[key]
  useEffect(() => {
    if (!button.current || !entry.thumbnailPath || thumbnail) return
    let requested = false
    const observer = new IntersectionObserver(items => {
      if (!items.some(item => item.isIntersecting) || requested) return
      requested = true
      send.current(entry.runtimeId, 'history-thumbnail', { jobId: entry.jobId, artifactPath: entry.thumbnailPath })
      observer.disconnect()
    })
    observer.observe(button.current)
    return () => observer.disconnect()
  }, [entry.jobId, entry.runtimeId, entry.thumbnailPath, thumbnail])
  if (!entry.thumbnailPath) return <span className="scientific-history-no-thumbnail">-</span>
  return <button ref={button} className="scientific-history-thumbnail" onClick={onPreview} title={`Preview ${entry.thumbnailPath}`} aria-label={`Preview image from ${entry.runtimeId} / ${entry.recipeId}`}>
    {thumbnail?.dataUrl ? <img src={thumbnail.dataUrl} alt="Saved render thumbnail" /> : <span>{thumbnail?.error ? 'Preview image' : 'Loading image...'}</span>}
  </button>
}

export function ScientificHistory({ native }: { native: ReturnType<typeof useScientificRuntime> }) {
  const entries = native.history
  const [runtimeFilter, setRuntimeFilter] = useState('')
  const [stateFilter, setStateFilter] = useState('')
  const runtimeOptions = [...new Set((entries ?? []).map(entry => entry.runtimeId))].sort()
  const filteredEntries = entries?.filter(entry => (!runtimeFilter || entry.runtimeId === runtimeFilter) && (!stateFilter || entry.state === stateFilter))
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null)
  const selectedVisible = !!selectedJobId && !!filteredEntries?.some(entry => entry.jobId === selectedJobId)
  const result = selectedVisible && selectedJobId ? native.historyResults[selectedJobId] ?? null : null
  const [imageSelection, setImageSelection] = useState<{ jobId: string; path: string } | null>(null)
  const imagePreview = imageSelection ? native.historyImages[`${imageSelection.jobId}|${imageSelection.path}`] : undefined
  const [imageError, setImageError] = useState('')
  const resultRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (selectedJobId && result?.runId === selectedJobId) resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [selectedJobId, result?.runId])
  const [comparisonOpen, setComparisonOpen] = useState(false)
  const [comparisonIds, setComparisonIds] = useState<string[]>([])
  const [paths, setPaths] = useState<Record<string, string>>({})
  const [camera, setCamera] = useState<Camera>(initialCamera)
  const meshArtifacts = (items: { path: string; role?: string }[] = []) => items.filter(item => item.role !== 'operand' && /\.(obj|stl|ply|vtp|m3dm)$/i.test(item.path))
  const toggleComparison = (entry: ScientificHistoryEntry) => {
    setComparisonOpen(true)
    setComparisonIds(current => current.includes(entry.jobId) ? current.filter(id => id !== entry.jobId) : [...current.slice(-1), entry.jobId])
    setCamera(initialCamera)
    if (!native.historyResults[entry.jobId]) native.send(entry.runtimeId, 'history-result', { jobId: entry.jobId })
  }
  const loadPreview = (jobId: string, runtimeId: string, path: string) => {
    setComparisonOpen(true)
    setPaths(previous => ({ ...previous, [jobId]: path }))
    setComparisonIds(current => current.includes(jobId) ? current : [...current.slice(-1), jobId])
    native.send(runtimeId, 'history-preview', { jobId, artifactPath: path })
  }
  const comparison = comparisonIds.map(jobId => {
    const entry = entries?.find(item => item.jobId === jobId)
    const saved = native.historyResults[jobId]
    const artifacts = meshArtifacts(saved?.artifacts)
    const path = artifacts.some(item => item.path === paths[jobId]) ? paths[jobId] : artifacts[0]?.path ?? ''
    return { jobId, entry, saved, artifacts, path, preview: native.historyPreviews[`${jobId}|${path}`] }
  })
  const meshes = comparison.flatMap(item => item.preview ? [item.preview.geometry.after] : [])
  const bounds = meshes.length ? [0, 1, 2].flatMap(axis => [Math.min(...meshes.map(mesh => mesh.bounds[axis * 2])), Math.max(...meshes.map(mesh => mesh.bounds[axis * 2 + 1]))]) : [0, 1, 0, 1, 0, 1]
  const first = comparison[0]?.saved, second = comparison[1]?.saved
  const firstInputHash = first?.inputArtifacts?.[0]?.sha256, secondInputHash = second?.inputArtifacts?.[0]?.sha256
  const sameValidation = first?.state === 'succeeded' && second?.state === 'succeeded'
    && first.runtimeId === 'cgal-win-conda' && second.runtimeId === first.runtimeId
    && first.recipeId === 'cgal.validate' && second.recipeId === first.recipeId
    && !!firstInputHash && firstInputHash === secondInputHash
  const firstOutputHash = first?.artifacts?.find(item => item.path === comparison[0]?.path)?.sha256
  const secondOutputHash = second?.artifacts?.find(item => item.path === comparison[1]?.path)?.sha256
  const integration = result?.recipeId === 'integration.math3d.native-boolean'
    ? (result as typeof result & { comparison?: { verdict: string; passed: number; total: number; checks: { name: string; passed: boolean }[]; cases?: { name: string; before: { faces: number }; reference?: { bounds: number[] | null; volume: number }; after?: { faces: number; bounds: number[] | null; volume: number }; metrics?: { boundsDelta: number | null; areaDelta: number | null; volumeDelta: number | null; sampledSurfaceDeviation: number | null }; tolerances?: { bounds: number; area: number; volume: number; sampledSurface: number } }[] } }).comparison
    : undefined
  return <section className="scientific-history" aria-label="Scientific run history">
    <h3>Run history</h3>
    <details className="scientific-history-presets"><summary>Prepare comparable runs</summary><ScientificComparisonPresets native={native} /></details>
    <p className="scientific-runtime-note">Completed runs for this profile are read from local result files. Loading history never starts a recipe.</p>
    <button disabled={native.pending} onClick={() => native.send('', 'history')}>{entries ? 'Refresh history' : 'Load history'}</button>
    {entries && (entries.length ? <>
      <div className="scientific-history-filters"><label>Runtime<select aria-label="History runtime filter" value={runtimeFilter} onChange={event => setRuntimeFilter(event.target.value)}><option value="">All runtimes</option>{runtimeOptions.map(runtime => <option key={runtime} value={runtime}>{runtime}</option>)}</select></label><label>Status<select aria-label="History status filter" value={stateFilter} onChange={event => setStateFilter(event.target.value)}><option value="">All statuses</option>{['succeeded', 'failed', 'cancelled', 'timed-out'].map(state => <option key={state} value={state}>{state}</option>)}</select></label><button disabled={!runtimeFilter && !stateFilter} onClick={() => { setRuntimeFilter(''); setStateFilter('') }}>Clear filters</button><span role="status">{filteredEntries?.length} of {entries.length} runs</span></div>
      {filteredEntries?.length ? <div className="scientific-history-scroll"><table><thead><tr><th>Preview</th><th>Finished</th><th>Runtime / recipe</th><th>State</th><th>Duration</th><th>Artifacts</th><th>Actions</th></tr></thead><tbody>{filteredEntries.map(entry => <tr key={entry.jobId}>
      <td><HistoryThumbnail entry={entry} native={native} onPreview={() => {
        if (!entry.thumbnailPath) return
        setSelectedJobId(entry.jobId); setImageSelection({ jobId: entry.jobId, path: entry.thumbnailPath }); setImageError('')
        native.send(entry.runtimeId, 'history-result', { jobId: entry.jobId })
        native.send(entry.runtimeId, 'history-image-preview', { jobId: entry.jobId, artifactPath: entry.thumbnailPath })
      }} /></td><td>{new Date(entry.finishedAtUtc).toLocaleString()}</td><td>{entry.runtimeId}<br /><strong>{entry.recipeId}</strong></td><td>{entry.state}</td><td>{(entry.durationMs / 1000).toFixed(1)} s</td><td>{entry.artifactCount}</td>
      <td><div className="scientific-history-actions"><button aria-pressed={selectedJobId === entry.jobId} onClick={() => { setSelectedJobId(entry.jobId); native.send(entry.runtimeId, 'history-result', { jobId: entry.jobId }) }}>{selectedJobId === entry.jobId ? 'Viewing' : 'Result'}</button><button onClick={() => native.send(entry.runtimeId, 'history-open-log', { jobId: entry.jobId })}>Log</button><button onClick={() => native.send(entry.runtimeId, 'history-open-output', { jobId: entry.jobId })}>Folder</button><button disabled={entry.state !== 'succeeded' || !(entry.meshArtifactCount ?? entry.artifactCount)} aria-pressed={comparisonIds.includes(entry.jobId)} onClick={() => toggleComparison(entry)}>{comparisonIds.includes(entry.jobId) ? 'Selected' : 'Compare'}</button></div></td>
    </tr>)}</tbody></table></div> : <p role="status">No runs match these filters. Clear filters to show all runs.</p>}
    </> : <p>No completed runs found for this profile.</p>)}
    {selectedVisible && !result && <div className="scientific-history-result" role="status">Loading result <code>{selectedJobId}</code>...</div>}
    {result && <div ref={resultRef} className="scientific-history-result"><h4>{result.runtimeId} / {result.recipeId} / {result.state}</h4><p><code>{result.runId}</code> / {result.durationMs} ms</p>
      {integration && <section aria-label="MATH3D integration verdict"><h5>Native worker comparison: {integration.verdict.toUpperCase()} / {integration.passed}/{integration.total}</h5><p className="scientific-runtime-note">MATH3D native Boolean operations and DevShell validation are different operations. Surface deviation samples vertices, edge midpoints, and face centroids; it is not a full Hausdorff proof.</p><details><summary>All {integration.total} checks</summary><ul>{integration.checks.map(check => <li key={check.name}>{check.passed ? 'PASS' : 'FAIL'} / {check.name}</li>)}</ul></details>
        <details><summary>Numeric comparisons by case</summary>{integration.cases?.map(item => <div key={item.name}><h5>{item.name} numeric comparison</h5>{item.reference && <p>Expected volume {item.reference.volume.toPrecision(6)}; actual {item.after?.volume.toPrecision(6) ?? 'none'}. Expected bounds [{item.reference.bounds?.join(', ') ?? 'empty'}]; actual [{item.after?.bounds?.join(', ') ?? (item.after ? 'empty' : 'none')}].</p>}{item.metrics && item.tolerances ? <table><thead><tr><th>Measure</th><th>Delta</th><th>Tolerance</th></tr></thead><tbody>
          <tr><td>Bounds</td><td>{metric(item.metrics.boundsDelta)}</td><td>{item.tolerances.bounds.toPrecision(4)}</td></tr>
          <tr><td>Surface area</td><td>{metric(item.metrics.areaDelta)}</td><td>{item.tolerances.area.toPrecision(4)}</td></tr>
          <tr><td>Enclosed volume</td><td>{metric(item.metrics.volumeDelta)}</td><td>{item.tolerances.volume.toPrecision(4)}</td></tr>
          <tr><td>Sampled surface</td><td>{metric(item.metrics.sampledSurfaceDeviation)}</td><td>{item.tolerances.sampledSurface.toPrecision(4)}</td></tr>
          <tr><td>Triangles</td><td>{item.before.faces} / {item.after?.faces ?? 'none'}</td><td>Topology checked separately</td></tr>
        </tbody></table> : <p>No geometry output recorded.</p>}</div>)}</details>
      </section>}
      {result.boolean && <p><strong>{result.boolean.operation.toUpperCase()}</strong> / {result.boolean.empty ? 'Empty result' : `Volume ${result.after?.volume ?? 'unavailable'}`} / Mesh B scale {result.boolean.scaleB}, offset [{result.boolean.translateB.join(', ')}]. Retained input snapshots reopen the same operands used for this run.</p>}
      <h5>Artifacts</h5>{result.artifacts?.length ? <ul className="scientific-history-artifacts">{result.artifacts.map(artifact => <li key={artifact.path}>
        <code>{artifact.path}</code>{artifact.bytes !== undefined && <small>{artifact.bytes.toLocaleString()} bytes</small>}
        <div className="scientific-history-actions">
          {meshArtifacts([artifact]).length > 0 && <button disabled={native.pending} onClick={() => loadPreview(result.runId, result.runtimeId, artifact.path)}>Preview mesh</button>}
          {/\.png$/i.test(artifact.path) && <button disabled={native.pending} onClick={() => { setImageSelection({ jobId: result.runId, path: artifact.path }); setImageError(''); native.send(result.runtimeId, 'history-image-preview', { jobId: result.runId, artifactPath: artifact.path }) }}>Preview image</button>}
          <button title="Open with the default application" onClick={() => native.send(result.runtimeId, 'history-open-artifact', { jobId: result.runId, artifactPath: artifact.path })}>Open</button>
          <button onClick={() => native.send(result.runtimeId, 'history-reveal-artifact', { jobId: result.runId, artifactPath: artifact.path })}>Reveal in folder</button>
        </div>
        {artifact.recoveredFromLegacyRun && <small>Recovered from a legacy run; size and hash checked when History loads.</small>}
      </li>)}</ul> : <p>No output artifacts recorded.</p>}
      {imageSelection?.jobId === result.runId && <figure className="scientific-history-image" aria-label="Saved artifact image preview">
        <figcaption><code>{imageSelection.path}</code><button onClick={() => setImageSelection(null)}>Close preview</button></figcaption>
        {imagePreview ? <img src={imagePreview.image.dataUrl} alt={`VTK render: ${imageSelection.path}`} onError={() => setImageError('The saved image could not be displayed. Use Open or Reveal in folder.')} /> : <p role="status">{native.pending ? 'Loading image preview...' : 'Image preview unavailable. Check the error above, or retry Preview image.'}</p>}
        {imageError && <p role="alert">{imageError}</p>}
      </figure>}
      <details><summary>Result contract</summary><pre>{JSON.stringify(result, null, 2)}</pre></details>
    </div>}
    {comparison.length > 0 && <details className="scientific-history-result" open={comparisonOpen} onToggle={event => setComparisonOpen(event.currentTarget.open)}><summary>Compare saved outputs ({comparison.length} selected)</summary><p className="scientific-runtime-note">Select up to two successful runs. Boolean runs include A/B/result inspection controls; other output previews share a camera and bounds. This is visual comparison, not mesh registration.</p><button onClick={() => { setComparisonIds([]); setCamera(initialCamera) }}>Clear comparison</button>{comparison.some(item => !item.preview?.geometry.beforeSecond) && <button onClick={() => setCamera(initialCamera)}>Reset camera</button>}
      {comparison.length === 2 && <div className="scientific-history-result" aria-label="Validation reproducibility evidence"><h5>Validation reproducibility evidence</h5>
        {!first || !second ? <p>Load both run results to compare their recorded hashes.</p>
          : !sameValidation ? <p>Choose two successful CGAL validation runs of the same registered input. Other pairs are not a reproducibility check.</p>
          : !firstOutputHash || !secondOutputHash ? <p>The input hashes match, but a recorded output hash is unavailable.</p>
          : <p>Input SHA-256 matches. Output bytes are {firstOutputHash === secondOutputHash ? 'identical' : 'different'} across two runs. Durations: {first.durationMs} ms / {second.durationMs} ms. {firstOutputHash !== secondOutputHash && 'Different bytes do not by themselves establish a geometry difference.'}</p>}
      </div>}
      <div className="scientific-history-compare-grid">{comparison.map((item, index) => <div className="scientific-history-compare-card" key={item.jobId}>
        <h5>Run {index + 1}: {item.entry?.runtimeId} / {item.entry?.recipeId}</h5><small>{item.jobId}</small>
        {item.artifacts.length ? <><label>Output mesh<select value={item.path} onChange={event => setPaths(previous => ({ ...previous, [item.jobId]: event.target.value }))}>{item.artifacts.map(artifact => <option key={artifact.path} value={artifact.path}>{artifact.path}</option>)}</select></label><button disabled={!item.path || native.pending} onClick={() => loadPreview(item.jobId, item.entry?.runtimeId ?? '', item.path)}>{item.preview ? 'Reload preview' : 'Load preview'}</button></> : <p>{item.entry ? 'Load the run result to see its mesh outputs.' : 'Run is no longer in the current history list.'}</p>}
        {item.preview && (item.preview.geometry.beforeSecond ? <ScientificMeshInspection key={`${item.jobId}|${item.path}`} geometry={item.preview.geometry} /> : <MeshCanvas mesh={item.preview.geometry.after} camera={camera} setCamera={setCamera} bounds={bounds} after={index === 1} label={`Run ${index + 1} / output`} />)}
      </div>)}</div>
    </details>}
  </section>
}
