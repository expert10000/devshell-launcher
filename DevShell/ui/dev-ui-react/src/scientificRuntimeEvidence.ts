export type RuntimeEvidenceInput = {
  configured: boolean
  loading: boolean
  loadError: string
  recordedState?: string
  version?: string | null
  edited?: boolean
  managedJobState?: string
}

// Installation inventory is a dated observation. A managed job is a separate
// observation, and neither label promotes an operation to qualified support.
export function runtimeEvidenceLabel(input: RuntimeEvidenceInput): string {
  if (!input.configured) return 'Not configured'
  if (input.edited) return 'Definition edited / recorded evidence stale'
  if (input.loading) return 'Inventory loading'
  if (input.loadError) return 'Inventory load failed'
  const recorded = input.recordedState
    ? `Recorded ${input.recordedState} / ${input.version || 'unknown version'}`
    : 'Inventory missing / version unknown'
  return input.managedJobState ? `${recorded} / managed test ${input.managedJobState}` : recorded
}
