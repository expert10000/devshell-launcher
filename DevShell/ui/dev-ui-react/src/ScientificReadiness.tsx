import { useEffect, useRef } from 'react';
import type { useScientificRuntime } from './useScientificRuntime';

type EvidenceStatus = 'passed' | 'failed' | 'untested';

type Check = Record<string, unknown>;

function getChecks(observed: unknown): Check[] {
  if (!observed || typeof observed !== 'object') return [];
  const value = (observed as Record<string, unknown>).checks;
  if (Array.isArray(value)) return value.filter((check): check is Check => !!check && typeof check === 'object');
  if (value && typeof value === 'object') return Object.entries(value).map(([id, item]) => ({
    id,
    ...(item && typeof item === 'object' ? item as Record<string, unknown> : { status: item }),
  }));
  return [];
}

function checkStatus(checks: Check[], id: string): EvidenceStatus {
  const check = checks.find((item) => item.id === id || item.name === id);
  if (!check) return 'untested';
  if (check.passed === true || check.ok === true || ['passed', 'pass', 'ok', 'succeeded'].includes(String(check.status ?? check.state ?? check.result).toLowerCase()))
    return 'passed';
  if (check.passed === false || check.ok === false || ['failed', 'fail', 'error', 'timed-out'].includes(String(check.status ?? check.state ?? check.result).toLowerCase()))
    return 'failed';
  return 'untested';
}

export default function ScientificReadiness({ profileId, runtimeId, observed, native }: { profileId: string; runtimeId: string; observed: unknown; native: ReturnType<typeof useScientificRuntime> }) {
  const requestedProfile = useRef<string | null>(null);
  useEffect(() => {
    if (native.history != null || requestedProfile.current === profileId) return;
    requestedProfile.current = profileId;
    void native.send('', 'history');
  }, [profileId, native.history, native.send]);

  const latestEntry = native.history
    ?.filter((entry) => entry.runtimeId === runtimeId && entry.recipeId === 'lab.probe')
    .sort((a, b) => Date.parse(b.finishedAtUtc) - Date.parse(a.finishedAtUtc))[0];
  const savedResult = latestEntry ? native.historyResults[latestEntry.jobId] : undefined;
  const validationEntry = runtimeId === 'cgal-win-conda' ? native.history
    ?.filter((entry) => entry.runtimeId === runtimeId && entry.recipeId === 'cgal.validate')
    .sort((a, b) => Date.parse(b.finishedAtUtc) - Date.parse(a.finishedAtUtc))[0] : undefined;
  const savedValidation = validationEntry ? native.historyResults[validationEntry.jobId] : undefined;
  const requestedResult = useRef<string | null>(null);
  useEffect(() => {
    if (!latestEntry || savedResult || requestedResult.current === `${profileId}:${latestEntry.jobId}`) return;
    requestedResult.current = `${profileId}:${latestEntry.jobId}`;
    void native.send(runtimeId, 'history-result', { jobId: latestEntry.jobId });
  }, [profileId, runtimeId, latestEntry?.jobId, savedResult, native.send]);
  const requestedValidation = useRef<string | null>(null);
  useEffect(() => {
    if (!validationEntry || savedValidation || requestedValidation.current === `${profileId}:${validationEntry.jobId}`) return;
    requestedValidation.current = `${profileId}:${validationEntry.jobId}`;
    void native.send(runtimeId, 'history-result', { jobId: validationEntry.jobId });
  }, [profileId, runtimeId, validationEntry?.jobId, savedValidation, native.send]);

  const recordedChecks = getChecks(observed);
  const probeJob = native.jobs[runtimeId];
  const job = probeJob && typeof probeJob === 'object' ? probeJob as unknown as Record<string, unknown> : null;
  const currentJob = job?.runtimeId === runtimeId && job?.recipeId === 'lab.probe' ? job : null;
  const liveResult = currentJob?.result && typeof currentJob.result === 'object' ? currentJob.result as Record<string, unknown> : null;
  const result = liveResult ?? (savedResult && typeof savedResult === 'object' ? savedResult as unknown as Record<string, unknown> : null);
  const probeOrigin = liveResult ? 'this session' : result ? 'History' : '';
  const probeChecks = Array.isArray(result?.probeResults)
    ? result.probeResults.filter((check): check is Check => !!check && typeof check === 'object')
    : [];
  const liveValidation = probeJob?.recipeId === 'cgal.validate' ? probeJob.result : undefined;
  const validation = liveValidation ?? savedValidation;
  const validationPassed = validation?.state === 'succeeded'
    && validation.validatedCapabilities?.includes('mesh.validate')
    && validation.artifacts?.some((artifact) => artifact.path.endsWith('.obj') && !!artifact.sha256);
  const matrixEntry = runtimeId === 'cgal-win-conda' ? native.history?.find((entry) => entry.runtimeId === runtimeId && entry.recipeId === 'matrix.cgal.validation') : undefined;
  const liveMatrix = probeJob?.recipeId === 'matrix.cgal.validation' ? probeJob.result : undefined;
  const matrix = liveMatrix?.matrixSummary ? liveMatrix : matrixEntry ? native.historyResults[matrixEntry.jobId] : undefined;
  const matrixPassed = matrix?.state === 'succeeded' && !!matrix.matrixSummary?.total && matrix.matrixSummary.passed === matrix.matrixSummary.total;
  const checkEvidence = (id: string): EvidenceStatus => {
    if (id === 'worker.recipe' && (validationPassed || matrixPassed)) return 'passed';
    const recent = checkStatus(probeChecks, id);
    return recent !== 'untested' ? recent : checkStatus(recordedChecks, id);
  };
  const kind = runtimeId.startsWith('cgal-') ? 'cgal' : 'vtk';
  const gates: { level: string; title: string; checks: string[] }[] = [
    { level: 'L0', title: 'Recorded inventory', checks: [] },
    { level: 'L1', title: 'Python executable', checks: ['python.version'] },
    { level: 'L2', title: 'Python binding', checks: [`${kind}.python`] },
    { level: 'L3', title: 'Basic geometry', checks: [kind === 'cgal' ? 'cgal.geometry' : 'vtk.polydata'] },
    { level: 'L4', title: 'C++ configure + link', checks: [`${kind}.configure`, `${kind}.compile-link`] },
    { level: 'L5', title: 'Worker recipe', checks: ['worker.recipe'] },
    { level: 'L6', title: 'Reproducible artifacts', checks: ['worker.reproducibility'] },
    { level: 'L7', title: 'Interoperability', checks: ['interop.roundtrip'] },
    { level: 'L8', title: 'Benchmarks', checks: ['benchmark.baseline'] },
    { level: 'L9', title: 'MATH3D integration', checks: ['math3d.integration'] },
  ];
  const status = (required: string[]): EvidenceStatus => {
    if (required.length === 0) return observed || probeChecks.length ? 'passed' : 'untested';
    const values = required.map(checkEvidence);
    if (values.includes('failed')) return 'failed';
    return values.every((value) => value === 'passed') ? 'passed' : 'untested';
  };

  return <section aria-label="Scientific readiness evidence" style={{ margin: '12px 0', padding: 12, border: '1px solid #39516a', borderRadius: 10 }}>
    <strong>Readiness evidence</strong>
    <p style={{ margin: '5px 0 10px', opacity: 0.75 }}>
      {probeChecks.length ? `Managed probe (${probeOrigin}): ${String(liveResult ? currentJob?.state ?? result?.status : latestEntry?.state ?? result?.status ?? 'recorded')} at ${String(result?.completedAtUtc ?? (liveResult ? currentJob?.startedAtUtc : latestEntry?.finishedAtUtc) ?? 'unknown time')}. ` : 'No saved managed probe evidence loaded for this profile. '}
      Other checks use the separately loaded installation report. Untested is not a failure or a blanket readiness claim.
    </p>
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(175px, 1fr))', gap: 6 }}>
      {gates.map((gate) => {
        const evidence = status(gate.checks);
        const fromProbe = gate.checks.length ? gate.checks.some((id) => checkStatus(probeChecks, id) !== 'untested') : probeChecks.length > 0;
        const fromValidation = gate.level === 'L5' && (validationPassed || matrixPassed);
        return <div key={gate.level} style={{ padding: '7px 9px', borderRadius: 7, background: 'rgba(255,255,255,0.05)', borderLeft: `3px solid ${evidence === 'passed' ? '#4db78a' : evidence === 'failed' ? '#d86b65' : '#6b7988'}` }}>
          <strong>{gate.level}</strong> {gate.title}<br />
          <small>{evidence} · {fromValidation ? matrixPassed ? `CGAL matrix ${matrix?.matrixSummary?.passed}/${matrix?.matrixSummary?.total} / ${liveMatrix ? 'this session' : 'History'}` : `managed CGAL validation / ${liveValidation ? 'this session' : 'History'}` : fromProbe ? `managed probe / ${probeOrigin}` : observed ? 'installation report' : 'no evidence'}</small>
        </div>;
      })}
    </div>
  </section>;
}
