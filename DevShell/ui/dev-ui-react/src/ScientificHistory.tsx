import type { useScientificRuntime } from './useScientificRuntime'

export function ScientificHistory({ native }: { native: ReturnType<typeof useScientificRuntime> }) {
  const entries = native.history
  const result = native.historyResult
  return <section className="scientific-history" aria-label="Scientific run history">
    <h3>Run history</h3>
    <p className="scientific-runtime-note">Completed runs for this profile are read from local result files. Loading history never starts a recipe.</p>
    <button disabled={native.pending} onClick={() => native.send('', 'history')}>{entries ? 'Refresh history' : 'Load history'}</button>
    {entries && (entries.length ? <div className="scientific-history-scroll"><table><thead><tr><th>Finished</th><th>Runtime / recipe</th><th>State</th><th>Duration</th><th>Artifacts</th><th>Actions</th></tr></thead><tbody>{entries.map(entry => <tr key={entry.jobId}>
      <td>{new Date(entry.finishedAtUtc).toLocaleString()}</td><td>{entry.runtimeId}<br /><strong>{entry.recipeId}</strong></td><td>{entry.state}</td><td>{(entry.durationMs / 1000).toFixed(1)} s</td><td>{entry.artifactCount}</td>
      <td><div className="scientific-history-actions"><button onClick={() => native.send(entry.runtimeId, 'history-result', { jobId: entry.jobId })}>Result</button><button onClick={() => native.send(entry.runtimeId, 'history-open-log', { jobId: entry.jobId })}>Log</button><button onClick={() => native.send(entry.runtimeId, 'history-open-output', { jobId: entry.jobId })}>Folder</button></div></td>
    </tr>)}</tbody></table></div> : <p>No completed runs found for this profile.</p>)}
    {result && <div className="scientific-history-result"><h4>{result.runtimeId} / {result.recipeId} / {result.state}</h4><p><code>{result.runId}</code> / {result.durationMs} ms</p>
      <h5>Artifacts</h5>{result.artifacts?.length ? <ul>{result.artifacts.map(artifact => <li key={artifact.path}><code>{artifact.path}</code> <button onClick={() => native.send(result.runtimeId, 'history-reveal-artifact', { jobId: result.runId, artifactPath: artifact.path })}>Reveal</button></li>)}</ul> : <p>No output artifacts recorded.</p>}
      <details><summary>Result contract</summary><pre>{JSON.stringify(result, null, 2)}</pre></details>
    </div>}
  </section>
}
