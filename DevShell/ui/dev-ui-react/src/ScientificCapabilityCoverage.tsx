import { useEffect, useRef } from 'react'
import type { ObservedScientificRuntime } from './scientificRuntimeReport'
import type { RuntimeProfile, ScientificRunResult } from './scientificRuntimeProfiles'
import type { useScientificRuntime } from './useScientificRuntime'

type TestKey = 'cgal-matrix' | 'cgal-remesh' | 'real-mesh' | 'vtk-inspect' | 'vtk-simplify' | 'vtk-normals' | 'vtk-offscreen'
type Capability = {
  id: string
  group: string
  name: string
  implementation: string | null
  math3dUi: boolean
  test?: TestKey
  positive: string
  rejection: string
  rejectionAutomated?: boolean
  rejectionCaseId?: string
  rejectionCaseIds?: string[]
}

const catalog: Record<'cgal' | 'vtk', Capability[]> = {
  cgal: [
    { id: 'mesh.read', group: 'Mesh I/O', name: 'Read OBJ/STL/PLY/OFF', implementation: 'CGAL validation worker', math3dUi: false, test: 'cgal-matrix', positive: 'Registered tetrahedron and cube input; verify matching input hash.', rejection: 'Malformed, degenerate, and non-manifold fixtures.', rejectionAutomated: true },
    { id: 'mesh.write', group: 'Mesh I/O', name: 'Write OBJ result', implementation: 'CGAL validation worker', math3dUi: false, test: 'cgal-matrix', positive: 'Validated OBJ output with SHA-256 and retained artifact.', rejection: 'No output artifact for a rejected input.', rejectionAutomated: true },
    { id: 'mesh.validate', group: 'Quality', name: 'Validate surface mesh', implementation: 'CGAL validation worker', math3dUi: false, test: 'cgal-matrix', positive: 'Valid closed and open fixtures produce recorded topology.', rejection: 'Problem fixtures must fail with the expected geometry reason.', rejectionAutomated: true },
    { id: 'mesh.remesh', group: 'Processing', name: 'Isotropic remesh', implementation: 'CGAL mesh worker', math3dUi: false, test: 'cgal-remesh', positive: 'Small registered mesh; one iteration; hashed OBJ output.', rejection: 'Invalid edge target or unsuitable geometry; automated rejection pending.' },
    { id: 'mesh.boolean.union', group: 'Boolean', name: 'Union', implementation: 'MATH3D native CGAL worker', math3dUi: true, test: 'real-mesh', positive: 'Armadillo/3DBenchy transformed pairs; volume identity and output mesh.', rejection: 'Known coplanar 3DBenchy overlap must report the CGAL corefinement diagnostic without an output.', rejectionCaseIds: ['3dbenchy-coplanar-overlap'] },
    { id: 'mesh.boolean.intersection', group: 'Boolean', name: 'Intersection', implementation: 'MATH3D native CGAL worker', math3dUi: true, test: 'real-mesh', positive: 'Armadillo/3DBenchy transformed pairs; volume identity and output mesh.', rejection: 'Open and non-manifold operands must be rejected without outputs.', rejectionCaseIds: ['armadillo-open-intersection', 'armadillo-nonmanifold-intersection'] },
    { id: 'mesh.boolean.difference', group: 'Boolean', name: 'Difference', implementation: 'MATH3D native CGAL worker', math3dUi: true, test: 'real-mesh', positive: 'Armadillo/3DBenchy transformed pairs; volume identity and output mesh.', rejection: 'Open and non-manifold operands must be rejected without outputs.', rejectionCaseIds: ['armadillo-open-difference', 'armadillo-nonmanifold-difference'] },
    { id: 'mesh.repair', group: 'Processing', name: 'Repair defects', implementation: null, math3dUi: false, positive: 'Hole, winding, and degenerate-face fixtures.', rejection: 'Unrepairable topology with explicit diagnostics.' },
    { id: 'mesh.decimate', group: 'Processing', name: 'Simplify / decimate', implementation: null, math3dUi: false, positive: 'Closed mesh with bounded reduction and topology checks.', rejection: 'Target that violates the geometry budget.' },
    { id: 'geometry.aabb', group: 'Geometry', name: 'AABB queries', implementation: null, math3dUi: false, positive: 'Known point-to-mesh and ray queries.', rejection: 'Empty or invalid acceleration input.' },
    { id: 'geometry.distance', group: 'Geometry', name: 'Mesh distance', implementation: null, math3dUi: false, positive: 'Known separated solids with analytic distance.', rejection: 'Non-finite coordinates.' },
    { id: 'geometry.intersection', group: 'Geometry', name: 'Intersection queries', implementation: null, math3dUi: false, positive: 'Crossing and disjoint triangle pairs.', rejection: 'Degenerate input.' },
    { id: 'mesh.generate3d', group: 'Meshing', name: '3D mesh generation', implementation: null, math3dUi: false, positive: 'Bounded domain with mesh quality checks.', rejection: 'Invalid or unbounded domain.' },
    { id: 'pointset.process', group: 'Point sets', name: 'Point-set processing', implementation: null, math3dUi: false, positive: 'Noisy sample with measured output.', rejection: 'Empty or non-finite sample.' },
  ],
  vtk: [
    { id: 'mesh.read', group: 'Mesh I/O', name: 'Read OBJ/STL/PLY/VTP', implementation: 'VTK mesh worker', math3dUi: false, test: 'vtk-inspect', positive: 'Registered mesh copy loads into vtkPolyData.', rejection: 'Malformed PLY must fail without an output artifact.', rejectionCaseId: 'read-truncated-ply' },
    { id: 'mesh.write', group: 'Mesh I/O', name: 'Write VTP', implementation: 'VTK mesh worker', math3dUi: false, test: 'vtk-inspect', positive: 'VTP output artifact has a recorded SHA-256.', rejection: 'Unsafe output path must be rejected.', rejectionCaseId: 'write-unsafe-path' },
    { id: 'geometry.polydata', group: 'Geometry', name: 'PolyData inspection', implementation: 'VTK mesh worker', math3dUi: false, test: 'vtk-inspect', positive: 'Inspect a registered small mesh and record point/face counts.', rejection: 'Malformed surface must fail without an output artifact.', rejectionCaseId: 'read-truncated-ply' },
    { id: 'mesh.filter', group: 'Processing', name: 'Topology-preserving simplify', implementation: 'VTK mesh worker', math3dUi: false, test: 'vtk-simplify', positive: 'Reduce a small mesh by 25% and retain VTP artifact.', rejection: 'Invalid target reduction must be rejected.', rejectionCaseId: 'simplify-invalid-reduction' },
    { id: 'mesh.normals', group: 'Processing', name: 'Compute normals', implementation: 'VTK mesh worker', math3dUi: false, test: 'vtk-normals', positive: 'Compute normals on a registered mesh.', rejection: 'Auto-orient an open surface must be rejected.', rejectionCaseId: 'normals-open-auto-orient' },
    { id: 'render.offscreen', group: 'Rendering', name: 'Offscreen rendering', implementation: 'VTK smoke recipe', math3dUi: false, test: 'vtk-offscreen', positive: 'Registered test-all smoke and offscreen check.', rejection: 'Unavailable graphics backend; automated rejection pending.' },
    { id: 'render.interactive', group: 'Rendering', name: 'Interactive VTK window', implementation: null, math3dUi: false, positive: 'Camera and interaction smoke.', rejection: 'Unavailable display backend.' },
    { id: 'image.filters', group: 'Imaging', name: 'Image filters', implementation: null, math3dUi: false, positive: 'Known voxel field and analytic filter output.', rejection: 'Invalid image extent.' },
    { id: 'volume.render', group: 'Rendering', name: 'Volume rendering', implementation: null, math3dUi: false, positive: 'Small volume with reproducible frame.', rejection: 'Unsupported scalar format.' },
    { id: 'mesh.clip', group: 'Processing', name: 'Clip / slice', implementation: null, math3dUi: false, positive: 'Plane cut through a cube.', rejection: 'Non-finite plane.' },
  ],
}

const recipeByTest: Record<TestKey, string> = {
  'cgal-matrix': 'matrix.cgal.validation', 'cgal-remesh': 'cgal.remesh', 'real-mesh': 'matrix.cgal.real-mesh',
  'vtk-inspect': 'mesh.inspect', 'vtk-simplify': 'mesh.simplify', 'vtk-normals': 'mesh.normals', 'vtk-offscreen': 'test-all',
}

const outputByTest: Partial<Record<TestKey, string>> = {
  'cgal-remesh': 'capability-remesh.obj', 'vtk-inspect': 'capability-inspect.vtp',
  'vtk-simplify': 'capability-simplify.vtp', 'vtk-normals': 'capability-normals.vtp',
}

export function ScientificCapabilityCoverage({ runtime, native, edited, observed }: {
  runtime: RuntimeProfile
  native: ReturnType<typeof useScientificRuntime>
  edited: boolean
  observed?: ObservedScientificRuntime
}) {
  const rows = runtime.kind === 'cgal' || runtime.kind === 'vtk' ? catalog[runtime.kind] : []
  const requested = useRef(new Set<string>())
  const refreshedSuite = useRef('')
  const loadedHistory = useRef(native.history)
  useEffect(() => {
    if (loadedHistory.current !== native.history) { loadedHistory.current = native.history; requested.current.clear() }
    const recipeIds = new Set(rows.map(row => row.test).filter((item): item is TestKey => !!item).map(test => recipeByTest[test]))
    if (runtime.kind === 'vtk') recipeIds.add('matrix.vtk.rejections')
    for (const recipeId of recipeIds) {
      const entry = native.history?.find(item => item.runtimeId === runtime.id && item.recipeId === recipeId)
      if (entry && !native.historyResults[entry.jobId] && !requested.current.has(entry.jobId)) {
        requested.current.add(entry.jobId)
        native.send(runtime.id, 'history-result', { jobId: entry.jobId })
      }
    }
  }, [runtime.id, native.history, native.historyResults, native.send])
  const activeSuite = native.jobs[runtime.id]
  useEffect(() => {
    if (activeSuite?.recipeId === 'matrix.vtk.rejections' && activeSuite.state !== 'running' && refreshedSuite.current !== activeSuite.jobId) {
      refreshedSuite.current = activeSuite.jobId
      native.send('', 'history')
    }
  }, [activeSuite?.jobId, activeSuite?.recipeId, activeSuite?.state, native.send])

  if (!rows.length) return null
  const available = runtime.execution === 'windows-native' && !edited && !native.busy && !native.pending
  const inputs = native.datasets?.entries ?? []
  const fixture = inputs.find(item => item.id === 'math3d/basic/02_cube.obj')
    ?? inputs.find(item => !item.expectedProblem && /\.(obj|stl|ply|off)$/i.test(item.path))
  const rejectionEntry = runtime.kind === 'vtk' ? native.history?.find(item => item.runtimeId === runtime.id && item.recipeId === 'matrix.vtk.rejections') : undefined
  const rejectionResult = activeSuite?.recipeId === 'matrix.vtk.rejections' ? activeSuite.result ?? (rejectionEntry ? native.historyResults[rejectionEntry.jobId] : undefined)
    : rejectionEntry ? native.historyResults[rejectionEntry.jobId] : undefined
  const rejectionSummary = rejectionResult?.rejectionSummary
  const run = (test: TestKey) => {
    if (test === 'cgal-matrix') native.send(runtime.id, 'run-matrix')
    else if (test === 'real-mesh') native.send(runtime.id, 'real-mesh-suite')
    else if (test === 'cgal-remesh' && fixture) native.send(runtime.id, 'cgal-recipe', { recipeId: 'cgal.remesh', parameters: { inputId: fixture.id, outputName: outputByTest[test], targetEdge: 0.5, iterations: 1, preserveBoundary: true } })
    else if (fixture && test !== 'vtk-offscreen') {
      const recipeId = recipeByTest[test]
      const parameters = { inputId: fixture.id, outputName: outputByTest[test], ...(test === 'vtk-simplify' ? { targetReduction: 0.25, preserveTopology: true, preserveBoundary: true } : {}), ...(test === 'vtk-normals' ? { featureAngle: 30, autoOrient: false } : {}) }
      native.send(runtime.id, 'recipe', { recipeId, parameters })
    } else if (test === 'vtk-offscreen') native.send(runtime.id, 'recipe', { recipeId: 'test-all' })
  }
  const testEvidence = (test: TestKey) => {
    const recipeId = recipeByTest[test]
    const live = native.jobs[runtime.id]?.recipeId === recipeId ? native.jobs[runtime.id] : undefined
    const entry = native.history?.find(item => item.runtimeId === runtime.id && item.recipeId === recipeId)
    const result = live?.result ?? (entry ? native.historyResults[entry.jobId] : undefined)
    const state = live?.state === 'running' ? 'running' : result?.state ?? (entry ? 'loading' : 'not run')
    const output = outputByTest[test]
    const artifact = output ? result?.artifacts?.find(item => item.path === output) : undefined
    const suite = (result as ScientificRunResult & { realMeshSuite?: { passed: number; total: number; cases: { name: string; status: string; operations: { operation: string; artifactSha256?: string }[] }[] } } | undefined)?.realMeshSuite
    const positiveCases = ['armadillo-shift', 'armadillo-rotated', '3dbenchy-cutter', '3dbenchy-second-cutter']
    const realMeshPositive = positiveCases.every(name => suite?.cases.some(item => item.name === name && item.status === 'passed'
      && ['union', 'intersection', 'difference'].every(operation => item.operations.some(value => value.operation === operation && !!value.artifactSha256))))
    const passed = state === 'succeeded' && (test === 'cgal-matrix' ? !!result?.matrixSummary?.total && result.matrixSummary.passed === result.matrixSummary.total
      : test === 'real-mesh' ? !!suite?.total && suite.passed === suite.total && realMeshPositive
      : output ? !!artifact?.sha256 : true)
    return { entry, result, state, passed, artifact, live }
  }

  return <section aria-label="Scientific capability coverage" style={{ marginBottom: 20 }}>
    <h3>MATH3D-scoped capability catalog</h3>
    <p className="scientific-runtime-note">{rows.length} relevant {runtime.name} capabilities. This is not the entire library API. Installed means recorded package evidence, not algorithm readiness. Worker, contract, MATH3D UI, and test are independent states. Saved evidence is not a live check.</p>
    <div className="scientific-inspector-actions"><button disabled={native.pending} onClick={() => { native.send('', 'datasets'); native.send('', 'history') }}>Load local copies and saved evidence</button>{runtime.kind === 'vtk' && <button disabled={!available || !native.datasets?.entries.length} onClick={() => native.send(runtime.id, 'vtk-rejections')}>Run VTK rejection checks</button>}</div>
    {runtime.kind === 'vtk' && <p className="scientific-runtime-note">VTK rejection suite: {activeSuite?.recipeId === 'matrix.vtk.rejections' && activeSuite.state === 'running' ? `Running ${activeSuite.stage ?? ''}` : rejectionSummary ? `${rejectionSummary.passed}/${rejectionSummary.total} cases passed; saved ${rejectionResult?.state ?? 'unknown'}` : 'No saved evidence loaded.'}{rejectionEntry && <> <button onClick={() => native.send(runtime.id, 'history-open-log', { jobId: rejectionEntry.jobId })}>Suite log</button></>}</p>}
    <div className="scientific-history-scroll"><table><thead><tr><th>Capability</th><th>Installed</th><th>Worker</th><th>Contract</th><th>MATH3D UI</th><th>Test evidence / action</th></tr></thead><tbody>
      {rows.map(row => {
        const evidence = row.test ? testEvidence(row.test) : undefined
        const needsFixture = row.test && !['real-mesh', 'vtk-offscreen'].includes(row.test)
        const disabled = !available || !row.test || (needsFixture && !fixture) || (row.test === 'cgal-matrix' && !native.datasets?.entries.length)
        const version = runtime.kind === 'cgal' ? evidence?.result?.versions?.cgal : evidence?.result?.versions?.vtk
        const rejectionCase = rejectionSummary?.cases.find(item => item.caseId === row.rejectionCaseId)
        const realMeshSuite = (evidence?.result as ScientificRunResult & { realMeshSuite?: { cases: { name: string; status: string; expectedOutcome?: string; observedOutcome?: string; rejection?: { operation?: string; artifactAbsent?: boolean } }[] } } | undefined)?.realMeshSuite
        const realMeshRejections = row.rejectionCaseIds?.map(id => realMeshSuite?.cases.find(item => item.name === id))
        const realMeshRejectionPassed = !!row.rejectionCaseIds?.length && !!realMeshRejections?.every(item => item?.status === 'passed'
          && item.expectedOutcome === 'rejected' && item.observedOutcome === 'rejected'
          && item.rejection?.operation === row.id.split('.').at(-1) && item.rejection?.artifactAbsent)
        const vtkRejectionPassed = !!rejectionCase && rejectionResult?.state === 'succeeded' && rejectionCase.verdict === 'pass'
        const rejectionPassed = realMeshRejectionPassed || vtkRejectionPassed
        const fullyPassed = !!evidence?.passed && (rejectionPassed || (!!row.rejectionAutomated && !row.rejectionCaseIds))
        return <tr key={row.id}>
          <td><strong>{row.name}</strong><br /><small>{row.group} / <code>{row.id}</code></small><details><summary>Acceptance scope</summary><small>Valid: {row.positive}<br />Rejection: {row.rejection}<br />{row.rejectionAutomated || row.rejectionCaseIds ? 'Valid and rejection cases automated.' : row.rejectionCaseId ? 'Rejection case runs in the VTK suite.' : 'Rejection case is not yet automated.'}</small></details></td>
          <td>{observed && observed.state !== 'missing' && observed.state !== 'failed' ? `Recorded ${observed.version ?? 'version unknown'}` : observed?.state ?? 'Not loaded'}</td>
          <td>{row.implementation ?? 'Not implemented'}{row.implementation && <><br /><small>{row.implementation}</small></>}</td>
          <td>{row.implementation ? 'Structured request/result' : 'Not exposed'}</td>
          <td>{row.math3dUi ? 'Connected' : 'Not this contract'}</td>
          <td>{evidence ? <><strong>{evidence.state === 'running' ? 'Running' : fullyPassed ? 'Passed' : evidence.passed ? 'Positive smoke passed / rejection pending' : rejectionPassed ? 'Rejection passed / positive pending' : evidence.state === 'succeeded' ? 'Incomplete evidence' : evidence.state}</strong>{evidence.result && <small><br />{version ? `${version} / ` : ''}{evidence.result.durationMs} ms / input <code>{evidence.result.inputArtifacts?.[0]?.sha256?.slice(0, 12) ?? '-'}</code> / output <code>{evidence.artifact?.sha256?.slice(0, 12) ?? evidence.result.artifacts?.[0]?.sha256?.slice(0, 12) ?? '-'}</code></small>}{realMeshRejections && <small><br />Rejections: {realMeshRejections.filter(item => item?.status === 'passed' && item.rejection?.artifactAbsent).length}/{realMeshRejections.length} passed with no output</small>}{rejectionCase && <small><br />Reject {rejectionCase.caseId}: {rejectionCase.verdict} / {rejectionCase.diagnostic}</small>}{evidence.result?.diagnostics?.filter(item => item.severity === 'error').map((item, index) => <p key={index} role="alert">{item.message}</p>)}{evidence.live?.error && <p role="alert">{evidence.live.error}</p>}<br /><button disabled={disabled} onClick={() => row.test && run(row.test)}>Run opt-in check</button>{needsFixture && !fixture && <small> Load local copies first.</small>}{evidence.entry && <button onClick={() => native.send(runtime.id, 'history-open-log', { jobId: evidence.entry!.jobId })}>Log</button>}</> : <span>Not available</span>}</td>
        </tr>
      })}
    </tbody></table></div>
    <p className="scientific-runtime-note">Each click starts only the registered check shown in its row. Shared checks cover several capabilities. A capability passes only when its positive evidence and registered rejection evidence have both passed. Run folders retain request/result JSON, logs, hashes, timings, diagnostics, and output artifacts when the worker supplies them.</p>
  </section>
}
