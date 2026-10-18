import { useEffect, useRef, useState } from 'react'
import type { ScientificRuntimeReport } from './scientificRuntimeReport'
import type { ScientificRunRequest, ScientificRunResult } from './scientificRuntimeProfiles'

export type ScientificBridge = { postMessage: (message: unknown) => void; addEventListener: (name: 'message', handler: (event: MessageEvent) => void) => void; removeEventListener: (name: 'message', handler: (event: MessageEvent) => void) => void }
export interface ScientificJob { jobId: string; profileId: string; runtimeId: string; recipeId: string; state: string; stage?: string; startedAtUtc?: string; durationMs: number; log: string; error?: string; outputDirectory: string; request?: ScientificRunRequest; result?: ScientificRunResult }
export interface ScientificDataset { id: string; name: string; category: string; path: string; bytes: number; sha256: string; sourcePath: string; sourceRoot: string; expectedProblem: boolean }
export interface ScientificEnvironment { environment: Record<string, string>; vcpkgRoot: string | null; installedVcpkg: string | null; vcpkgUsed: boolean; report: ScientificRuntimeReport; evidence?: { compilerVersion?: string | null; compilerSource?: string; rendering?: ScientificRunResult['rendering'] } }
export interface ScientificMeshPreview { name: string; positions: number[]; bounds: number[]; points: number; triangles: number; previewTriangles: number; sampled: boolean; note: string }
export interface ScientificArtifactPreview { jobId: string; artifactPath: string; geometry: { before: ScientificMeshPreview | null; beforeSecond?: ScientificMeshPreview | null; after: ScientificMeshPreview }; result: ScientificRunResult }
export interface ScientificHistoryImagePreview { jobId: string; artifactPath: string; image: { dataUrl: string; mimeType: string; size: number } }
export interface ScientificHistoryEntry { jobId: string; runtimeId: string; recipeId: string; testCaseId?: string | null; state: string; durationMs: number; finishedAtUtc: string; artifactCount: number; meshArtifactCount?: number }
export interface ScientificMatrixCase { id: string; datasetId: string; name: string; expected: 'succeeded' | 'rejected'; reason: string }

export function useScientificRuntime(bridge: ScientificBridge | null, profileId: string | null, refreshReport: () => void) {
  const [jobs, setJobs] = useState<Record<string, ScientificJob>>({})
  const [environments, setEnvironments] = useState<Record<string, ScientificEnvironment>>({})
  const [previews, setPreviews] = useState<Record<string, ScientificArtifactPreview>>({})
  const [datasets, setDatasets] = useState<{ importedAt: string; note: string; entries: ScientificDataset[] } | null>(null)
  const [history, setHistory] = useState<ScientificHistoryEntry[] | null>(null)
  const [historyResult, setHistoryResult] = useState<ScientificRunResult | null>(null)
  const [historyResults, setHistoryResults] = useState<Record<string, ScientificRunResult>>({})
  const [historyPreviews, setHistoryPreviews] = useState<Record<string, ScientificArtifactPreview>>({})
  const [historyImages, setHistoryImages] = useState<Record<string, ScientificHistoryImagePreview>>({})
  const [testMatrix, setTestMatrix] = useState<ScientificMatrixCase[] | null>(null)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const requests = useRef(new Map<string, { action: string; timer: ReturnType<typeof setTimeout> }>())
  const completed = useRef(new Set<string>())
  const refresh = useRef(refreshReport); refresh.current = refreshReport
  const mergeJob = (job: ScientificJob) => {
    if (!job || job.profileId !== profileId) return
    setJobs(previous => {
      const existing = previous[job.runtimeId]
      if (existing?.jobId === job.jobId && existing.state !== 'running' && job.state === 'running') return previous
      return { ...previous, [job.runtimeId]: job }
    })
    if (job.state === 'succeeded' && job.recipeId === 'diagnostics' && !completed.current.has(job.jobId)) { completed.current.add(job.jobId); refresh.current() }
  }
  const send = (runtimeId: string, action: string, extra: Record<string, unknown> = {}) => {
    if (!bridge || !profileId) { setError('This action requires the DevShell desktop app and a selected profile.'); return }
    const requestId = crypto.randomUUID()
    setError(''); setNotice(''); setPending(true)
    const timer = setTimeout(() => { requests.current.delete(requestId); setPending(requests.current.size > 0); setError(`${action} response timed out. Inspect job status before retrying a run.`) }, action === 'export' ? 600000 : 30000)
    requests.current.set(requestId, { action, timer })
    bridge.postMessage({ type: 'scientific.runtime', profileId, runtimeId, requestId, action, ...extra })
  }
  useEffect(() => {
    setJobs({}); setEnvironments({}); setPreviews({}); setDatasets(null); setHistory(null); setHistoryResult(null); setHistoryResults({}); setHistoryPreviews({}); setHistoryImages({}); setTestMatrix(null); setError(''); setNotice(''); setPending(false); completed.current.clear()
    if (!bridge || !profileId) return
    const receive = (event: MessageEvent) => {
      let message: { type?: string; profileId?: string; runtimeId?: string; requestId?: string; action?: string; error?: string; job?: ScientificJob; data?: unknown }
      try { message = typeof event.data === 'string' ? JSON.parse(event.data) : event.data } catch { return }
      if (message.type === 'scientific.runtime.job') { if (message.job?.profileId === profileId) mergeJob(message.job); return }
      if (message.type !== 'scientific.runtime.result' || message.profileId !== profileId || !message.requestId) return
      const waiting = requests.current.get(message.requestId)
      if (!waiting) return
      clearTimeout(waiting.timer); requests.current.delete(message.requestId); setPending(requests.current.size > 0)
      if (message.error) { setError(message.error); return }
      if (message.action === 'status' && Array.isArray(message.data)) message.data.forEach(item => mergeJob(item as ScientificJob))
      else if (message.action === 'history' && Array.isArray(message.data)) { setHistory(message.data as ScientificHistoryEntry[]); setHistoryResult(null); setHistoryResults({}); setHistoryPreviews({}); setHistoryImages({}) }
      else if (message.action === 'history-result' && message.data) { const result = message.data as ScientificRunResult; setHistoryResult(result); setHistoryResults(previous => ({ ...previous, [result.runId]: result })) }
      else if (message.action === 'history-image-preview' && message.data) { const preview = message.data as ScientificHistoryImagePreview; setHistoryImages(previous => ({ ...previous, [`${preview.jobId}|${preview.artifactPath}`]: preview })) }
      else if (message.action === 'history-preview' && message.data) { const preview = message.data as ScientificArtifactPreview; setHistoryPreviews(previous => ({ ...previous, [`${preview.jobId}|${preview.artifactPath}`]: preview })) }
      else if ((message.action === 'recipe' || message.action === 'cgal-recipe' || message.action === 'test-hold' || message.action === 'stop') && message.data) mergeJob(message.data as ScientificJob)
      else if (message.action === 'artifacts' && message.data && message.runtimeId) setPreviews(previous => ({ ...previous, [message.runtimeId!]: message.data as ScientificArtifactPreview }))
      else if (message.action === 'environment' && message.data && message.runtimeId) setEnvironments(previous => ({ ...previous, [message.runtimeId!]: message.data as ScientificEnvironment }))
      else if (message.action === 'datasets' && message.data) setDatasets(message.data as { importedAt: string; note: string; entries: ScientificDataset[] })
      else if (message.action === 'test-matrix' && Array.isArray(message.data)) setTestMatrix(message.data as ScientificMatrixCase[])
      else if (message.action === 'run-matrix' && message.data) mergeJob(message.data as ScientificJob)
      else if (message.action === 'export') { const result = message.data as { path?: string; cancelled?: boolean }; setNotice(result.cancelled ? 'Profile export cancelled.' : `Profile exported: ${result.path ?? ''}`) }
      else if (message.action === 'terminal') setNotice('External scientific PowerShell opened; not a VS developer shell.')
    }
    bridge.addEventListener('message', receive)
    send('', 'status') // Metadata only; never rerun a restored recipe.
    return () => { bridge.removeEventListener('message', receive); requests.current.forEach(item => clearTimeout(item.timer)); requests.current.clear() }
    // Callback refs keep completed diagnostics from restarting subscriptions.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bridge, profileId])
  return { jobs, environments, previews, datasets, history, historyResult, historyResults, historyPreviews, historyImages, testMatrix, pending, error, notice, send, busy: Object.values(jobs).some(job => job.state === 'running') }
}
