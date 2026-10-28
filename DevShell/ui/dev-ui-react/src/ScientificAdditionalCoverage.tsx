import type { RuntimeKind, RuntimeProfile } from './scientificRuntimeProfiles'
import type { ObservedScientificRuntime } from './scientificRuntimeReport'
import type { useScientificRuntime } from './useScientificRuntime'

type CoveredKind = Extract<RuntimeKind, 'gmsh' | 'python' | 'sage'>

interface Candidate {
  name: string
  capability: string
  upstream: string
  positive: string
  rejection: string
  probeId?: string
}

const documentation: Record<CoveredKind, string> = {
  gmsh: 'https://gmsh.info/doc/texinfo/',
  python: 'https://docs.scipy.org/doc/scipy/reference/',
  sage: 'https://doc.sagemath.org/html/en/reference/',
}

const candidates: Record<CoveredKind, Candidate[]> = {
  gmsh: [
    { name: 'CAD geometry / OpenCASCADE', capability: 'geometry.occ', upstream: 'gmsh.model.occ', positive: 'Import a closed STEP solid and record entity bounds.', rejection: 'Reject an unreadable or unsupported CAD file.' },
    { name: '2D surface meshing', capability: 'mesh.generate', upstream: 'gmsh.model.mesh.generate(2)', positive: 'Mesh a bounded plane surface; check element count and boundary tags.', rejection: 'Reject a missing mesh file.', probeId: 'gmsh.surface2d' },
    { name: '3D volume meshing', capability: 'mesh.generate', upstream: 'gmsh.model.mesh.generate(3)', positive: 'Mesh a closed volume; check positive tetrahedron count and bounds.', rejection: 'Reject an open shell as a volume.' },
    { name: 'Mesh-size fields', capability: 'mesh.size-field', upstream: 'gmsh.model.mesh.field', positive: 'Apply a local size field and compare element density.', rejection: 'Reject a field with invalid parameters.' },
    { name: 'Physical groups', capability: 'mesh.groups', upstream: 'gmsh.model.addPhysicalGroup', positive: 'Export and reimport tagged boundary and volume groups.', rejection: 'Reject references to nonexistent entities.' },
    { name: 'MSH read', capability: 'mesh.read', upstream: 'gmsh.open', positive: 'Read a bounded MSH fixture and verify nodes, elements, and groups.', rejection: 'Reject a truncated MSH file.' },
    { name: 'MSH write', capability: 'mesh.write', upstream: 'gmsh.write', positive: 'Round-trip a generated mesh with stable counts and tags.', rejection: 'Reject an unsafe or unwritable output target.' },
    { name: 'Mesh optimization', capability: 'mesh.optimize', upstream: 'gmsh.model.mesh.optimize', positive: 'Improve a poor-quality bounded mesh without losing physical groups.', rejection: 'Report a mesh that cannot be optimized within limits.' },
  ],
  python: [
    { name: 'Dense linear algebra', capability: 'math.linear-algebra', upstream: 'scipy.linalg', positive: 'Solve a small conditioned system and check residual.', rejection: 'Report a singular system clearly.', probeId: 'scipy.solve' },
    { name: 'Sparse linear systems', capability: 'math.linear-algebra', upstream: 'scipy.sparse.linalg', positive: 'Solve a sparse Poisson fixture and check residual and shape.', rejection: 'Reject a non-square system.' },
    { name: 'Spatial nearest neighbors', capability: 'math.numeric', upstream: 'scipy.spatial.cKDTree', positive: 'Query known point distances and indices.', rejection: 'Reject non-finite input coordinates.' },
    { name: 'Convex hull / Delaunay', capability: 'math.numeric', upstream: 'scipy.spatial', positive: 'Compute a tetrahedral hull with expected volume and facets.', rejection: 'Report coplanar or degenerate input.' },
    { name: 'Optimization', capability: 'math.numeric', upstream: 'scipy.optimize', positive: 'Minimize a convex fixture and check convergence.', rejection: 'Report invalid bounds or non-finite objective values.' },
    { name: 'Numerical integration', capability: 'math.numeric', upstream: 'scipy.integrate', positive: 'Integrate a known function within tolerance.', rejection: 'Reject non-finite integrand output.' },
    { name: 'Interpolation', capability: 'math.numeric', upstream: 'scipy.interpolate', positive: 'Interpolate a known sample at interior points.', rejection: 'Report malformed or duplicate sample coordinates.' },
  ],
  sage: [
    { name: 'Symbolic expressions', capability: 'math.symbolic', upstream: 'Sage symbolic ring', positive: 'Differentiate and simplify a known expression exactly.', rejection: 'Report division by zero in exact arithmetic.', probeId: 'sage.symbolic' },
    { name: 'Exact polynomial factor contract', capability: 'math.symbolic', upstream: 'PolynomialRing(QQ, "x").factor()', positive: 'Factor x² − 1 from integer coefficient JSON and verify exact reconstruction.', rejection: 'Reject a noninteger coefficient.', probeId: 'sage.factor' },
    { name: 'Exact arithmetic', capability: 'math.number-theory', upstream: 'ZZ / QQ / number fields', positive: 'Preserve rational results without floating-point rounding.', rejection: 'Reject division by zero with a clear diagnostic.' },
    { name: 'Integer factorization', capability: 'math.number-theory', upstream: 'factor', positive: 'Factor a known composite and multiply factors back.', rejection: 'Reject unsupported or unbounded input.' },
    { name: 'Exact matrices', capability: 'math.linear-algebra', upstream: 'matrix over QQ', positive: 'Solve an exact system and verify equality.', rejection: 'Report a singular matrix.' },
    { name: 'Polyhedra', capability: 'geometry.polyhedron', upstream: 'Polyhedron', positive: 'Construct a rational cube and verify volume and facets.', rejection: 'Reject inconsistent inequalities.' },
    { name: 'Lattice polytopes', capability: 'geometry.lattice', upstream: 'integral_points', positive: 'Count lattice points of a small rational polytope.', rejection: 'Bound or reject unbounded enumeration.' },
  ],
}

export function ScientificAdditionalCoverage({ runtime, observed, native }: { runtime: RuntimeProfile; observed?: ObservedScientificRuntime; native: ReturnType<typeof useScientificRuntime> }) {
  if (runtime.kind !== 'gmsh' && runtime.kind !== 'python' && runtime.kind !== 'sage') return null
  const kind = runtime.kind
  const rows = candidates[kind]
  const declared = rows.filter(row => runtime.capabilities.includes(row.capability)).length
  const job = native.jobs[runtime.id]
  const saved = native.history?.find(entry => entry.runtimeId === runtime.id && entry.recipeId === 'lab.probe')
  const result = native.historyResult?.runtimeId === runtime.id && native.historyResult.recipeId === 'lab.probe' ? native.historyResult : job?.result
  const probeResults = result?.probeResults ?? []
  const registered = rows.filter(row => row.probeId).length
  const runnable = runtime.kind === 'sage' ? runtime.id === 'sage-wsl' : runtime.execution === 'windows-native'
  return <section aria-label={`${runtime.name} capability coverage`}>
    <h3>{runtime.name} capability coverage</h3>
    <p className="scientific-runtime-note">Scoped MATH3D candidates, not a claim that the full upstream library is supported. {declared}/{rows.length} entries map to this profile's declared capabilities; {registered} has a bounded positive and rejection probe. Package installation and version do not prove a worker operation.</p>
    <p className="scientific-runtime-note"><a href={documentation[kind]} target="_blank" rel="noopener noreferrer">Upstream reference</a> · Install/package evidence: Environment · Execution evidence: History</p>
    <div className="scientific-runtime-actions">
      <button type="button" disabled={!runnable || native.pending || native.busy} onClick={() => native.send(runtime.id, 'lab-probe')}>{native.pending ? 'Starting probes...' : `Run ${runtime.name} probes`}</button>
      <button type="button" onClick={() => native.send('', 'history')}>Refresh saved evidence</button>
      {saved && <button type="button" onClick={() => native.send(runtime.id, 'history-result', { jobId: saved.jobId })}>Load saved result</button>}
    </div>
    {!runnable && <p className="scientific-runtime-note">{runtime.kind === 'sage' ? 'Select WSL Ubuntu under Environment to run the installed SageMath probes.' : 'Select Windows Native under Environment to run the registered probes.'}</p>}
    {native.error && <p role="alert" className="scientific-runtime-note">Probe request failed: {native.error}</p>}
    <p className="scientific-runtime-note">{job ? `Managed job: ${job.state}` : 'No managed probe job in this session.'} {saved ? `Saved run: ${saved.jobId}` : 'No saved probe result loaded.'} {observed?.version ? `Installed version: ${observed.version}.` : 'Installed version not recorded.'}</p>
    {result && <p className="scientific-runtime-note">Probe evidence: {probeResults.filter(probe => probe.status === 'passed').length}/{probeResults.length} passed. {probeResults.map(probe => `${probe.id}: ${probe.status} (${probe.durationMs} ms)`).join('; ')}</p>}
    <div className="scientific-history-scroll"><table><thead><tr><th>Candidate / upstream API</th><th>Profile intent</th><th>Worker / contract</th><th>MATH3D UI</th><th>Opt-in test plan</th></tr></thead><tbody>{rows.map(row => <tr key={row.name}>
      <td><strong>{row.name}</strong><br /><small><code>{row.upstream}</code></small></td>
      <td>{runtime.capabilities.includes(row.capability) ? <><strong>Declared</strong><br /><small><code>{row.capability}</code></small></> : <><strong>Not declared</strong><br /><small><code>{row.capability}</code></small></>}</td>
      <td>Not registered</td>
      <td>Not assessed in this contract</td>
      <td><strong>{row.probeId ? (() => { const positive = probeResults.find(probe => probe.id === row.probeId); const rejection = probeResults.find(probe => probe.id === `${row.probeId}.reject`); return positive?.status === 'passed' && rejection?.status === 'passed' ? 'Pass: accept and reject' : positive || rejection ? `Accept ${positive?.status ?? 'not run'} / reject ${rejection?.status ?? 'not run'}` : 'Registered, not run' })() : 'Not registered'}</strong><br /><small>Accept: {row.positive}<br />Reject: {row.rejection}</small></td>
    </tr>)}</tbody></table></div>
    <p className="scientific-runtime-note">These bounded probes establish only environment/API evidence, not a MATH3D worker contract. Remaining catalog rows have no registered probe.</p>
  </section>
}
