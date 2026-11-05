# Theory Lab worker diagnostics in DevShell

The desktop-five Repositories and Health check views probe the configured Theory Lab checkout. The probe calls the worker's `hello`, `health`, `capabilities`, and `resources` methods, then runs the checked two-level native fixture twice. It reports the worker version and a SHA-256 of the repeatable eigenvalues. A missing Python environment or worker dependency is shown as a health error, without changing the checkout.

For a full reproducibility report and optional acceleration benchmark:

```powershell
& 'G:\master\.venvs\devshell-jupyter\Scripts\python.exe' tools/quantum_runtime_diagnostics.py 'G:\master\theory-lab-roadmap-audit-2026-11-04' --report "$env:TEMP\theory-lab-runtime.json"
& 'G:\master\.venvs\devshell-jupyter\Scripts\python.exe' tools/quantum_runtime_diagnostics.py 'G:\master\theory-lab-roadmap-audit-2026-11-04' --benchmark --report "$env:TEMP\theory-lab-benchmark.json"
```

The benchmark reports numerical agreement and repeatability before timing claims. The report records versions, engine availability, fixture energies and hash, and timings. It does not include user paths or job logs. The health view is intentionally a short fixture probe; run the worker's full unit suite separately before release.

The checked Windows run from 2026-11-05 is in [qi35-windows-runtime-report.json](qi35-windows-runtime-report.json). Its native fixture passed with energies ±0.6403124237432849 and digest `265184744cfdb0e356ac87530e8adefe7b983b84221e76a9483c53ffa94d0a8a`.
