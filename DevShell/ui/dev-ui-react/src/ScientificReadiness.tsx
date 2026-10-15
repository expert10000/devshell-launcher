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

export default function ScientificReadiness({ runtimeId, observed, probeJob }: { runtimeId: string; observed: unknown; probeJob?: unknown }) {
  const recordedChecks = getChecks(observed);
  const job = probeJob && typeof probeJob === 'object' ? probeJob as Record<string, unknown> : null;
  const currentJob = job?.runtimeId === runtimeId && job?.recipeId === 'lab.probe' ? job : null;
  const result = currentJob?.result && typeof currentJob.result === 'object' ? currentJob.result as Record<string, unknown> : null;
  const probeChecks = Array.isArray(result?.probeResults)
    ? result.probeResults.filter((check): check is Check => !!check && typeof check === 'object')
    : [];
  const checkEvidence = (id: string): EvidenceStatus => {
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
      {probeChecks.length ? `Latest managed probe: ${String(currentJob?.state ?? result?.status ?? 'recorded')} at ${String(result?.completedAtUtc ?? currentJob?.startedAtUtc ?? 'unknown time')}. ` : 'No managed probe evidence in this session. '}
      Other checks use the separately loaded installation report. Untested is not a failure or a blanket readiness claim.
    </p>
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(175px, 1fr))', gap: 6 }}>
      {gates.map((gate) => {
        const evidence = status(gate.checks);
        const fromProbe = gate.checks.length ? gate.checks.some((id) => checkStatus(probeChecks, id) !== 'untested') : probeChecks.length > 0;
        return <div key={gate.level} style={{ padding: '7px 9px', borderRadius: 7, background: 'rgba(255,255,255,0.05)', borderLeft: `3px solid ${evidence === 'passed' ? '#4db78a' : evidence === 'failed' ? '#d86b65' : '#6b7988'}` }}>
          <strong>{gate.level}</strong> {gate.title}<br />
          <small>{evidence} · {fromProbe ? 'managed probe' : observed ? 'installation report' : 'no evidence'}</small>
        </div>;
      })}
    </div>
  </section>;
}
