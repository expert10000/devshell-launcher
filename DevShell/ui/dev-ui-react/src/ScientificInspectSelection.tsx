import { useState } from 'react'
import type { InspectSelection, useScientificRuntime } from './useScientificRuntime'

export function ScientificInspectSelection({ native, onHistory }: {
  native: ReturnType<typeof useScientificRuntime>
  onHistory: () => void
}) {
  const [inputPath, setInputPath] = useState('')
  const [sharedRecord, setSharedRecord] = useState('')
  const [classRecord, setClassRecord] = useState('')
  const [manualProvider, setManualProvider] = useState('')
  const job = native.jobs['cgal-win-conda']?.recipeId === 'l9.math3d-inspect-selection'
    ? native.jobs['cgal-win-conda'] : undefined
  const saved = (job?.result as unknown as { selection?: InspectSelection } | undefined)?.selection
  const selection = saved ?? native.inspectSelection
  const ready = !!inputPath.trim() && !!(classRecord.trim() || sharedRecord.trim())
  const request = { inputPath: inputPath.trim(), sharedRecord: sharedRecord.trim() || null,
    classRecord: classRecord.trim() || null, manualProvider: manualProvider || null }
  const phases = selection?.rankingEvidence?.phases
  return <section aria-label="MATH3D inspection backend selection" className="scientific-inspector">
    <h3>MATH3D inspection backend</h3>
    <p>Choose an OBJ and a current shared or bounded class evidence record. Preview verifies desktop and broker support, shows paired uncertainty, and may abstain. Run uses the selected qualified provider or the direct MATH3D importer, then reopens the saved document and viewport.</p>
    <div className="scientific-runtime-fields">
      <label>OBJ input<input aria-label="Inspection OBJ input" value={inputPath} onChange={event => setInputPath(event.target.value)} spellCheck={false} /></label>
      <label>Bounded class record<input aria-label="Bounded inspection class record" value={classRecord} onChange={event => setClassRecord(event.target.value)} placeholder="classes.json" spellCheck={false} /></label>
      <label>Shared exact tier record<input aria-label="Shared inspection record" value={sharedRecord} onChange={event => setSharedRecord(event.target.value)} placeholder="shared-inspect.json" spellCheck={false} /></label>
      <label>Provider<select aria-label="Inspection provider override" value={manualProvider} onChange={event => setManualProvider(event.target.value)}><option value="">Automatic recommendation</option><option value="cgal-win-conda">CGAL (manual)</option><option value="vtk-win-conda">VTK (manual)</option></select></label>
    </div>
    <div className="scientific-runtime-actions">
      <button disabled={!ready || native.pending || native.busy} onClick={() => native.send('cgal-win-conda', 'inspect-selection-preview', request)}>Verify and preview</button>
      <button disabled={!ready || native.pending || native.busy} onClick={() => native.send('cgal-win-conda', 'inspect-selection-run', request)}>Run and reopen in MATH3D</button>
      {job?.state === 'running' && <button onClick={() => native.send('cgal-win-conda', 'stop', { jobId: job.jobId })}>Stop</button>}
      <button onClick={onHistory}>History</button>
    </div>
    {selection && <div role="status" className="scientific-history-result">
      <p><strong>{selection.state}</strong> / selected {selection.selectedProvider} / recommended {selection.recommendedProvider ?? 'none'} / {selection.classId ?? selection.tier ?? 'outside qualified scope'}</p>
      <p>{selection.reason}</p>
      {phases && <table><thead><tr><th>Phase</th><th>CGAL median</th><th>VTK median</th><th>Paired CGAL−VTK 95% interval</th></tr></thead><tbody>{Object.entries(phases).map(([name, phase]) => <tr key={name}><td>{name}</td><td>{phase.mediansMs['cgal-win-conda']} ms</td><td>{phase.mediansMs['vtk-win-conda']} ms</td><td>{phase.pairedCgalMinusVtk95PctMs.join(' to ')} ms</td></tr>)}</tbody></table>}
      {saved?.productFiles && <p>Saved MATH3D document, resource, M3DM, and viewport reloaded. Product artifacts: {Object.keys(saved.productFiles).join(', ')}.</p>}
    </div>}
    {job && <p role="status">Managed run {job.jobId}: {job.state} / {job.stage ?? job.state}. {job.error}</p>}
  </section>
}
