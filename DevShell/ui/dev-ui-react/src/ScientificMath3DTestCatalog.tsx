import { useEffect, useRef, useState } from 'react'
import type { useScientificRuntime, ScientificHistoryEntry } from './useScientificRuntime'

type CatalogTest = {
  id: string
  name: string
  runtimeId: string
  recipeId: string
  action: string
  expected: string
  requires?: 'datasets' | 'matrix' | 'integration'
}

// These IDs are registered by the managed Scientific runner. A catalog entry
// describes a fixed test; it never supplies an arbitrary command or script.
const math3dTestCatalog: readonly CatalogTest[] = [
  { id: 'sage-version', name: 'SageMath installation', runtimeId: 'sage-wsl', recipeId: 'sage.version', action: 'sage-recipe', expected: 'Sage version is recorded.' },
  { id: 'sage-factor', name: 'Exact factorization', runtimeId: 'sage-wsl', recipeId: 'sage.factor-smoke', action: 'sage-recipe', expected: 'x² − 1 factors as (x − 1) × (x + 1).' },
  { id: 'cgal-matrix', name: 'CGAL validation matrix', runtimeId: 'cgal-win-conda', recipeId: 'matrix.cgal.validation', action: 'run-matrix', expected: 'Registered mesh cases match their expected verdicts.', requires: 'matrix' },
  { id: 'vtk-probe', name: 'VTK runtime probes', runtimeId: 'vtk-win-conda', recipeId: 'lab.probe', action: 'lab-probe', expected: 'Installed VTK binding and render probes report their evidence.' },
  { id: 'vtk-rejections', name: 'VTK rejection checks', runtimeId: 'vtk-win-conda', recipeId: 'matrix.vtk.rejections', action: 'vtk-rejections', expected: 'Invalid mesh requests are rejected with diagnostics.', requires: 'datasets' },
  { id: 'math3d-native', name: 'Math3D native Boolean integration', runtimeId: 'cgal-win-conda', recipeId: 'integration.math3d.native-boolean', action: 'math3d-prepare-run', expected: 'Fourteen native Boolean cases pass their saved comparisons.', requires: 'integration' },
]

const latest = (history: ScientificHistoryEntry[] | null, test: CatalogTest) =>
  history?.filter(item => item.runtimeId === test.runtimeId && item.recipeId === test.recipeId)
    .sort((a, b) => b.finishedAtUtc.localeCompare(a.finishedAtUtc))[0]

export function ScientificMath3DTestCatalog({ native, runtimeId, onHistory }: { native: ReturnType<typeof useScientificRuntime>; runtimeId: string; onHistory: () => void }) {
  const send = useRef(native.send)
  useEffect(() => { send.current = native.send }, [native.send])
  const refreshed = useRef(new Set<string>())
  const [selectedResult, setSelectedResult] = useState<string | null>(null)

  useEffect(() => {
    refreshed.current.clear()
    if (native.profileId) send.current('', 'history')
  }, [native.profileId])
  useEffect(() => {
    Object.values(native.jobs).forEach(job => {
      if (job.state === 'running' || refreshed.current.has(job.jobId)) return
      refreshed.current.add(job.jobId)
      if (math3dTestCatalog.some(test => test.runtimeId === job.runtimeId && test.recipeId === job.recipeId)) send.current('', 'history')
    })
  }, [native.jobs])

  const checkInputs = () => {
    native.send('', 'datasets')
    if (runtimeId === 'cgal-win-conda') {
      native.send(runtimeId, 'test-matrix')
      native.send(runtimeId, 'math3d-readiness')
    }
  }
  const available = (test: CatalogTest) => {
    if (test.requires === 'datasets') return !!native.datasets?.entries.length
    if (test.requires === 'matrix') return !!native.testMatrix?.length && native.testMatrix.every(item => native.datasets?.entries.some(dataset => dataset.id === item.datasetId))
    if (test.requires === 'integration') return !!native.math3dReadiness?.canPrepare
    return true
  }

  return <section className="scientific-test-catalog" aria-label="Math3D test catalog">
    <h3>Math3D test catalog</h3>
    <p>Choose a fixed test to run it as a managed job. Stop cancels that job. Completed and cancelled runs remain in this profile’s saved History.</p>
    <div className="scientific-inspector-actions">
      {runtimeId !== 'sage-wsl' && <button type="button" disabled={native.pending} onClick={checkInputs}>Check local inputs</button>}
      <button type="button" disabled={native.pending} onClick={() => native.send('', 'history')}>Refresh saved results</button>
      <button type="button" onClick={onHistory}>Open full History</button>
    </div>
    <div className="scientific-test-catalog-grid">
      {math3dTestCatalog.filter(test => test.runtimeId === runtimeId).map(test => {
        const job = native.jobs[test.runtimeId]?.recipeId === test.recipeId ? native.jobs[test.runtimeId] : undefined
        const saved = latest(native.history, test)
        const result = saved && selectedResult === saved.jobId ? native.historyResults[saved.jobId] : undefined
        const reason = test.requires === 'datasets' ? 'Import local datasets first.' : test.requires === 'matrix' ? 'Import the registered matrix datasets first.' : 'Check Math3D prerequisites first.'
        return <article key={test.id} className="scientific-test-catalog-card">
          <div className="scientific-test-catalog-heading"><h4>{test.name}</h4><code>{test.runtimeId}</code></div>
          <p>{test.expected}</p>
          <div className="scientific-inspector-actions">
            <button type="button" disabled={native.pending || native.busy || !available(test)} onClick={() => native.send(test.runtimeId, test.action, test.action === 'sage-recipe' ? { recipeId: test.recipeId } : {})}>{test.requires === 'integration' ? 'Prepare & Run' : 'Run test'}</button>
            <button type="button" disabled={job?.state !== 'running'} onClick={() => native.send(test.runtimeId, 'stop', { jobId: job?.jobId })}>Stop</button>
            {saved && <button type="button" onClick={() => { setSelectedResult(saved.jobId); native.send(test.runtimeId, 'history-result', { jobId: saved.jobId }) }}>Latest result</button>}
          </div>
          {!available(test) && <small>{reason}</small>}
          {job && <p role="status">Current: {job.state} / {job.stage ?? 'queued'}{job.error ? ` / ${job.error}` : ''}</p>}
          <p className="scientific-runtime-note">Saved: {saved ? `${saved.state} · ${new Date(saved.finishedAtUtc).toLocaleString()} · ${(saved.durationMs / 1000).toFixed(1)} s` : 'No run in this profile'}</p>
          {result && <div className="scientific-test-catalog-result" aria-label={`${test.name} saved result`}>
            <strong>{result.state.toUpperCase()}</strong> <code>{result.runId}</code>
            {result.diagnostics?.map((diagnostic, index) => <p key={index}>{diagnostic.message}</p>)}
            {result.matrixSummary && <p>{result.matrixSummary.passed}/{result.matrixSummary.total} matrix cases passed.</p>}
            {result.rejectionSummary && <p>{result.rejectionSummary.passed}/{result.rejectionSummary.total} rejection cases passed.</p>}
            {result.validatedCapabilities?.length > 0 && <p>Validated: {result.validatedCapabilities.join(', ')}</p>}
            <button type="button" onClick={onHistory}>Open in History</button>
          </div>}
        </article>
      })}
    </div>
  </section>
}
