import type { WorkspaceTabInput, WorkspaceViewTab } from './useWorkspaceTabs'

const allowed = new Set(['logs', 'diff', 'files', 'pdf', 'browser', 'jupyter'])
function relative(value?: string) { return value === undefined || value.length <= 2048 && !/^[\/]|[\\:\0]/.test(value) && !value.split('/').some(part => part === '.' || part === '..' || part.toLowerCase() === '.git') }
function cleanUrl(value?: string) {
  try { const url = new URL(value ?? ''); if (!['http:', 'https:'].includes(url.protocol)) return undefined; url.username = ''; url.password = ''; url.search = ''; url.hash = ''; return url.href } catch { return undefined }
}
function identity(tab: WorkspaceTabInput) {
  return tab.kind === 'pdf' ? `pdf:${tab.projectId}:${tab.repositoryId}:${tab.filePath ?? ''}` : tab.kind === 'browser' ? `browser:${cleanUrl(tab.url)}` : tab.kind === 'jupyter' ? `jupyter:${tab.projectId}:${tab.servicePath ?? ''}` : `${tab.kind}:${tab.projectId}:${tab.repositoryId}`
}
export function restoreWorkspaceDescriptors(previous: WorkspaceViewTab[], inputs: WorkspaceTabInput[], focused?: string) {
  const failure = (error: string) => ({ tabs: previous, primaryId: '', secondaryId: '', focusedId: '', error })
  if (!Array.isArray(inputs) || inputs.length !== 2 || inputs.some(tab => !tab || !allowed.has(tab.kind) || !relative(tab.filePath) || !relative(tab.servicePath) || tab.kind === 'browser' && !cleanUrl(tab.url) || ['logs', 'diff', 'files', 'pdf'].includes(tab.kind) && (!tab.projectId || !tab.repositoryId))) return failure('This layout contains invalid workspace descriptors.')
  if (identity(inputs[0]) === identity(inputs[1])) return failure('A split layout needs two distinct views.')
  const next = [...previous]; const restored: WorkspaceViewTab[] = []
  for (const input of inputs) {
    const existing = next.find(tab => identity(tab) === identity(input))
    const tab: WorkspaceViewTab = existing ? { ...existing, activationId: undefined, revealPath: undefined, sourceLine: undefined } : {
      id: crypto.randomUUID(), kind: input.kind, projectId: input.projectId, repositoryId: input.repositoryId, filePath: input.filePath,
      side: input.side === 'staged' ? 'staged' : 'working', page: input.page, url: cleanUrl(input.url), servicePath: input.servicePath, restored: true,
    }
    if (existing) next[next.findIndex(item => item.id === tab.id)] = tab
    else next.push(tab)
    restored.push(tab)
  }
  if (next.length > 24) return failure('Close some workspace tabs before restoring this layout (limit: 24).')
  return { tabs: next, primaryId: restored[0].id, secondaryId: restored[1].id, focusedId: restored[focused === 'secondary' ? 1 : 0].id, error: '' }
}
