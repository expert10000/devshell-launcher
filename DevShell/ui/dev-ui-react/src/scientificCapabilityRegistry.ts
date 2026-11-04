import catalog from '../../../../schemas/scientific-capabilities.v1.json'
import type { RuntimeExecution, RuntimeKind } from './scientificRuntimeProfiles'

export interface CapabilityProvider {
  runtimeId: string
  backend: RuntimeExecution
  limitations: string
}

export interface SemanticCapability {
  id: string
  version: number
  parametersSchema: string
  resultSchema: string
  providers: CapabilityProvider[]
}

const runtimeId = (kind: Exclude<RuntimeKind, 'custom'>, execution: RuntimeExecution) =>
  `${kind}-${execution === 'windows-native' ? 'win-conda' : execution}`

export const capabilityRegistryVersion = catalog.schemaVersion
export const semanticCapabilities: SemanticCapability[] = catalog.capabilities as SemanticCapability[]

export function capabilitiesFor(kind: Exclude<RuntimeKind, 'custom'>, execution: RuntimeExecution): SemanticCapability[] {
  const id = runtimeId(kind, execution)
  return semanticCapabilities.filter(capability => capability.providers.some(provider => provider.runtimeId === id && provider.backend === execution))
}

export function capabilityProvider(capabilityId: string, kind: Exclude<RuntimeKind, 'custom'>, execution: RuntimeExecution): CapabilityProvider | undefined {
  const id = runtimeId(kind, execution)
  return semanticCapabilities.find(capability => capability.id === capabilityId)?.providers.find(provider => provider.runtimeId === id && provider.backend === execution)
}
