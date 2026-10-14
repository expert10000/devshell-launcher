import type { ScientificBridge } from './useScientificRuntime'

export interface ObservedScientificRuntime {
  id: string
  name: string
  kind: string
  execution: string
  environmentRoot: string
  executable: string
  version: string | null
  state: 'partial' | 'missing' | 'failed' | 'ready'
  pythonVersion?: string
  architecture?: string
  sdk?: { root: string; include: string; cmakeConfig: string | null; installed: boolean; compilation: string; linking: string; rendering: string; renderingEvidence?: { state?: string; backend?: string; capabilities?: string } }
  tools?: Record<string, { path: string; version: string | null; state: string }>
  checks: { id: string; name: string; state: string; detail: string; durationMs: number }[]
  packages: { name: string; version: string; build: string; source: string }[]
  validatedCapabilities: string[]
}
export interface ScientificRuntimeReport {
  schemaVersion: 1
  generatedAt: string
  runtimeRoot: string
  compiler: { state: string; installation: string | null; version: string | null; actualVersion?: string | null; binaryVersion?: string | null; toolsetVersion?: string; versionProbe?: string; path: string | null; compilation: string }
  runtimes: ObservedScientificRuntime[]
  notes: string[]
}

export async function loadScientificRuntimeReport(bridge: ScientificBridge | null = null, profileId: string | null = null): Promise<ScientificRuntimeReport> {
  let report: ScientificRuntimeReport
  if (bridge && profileId) {
    const requestId = crypto.randomUUID()
    report = await new Promise<ScientificRuntimeReport>((resolve, reject) => {
      let timer: ReturnType<typeof setTimeout>
      const cleanup = () => { clearTimeout(timer); bridge.removeEventListener('message', receive) }
      const receive = (event: MessageEvent) => {
        let message: { type?: string; profileId?: string; requestId?: string; action?: string; error?: string; data?: ScientificRuntimeReport }
        try { message = typeof event.data === 'string' ? JSON.parse(event.data) : event.data } catch { return }
        if (!message || message.type !== 'scientific.runtime.result' || message.profileId !== profileId || message.requestId !== requestId || message.action !== 'report') return
        cleanup()
        if (message.error) reject(new Error(message.error))
        else if (!message.data) reject(new Error('The native report response was empty.'))
        else resolve(message.data)
      }
      timer = setTimeout(() => { cleanup(); reject(new Error('Native report loading timed out.')) }, 10000)
      bridge.addEventListener('message', receive)
      try { bridge.postMessage({ type: 'scientific.runtime', profileId, runtimeId: '', requestId, action: 'report' }) }
      catch (error) { cleanup(); reject(error) }
    })
    if (JSON.stringify(report).length > 1048576) throw new Error('Local report exceeds 1 MiB.')
  } else {
    const response = await fetch('/scientific-runtime-report.json', { cache: 'no-store', signal: AbortSignal.timeout(10000) })
    if (!response.ok) throw new Error('No local report. Run Install-ScientificRuntimes.ps1 or Inspect-ScientificRuntimes.ps1 with -PublishToLauncher.')
    if (Number(response.headers.get('content-length') ?? 0) > 1048576) throw new Error('Local report exceeds 1 MiB.')
    const text = await response.text()
    if (text.length > 1048576) throw new Error('Local report exceeds 1 MiB.')
    report = JSON.parse(text) as ScientificRuntimeReport
  }
  if (report.schemaVersion !== 1 || typeof report.generatedAt !== 'string' || typeof report.runtimeRoot !== 'string' || !report.compiler || !Array.isArray(report.runtimes) || report.runtimes.length > 20 || !Array.isArray(report.notes)) throw new Error('Unsupported local report format.')
  for (const runtime of report.runtimes) {
    if (!runtime || typeof runtime.id !== 'string' || typeof runtime.name !== 'string' || typeof runtime.environmentRoot !== 'string' || typeof runtime.executable !== 'string' || !['partial', 'missing', 'failed', 'ready'].includes(runtime.state) || !Array.isArray(runtime.checks) || !Array.isArray(runtime.packages) || runtime.checks.length > 100 || runtime.packages.length > 1000) throw new Error('Invalid runtime report entry.')
    if (runtime.checks.some(check => typeof check.id !== 'string' || typeof check.name !== 'string' || typeof check.detail !== 'string' || typeof check.state !== 'string' || typeof check.durationMs !== 'number') || runtime.packages.some(item => typeof item.name !== 'string' || typeof item.version !== 'string' || typeof item.build !== 'string' || typeof item.source !== 'string')) throw new Error('Invalid probe/package inventory.')
  }
  return report
}
