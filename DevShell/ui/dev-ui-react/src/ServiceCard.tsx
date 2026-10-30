import type { ReactNode } from 'react'

export type ServiceCardProps = {
  name: string
  project: string
  state: string
  detail: string
  message?: string
  error?: string
  busy: boolean
  canStart: boolean
  canStop: boolean
  canRestart: boolean
  canOpen: boolean
  onStart: () => void
  onStop: () => void
  onRestart: () => void
  onOpen?: () => void
  onOpenExternal?: () => void
  onLogs: () => void
  onRefresh: () => void
  onSetup?: () => void
  setupOpen?: boolean
  setupContent?: ReactNode
  logs?: string
  onRefreshLogs?: () => void
}

export function ServiceCard({ name, project, state, detail, message, error, busy, canStart, canStop,
  canRestart, canOpen, onStart, onStop, onRestart, onOpen, onOpenExternal, onLogs, onRefresh,
  logs, onRefreshLogs, onSetup, setupOpen, setupContent }: ServiceCardProps) {
  return <section className="service-card" aria-label={`${name} service controls`}>
    <div className="service-project">{project}</div>
    <div className="service-heading"><strong>{name}</strong><span className={`service-state ${state}`}>{state}</span></div>
    <div className="service-detail">{detail}</div>
    {message && <div className="service-detail" role="status">{message}</div>}
    {error && <div className="service-detail check-error" role="alert">{error}</div>}
    <div className="service-actions">
      <button disabled={busy || !canStart} onClick={onStart}>Start</button>
      <button disabled={busy || !canOpen || !onOpen} onClick={onOpen}>Open</button>
      <button disabled={!canStop} onClick={onStop}>Stop</button>
      <button disabled={busy || !canRestart} onClick={onRestart}>Restart</button>
      <button onClick={onLogs}>Logs</button>
      <button disabled={busy} onClick={onRefresh}>Refresh</button>
      {onSetup && <button aria-expanded={!!setupOpen} onClick={onSetup}>Setup / Fix</button>}
      {onOpenExternal && <button disabled={busy || !canOpen} onClick={onOpenExternal}>Open externally</button>}
    </div>
    {logs !== undefined && <div className="service-log-panel"><button onClick={onRefreshLogs}>Refresh logs</button><pre>{logs}</pre></div>}
    {setupOpen && setupContent && <div className="service-setup-panel">{setupContent}</div>}
  </section>
}
