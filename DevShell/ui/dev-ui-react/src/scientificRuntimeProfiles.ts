export type RuntimeKind = 'cgal' | 'vtk' | 'gmsh' | 'sage' | 'python' | 'custom'
export type RuntimeExecution = 'windows-native' | 'wsl' | 'docker'
export type RuntimeReadiness = 'not-checked' | 'checking' | 'ready' | 'missing' | 'failed'

export interface CommandRecipe {
  schemaVersion: 1
  id: string
  name: string
  runtimeId: string
  operation: string
  steps: { executable: string; arguments: string[]; cwd?: string; timeoutSeconds: number }[]
  artifacts: { path: string; mediaType: string }[]
}

export interface RuntimeProbe {
  id: string
  name: string
  category: 'version' | 'package' | 'compiler' | 'geometry' | 'rendering'
  capability?: string
  recipeId?: string
}

export interface RuntimeProfile {
  schemaVersion: 1
  id: string
  name: string
  kind: RuntimeKind
  execution: RuntimeExecution
  environmentRoot?: string
  executable?: string
  compiler?: string
  cmake?: string
  sdkRoot?: string
  environment: Record<string, string>
  versionProbe: RuntimeProbe
  healthChecks: RuntimeProbe[]
  capabilities: string[]
  recipes: CommandRecipe[]
}

export interface ScientificRunRequest {
  schemaVersion: 1
  runId: string
  runtimeId: string
  recipeId: string
  operation: string
  parameters: Record<string, unknown>
  inputArtifacts: { path: string; mediaType: string }[]
  workingDirectory: string
  timeoutSeconds: number
  outputArtifacts: { path: string; mediaType: string }[]
}

export interface ScientificRunResult {
  schemaVersion: 1
  runId: string
  runtimeId: string
  state: 'succeeded' | 'failed' | 'cancelled' | 'timed-out'
  exitCode: number | null
  durationMs: number
  versions: Record<string, string>
  validatedCapabilities: string[]
  diagnostics: { severity: 'info' | 'warning' | 'error'; message: string }[]
  logReference?: string
  artifacts: { path: string; mediaType: string }[]
}

const definitions: { kind: RuntimeKind; name: string; capabilities: string[]; checks: RuntimeProbe[] }[] = [
  { kind: 'cgal', name: 'CGAL', capabilities: ['mesh.read', 'mesh.write', 'mesh.validate', 'mesh.repair', 'mesh.boolean', 'mesh.decimate', 'mesh.remesh', 'geometry.aabb', 'geometry.distance'], checks: [
    { id: 'cgal.dependencies', name: 'Boost / GMP / MPFR / Eigen provenance', category: 'package' },
    { id: 'cgal.include', name: 'CGAL include / compiler test', category: 'compiler' },
    { id: 'cgal.link', name: 'CGAL link test and linked libraries', category: 'compiler' },
    { id: 'cgal.surface-mesh', name: 'Surface_mesh smoke test', category: 'geometry', capability: 'mesh.validate' },
  ] },
  { kind: 'vtk', name: 'VTK', capabilities: ['mesh.read', 'mesh.write', 'mesh.filter', 'geometry.polydata', 'render.interactive', 'render.offscreen'], checks: [
    { id: 'vtk.cpp', name: 'VTK C++ SDK / include / link', category: 'compiler' },
    { id: 'vtk.python', name: 'VTK Python bindings', category: 'package' },
    { id: 'vtk.polydata', name: 'vtkPolyData smoke test', category: 'geometry', capability: 'geometry.polydata' },
    { id: 'vtk.opengl', name: 'Rendering / OpenGL / offscreen rendering', category: 'rendering', capability: 'render.offscreen' },
  ] },
  { kind: 'gmsh', name: 'Gmsh', capabilities: ['mesh.generate', 'mesh.read', 'mesh.write'], checks: [{ id: 'gmsh.import', name: 'Executable / Python module probe', category: 'package' }] },
  { kind: 'sage', name: 'SageMath', capabilities: ['math.symbolic', 'math.number-theory'], checks: [{ id: 'sage.session', name: 'Sage interpreter smoke test', category: 'geometry' }] },
  { kind: 'python', name: 'Python / SciPy', capabilities: ['math.numeric', 'math.linear-algebra'], checks: [{ id: 'python.scipy', name: 'Python / NumPy / SciPy imports and versions', category: 'package' }] },
]

export const executionNames: Record<RuntimeExecution, string> = {
  'windows-native': 'Windows Native', wsl: 'WSL Ubuntu', docker: 'Docker',
}

export function createScientificProfiles(hostRoot: string, execution: RuntimeExecution): RuntimeProfile[] {
  const root = hostRoot.replace(/[\\/]+$/, '')
  return definitions.map(definition => {
    const suffix = definition.kind === 'vtk' ? 'devshell-vtk' : definition.kind === 'cgal' ? 'devshell-cgal' : 'devshell-scientific'
    const environmentRoot = execution === 'windows-native' && root ? `${root}\\.conda\\${suffix}` : undefined
    const id = `${definition.kind}-${execution === 'windows-native' ? 'win-conda' : execution}`
    const executable = execution === 'windows-native'
      ? definition.kind === 'sage' ? '' : definition.kind === 'gmsh' ? 'gmsh' : environmentRoot ? `${environmentRoot}\\python.exe` : 'python'
      : execution === 'wsl' ? definition.kind === 'sage' ? 'sage' : 'python3' : 'python'
    const recipes: CommandRecipe[] = definition.kind === 'vtk' ? [{
      schemaVersion: 1, id: `${id}.version`, name: 'VTK Python version', runtimeId: id, operation: 'runtime.version',
      steps: [{ executable: executable || 'python', arguments: ['-c', 'from vtkmodules.vtkCommonCore import vtkVersion; print(vtkVersion.GetVTKVersion())'], timeoutSeconds: 15 }], artifacts: [],
    }] : definition.kind === 'python' ? [{
      schemaVersion: 1, id: `${id}.version`, name: 'Python version', runtimeId: id, operation: 'runtime.version',
      steps: [{ executable: executable || 'python', arguments: ['--version'], timeoutSeconds: 15 }], artifacts: [],
    }] : []
    return {
      schemaVersion: 1, id, name: definition.name, kind: definition.kind, execution, environmentRoot,
      executable, compiler: definition.kind === 'cgal' || definition.kind === 'vtk' ? execution === 'windows-native' ? 'MSVC (configure toolchain)' : 'C++ (configure toolchain)' : undefined,
      cmake: definition.kind === 'cgal' || definition.kind === 'vtk' ? 'cmake' : undefined,
      environment: {}, versionProbe: { id: `${definition.kind}.version`, name: `${definition.name} version / provenance`, category: 'version', recipeId: recipes[0]?.id },
      healthChecks: definition.checks, capabilities: definition.capabilities, recipes,
    }
  })
}
