import type { ScientificArtifactPreview, ScientificMeshPreview } from './useScientificRuntime'
import type { ScientificRunResult } from './scientificRuntimeProfiles'

function finite(value: number) { return Number.isFinite(value) ? value.toPrecision(6) : 'unavailable' }

type ExactFactor = { coefficients: string[]; multiplicity: number }
type ExactView = { source: string; polynomial: string; factors: ExactFactor[]; unit: string; verified: boolean }

function exactView(result: ScientificRunResult): ExactView | null {
  if (result.runtimeId !== 'sage-wsl' || result.state !== 'succeeded') return null
  for (const probe of result.probeResults ?? []) {
    if (probe.id !== 'sage.factor' || probe.status !== 'passed') continue
    try {
      const line = probe.stdout.split(/\r?\n/).find(item => item.trim().startsWith('{'))
      const parsed = JSON.parse(line ?? '') as { operation?: string; result?: { inputCoefficients?: unknown; unit?: unknown; factors?: unknown; verified?: unknown } }
      const value = parsed.result
      if (parsed.operation !== 'symbolic.factor' || value?.verified !== true || !Array.isArray(value.inputCoefficients)
          || !value.inputCoefficients.every(item => typeof item === 'string')
          || !Array.isArray(value.factors) || typeof value.unit !== 'string') continue
      const factors = value.factors.filter((item): item is ExactFactor => !!item && typeof item === 'object'
        && Array.isArray((item as ExactFactor).coefficients) && (item as ExactFactor).coefficients.every(v => typeof v === 'string')
        && Number.isInteger((item as ExactFactor).multiplicity))
      if (factors.length !== value.factors.length) continue
      return { source: 'Saved Sage factor probe', polynomial: value.inputCoefficients.join(', '), factors, unit: value.unit, verified: true }
    } catch { /* Older probe output may be plain text. */ }
  }
  const evidence = (result as ScientificRunResult & { evidence?: { output?: string } }).evidence
  if (result.recipeId === 'sage.factor-smoke' && evidence?.output === 'verified: (x - 1) * (x + 1)')
    return { source: 'Saved Sage factor smoke', polynomial: '-1, 0, 1',
      factors: [{ coefficients: ['-1', '1'], multiplicity: 1 }, { coefficients: ['1', '1'], multiplicity: 1 }], unit: '1', verified: true }
  return null
}

export function ScientificExactMathInspector({ result }: { result: ScientificRunResult }) {
  const value = exactView(result)
  if (result.runtimeId !== 'sage-wsl') return null
  return <section aria-label="Exact math artifact inspector"><h5>Exact math result</h5>
    {value ? <><p>{value.source} / reconstructed in Sage: <strong>{value.verified ? 'verified' : 'unverified'}</strong>.</p>
      <p>Polynomial coefficients (constant first): <code>[{value.polynomial}]</code>; unit <code>{value.unit}</code>.</p>
      <table><thead><tr><th>Factor coefficients</th><th>Multiplicity</th></tr></thead><tbody>{value.factors.map((factor, index) =>
        <tr key={index}><td><code>[{factor.coefficients.join(', ')}]</code></td><td>{factor.multiplicity}</td></tr>)}</tbody></table></>
      : <p>No structured, verified factor result is saved for this run. Inspect its recorded diagnostics.</p>}
  </section>
}

export function ScientificMeshFacts({ preview, result }: { preview: ScientificArtifactPreview; result: ScientificRunResult }) {
  const mesh = preview.geometry.after
  const before = preview.geometry.before
  return <section aria-label="Mesh artifact statistics"><h5>Artifact statistics: <code>{preview.artifactPath}</code></h5>
    <table><thead><tr><th>Measure</th><th>Input</th><th>Output</th><th>Change</th></tr></thead><tbody>
      {(['points', 'triangles'] as const).map(key => <tr key={key}><th>{key}</th><td>{before?.[key] ?? 'unavailable'}</td><td>{mesh[key]}</td><td>{before ? mesh[key] - before[key] : 'unavailable'}</td></tr>)}
      {(['X', 'Y', 'Z'] as const).map((axis, index) => <tr key={axis}><th>{axis} span</th><td>{before ? finite(before.bounds[index * 2 + 1] - before.bounds[index * 2]) : 'unavailable'}</td><td>{finite(mesh.bounds[index * 2 + 1] - mesh.bounds[index * 2])}</td><td>{before ? finite((mesh.bounds[index * 2 + 1] - mesh.bounds[index * 2]) - (before.bounds[index * 2 + 1] - before.bounds[index * 2])) : 'unavailable'}</td></tr>)}
    </tbody></table>
    <p>Output bounds: [{mesh.bounds.map(finite).join(', ')}]. {mesh.sampled ? `Preview renders ${mesh.previewTriangles} sampled triangles; counts and bounds describe the full mesh.` : 'Preview renders the full triangle set.'}</p>
    {result.after && <p>Worker topology: {String(result.after.closed ?? 'unknown')} closed / {String(result.after.boundaryEdges ?? 'unknown')} boundary edges / {String(result.after.nonManifoldEdges ?? 'unknown')} non-manifold edges.</p>}
    <p>Recorded SHA-256: <code>{result.artifacts.find(item => item.path === preview.artifactPath)?.sha256 ?? 'unavailable'}</code>.</p>
  </section>
}

export function ScientificMeshNumericDiff({ left, right, leftHash, rightHash }: {
  left: ScientificMeshPreview; right: ScientificMeshPreview; leftHash?: string; rightHash?: string
}) {
  return <section aria-label="Numeric artifact differences"><h5>Numeric output differences</h5>
    <table><thead><tr><th>Measure</th><th>Run 1</th><th>Run 2</th><th>Run 2 − run 1</th></tr></thead><tbody>
      {(['points', 'triangles'] as const).map(key => <tr key={key}><th>{key}</th><td>{left[key]}</td><td>{right[key]}</td><td>{right[key] - left[key]}</td></tr>)}
      {left.bounds.map((value, index) => <tr key={index}><th>{['X min', 'X max', 'Y min', 'Y max', 'Z min', 'Z max'][index]}</th><td>{finite(value)}</td><td>{finite(right.bounds[index])}</td><td>{finite(right.bounds[index] - value)}</td></tr>)}
    </tbody></table><p>Output hashes: {leftHash && rightHash ? leftHash === rightHash ? 'identical bytes' : 'different bytes' : 'not recorded'}.</p>
    <p className="scientific-runtime-note">Bounds and counts are numeric comparisons; equal values alone do not prove equal topology or surface geometry.</p>
  </section>
}
