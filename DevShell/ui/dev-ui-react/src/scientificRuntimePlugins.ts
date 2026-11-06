import type { RuntimeExecution, RuntimeKind, RuntimeProbe } from './scientificRuntimeProfiles'

export const scientificSections = ['State', 'Matrix', 'Environment', 'Commands', 'Boolean', 'Tests', 'Catalog', 'Benchmarks', 'Packages', 'Artifacts', 'History', 'Integration'] as const
export type ScientificSection = typeof scientificSections[number]

export interface ScientificCatalogTest {
  id: string
  name: string
  recipeId: string
  action: string
  expected: string
  requires?: 'datasets' | 'matrix' | 'integration'
}

export interface ScientificRuntimePlugin {
  kind: Exclude<RuntimeKind, 'custom'>
  name: string
  checks: RuntimeProbe[]
  configuredBackends: RuntimeExecution[]
  sections: ScientificSection[]
  environmentName: string
  commandView: 'mesh' | 'sage' | 'none'
  testView: 'cgal' | 'vtk' | 'candidate' | 'sage'
  artifactView: 'mesh' | 'none'
  integrationView: 'cgal' | 'unconfigured'
  versionArguments?: string[]
  sdk: boolean
  labProbe?: boolean
  holdTest?: boolean
  comparisonPresets?: boolean
  catalogTests?: ScientificCatalogTest[]
}

const common: ScientificSection[] = ['State', 'Matrix', 'Environment', 'Tests', 'Benchmarks', 'Packages', 'History', 'Integration']

// These declarations describe shipped UI and managed entry points, not installed libraries
// or certified capabilities. Qualification still comes from run-scoped evidence.
export const scientificRuntimePlugins: ScientificRuntimePlugin[] = [
  { kind: 'cgal', name: 'CGAL', environmentName: 'devshell-cgal', commandView: 'mesh', testView: 'cgal', artifactView: 'mesh', integrationView: 'cgal', sdk: true, labProbe: true, holdTest: true, comparisonPresets: true, configuredBackends: ['windows-native'], sections: [...common, 'Commands', 'Boolean', 'Catalog', 'Artifacts'], catalogTests: [
    { id: 'cgal-matrix', name: 'CGAL validation matrix', recipeId: 'matrix.cgal.validation', action: 'run-matrix', expected: 'Registered mesh cases match their expected verdicts.', requires: 'matrix' },
    { id: 'math3d-native', name: 'Math3D native Boolean integration', recipeId: 'integration.math3d.native-boolean', action: 'math3d-prepare-run', expected: 'Fourteen native Boolean cases pass their saved comparisons.', requires: 'integration' },
  ], checks: [
    { id: 'cgal.dependencies', name: 'Boost / GMP / MPFR / Eigen provenance', category: 'package' },
    { id: 'cgal.include', name: 'CGAL include / compiler test', category: 'compiler' },
    { id: 'cgal.link', name: 'CGAL link test and linked libraries', category: 'compiler' },
    { id: 'cgal.surface-mesh', name: 'Surface_mesh smoke test', category: 'geometry', capability: 'mesh.validate' },
  ] },
  { kind: 'vtk', name: 'VTK', environmentName: 'devshell-vtk', commandView: 'mesh', testView: 'vtk', artifactView: 'mesh', integrationView: 'unconfigured', versionArguments: ['-c', 'from vtkmodules.vtkCommonCore import vtkVersion; print(vtkVersion.GetVTKVersion())'], sdk: true, labProbe: true, holdTest: true, configuredBackends: ['windows-native'], sections: [...common, 'Commands', 'Catalog', 'Artifacts'], catalogTests: [
    { id: 'vtk-probe', name: 'VTK runtime probes', recipeId: 'lab.probe', action: 'lab-probe', expected: 'Installed VTK binding and render probes report their evidence.' },
    { id: 'vtk-rejections', name: 'VTK rejection checks', recipeId: 'matrix.vtk.rejections', action: 'vtk-rejections', expected: 'Invalid mesh requests are rejected with diagnostics.', requires: 'datasets' },
  ], checks: [
    { id: 'vtk.cpp', name: 'VTK C++ SDK / include / link', category: 'compiler' },
    { id: 'vtk.python', name: 'VTK Python bindings', category: 'package' },
    { id: 'vtk.polydata', name: 'vtkPolyData smoke test', category: 'geometry', capability: 'geometry.polydata' },
    { id: 'vtk.opengl', name: 'Rendering / OpenGL / offscreen rendering', category: 'rendering', capability: 'render.offscreen' },
  ] },
  { kind: 'gmsh', name: 'Gmsh', environmentName: 'devshell-scientific', commandView: 'mesh', testView: 'candidate', artifactView: 'none', integrationView: 'unconfigured', sdk: false, labProbe: true, configuredBackends: ['windows-native'], sections: [...common, 'Commands'], checks: [{ id: 'gmsh.import', name: 'Executable / Python module probe', category: 'package' }] },
  { kind: 'sage', name: 'SageMath', environmentName: '', commandView: 'sage', testView: 'sage', artifactView: 'none', integrationView: 'unconfigured', sdk: false, configuredBackends: ['wsl'], sections: [...common, 'Commands', 'Catalog'], catalogTests: [
    { id: 'sage-version', name: 'SageMath installation', recipeId: 'sage.version', action: 'sage-recipe', expected: 'Sage version is recorded.' },
    { id: 'sage-factor', name: 'Exact factorization', recipeId: 'sage.factor-smoke', action: 'sage-recipe', expected: 'x² − 1 factors as (x − 1) × (x + 1).' },
  ], checks: [{ id: 'sage.session', name: 'Sage interpreter smoke test', category: 'geometry' }] },
  { kind: 'python', name: 'Python / SciPy', environmentName: 'devshell-scientific', commandView: 'none', testView: 'candidate', artifactView: 'none', integrationView: 'unconfigured', versionArguments: ['--version'], sdk: false, configuredBackends: ['windows-native'], sections: common, checks: [{ id: 'python.scipy', name: 'Python / NumPy / SciPy imports and versions', category: 'package' }] },
]

export function scientificPlugin(kind: RuntimeKind): ScientificRuntimePlugin | undefined {
  return scientificRuntimePlugins.find(item => item.kind === kind)
}

export function runtimeSections(kind: RuntimeKind, execution: RuntimeExecution): ScientificSection[] {
  const plugin = scientificPlugin(kind)
  if (!plugin || !plugin.configuredBackends.includes(execution)) return ['State', 'Matrix', 'Environment', 'Packages', 'History']
  return scientificSections.filter(section => plugin.sections.includes(section))
}
