import { useEffect, useMemo, useState } from 'react'
import { createScientificProfiles, executionNames } from './scientificRuntimeProfiles'
import type { RuntimeExecution, RuntimeProfile, ScientificRunRequest } from './scientificRuntimeProfiles'

type ScientificProject = { id: string; name: string; root?: string | null; repositories?: { id: string; name: string; path?: string | null }[] }
const sections = ['Health', 'Environment', 'Commands', 'Tests', 'Benchmarks', 'Packages', 'Artifacts', 'Integration'] as const
type Section = typeof sections[number]

function hostRootFor(projects: ScientificProject[]) {
  const math3d = projects.flatMap(project => project.repositories ?? []).find(repository => repository.name.toLowerCase() === 'math3d')
  return (math3d?.path ?? projects[0]?.root ?? '').replace(/[\\/][^\\/]+[\\/]*$/, '')
}

export function ScientificRuntimesWorkspace({ profileId, projects }: { profileId: string | null; projects: ScientificProject[] }) {
  const hostRoot = hostRootFor(projects)
  const [execution, setExecution] = useState<RuntimeExecution>('windows-native')
  const [runtimeKind, setRuntimeKind] = useState('cgal')
  const [section, setSection] = useState<Section>('Health')
  const [overrides, setOverrides] = useState<Record<string, Partial<RuntimeProfile>>>({})
  const [copyStatus, setCopyStatus] = useState('')
  useEffect(() => { setExecution('windows-native'); setRuntimeKind('cgal'); setSection('Health'); setOverrides({}); setCopyStatus('') }, [profileId])
  const profiles = useMemo(() => createScientificProfiles(hostRoot, execution), [hostRoot, execution])
  const seed = profiles.find(profile => profile.kind === runtimeKind) ?? profiles[0]
  const runtime = { ...seed, ...overrides[seed.id] }
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
  return <main className="scientific-runtime-workspace" aria-label="Scientific Runtimes">
    <header className="scientific-runtime-header"><div><span className="scientific-runtime-kicker">RUNTIMES / SCIENTIFIC</span><h1>Scientific Runtimes</h1><p>A scientific-runtime laboratory for MATH3D. Profiles describe intent; probes establish readiness.</p></div><span className="scientific-runtime-status">Foundation / no probes run</span></header>
    <div className="scientific-runtime-grid">
      <aside className="scientific-runtime-inventory" aria-label="Scientific runtime inventory">
        <label>Environment<select aria-label="Scientific execution environment" value={execution} onChange={event => { setExecution(event.target.value as RuntimeExecution); setCopyStatus('') }}>{Object.entries(executionNames).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <p className="scientific-runtime-note">{execution === 'windows-native' ? 'Candidate native paths only. Installation and probes are not checked.' : 'Adapter planned. Selecting it does not start WSL or Docker.'}</p>
        {profiles.map(profile => <button key={profile.id} className={`scientific-runtime-item ${runtime.kind === profile.kind ? 'selected' : ''}`} aria-pressed={runtime.kind === profile.kind} onClick={() => { setRuntimeKind(profile.kind); setCopyStatus('') }}><strong>{profile.name}</strong><span>Not checked</span><small>{profile.id}</small></button>)}
      </aside>
      <section className="scientific-runtime-detail" aria-label={`${runtime.name} runtime details`}>
        <div className="scientific-runtime-detail-heading"><div><h2>{runtime.name} / {executionNames[execution]}</h2><code>{runtime.id}</code></div><span className="scientific-runtime-status">Not checked / version unknown</span></div>
        <nav className="scientific-runtime-sections" aria-label="Scientific runtime sections">{sections.map(name => <button key={name} className={section === name ? 'selected' : ''} aria-pressed={section === name} onClick={() => { setSection(name); setCopyStatus('') }}>{name}</button>)}</nav>
        <div className="scientific-runtime-section">
          {section === 'Health' && <><h3>Readiness evidence</h3><p>No tools have been discovered or executed. Candidate capabilities below are not validated.</p><ul className="scientific-runtime-checks">{checks.map(check => <li key={check.id}><span>{check.name}</span><small>Not checked</small></li>)}</ul><button disabled title="The bounded native probe runner is the next implementation slice">Run health probes</button><p className="scientific-runtime-note">Compiler, linked-library, geometry, and rendering checks will run explicitly with cancellation and timeouts. A VTK import will not imply C++ SDK or OpenGL readiness.</p></>}
          {section === 'Environment' && <><h3>Candidate environment definition</h3><p>Paths are editable for this session only. They do not create environments or change PATH.</p><div className="scientific-runtime-fields">{([['environmentRoot', 'Environment root'], ['executable', 'Executable / Python'], ['compiler', 'Compiler'], ['cmake', 'CMake'], ['sdkRoot', 'C++ SDK / vcpkg root']] as const).map(([field, name]) => <label key={field}>{name}<input aria-label={`Scientific ${name}`} value={runtime[field] ?? ''} placeholder="Not configured" onChange={event => patchProfile(field, event.target.value)} spellCheck={false} /></label>)}</div><p className="scientific-runtime-note">CGAL and VTK use separate environment candidates. Inherited environment variables are neither read nor displayed; persistent overrides and validation belong to the runtime-profile slice.</p><button onClick={copyProfile}>Copy profile definition</button></>}
          {section === 'Commands' && <><h3>Declarative command recipes</h3><p>Recipes carry runtime identity, argv, timeout, operation, and output references. There is no shell execution in this foundation.</p>{runtime.recipes.length ? runtime.recipes.map(recipe => <details key={recipe.id}><summary>{recipe.name} / planned</summary><pre>{JSON.stringify({ ...recipe, steps: recipe.steps.map(step => ({ ...step, executable: runtime.executable || step.executable })) }, null, 2)}</pre></details>) : <p>Configure / Build / Run / Test all recipes will be added after toolchain validation.</p>}<button disabled title="Managed recipe execution is planned">Run recipe</button></>}
          {section === 'Tests' && <><h3>Capability acceptance tests</h3><ul className="scientific-runtime-checks">{runtime.healthChecks.map(check => <li key={check.id}><span>{check.name}{check.capability && <code>{check.capability}</code>}</span><small>Planned / not run</small></li>)}</ul><p>Tests must emit machine-readable results, logs, resolved versions, and geometry artifact references. No imported code runs by selecting a test.</p></>}
          {section === 'Benchmarks' && <><h3>Reproducible benchmarks</h3><p>No benchmark runs. The runner will record input size, runtime/tool versions, hardware metadata, duration, and output validity before timings can be compared.</p><button disabled title="Benchmark recipes follow the managed runner">Run benchmark</button></>}
          {section === 'Packages' && <><h3>Package provenance</h3><p>No package inventory has been read.</p><p>{runtime.kind === 'cgal' ? 'Target inventory: CGAL, Boost, GMP, MPFR, Eigen, compiler, CMake, Ninja, and vcpkg/Conda provenance.' : runtime.kind === 'vtk' ? 'Target inventory: VTK C++ SDK, vtk Python bindings, compiler, rendering libraries, and OpenGL support.' : 'Package versions will come from explicit runtime probes, not the launcher environment.'}</p><p className="scientific-runtime-note">Setup recipes will require confirmation. DevShell has not installed or upgraded any packages.</p></>}
          {section === 'Artifacts' && <><h3>Geometry and report artifacts</h3><p>No scientific run artifacts yet. Run results will reference scoped geometry, result JSON, logs, and previewable reports.</p><button disabled={!math3dProject || !math3dRepo} onClick={() => { if (math3dProject && math3dRepo) window.dispatchEvent(new CustomEvent('devshell.workspace.open', { detail: { kind: 'files', projectId: math3dProject.id, repositoryId: math3dRepo.id } })) }}>Open MATH3D files</button><p className="scientific-runtime-note">Opening existing files does not generate geometry or start a worker.</p></>}
          {section === 'Integration' && <><h3>MATH3D execution contract</h3><p>This is a request-schema preview, not a submitted job. Worker transport must consume structured requests/results, not parse terminal presentation.</p><pre>{JSON.stringify(contract, null, 2)}</pre><button onClick={copyProfile}>Copy profile definition</button><p>Outputs include exit state, duration, resolved versions, validated capabilities, diagnostics, log references, and scoped artifact references.</p></>}
          {copyStatus && <p role="status">{copyStatus}</p>}
        </div>
        <footer className="scientific-runtime-capabilities"><strong>Declared capabilities / unvalidated</strong><div>{runtime.capabilities.map(capability => <code key={capability}>{capability}</code>)}</div></footer>
      </section>
    </div>
  </main>
}
