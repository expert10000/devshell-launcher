import type { RuntimeExecution, RuntimeKind, RuntimeProbe } from './scientificRuntimeProfiles'

export const scientificSections = ['State', 'Environment', 'Commands', 'Boolean', 'Tests', 'Catalog', 'Benchmarks', 'Packages', 'Artifacts', 'History', 'Integration'] as const
export type ScientificSection = typeof scientificSections[number]

export interface ScientificRuntimePlugin {
  kind: Exclude<RuntimeKind, 'custom'>
  name: string
  capabilities: string[]
  checks: RuntimeProbe[]
  configuredBackends: RuntimeExecution[]
  sections: ScientificSection[]
}

const common: ScientificSection[] = ['State', 'Environment', 'Tests', 'Benchmarks', 'Packages', 'History', 'Integration']

// These declarations describe shipped UI and managed entry points, not installed libraries
// or certified capabilities. Qualification still comes from run-scoped evidence.
export const scientificRuntimePlugins: ScientificRuntimePlugin[] = [
  { kind: 'cgal', name: 'CGAL', configuredBackends: ['windows-native'], sections: [...common, 'Commands', 'Boolean', 'Catalog', 'Artifacts'], capabilities: ['mesh.read', 'mesh.write', 'mesh.validate', 'mesh.repair', 'mesh.boolean', 'mesh.decimate', 'mesh.remesh', 'geometry.aabb', 'geometry.distance'], checks: [
    { id: 'cgal.dependencies', name: 'Boost / GMP / MPFR / Eigen provenance', category: 'package' },
    { id: 'cgal.include', name: 'CGAL include / compiler test', category: 'compiler' },
    { id: 'cgal.link', name: 'CGAL link test and linked libraries', category: 'compiler' },
    { id: 'cgal.surface-mesh', name: 'Surface_mesh smoke test', category: 'geometry', capability: 'mesh.validate' },
  ] },
  { kind: 'vtk', name: 'VTK', configuredBackends: ['windows-native'], sections: [...common, 'Commands', 'Artifacts'], capabilities: ['mesh.read', 'mesh.write', 'mesh.filter', 'geometry.polydata', 'render.interactive', 'render.offscreen'], checks: [
    { id: 'vtk.cpp', name: 'VTK C++ SDK / include / link', category: 'compiler' },
    { id: 'vtk.python', name: 'VTK Python bindings', category: 'package' },
    { id: 'vtk.polydata', name: 'vtkPolyData smoke test', category: 'geometry', capability: 'geometry.polydata' },
    { id: 'vtk.opengl', name: 'Rendering / OpenGL / offscreen rendering', category: 'rendering', capability: 'render.offscreen' },
  ] },
  { kind: 'gmsh', name: 'Gmsh', configuredBackends: ['windows-native'], sections: common, capabilities: ['mesh.generate', 'mesh.read', 'mesh.write'], checks: [{ id: 'gmsh.import', name: 'Executable / Python module probe', category: 'package' }] },
  { kind: 'sage', name: 'SageMath', configuredBackends: ['wsl'], sections: [...common, 'Commands'], capabilities: ['math.symbolic', 'math.number-theory'], checks: [{ id: 'sage.session', name: 'Sage interpreter smoke test', category: 'geometry' }] },
  { kind: 'python', name: 'Python / SciPy', configuredBackends: ['windows-native'], sections: common, capabilities: ['math.numeric', 'math.linear-algebra'], checks: [{ id: 'python.scipy', name: 'Python / NumPy / SciPy imports and versions', category: 'package' }] },
]

export function runtimeSections(kind: RuntimeKind, execution: RuntimeExecution): ScientificSection[] {
  const plugin = scientificRuntimePlugins.find(item => item.kind === kind)
  if (!plugin || !plugin.configuredBackends.includes(execution)) return ['State', 'Environment', 'Packages', 'History']
  return scientificSections.filter(section => plugin.sections.includes(section))
}
