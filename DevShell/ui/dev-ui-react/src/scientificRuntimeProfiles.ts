import { scientificRuntimePlugins } from './scientificRuntimePlugins'
import { capabilitiesFor } from './scientificCapabilityRegistry'

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
  inputArtifacts: { path: string; mediaType: string; sha256?: string; bytes?: number; datasetId?: string; sourcePath?: string; sourceRoot?: string }[]
  workingDirectory: string
  timeoutSeconds: number
  outputArtifacts: { path: string; mediaType: string }[]
  provenance?: Record<string, unknown>
}

export interface ScientificRunResult {
  schemaVersion: 1
  runId: string
  runtimeId: string
  recipeId: string
  operation?: string
  testCaseId?: string
  environmentFingerprint?: string
  environmentFingerprintScope?: string
  runFingerprintSha256?: string
  runFingerprintReference?: string
  qualificationSha256?: string
  qualificationReference?: string
  l6Evidence?: { verdict: 'matched' | 'mismatch'; comparison: string; baseline: { runId: string; recordId: string; artifactPath: string; artifactSha256: string }; positive: { artifactPath: string; artifactSha256: string }; rejection: { state: string; outputAbsent: boolean }; roundTrip?: { parserVersion: number; format: string; points: number; triangles: number; bounds: number[]; boundaryEdges: number; nonManifoldEdges: number; closed: boolean; absoluteVolume: number } }
  l7Evidence?: { source: { runId: string; artifactSha256: string }; objSha256: string; consumer: { consumer: string; points: number; triangles: number; bounds: number[]; boundaryEdges: number; nonManifoldEdges: number; closed: boolean } }
  l7InteropEvidence?: { source: { runId: string; artifactSha256: string }; consumerContractSha256: string; vtkConsumer: { points: number; triangles: number; bounds: number[]; signedVolume: number; surfaceArea: number }; math3dConsumer: { points: number; triangles: number; bounds: number[]; signedVolume: number; surfaceArea: number }; rejection: { state: string; reason: string } }
  l8Evidence?: { sourceL7RunId: string; sourceL7ContractSha256: string; observations: { repeats: { caseId: string; durationMs: number; peakProcessMemoryBytes: number; resultSha256: string }[]; cancellation: { state: string; durationMs: number }; timeout: { state: string; durationMs: number; limitSeconds: number }; memory: { state: string; limitBytes: number; requestedBytes: number; exitCode: number } } }
  l9Evidence?: { sourceL8RunId: string; productContractSha256: string; documentSha256: string; resourceSha256: string; viewerSha256: string; regression: { regression: string; documentId: string; structuralHash: string; blueMeshPixels: number; points: number; triangles: number; viewerState: string } }
  l9GmshEvidence?: { sourceL8RunId: string; productContractSha256: string; documentSha256: string; resourceSha256: string; viewerSha256: string; m3dmSha256: string; roundtrip: { verdict: string; geometry: string; topology: string; orientation: string; scale: string }; regression: { regression: string; documentId: string; blueMeshPixels: number; points: number; triangles: number; viewerState: string } }
  volumeEvidence?: { suiteId: string; capabilityId: string; level: string; artifactSha256: string; candidateRecordSha256: string; boundaryArtifactSha256?: string; baseline?: { runId: string; recordId: string; level: string; artifactSha256: string }; reload?: { points: number; tetrahedra: number; boundaryTriangles: number; boundaryEdges: number; nonManifoldEdges: number; volume: number; surfaceArea: number; bounds: number[] }; vtk?: { state: string; points: number; triangles: number; signedVolume: number }; math3d?: { state: string; points: number; triangles: number; signedVolume: number } }
  l8GmshVolumeEvidence?: { sourceL7RunId: string; sourceArtifactSha256: string; observations: { repeats: { caseId: string; durationMs: number; peakProcessMemoryBytes: number }[]; cancellation: { state: string }; timeout: { state: string }; memory: { state: string } } }
  volumeProductReadiness?: { status: string; reason: string; sourceL8RunId: string; tetrahedra: number; sourceMshSha256: string; requiredConsumerContract: string; declaresTetrahedralDocument: boolean }
  qualifications?: { recordId: string; capabilityId: string; level: 'L0' | 'L1' | 'L2' | 'L3' | 'L4' | 'L5' | 'L6' | 'L7' | 'L8' | 'L9'; evidenceId: string; evidenceSha256?: string; status: 'current' | 'stale' | 'unknown'; staleReasons: string[] }[]
  sourceDrift?: { state: 'current' | 'stale' | 'unknown'; comparedFiles: number; unavailableFiles: number; reasons: string[] }
  environmentDrift?: { state: 'current' | 'stale' | 'unknown'; comparedComponents: number; unavailableComponents: number; reasons: string[] }
  state: 'succeeded' | 'failed' | 'cancelled' | 'timed-out'
  exitCode: number | null
  durationMs: number
  workerDurationMs?: number
  stage?: string
  versions: Record<string, string>
  validatedCapabilities: string[]
  diagnostics: { severity: 'info' | 'warning' | 'error'; message: string }[]
  logReference?: string
  artifacts: { path: string; mediaType: string; bytes?: number; sha256?: string; recoveredFromLegacyRun?: boolean; role?: 'result' | 'operand' }[]
  inputArtifacts?: ScientificRunRequest['inputArtifacts']
  before?: Record<string, number | boolean>
  after?: Record<string, number | boolean>
  scope?: string
  provenance?: Record<string, unknown>
  rerunOf?: string
  imports?: { name: string; id?: string; state: string; bytes?: number; sha256?: string; closed?: boolean; triangles?: number; message?: string }[]
  boolean?: { operation: string; scaleB: number; translateB: number[]; empty: boolean; outputArtifact: string; operands: { role: string; datasetId: string; sha256: string; statistics: { vertices: number; faces: number; volume: number; components: number } }[] }
  rendering?: { state?: string; backend?: string; version?: string; capabilities?: string }
  probeResults?: { id: string; readinessLevel: string; status: string; exitCode: number | null; startedAtUtc: string; durationMs: number; stdout: string; stderr: string }[]
  matrixSummary?: { suiteId: string; total: number; passed: number; cases: { caseId: string; runId: string; expected: string; observed: string; verdict: string; durationMs: number }[] }
  rejectionSummary?: { suiteId: string; total: number; passed: number; cases: { caseId: string; recipeId: string; expected: string; observed: string; verdict: string; durationMs: number; diagnostic: string; inputSha256?: string; requestPath: string; resultPath?: string }[] }
}

export const executionNames: Record<RuntimeExecution, string> = {
  'windows-native': 'Windows Native', wsl: 'WSL Ubuntu', docker: 'Docker',
}

export function createScientificProfiles(hostRoot: string, execution: RuntimeExecution): RuntimeProfile[] {
  const root = hostRoot.replace(/[\\/]+$/, '')
  return scientificRuntimePlugins.map(definition => {
    const environmentRoot = execution === 'windows-native' && root && definition.environmentName ? `${root}\\.conda\\${definition.environmentName}` : undefined
    const id = `${definition.kind}-${execution === 'windows-native' ? 'win-conda' : execution}`
    const executable = execution === 'windows-native'
      ? definition.kind === 'sage' ? '' : environmentRoot ? `${environmentRoot}\\python.exe` : 'python'
      : execution === 'wsl' ? definition.kind === 'sage' ? 'sage' : 'python3' : 'python'
    const recipes: CommandRecipe[] = definition.versionArguments ? [{
      schemaVersion: 1, id: `${id}.version`, name: `${definition.name} version`, runtimeId: id, operation: 'runtime.version',
      steps: [{ executable: executable || 'python', arguments: definition.versionArguments, timeoutSeconds: 15 }], artifacts: [],
    }] : []
    return {
      schemaVersion: 1, id, name: definition.name, kind: definition.kind, execution, environmentRoot,
      executable, compiler: definition.sdk ? execution === 'windows-native' ? 'MSVC (configure toolchain)' : 'C++ (configure toolchain)' : undefined,
      cmake: definition.sdk ? 'cmake' : undefined,
      environment: {}, versionProbe: { id: `${definition.kind}.version`, name: `${definition.name} version / provenance`, category: 'version', recipeId: recipes[0]?.id },
      healthChecks: definition.checks, capabilities: capabilitiesFor(definition.kind, execution).map(capability => capability.id), recipes,
    }
  })
}
