import { useEffect, useRef } from 'react'
import type { RuntimeProfile } from './scientificRuntimeProfiles'
import type { useScientificRuntime } from './useScientificRuntime'

const inputId = 'math3d/basic/01_tetrahedron.obj'
const outputName = 'math3d-contract-tetrahedron.obj'

export function ScientificMath3DIntegration({ runtime, native, edited, onHistory }: {
  runtime: RuntimeProfile
  native: ReturnType<typeof useScientificRuntime>
  edited: boolean
  onHistory: () => void
}) {
  const requestedDatasets = useRef(false)
  useEffect(() => {
    if (runtime.id !== 'cgal-win-conda' || native.datasets || requestedDatasets.current) return
    requestedDatasets.current = true
    native.send('', 'datasets')
  }, [runtime.id, native.datasets])
  const dataset = native.datasets?.entries.find(item => item.id === inputId)
  const current = native.jobs[runtime.id]
  const request = current?.request
  const isIntegrationRun = current?.recipeId === 'cgal.validate'
    && request?.parameters?.inputId === inputId
    && request?.parameters?.outputName === outputName
  const job = isIntegrationRun ? current : undefined
  const result = job?.result
  const input = result?.inputArtifacts?.[0]
  const output = result?.artifacts?.find(item => item.path === outputName)
  const beforePoints = Number(result?.before?.points)
  const afterPoints = Number(result?.after?.points)
  const beforeTriangles = Number(result?.before?.triangles)
  const afterTriangles = Number(result?.after?.triangles)
  const comparisons: [string, boolean, string][] = result ? [
    ['Registered MATH3D copy', !!dataset && input?.datasetId === inputId && input.sha256?.toLowerCase() === dataset.sha256.toLowerCase(), input?.sha256 ?? 'Missing input hash'],
    ['Validated OBJ artifact', !!output?.sha256 && (output.bytes ?? 0) > 0 && result.validatedCapabilities.includes('mesh.validate'), output?.sha256 ?? 'Missing output hash'],
    ['Geometry preserved', beforePoints > 0 && beforeTriangles > 0 && beforePoints === afterPoints && beforeTriangles === afterTriangles, `${beforePoints} vertices / ${beforeTriangles} triangles → ${afterPoints} vertices / ${afterTriangles} triangles`],
    ['Diagnostics', result.diagnostics.length === 0, result.diagnostics.length ? result.diagnostics.map(item => `${item.severity}: ${item.message}`).join(' | ') : 'No diagnostics'],
  ] : []
  const passed = result?.state === 'succeeded' && comparisons.every(([, ok]) => ok)
  const canRun = runtime.id === 'cgal-win-conda' && runtime.execution === 'windows-native' && !edited && !!dataset && !native.busy && !native.pending
  return <section aria-label="MATH3D fixture contract test" className="scientific-inspector">
    <h3>MATH3D fixture-to-contract test</h3>
    <p>Runs one registered, duplicated MATH3D tetrahedron through the same managed <code>cgal.validate</code> JSON request and CGAL worker used by the matrix. It compares input identity, output artifact, geometry, and diagnostics. It does not exercise MATH3D's separate desktop binary worker.</p>
    <p>Input: <code>{inputId}</code>{dataset ? ` / ${dataset.bytes} bytes` : ' / local copy not loaded'}</p>
    <button disabled={!canRun} onClick={() => native.send(runtime.id, 'cgal-recipe', { recipeId: 'cgal.validate', parameters: { inputId, outputName } })}>Run MATH3D mesh contract test</button>{' '}
    <button onClick={onHistory}>Open run history</button>
    {job && <p role="status">Run {job.jobId}: {result ? passed ? 'PASS' : 'FAIL' : job.state} / {job.stage ?? job.state}</p>}
    {result && <><dl className="scientific-inspector-facts">{comparisons.map(([name, ok, detail]) => <div key={name}><dt>{name}</dt><dd>{ok ? 'PASS' : 'FAIL'} / {detail}</dd></div>)}</dl><p>Worker: CGAL {result.versions?.cgal ?? 'unknown'} / {result.durationMs} ms. Input and output are retained in this run's scoped artifact directory.</p></>}
    {!dataset && <p className="scientific-runtime-note">Import the duplicated MATH3D test set, then return here to run. No source repository mesh is modified.</p>}
  </section>
}
