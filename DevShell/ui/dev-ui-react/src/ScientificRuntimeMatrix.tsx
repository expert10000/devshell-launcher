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
    native.send('', 'ci-matrix')
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
    <section aria-label="Selective requalification">
      <h4>Selective requalification</h4>
      <p>Preview a sealed plan from the oldest of the latest five L9 source snapshots. Selected managed suites run in dependency order and stop at the first failed qualification.</p>
      <button disabled={native.pending || native.busy} onClick={() => native.send('', 'retest-plan')}>Preview retest plan</button>
      {native.retestPlan && <><p>Plan <code>{native.retestPlan.planId}</code> / baseline <code>{native.retestPlan.baseline}</code> / {native.retestPlan.suites.length} selected suites. {native.retestPlan.execution?.state ?? 'Ready to run'}.</p>
        {native.retestPlan.unmappedChanges.length > 0 && <p role="status">Unmapped changes select all suites: {native.retestPlan.unmappedChanges.join(', ')}</p>}
        <button disabled={native.pending || native.busy || native.retestPlan.execution?.state === 'running'} onClick={() => native.send('', 'retest-start', { planId: native.retestPlan!.planId })}>Run managed suites</button>
        <button disabled={native.pending || native.retestPlan.execution?.state !== 'running'} onClick={() => native.send('', 'retest-stop', { planId: native.retestPlan!.planId })}>Stop retest</button>
        <button disabled={native.pending} onClick={() => native.send('', 'retest-status', { planId: native.retestPlan!.planId })}>Refresh plan status</button>
        <div className="scientific-history-scroll"><table><thead><tr><th>Suite</th><th>Reason</th><th>Action and result</th></tr></thead><tbody>{native.retestPlan.suites.map(suite => { const result = native.retestPlan!.execution?.suites.find(item => item.id === suite.id); return <tr key={suite.id}><td><code>{suite.id}</code></td><td>{suite.reasons.join('; ')}</td><td>{suite.managedAction ?? suite.runner} / {result?.state ?? 'pending'} {result?.runId && <button onClick={() => onOpenRun(suite.provider, result.runId!)}>{result.runId.slice(0, 8)}</button>}</td></tr> })}</tbody></table></div>
      </>}
    </section>
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
    <h4>Imported CI evidence</h4>
    <p className="scientific-runtime-note">CI bundles are shown separately from local qualification. Agent authentication and applicability were checked at import; reimport after suite or environment changes.</p>
    <button disabled={native.pending} onClick={() => native.send('', 'ci-matrix')}>Refresh CI imports</button>
    {native.ciMatrix?.length ? <div className="scientific-history-scroll"><table><thead><tr><th>Agent / host</th><th>Provider / capability</th><th>CI verdict</th><th>Evidence</th></tr></thead><tbody>{native.ciMatrix.map(item => <tr key={item.bundleId}><td>{item.agentId}<br /><code>{item.hostFingerprintSha256.slice(0, 12)}</code> / {item.gpuAgent ? 'GPU agent' : 'CPU agent'}</td><td>{item.runtimeId}<br /><code>{item.capabilityId}</code></td><td>{item.jobState} / {item.applicability}{item.reasons.length > 0 && <small> / {item.reasons.join('; ')}</small>}</td><td><details><summary>Bundle {item.bundleId.slice(0, 12)}</summary><div>Source job <code>{item.sourceJobId}</code></div><div>Qualification <code>{item.certificationRecordId}</code></div><div>Suite <code>{item.suiteRevisionSha256}</code></div><div>Environment <code>{item.environmentFingerprintSha256}</code></div><div>Full bundle SHA-256 <code>{item.bundleId}</code></div></details></td></tr>)}</tbody></table></div> : <p>{native.ciMatrix ? 'No authenticated CI bundles imported.' : 'Loading CI imports...'}</p>}
    {!native.history && <p role="status">Loading saved History before deriving verdicts...</p>}
  </section>
}
