import { useEffect, useRef } from 'react'
import type { RuntimeProfile } from './scientificRuntimeProfiles'
import type { useScientificRuntime } from './useScientificRuntime'
import { ScientificRealMeshSuite } from './ScientificRealMeshSuite'

export function ScientificTestMatrix({ runtime, native, edited, math3dRepositoryPath }: {
  runtime: RuntimeProfile; native: ReturnType<typeof useScientificRuntime>; edited: boolean; math3dRepositoryPath?: string | null
}) {
  const requested = useRef(new Set<string>())
  const loadedHistory = useRef(native.history)
  const cases = native.testMatrix ?? []
  useEffect(() => { native.send(runtime.id, 'test-matrix') }, [runtime.id])
  useEffect(() => {
    if (loadedHistory.current !== native.history) { loadedHistory.current = native.history; requested.current.clear() }
    for (const test of cases) {
      const entry = native.history?.find(item => item.runtimeId === 'cgal-win-conda' && item.recipeId === 'cgal.validate' && item.testCaseId === test.id)
      if (entry && !native.historyResults[entry.jobId] && !requested.current.has(entry.jobId)) {
        requested.current.add(entry.jobId)
        native.send('cgal-win-conda', 'history-result', { jobId: entry.jobId })
      }
    }
  }, [native.history, native.historyResults, native.send])

  const available = runtime.id === 'cgal-win-conda' && runtime.execution === 'windows-native' && !edited
  const load = () => { native.send(runtime.id, 'test-matrix'); native.send('', 'datasets'); native.send('', 'history') }
  const summary = native.jobs[runtime.id]?.result?.matrixSummary
  return <section aria-label="CGAL test matrix">
    <ScientificRealMeshSuite runtimeId={runtime.id} native={native} available={available} repositoryPath={math3dRepositoryPath ?? null} />
    <h3>CGAL validation test matrix</h3>
    <p className="scientific-runtime-note">Manifest-declared expectations for duplicated local fixtures. Saved outcomes are recorded evidence, not live health checks. Loading the matrix never runs a recipe.</p>
    <button disabled={native.pending} onClick={load}>{native.history && native.datasets ? 'Refresh saved evidence' : 'Load local copies and saved evidence'}</button>
    {' '}<button disabled={!available || !native.datasets || !cases.length || native.busy || native.pending || cases.some(test => !native.datasets?.entries.some(item => item.id === test.datasetId))} onClick={() => native.send(runtime.id, 'run-matrix')}>Run matrix</button>
    {!cases.length && <p className="scientific-runtime-note">Load the registered Test Matrix manifest to show cases.</p>}
    {summary && <p className="scientific-runtime-note">Last managed suite: {summary.passed}/{summary.total} passed. Refresh saved evidence to see each case.</p>}
    <div className="scientific-history-scroll"><table><thead><tr><th>Case / expectation</th><th>Recorded outcome</th><th>Evidence</th><th>Actions</th></tr></thead><tbody>{cases.map(test => {
      const dataset = native.datasets?.entries.find(item => item.id === test.datasetId)
      const entry = native.history?.find(item => item.runtimeId === runtime.id && item.recipeId === 'cgal.validate' && item.testCaseId === test.id)
      const result = entry ? native.historyResults[entry.jobId] : undefined
      const input = result?.inputArtifacts?.[0]
      const matchingInput = !!dataset && input?.datasetId === dataset.id && input.sha256?.toLowerCase() === dataset.sha256.toLowerCase()
      const output = result?.artifacts?.find(item => item.path === `matrix-${test.id}.obj`)
      const reasonMatched = result?.diagnostics?.some(item => item.message.toLowerCase().includes(test.reason))
      const verdict = !dataset ? 'skip / copy unavailable' : !entry ? 'skip / not run'
        : !result ? 'loading saved result' : !matchingInput ? 'skip / input changed'
        : test.expected === 'succeeded'
          ? result.state === 'succeeded' && !!output?.sha256 && result.validatedCapabilities?.includes('mesh.validate') ? 'pass' : 'fail'
          : result.state === 'failed' && !!reasonMatched ? 'pass / expected rejection' : 'fail'
      return <tr key={test.id}>
        <td><strong>{test.name}</strong><br /><small><code>{test.datasetId}</code><br />Expected: {test.expected === 'rejected' ? `reject with “${test.reason}” diagnostic` : 'validated OBJ output'}</small></td>
        <td><strong>{verdict}</strong>{entry && <><br /><small>Saved {new Date(entry.finishedAtUtc).toLocaleString()} / {entry.state}</small></>}</td>
        <td>{result ? <small>CGAL {result.versions?.cgal ?? 'unknown'} / {result.durationMs} ms<br />Environment: <code title={result.environmentFingerprintScope ?? 'Fingerprint scope unavailable'}>{result.environmentFingerprint?.slice(0, 12) ?? 'not captured'}</code><br />Input SHA-256: <code>{input?.sha256?.slice(0, 12) ?? 'unavailable'}</code>{output && <><br />Output SHA-256: <code>{output.sha256?.slice(0, 12) ?? 'unavailable'}</code></>}</small> : <small>Load a matching saved result for versions, timing, and hashes.</small>}</td>
        <td><div className="scientific-history-actions"><button disabled={!available || !dataset || native.busy || native.pending} onClick={() => native.send(runtime.id, 'cgal-recipe', { recipeId: 'cgal.validate', parameters: { inputId: test.datasetId, outputName: `matrix-${test.id}.obj`, testCaseId: test.id } })}>Run case</button>{entry && <><button onClick={() => native.send(runtime.id, 'history-open-log', { jobId: entry.jobId })}>Log</button><button onClick={() => native.send(runtime.id, 'history-open-output', { jobId: entry.jobId })}>Folder</button>{output && <button onClick={() => native.send(runtime.id, 'history-reveal-artifact', { jobId: entry.jobId, artifactPath: output.path })}>Artifact</button>}</>}</div></td>
      </tr>
    })}</tbody></table></div>
    <p className="scientific-runtime-note">Run one case at a time, then refresh saved evidence. An expected rejection passes only when the geometry diagnostic matches; build, timeout, and missing-environment failures do not count. The fingerprint covers Conda history, the compiled worker, and its Python adapter, not the whole machine.</p>
  </section>
}
