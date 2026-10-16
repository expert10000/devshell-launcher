import { useState } from 'react'
import type { useScientificRuntime } from './useScientificRuntime'

export function ScientificComparisonPresets({ native }: { native: ReturnType<typeof useScientificRuntime> }) {
  const [datasetId, setDatasetId] = useState('')
  const [targetEdge, setTargetEdge] = useState('0.1')
  const [iterations, setIterations] = useState(1)
  const [preserveBoundary, setPreserveBoundary] = useState(true)
  const datasets = (native.datasets?.entries ?? []).filter(item => !item.expectedProblem && /\.(obj|stl|ply|off)$/i.test(item.path))
  const selectedId = datasets.some(item => item.id === datasetId) ? datasetId : datasets[0]?.id ?? ''
  const edge = Number(targetEdge)
  const validEdge = Number.isFinite(edge) && edge > 0 && edge <= 1000000
  const validIterations = Number.isInteger(iterations) && iterations >= 1 && iterations <= 10
  const disabled = !selectedId || native.pending || native.busy
  const run = (recipeId: 'cgal.validate' | 'cgal.remesh') => {
    if (!selectedId || native.pending || native.busy || (recipeId === 'cgal.remesh' && (!validEdge || !validIterations))) return
    native.send('cgal-win-conda', 'cgal-recipe', {
      recipeId,
      parameters: {
        inputId: selectedId,
        outputName: recipeId === 'cgal.validate' ? 'preset-baseline.obj' : 'preset-remesh.obj',
        ...(recipeId === 'cgal.remesh' ? { targetEdge: edge, iterations, preserveBoundary } : {}),
      },
    })
  }
  return <section className="scientific-comparison-presets" aria-label="Comparison run presets">
    <h4>Prepare two comparable runs</h4>
    <p className="scientific-runtime-note">Both presets use the same registered local mesh and the Windows Native CGAL worker. Run them one at a time; neither runs when this section opens.</p>
    <button disabled={native.pending} onClick={() => native.send('', 'datasets')}>{native.datasets ? 'Reload local mesh copies' : 'Load local mesh copies'}</button>
    <div className="scientific-comparison-preset-fields">
      <label>Input mesh<select aria-label="Comparison input mesh" value={selectedId} onChange={event => setDatasetId(event.target.value)} disabled={!datasets.length}>{!datasets.length && <option value="">Load registered mesh copies first</option>}{datasets.map(item => <option key={item.id} value={item.id}>{item.category} / {item.name}</option>)}</select></label>
      <label>Remesh target edge length<input aria-label="Preset target edge length" type="number" min="0.000001" max="1000000" step="any" value={targetEdge} onChange={event => setTargetEdge(event.target.value)} /></label>
      <label>Remesh iterations<input aria-label="Preset remesh iterations" type="number" min="1" max="10" step="1" value={iterations} onChange={event => setIterations(Number(event.target.value))} /></label>
      <label className="scientific-comparison-preset-check"><input type="checkbox" checked={preserveBoundary} onChange={event => setPreserveBoundary(event.target.checked)} /> Preserve boundary</label>
    </div>
    {!validEdge && <p role="alert">Enter a positive finite target edge length.</p>}
    {!validIterations && <p role="alert">Iterations must be an integer from 1 to 10.</p>}
    <div className="scientific-history-actions"><button disabled={disabled} onClick={() => run('cgal.validate')}>1. Run baseline validation</button><button disabled={disabled} onClick={() => run('cgal.validate')}>Repeat baseline</button><button disabled={disabled || !validEdge || !validIterations} onClick={() => run('cgal.remesh')}>2. Run remesh variant</button></div>
    <p className="scientific-runtime-note">Repeat baseline uses the same selected mesh and request parameters in a fresh run folder. Wait for each job to finish, then Refresh history and compare the two validation runs for input/output hashes. The remesh variant is a separate operation; target edge length uses the mesh's own units.</p>
  </section>
}
