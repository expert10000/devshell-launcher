import type { FileReference } from './WorkspaceFileNavigation'
export type ComparisonPair = { left?: FileReference; right?: FileReference }
const pairs = new Map<string, ComparisonPair>()
export function comparisonPair(profileId: string): ComparisonPair { return pairs.get(profileId) ?? {} }
export function setComparisonPair(profileId: string, pair: ComparisonPair) {
  if (!pairs.has(profileId) && pairs.size >= 20) pairs.delete(pairs.keys().next().value!)
  pairs.set(profileId, pair)
  window.dispatchEvent(new CustomEvent('devshell.workspace.comparison', { detail: { profileId } }))
}
export function selectComparisonArtifact(profileId: string, side: 'left' | 'right', file: FileReference) {
  if (file.kind === 'pdf') return
  setComparisonPair(profileId, { ...comparisonPair(profileId), [side]: file })
}
export function compareTextLines(left: string, right: string) {
  const a = left.replace(/\r\n?/g, '\n').split('\n'); const b = right.replace(/\r\n?/g, '\n').split('\n')
  const rows: { line: number; left?: string; right?: string }[] = []; let changed = 0
  const limit = Math.min(5000, Math.max(a.length, b.length))
  for (let index = 0; index < limit; index++) if (a[index] !== b[index]) {
    changed++; if (rows.length < 100) rows.push({ line: index + 1, left: a[index]?.slice(0, 4096), right: b[index]?.slice(0, 4096) })
  }
  return { rows, changed, truncated: Math.max(a.length, b.length) > 5000 || changed > rows.length, linesCompared: limit }
}
