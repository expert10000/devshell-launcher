import { useState } from 'react'
import { RepositoryChangesPanel } from './RepositoryChangesPanel'

type Repo = { id: string; name: string; path: string; url?: string; buildTask?: string; pdfPath?: string; pdfDirectory?: string }
type Status = { projectId: string; id: string; path: string; branch?: string; upstream?: string; ahead?: number; behind?: number; changed: number; error?: string;
  lastCommit?: { hash: string; subject: string; author: string; timestamp: string };
  remotes?: { name: string; url: string; direction: string }[];
  worktrees?: { path: string; branch?: string; head?: string; detached: boolean; locked: boolean; prunable: boolean; bare: boolean }[];
  metadataErrors?: string[] }
type Job = { key: string; state: string; action?: string }
type Action = 'diff' | 'commit' | 'pull' | 'push' | 'history' | 'github' | 'fetch' | 'log' | 'build' | 'pdf' | 'files'

export function RepositoryStrip({ project, profileId, statuses, jobs, errors, reservedKeys, onAction }: {
  project: { id: string; name: string; repositories?: Repo[] }; profileId?: string | null; statuses: Status[];
  jobs: Job[]; errors: Record<string, string>; reservedKeys: Set<string>; onAction: (repoId: string, action: Action) => void
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [changesId, setChangesId] = useState<string | null>(null)
  const repos = project.repositories ?? []
  const selected = repos.find((repo) => repo.id === selectedId) ?? repos[0]
  const statusOf = (repo: Repo) => statuses.find((status) => status.projectId === project.id && status.id === repo.id)
  const summary = (status?: Status) => !status ? 'Checking...' : status.error ? 'Unavailable' :
    `${status.branch ?? 'No branch'} · ${status.changed ? `${status.changed} modified` : 'clean'} · ${status.upstream ? `↑${status.ahead ?? '?'} ↓${status.behind ?? '?'}` : 'no upstream'}`
  if (!selected) return <section className="repository-strip" aria-label="Project repository"><span>{project.name}: no Git repository found. Configure repositories or choose a folder inside a checkout.</span></section>
  const status = statusOf(selected)
  const key = `${profileId}:${project.id}:${selected.id}`
  const job = jobs.find((item) => item.key === key)
  const busy = !!job && ['queued', 'building', 'running'].includes(job.state)
  const blocked = busy || reservedKeys.has(key)
  const unavailable = !status || !!status.error
  const detached = status?.branch === '(detached)'
  return <section className="repository-strip" aria-label={`${project.name} repositories`}>
    <div className="repository-strip-selector" role="group" aria-label="Select repository">
      {repos.map((repo) => <button key={repo.id} aria-pressed={repo.id === selected.id} title={statusOf(repo)?.path ?? repo.path} onClick={() => setSelectedId(repo.id)}>
        <strong>{repo.name}</strong><span>{summary(statusOf(repo))}</span>
      </button>)}
    </div>
    <div className="repository-strip-actions">
      <button disabled={blocked || unavailable} onClick={() => setChangesId(selected.id)}>Changes</button>
      <button disabled={unavailable} onClick={() => onAction(selected.id, 'diff')}>Diff</button>
      <button disabled={blocked || unavailable || detached} title="Preview and commit staged files only" onClick={() => onAction(selected.id, 'commit')}>Commit</button>
      <button disabled={blocked || unavailable || detached || !status?.upstream || !!status?.changed} title={status?.changed ? 'Commit or stash local changes first' : 'Fast-forward pull only'} onClick={() => onAction(selected.id, 'pull')}>Pull</button>
      <button disabled={blocked || unavailable || detached || !status?.upstream} title="Confirm destination and push this commit without force" onClick={() => onAction(selected.id, 'push')}>Push</button>
      <button disabled={blocked || unavailable || !status?.lastCommit} onClick={() => onAction(selected.id, 'history')}>History</button>
      <button disabled={!selected.url && !status?.remotes?.length} onClick={() => onAction(selected.id, 'github')}>Open GitHub</button>
      <button disabled={blocked || unavailable} title="Refresh remote references; counts otherwise use the last fetch" onClick={() => onAction(selected.id, 'fetch')}>Fetch</button>
      <button onClick={() => onAction(selected.id, 'log')}>Logs</button>
      <button title="Browse repository files without a terminal session" onClick={() => onAction(selected.id, 'files')}>Files</button>
      {(selected.pdfPath || selected.pdfDirectory) && <>
        {selected.buildTask && <button disabled={blocked || unavailable} onClick={() => onAction(selected.id, 'build')}>Build PDFs</button>}
        <button disabled={unavailable} onClick={() => onAction(selected.id, 'pdf')}>Open PDF</button>
      </>}
      {job && <span role="status">{job.action ?? 'Job'}: {job.state}</span>}
    </div>
    {errors[key] && <p className="check-error" role="alert">{errors[key]}</p>}
    {status?.error && <p className="check-error">{status.error}</p>}
    <details className="repository-strip-details"><summary>Repository details · ahead/behind use the last fetch</summary>
      <p className="repo-path">{status?.path ?? selected.path}</p>
      {status?.lastCommit && <p><strong>{status.lastCommit.hash.slice(0, 8)}</strong> {status.lastCommit.subject}<br />{status.lastCommit.author} · {new Date(status.lastCommit.timestamp).toLocaleString()}</p>}
      <strong>Remotes</strong><ul>{status?.remotes?.map((remote, index) => <li key={index}>{remote.name} ({remote.direction}): {remote.url}</li>)}</ul>
      <strong>Worktrees</strong><ul>{status?.worktrees?.map((worktree) => <li key={worktree.path}>{worktree.path} · {worktree.bare ? 'bare' : worktree.detached ? 'detached HEAD' : worktree.branch ?? 'No branch'}{worktree.head ? ` · ${worktree.head.slice(0, 8)}` : ''}{worktree.locked ? ' · locked' : ''}{worktree.prunable ? ' · prunable' : ''}</li>)}</ul>
      {status?.metadataErrors?.map((error) => <p key={error}>{error}</p>)}
    </details>
    {changesId && profileId && <RepositoryChangesPanel key={`${profileId}:${project.id}:${changesId}`} profileId={profileId} projectId={project.id} repositoryId={changesId}
      name={repos.find((repo) => repo.id === changesId)?.name ?? changesId} blocked={blocked} onClose={() => setChangesId(null)} onCommit={() => onAction(changesId, 'commit')} />}
  </section>
}
