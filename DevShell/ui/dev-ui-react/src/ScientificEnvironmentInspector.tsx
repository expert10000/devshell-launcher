import { useState } from 'react'
import type { RuntimeProfile } from './scientificRuntimeProfiles'
import type { ObservedScientificRuntime, ScientificRuntimeReport } from './scientificRuntimeReport'
import type { useScientificRuntime } from './useScientificRuntime'

export function ScientificEnvironmentInspector({ runtime, observed, report, native, edited }: { runtime: RuntimeProfile; observed?: ObservedScientificRuntime; report: ScientificRuntimeReport | null; native: ReturnType<typeof useScientificRuntime>; edited: boolean }) {
  const [copyStatus, setCopyStatus] = useState('')
  const environment = native.environments[runtime.id]
  const result = native.jobs[runtime.id]?.result
  const compiler = result?.versions.msvc ?? environment?.evidence?.compilerVersion ?? report?.compiler.actualVersion
  const rendering = result?.rendering ?? environment?.evidence?.rendering ?? observed?.sdk?.renderingEvidence
  const renderingLines = rendering?.capabilities?.split(/\r?\n/).filter(line => /OpenGL.*(vendor|renderer|version)/i.test(line)) ?? []
  const enabled = runtime.execution === 'windows-native' && (runtime.kind === 'cgal' || runtime.kind === 'vtk') && !edited
  const status = (value?: string) => value === 'passed' ? 'Passed' : value === 'not-tested' ? 'Not tested' : value ?? 'Unknown'
  const packageVersion = (...names: string[]) => observed?.packages.find(item => names.includes(item.name))?.version ?? 'Not recorded'
  const evidence = (id: string) => observed?.checks.find(check => check.id === id)?.state
  const rows: [string, string][] = [
    ['Status', edited ? 'Definition changed / not checked' : observed?.state ?? 'Not checked'],
    [runtime.kind === 'vtk' ? 'VTK SDK' : 'CGAL SDK', observed?.version ?? 'Unknown'],
    ['Python', observed?.pythonVersion ?? 'Unknown'],
    ['Boost', packageVersion('libboost', 'boost-cpp', 'boost')], ['GMP', packageVersion('gmp')], ['MPFR', packageVersion('mpfr')], ['Eigen', packageVersion('eigen')],
    ['CMake', observed?.tools?.cmake?.version ?? 'Unknown'], ['Ninja', observed?.tools?.ninja?.version ?? 'Unknown'],
    ['MSVC compiler version', compiler ?? 'Not probed / refresh inventory or run a CMake configure'],
    ['Compiler version evidence', result?.versions.msvc ? 'Recorded CMake compiler identification' : environment?.evidence?.compilerVersion ? environment.evidence.compilerSource ?? 'Recorded compiler probe' : report?.compiler.actualVersion ? 'cl.exe /Bv (version only, not compilation)' : 'No actual compiler version recorded'],
    ['MSVC toolset folder', report?.compiler.toolsetVersion ?? 'Not recorded'],
    ['MSVC binary metadata (not compiler version)', report?.compiler.binaryVersion ?? report?.compiler.version ?? 'Unknown'],
    ['vcpkg', environment ? `${environment.installedVcpkg ?? 'Not found'} / not used by this Conda SDK` : 'Load environment to inspect'],
    ['C++ SDK files', observed?.sdk?.installed ? 'Present / headers and CMake config' : 'Not recorded'],
    ['Python bindings', status(evidence(`${runtime.kind}.python`))],
    ['Compiler / include / link smoke', status(observed?.sdk?.compilation)],
    ['C++ link smoke', status(observed?.sdk?.linking)],
    [runtime.kind === 'vtk' ? 'vtkPolyData' : 'Surface_mesh smoke', status(evidence(`${runtime.kind}.geometry`) ?? (runtime.kind === 'vtk' ? evidence('vtk.polydata') : undefined))],
    ['Offscreen rendering', runtime.kind === 'vtk' ? rendering?.state === 'succeeded' ? 'Passed / recorded render result' : status(observed?.sdk?.rendering) : 'Not applicable to the CGAL adapter'],
    ['Rendering backend', runtime.kind === 'vtk' ? rendering?.backend ?? 'Not recorded / Load environment for saved rendering evidence' : 'Not applicable'],
    ['OpenGL evidence', runtime.kind === 'vtk' ? renderingLines.join(' / ') || 'Not recorded (a VTK import is not an OpenGL test)' : 'Not applicable'],
    ['Interactive rendering', 'Not tested'],
  ]
  const copyEnvironment = async () => {
    if (!environment) return
    try { await navigator.clipboard.writeText(JSON.stringify(environment.environment, null, 2)); setCopyStatus('Allowlisted child environment copied; no tokens, proxies, or full host environment.') }
    catch { setCopyStatus('Clipboard unavailable.') }
  }
  return <section className="scientific-inspector" aria-label="Scientific Environment Inspector">
    <h3>Environment Inspector</h3>
    <dl className="scientific-inspector-facts">{rows.map(([name, value]) => <div key={name}><dt>{name}</dt><dd>{value}</dd></div>)}</dl>
    <div className="scientific-inspector-actions">
      <button disabled={!enabled || native.pending} onClick={() => native.send(runtime.id, 'environment')}>Load environment</button>
      <button disabled={!enabled || native.pending} title="Opens an external runtime PowerShell, not a VS developer shell" onClick={() => native.send(runtime.id, 'terminal')}>Open terminal</button>
      <button disabled={!environment} onClick={copyEnvironment}>Copy environment</button>
      <button disabled={!enabled || native.busy || native.pending} onClick={() => native.send(runtime.id, 'recipe', { recipeId: 'diagnostics' })}>Run diagnostics</button>
      <button disabled={!enabled || native.pending} title="Exports the installed definition, not edited session overrides or readiness evidence" onClick={() => native.send(runtime.id, 'export')}>Export profile</button>
    </div>
    {environment && <details><summary>Child environment / SDK paths</summary><dl className="scientific-inspector-facts">{Object.entries(environment.environment).map(([name, value]) => <div key={name}><dt>{name}</dt><dd><code>{value}</code></dd></div>)}<div><dt>VCPKG_ROOT</dt><dd>{environment.vcpkgRoot ?? 'Unset / Conda SDK selected'}</dd></div></dl></details>}
    <p className="scientific-runtime-note">Only allowlisted child settings are displayed/copied. Diagnostics perform inventory/import and compiler-version probes, not C++ compilation or rendering tests. Recorded smoke/render evidence is not a live health check and may be replaced by fresh inventory. Edited definitions and WSL/Docker adapters cannot execute these native actions.</p>
    {copyStatus && <p role="status">{copyStatus}</p>}
  </section>
}
