import { useEffect, useMemo, useRef, useState } from 'react'
import { createScientificProfiles, executionNames } from './scientificRuntimeProfiles'
import type { RuntimeExecution, RuntimeProfile, ScientificRunRequest } from './scientificRuntimeProfiles'
import { loadScientificRuntimeReport } from './scientificRuntimeReport'
import type { ScientificRuntimeReport } from './scientificRuntimeReport'
import { useScientificRuntime } from './useScientificRuntime'
import type { ScientificBridge } from './useScientificRuntime'
import { ScientificEnvironmentInspector } from './ScientificEnvironmentInspector'
import { ScientificRecipePanel } from './ScientificRecipePanel'
import { ScientificArtifacts } from './ScientificArtifacts'

type ScientificProject = { id: string; name: string; root?: string | null; repositories?: { id: string; name: string; path?: string | null }[] }
const sections = ['Health', 'Environment', 'Commands', 'Tests', 'Benchmarks', 'Packages', 'Artifacts', 'Integration'] as const
type Section = typeof sections[number]

function hostRootFor(projects: ScientificProject[]) {
  const math3d = projects.flatMap(project => project.repositories ?? []).find(repository => repository.name.toLowerCase() === 'math3d')
  return (math3d?.path ?? projects[0]?.root ?? '').replace(/[\\/][^\\/]+[\\/]*$/, '')
}

export function ScientificRuntimesWorkspace({ profileId, projects, bridge }: { profileId: string | null; projects: ScientificProject[]; bridge: ScientificBridge | null }) {
  const hostRoot = hostRootFor(projects)
  const [execution, setExecution] = useState<RuntimeExecution>('windows-native')
  const [runtimeKind, setRuntimeKind] = useState('cgal')
  const [section, setSection] = useState<Section>('Health')
  const [overrides, setOverrides] = useState<Record<string, Partial<RuntimeProfile>>>({})
  const [copyStatus, setCopyStatus] = useState('')
  const [report, setReport] = useState<ScientificRuntimeReport | null>(null)
  const [reportError, setReportError] = useState('')
  const [reportLoading, setReportLoading] = useState(false)
  const reportGeneration = useRef(0)
  useEffect(() => { reportGeneration.current++; setExecution('windows-native'); setRuntimeKind('cgal'); setSection('Health'); setOverrides({}); setCopyStatus(''); setReport(null); setReportError(''); setReportLoading(false); return () => { reportGeneration.current++ } }, [profileId])
  const profiles = useMemo(() => createScientificProfiles(hostRoot, execution), [hostRoot, execution])
  const seed = profiles.find(profile => profile.kind === runtimeKind) ?? profiles[0]
  const observed = report?.runtimes.find(item => item.id === seed.id)
  const runtime = { ...seed, ...(observed ? { environmentRoot: observed.environmentRoot, executable: observed.executable, cmake: observed.tools?.cmake?.path ?? seed.cmake, compiler: report?.compiler.path ?? seed.compiler, sdkRoot: observed.sdk?.root } : {}), ...overrides[seed.id] }
  const edited = !!overrides[seed.id]
  const checks = [runtime.versionProbe, ...runtime.healthChecks]
  const patchProfile = (field: 'executable' | 'environmentRoot' | 'compiler' | 'cmake' | 'sdkRoot', value: string) => {
    setOverrides(previous => ({ ...previous, [runtime.id]: { ...previous[runtime.id], [field]: value } }))
    setCopyStatus('')
  }
  const contract: ScientificRunRequest = {
    schemaVersion: 1, runId: '<assigned-by-runner>', runtimeId: runtime.id,
    recipeId: runtime.recipes[0]?.id ?? '<validated-recipe-id>', operation: 'runtime.health',
    parameters: {}, inputArtifacts: [], workingDirectory: '<scoped-run-directory>', timeoutSeconds: 30,
    outputArtifacts: [{ path: 'results.json', mediaType: 'application/json' }],
  }
  const copyProfile = async () => {
    try {
      // Only explicit path/tool fields and recipe metadata; never copy the host environment.
      await navigator.clipboard.writeText(JSON.stringify({ ...runtime, environment: {}, recipes: runtime.recipes.map(recipe => ({ ...recipe, steps: recipe.steps.map(step => ({ ...step, executable: runtime.executable || step.executable })) })) }, null, 2))
      setCopyStatus('Profile definition copied. No environment values or probe results were exported.')
    } catch { setCopyStatus('Clipboard access unavailable. No profile was exported.') }
  }
  const math3dProject = projects.find(project => project.repositories?.some(repository => repository.name.toLowerCase() === 'math3d'))
  const math3dRepo = math3dProject?.repositories?.find(repository => repository.name.toLowerCase() === 'math3d')
  const loadReport = async () => {
    const generation = ++reportGeneration.current
    setReportLoading(true); setReportError('')
    try { const next = await loadScientificRuntimeReport(bridge, profileId); if (generation === reportGeneration.current) setReport(next) }
    catch (error) { if (generation === reportGeneration.current) setReportError(error instanceof Error ? error.message : 'Could not load local report.') }
    finally { if (generation === reportGeneration.current) setReportLoading(false) }
  }
  const native = useScientificRuntime(bridge, profileId, () => { void loadReport() })
  const jobs = Object.values(native.jobs).sort((a, b) => Number(b.state === 'running') - Number(a.state === 'running') || Date.parse(b.startedAtUtc ?? '') - Date.parse(a.startedAtUtc ?? ''))
  const [clock, setClock] = useState(() => Date.now())
  useEffect(() => {
    if (!jobs.some(job => job.state === 'running')) return
    const timer = window.setInterval(() => setClock(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [jobs.some(job => job.state === 'running')])
  const showArtifacts = (runtimeId: string) => {
    const target = createScientificProfiles(hostRoot, 'windows-native').find(profile => profile.id === runtimeId)
    if (!target) return
    setExecution('windows-native'); setRuntimeKind(target.kind); setSection('Artifacts')
  }
  return <main className="scientific-runtime-workspace" aria-label="Scientific Runtimes">
    <header className="scientific-runtime-header"><div><span className="scientific-runtime-kicker">RUNTIMES / SCIENTIFIC</span><h1>Scientific Runtimes</h1><p>A scientific-runtime laboratory for MATH3D. Profiles describe intent; probes establish readiness.</p></div><div><button disabled={reportLoading} onClick={loadReport}>{reportLoading ? 'Loading report...' : 'Load local report'}</button><p className="scientific-runtime-note">{report ? `Recorded ${new Date(report.generatedAt).toLocaleString()}` : 'No inventory loaded / opening does not run probes'}</p></div></header>
    {reportError && <p role="alert">{reportError}</p>}
    {native.error && <p role="alert">{native.error}</p>}
    {native.notice && <p role="status">{native.notice}</p>}
    <section className="scientific-job-bar" aria-label="Scientific job status">
      <strong>Managed jobs</strong>
      {!jobs.length ? <span className="scientific-job-idle">No jobs in this profile. Opening this workspace does not run a recipe.</span> : jobs.map(job => {
        const started = Date.parse(job.startedAtUtc ?? '')
        const duration = job.state === 'running' && Number.isFinite(started) ? Math.max(job.durationMs, clock - started) : job.durationMs
        const elapsed = `${Math.floor(duration / 60000)}:${String(Math.floor(duration / 1000) % 60).padStart(2, '0')}`
        return <div className="scientific-job-summary" key={job.jobId}>
          <span className={`scientific-job-state ${job.state === 'running' ? 'running' : ''}`}>{job.state}</span>
          <span className="scientific-job-name" title={`${job.runtimeId} / ${job.recipeId}`}>{job.runtimeId} / {job.recipeId}</span>
          <span className="scientific-job-stage" role="status">{job.stage || job.state}</span>
          <time aria-label="Elapsed time">{elapsed}</time>
          <button disabled={job.state !== 'running'} onClick={() => native.send(job.runtimeId, 'stop', { jobId: job.jobId })}>Stop</button>
          <button disabled={!createScientificProfiles(hostRoot, 'windows-native').some(profile => profile.id === job.runtimeId)} onClick={() => showArtifacts(job.runtimeId)}>View artifacts</button>
        </div>
      })}
    </section>
    <div className="scientific-runtime-grid">
      <aside className="scientific-runtime-inventory" aria-label="Scientific runtime inventory">
        <label>Environment<select aria-label="Scientific execution environment" value={execution} onChange={event => { setExecution(event.target.value as RuntimeExecution); setCopyStatus('') }}>{Object.entries(executionNames).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <p className="scientific-runtime-note">{execution === 'windows-native' ? report ? 'Recorded installation and probe evidence loaded. Partial means some capabilities remain untested; this is not a live health check.' : 'Candidate native paths. Load a local report to see recorded installation and probe evidence.' : 'Adapter planned. Selecting it does not start WSL or Docker.'}</p>
        {profiles.map(profile => { const inventory = report?.runtimes.find(item => item.id === profile.id); return <button key={profile.id} className={`scientific-runtime-item ${runtime.kind === profile.kind ? 'selected' : ''}`} aria-pressed={runtime.kind === profile.kind} onClick={() => { setRuntimeKind(profile.kind); setCopyStatus('') }}><strong>{profile.name}</strong><span>{inventory ? `${inventory.state} / ${inventory.version ?? 'unknown version'}` : 'Not checked'}</span><small>{profile.id}</small></button> })}
      </aside>
      <section className="scientific-runtime-detail" aria-label={`${runtime.name} runtime details`}>
        <div className="scientific-runtime-detail-heading"><div><h2>{runtime.name} / {executionNames[execution]}</h2><code>{runtime.id}</code></div><span className="scientific-runtime-status">{edited ? 'Definition edited / not checked' : observed ? `${observed.state} / ${observed.version ?? 'unknown version'}` : 'Not checked / version unknown'}</span></div>
        <nav className="scientific-runtime-sections" aria-label="Scientific runtime sections">{sections.map(name => <button key={name} className={section === name ? 'selected' : ''} aria-pressed={section === name} onClick={() => { setSection(name); setCopyStatus('') }}>{name}</button>)}</nav>
        <div className="scientific-runtime-section">
          {section === 'Health' && <><h3>Readiness evidence</h3>{observed ? <><p>Recorded checks for <code>{observed.environmentRoot}</code>. {edited && 'These describe the installed environment, not your edited definition.'}</p><ul className="scientific-runtime-checks">{observed.checks.map(check => <li key={check.id}><span>{check.name}<code>{check.detail}</code></span><small>{check.state} / {check.durationMs} ms</small></li>)}</ul><p>Python {observed.pythonVersion ?? 'unknown'} / {observed.architecture ?? 'unknown architecture'}. C++ compile: {observed.sdk?.compilation ?? 'not-tested'} / link: {observed.sdk?.linking ?? 'not-tested'} / offscreen rendering: {runtime.kind === 'vtk' ? observed.sdk?.rendering ?? 'not-tested' : 'not applicable'}.</p></> : <p>No inventory is loaded for this runtime. Candidate capabilities are not validated.</p>}<details><summary>Planned acceptance checks</summary><ul className="scientific-runtime-checks">{checks.map(check => <li key={check.id}><span>{check.name}</span><small>Not checked</small></li>)}</ul></details><p className="scientific-runtime-note">Run tools/Inspect-ScientificRuntimes.ps1 explicitly, then Load local report. A VTK import does not imply rendering readiness; installed SDK files do not imply a successful C++ build.</p></>}
          {section === 'Environment' && <><h3>Candidate environment definition</h3><p>Paths are editable for this session only. They do not create environments or change PATH.</p><div className="scientific-runtime-fields">{([['environmentRoot', 'Environment root'], ['executable', 'Executable / Python'], ['compiler', 'Compiler'], ['cmake', 'CMake'], ['sdkRoot', 'C++ SDK / vcpkg root']] as const).map(([field, name]) => <label key={field}>{name}<input aria-label={`Scientific ${name}`} value={runtime[field] ?? ''} placeholder="Not configured" onChange={event => patchProfile(field, event.target.value)} spellCheck={false} /></label>)}</div><p className="scientific-runtime-note">CGAL and VTK use separate environment candidates. Inherited environment variables are neither read nor displayed; persistent overrides and validation belong to the runtime-profile slice.</p><button onClick={copyProfile}>Copy profile definition</button></>}
          {section === 'Commands' && <ScientificRecipePanel runtime={runtime} native={native} edited={edited} onArtifacts={() => setSection('Artifacts')} />}
          {section === 'Tests' && <><h3>Capability acceptance tests</h3><ul className="scientific-runtime-checks">{runtime.healthChecks.map(check => <li key={check.id}><span>{check.name}{check.capability && <code>{check.capability}</code>}</span><small>Planned / not run</small></li>)}</ul><p>Tests must emit machine-readable results, logs, resolved versions, and geometry artifact references. No imported code runs by selecting a test.</p></>}
          {section === 'Benchmarks' && <><h3>Reproducible benchmarks</h3><p>No benchmark runs. The runner will record input size, runtime/tool versions, hardware metadata, duration, and output validity before timings can be compared.</p><button disabled title="Benchmark recipes follow the managed runner">Run benchmark</button></>}
          {section === 'Packages' && <><h3>Package provenance</h3>{observed ? <div className="scientific-runtime-package-scroll"><table><thead><tr><th>Package</th><th>Version</th><th>Build</th><th>Source</th></tr></thead><tbody>{observed.packages.map((item, index) => <tr key={`${item.name}:${index}`}><td>{item.name}</td><td>{item.version}</td><td>{item.build}</td><td>{item.source}</td></tr>)}</tbody></table></div> : <p>No package inventory loaded.</p>}<p>Explicit install-missing workflow: <code>tools/Install-ScientificRuntimes.ps1 -WorkspaceRoot &lt;workspace&gt; -CondaExecutable &lt;conda.exe&gt; -PublishToLauncher</code></p><p className="scientific-runtime-note">Creates separate devshell-cgal/devshell-vtk environments. Existing MATH3D environments and system PATH are unchanged; environments with all required packages are not upgraded.</p></>}
          {section === 'Artifacts' && <><ScientificArtifacts runtime={runtime} native={native} /><button disabled={!math3dProject || !math3dRepo} onClick={() => { if (math3dProject && math3dRepo) window.dispatchEvent(new CustomEvent('devshell.workspace.open', { detail: { kind: 'files', projectId: math3dProject.id, repositoryId: math3dRepo.id } })) }}>Open MATH3D files</button></>}
          {section === 'Integration' && <><h3>MATH3D execution contract</h3><p>This is a request-schema preview, not a submitted job. Worker transport must consume structured requests/results, not parse terminal presentation.</p><pre>{JSON.stringify(contract, null, 2)}</pre><button onClick={copyProfile}>Copy profile definition</button><p>Outputs include exit state, duration, resolved versions, validated capabilities, diagnostics, log references, and scoped artifact references.</p></>}
          {(section === 'Health' || section === 'Environment') && <ScientificEnvironmentInspector runtime={runtime} observed={observed} report={report} native={native} edited={edited} />}
          {section === 'Environment' && observed && <details><summary>Installed tools / SDK evidence</summary><pre>{JSON.stringify({ environmentRoot: observed.environmentRoot, executable: observed.executable, compiler: report?.compiler, sdk: observed.sdk, tools: observed.tools }, null, 2)}</pre></details>}
          {copyStatus && <p role="status">{copyStatus}</p>}
        </div>
        <footer className="scientific-runtime-capabilities"><strong>Declared capabilities / evidence-specific, not blanket readiness</strong><div>{runtime.capabilities.map(capability => { const recorded = observed?.validatedCapabilities.includes(capability) || native.jobs[runtime.id]?.result?.validatedCapabilities.includes(capability); return <code key={capability}>{capability} / {recorded ? 'recorded pass' : 'not validated'}</code> })}</div></footer>
      </section>
    </div>
  </main>
}
