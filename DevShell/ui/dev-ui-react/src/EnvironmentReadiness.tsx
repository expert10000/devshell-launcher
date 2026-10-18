export type EnvironmentHealthCheck = {
  name: string; state: string; detail: string; projectId?: string; repositoryId?: string
  fixTarget?: string; fixLabel?: string; guidance?: string; optional?: boolean
}
export type EnvironmentSetupPlan = { steps: { name: string; directory: string }[]; issues: string[]; targets: string[] }

export function EnvironmentReadiness({ name, checks, checking, blocked, plan, onFix, onPreview, onSetup, onRecheck, onClone }: {
  name: string; checks: EnvironmentHealthCheck[]; checking: boolean; blocked: boolean; plan?: EnvironmentSetupPlan
  onFix: (targets: string[]) => void; onPreview: (targets: string[]) => void; onSetup: () => void
  onRecheck: () => void; onClone?: () => void
}) {
  const errors = checks.filter(check => check.state === 'error')
  const warnings = checks.filter(check => check.state === 'warning')
  const review = warnings.some(check => !check.optional)
  const targets = [...new Set(errors.map(check => check.fixTarget).filter((target): target is string => !!target && target !== 'clone'))]
  const state = checking ? 'checking' : !checks.length ? 'unknown' : errors.length ? 'blocked' : review ? 'review' : 'ready'
  const label = state === 'checking' ? 'Checking environment…' : state === 'unknown' ? 'Environment not checked' : state === 'blocked'
    ? `Blocked · ${errors.length} required ${errors.length === 1 ? 'check' : 'checks'}` : state === 'review' ? 'Environment needs review' : 'Environment ready'
  const issue = (check: EnvironmentHealthCheck, index: number) => <li key={`${check.name}:${index}`} className={`environment-issue ${check.state}`}>
    <strong>{check.state === 'error' ? 'Required' : check.optional ? 'Optional' : 'Review'} · {check.name}</strong>
    <p>{check.detail}</p>{check.guidance && <p className="service-detail">{check.guidance}</p>}
    {check.fixTarget === 'clone' ? onClone && <button disabled={blocked || checking} onClick={onClone}>Clone repository</button>
      : check.state === 'error' && check.fixTarget ? <button disabled={blocked || checking} onClick={() => onFix([check.fixTarget!])}>{check.fixLabel ?? 'Fix this requirement'}</button>
        : check.state === 'error' && <span className="service-detail">Manual step required</span>}
  </li>
  return <section className={`environment-readiness ${state}`} aria-label={`${name} environment readiness`}>
    <div className="environment-heading"><strong role="status">{label}</strong><button disabled={checking || blocked} onClick={onRecheck}>Recheck</button></div>
    {!errors.length && !!warnings.length && <p className="service-detail">{warnings.length} {review ? 'checks need manual verification' : 'optional capabilities unavailable'}.</p>}
    {!!errors.length && <ul className="environment-issues">{errors.map(issue)}</ul>}
    {!!targets.length && <div className="environment-actions"><button disabled={blocked || checking} onClick={() => onFix(targets)}>Fix required dependencies</button><button disabled={blocked || checking} onClick={() => onPreview(targets)}>Preview fixes</button></div>}
    {plan && <div className="environment-plan" role="region" aria-label={`${name} repair plan`}><strong>Repair steps · {plan.steps.length}</strong><ol>{plan.steps.map((step, index) => <li key={index}>{step.name}<div className="repo-path">{step.directory}</div></li>)}</ol>{plan.issues.map(problem => <p className="check-error" key={problem}>{problem}</p>)}{!!plan.targets.length && !plan.issues.length && <button disabled={blocked || checking} onClick={() => onFix(plan.targets)}>Run these fixes</button>}</div>}
    <details><summary>All checks · {checks.length}{warnings.length ? ` · ${warnings.length} warnings` : ''}</summary>
      {!!warnings.length && <ul className="environment-issues">{warnings.map(issue)}</ul>}
      {checks.filter(check => check.state === 'ok').map((check, index) => <div className="environment-passed" key={index}><strong>OK · {check.name}</strong><p>{check.detail}</p></div>)}
      <p className="service-detail">Readiness covers declared tools and dependencies. Builds and running apps can report additional requirements.</p>
      <button disabled={blocked || checking} onClick={onSetup}>Full environment setup</button>
    </details>
  </section>
}
