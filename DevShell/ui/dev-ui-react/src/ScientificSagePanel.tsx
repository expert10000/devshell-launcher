import type { useScientificRuntime } from './useScientificRuntime'

export function ScientificSagePanel({ native }: { native: ReturnType<typeof useScientificRuntime> }) {
  const job = native.jobs['sage-wsl']
  const running = job?.state === 'running'
  return <section className="scientific-lab-probe" aria-label="SageMath WSL checks">
    <h3>SageMath on WSL Ubuntu</h3>
    <p>Run an explicit installation check or exact factorization. The test uses Sage installed in Ubuntu, including a named <code>sage</code> Conda environment. A cold WSL start may take a minute.</p>
    <div className="scientific-runtime-header-actions">
      <button type="button" disabled={native.pending || native.busy} onClick={() => native.send('sage-wsl', 'sage-recipe', { recipeId: 'sage.version' })}>Check Sage installation</button>
      <button type="button" disabled={native.pending || native.busy} onClick={() => native.send('sage-wsl', 'sage-recipe', { recipeId: 'sage.factor-smoke' })}>Test exact factorization</button>
      <button type="button" disabled={!running} onClick={() => native.send('sage-wsl', 'stop', { jobId: job?.jobId })}>Stop</button>
    </div>
    {job && <><p role="status">{job.recipeId}: {job.state} / {job.stage ?? 'queued'} / {Math.round(job.durationMs / 1000)} s</p>
      {job.error && <p role="alert">{job.error}</p>}
      <pre aria-label="SageMath test log">{job.log || 'Waiting for WSL output…'}</pre>
      {job.state !== 'running' && <button type="button" onClick={() => native.send('', 'history')}>Load test history</button>}
    </>}
  </section>
}
