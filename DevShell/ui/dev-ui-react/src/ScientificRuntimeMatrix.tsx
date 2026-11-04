import { useEffect } from 'react'
import type { RuntimeProfile } from './scientificRuntimeProfiles'
import type { ScientificRuntimeReport } from './scientificRuntimeReport'
import type { ScientificHistoryEntry, useScientificRuntime } from './useScientificRuntime'

type Native = ReturnType<typeof useScientificRuntime>

function failuresAfterSuccess(entries: ScientificHistoryEntry[]) {
  const byRecipe = new Map<string, ScientificHistoryEntry[]>()
  for (const entry of entries) {
    const key = `${entry.runtimeId}|${entry.recipeId}`
    byRecipe.set(key, [...(byRecipe.get(key) ?? []), entry])
  }
  return [...byRecipe.values()].flatMap(group => {
    const ordered = [...group].sort((a, b) => Date.parse(b.finishedAtUtc) - Date.parse(a.finishedAtUtc))
    const latest = ordered[0]
    const earlier = ordered.slice(1).find(entry => entry.state === 'succeeded')
    return latest && earlier && ['failed', 'partial', 'timed-out'].includes(latest.state) ? [{ latest, earlier }] : []
  })
}

export function ScientificRuntimeMatrix({ profiles, report, native, onOpenRun, onOpenProvider }: {
  profiles: RuntimeProfile[]
  report: ScientificRuntimeReport | null
  native: Native
  onOpenRun: (runtimeId: string, runId: string) => void
  onOpenProvider: (runtimeId: string, section: 'State' | 'History') => void
}) {
  const ids = profiles.map(profile => profile.id).join('|')
  useEffect(() => {
    if (!native.history) { native.send('', 'history'); return }
    for (const runtimeId of ids.split('|')) native.send(runtimeId, 'qualification-summary')
    for (const runtimeId of ids.split('|')) {
      const recent = native.history.filter(entry => entry.runtimeId === runtimeId && entry.state === 'succeeded').slice(0, 2)
      for (const entry of recent) native.send(runtimeId, 'history-result', { jobId: entry.jobId })
    }
    // The matrix refreshes its saved evidence when History changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [native.history, ids])
  const regressions = failuresAfterSuccess(native.history ?? [])
  return <section aria-label="Scientific runtime matrix" className="scientific-history">
    <h3>Runtime matrix</h3>
    <p className="scientific-runtime-note">Availability comes from the recorded local inventory. Qualification levels use verified, current runs. A failure after an earlier success is a review candidate, not a confirmed scientific regression.</p>
    <button disabled={native.pending} onClick={() => native.send('', 'history')}>Refresh saved evidence</button>
    <div className="scientific-history-scroll"><table><thead><tr><th>Provider</th><th>Availability evidence</th><th>Current capabilities</th><th>Stale or unknown records</th></tr></thead><tbody>{profiles.map(profile => {
      const inventory = report?.runtimes.find(item => item.id === profile.id)
      const summary = native.qualificationSummaries[profile.id]
      const nonCurrent = Object.values(native.historyResults).filter(item => item.runtimeId === profile.id)
        .flatMap(item => (item.qualifications ?? []).filter(record => record.status !== 'current')
          .map(record => ({ ...record, runId: item.runId }))).slice(0, 30)
      return <tr key={profile.id}>
        <td><strong>{profile.name}</strong><br /><code>{profile.id}</code></td>
        <td>{inventory ? <><strong>{inventory.state}</strong> / {inventory.version ?? 'unknown version'}<br /><small>{inventory.checks.length} recorded checks / {new Date(report!.generatedAt).toLocaleString()}</small></> : 'Inventory unavailable'}<br /><button onClick={() => onOpenProvider(profile.id, 'State')}>State evidence</button></td>
        <td>{!summary ? 'Loading verified levels...' : summary.capabilities.length ? summary.capabilities.map(capability => <div key={capability.capabilityId}><code>{capability.capabilityId}</code> <strong>{capability.highestLevel}</strong> {capability.supportingRuns.map(run => <button key={run.recordId} title={`Open run ${run.runId} / record ${run.recordId}`} onClick={() => onOpenRun(profile.id, run.runId)}>{run.runId.slice(0, 8)}</button>)}</div>) : 'No current qualification'}</td>
        <td>{summary ? <><span>{summary.excludedStaleRecords} stale / {summary.excludedUnknownRecords} unknown</span>{nonCurrent.map(record => <div key={`${record.runId}|${record.recordId}`}><code>{record.capabilityId}</code> {record.level} {record.status}: {record.staleReasons.join('; ') || 'Reason unavailable'} <button title={`Open run ${record.runId} / record ${record.recordId}`} onClick={() => onOpenRun(profile.id, record.runId)}>{record.runId.slice(0, 8)}</button></div>)}{summary.excludedStaleRecords + summary.excludedUnknownRecords > nonCurrent.length && <button onClick={() => onOpenProvider(profile.id, 'History')}>Inspect saved records</button>}</> : 'Loading verified records...'}</td>
      </tr>
    })}</tbody></table></div>
    <h4>Failures after a saved success</h4>
    {regressions.length ? <div className="scientific-history-scroll"><table><thead><tr><th>Provider / recipe</th><th>Latest failure</th><th>Earlier success</th></tr></thead><tbody>{regressions.map(({ latest, earlier }) => <tr key={`${latest.runtimeId}|${latest.recipeId}`}><td>{latest.runtimeId}<br /><code>{latest.recipeId}</code></td><td>{latest.state} <button onClick={() => onOpenRun(latest.runtimeId, latest.jobId)}>{latest.jobId.slice(0, 12)}</button></td><td><button onClick={() => onOpenRun(earlier.runtimeId, earlier.jobId)}>{earlier.jobId.slice(0, 12)}</button></td></tr>)}</tbody></table></div> : <p>No failure-after-success candidate in loaded History.</p>}
    {!native.history && <p role="status">Loading saved History before deriving verdicts...</p>}
  </section>
}
