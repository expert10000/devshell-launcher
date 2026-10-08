export type WorkspaceSplitState = {
  profileId: string; direction: 'right' | 'below' | null; primaryId: string | null; secondaryId: string | null;
  focused: 'primary' | 'secondary'; ratio: number
}

export function singleWorkspacePane(profileId: string, activeId: string | null): WorkspaceSplitState {
  return { profileId, direction: null, primaryId: activeId, secondaryId: null, focused: 'primary', ratio: 50 }
}

export function resolveWorkspaceSplit(state: WorkspaceSplitState, profileId: string, ids: string[], activeId: string | null): WorkspaceSplitState {
  const selected = activeId && ids.includes(activeId) ? activeId : null
  if (state.profileId !== profileId) return singleWorkspacePane(profileId, selected)
  let next: WorkspaceSplitState
  if (!state.direction) next = { ...state, primaryId: selected, secondaryId: null, focused: 'primary' }
  else if (!state.primaryId || !state.secondaryId || !ids.includes(state.primaryId) || !ids.includes(state.secondaryId) || state.primaryId === state.secondaryId)
    next = singleWorkspacePane(profileId, selected ?? (state.primaryId && ids.includes(state.primaryId) ? state.primaryId : state.secondaryId && ids.includes(state.secondaryId) ? state.secondaryId : null))
  else if (!selected) next = state // Temporarily showing terminals/dashboard does not discard the split.
  else if (selected === state.primaryId) next = { ...state, focused: 'primary' }
  else if (selected === state.secondaryId) next = { ...state, focused: 'secondary' }
  else next = { ...state, [state.focused === 'primary' ? 'primaryId' : 'secondaryId']: selected }
  return next.profileId === state.profileId && next.direction === state.direction && next.primaryId === state.primaryId && next.secondaryId === state.secondaryId && next.focused === state.focused && next.ratio === state.ratio ? state : next
}

export function splitWorkspacePane(state: WorkspaceSplitState, direction: 'right' | 'below', ids: string[], activeId: string | null): WorkspaceSplitState {
  const current = resolveWorkspaceSplit(state, state.profileId, ids, activeId)
  if (current.direction) return { ...current, direction }
  const other = ids.find(id => id !== activeId)
  if (!activeId || !ids.includes(activeId) || !other) return current
  return { ...current, direction, primaryId: activeId, secondaryId: other, focused: 'primary', ratio: 50 }
}

export function chooseWorkspacePane(state: WorkspaceSplitState, pane: 'primary' | 'secondary', id: string): WorkspaceSplitState {
  const key = pane === 'primary' ? 'primaryId' : 'secondaryId'
  const otherKey = pane === 'primary' ? 'secondaryId' : 'primaryId'
  // Explicitly choosing the other pane's tab swaps slots rather than duplicating a viewer.
  return { ...state, [key]: id, [otherKey]: state[otherKey] === id ? state[key] : state[otherKey], focused: pane }
}

export function resizeWorkspacePanes(state: WorkspaceSplitState, ratio: number): WorkspaceSplitState {
  return { ...state, ratio: Number.isFinite(ratio) ? Math.min(80, Math.max(20, ratio)) : 50 }
}
