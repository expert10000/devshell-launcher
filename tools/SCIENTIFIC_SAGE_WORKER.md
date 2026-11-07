# Sage exact worker (DS-SCI-016)

`scientific-sage-worker.py` implements three bounded exact operations through SageMath in WSL: `rational.add`, `polynomial.factor`, and `matrix.solve`. `scientific-sage-wsl.py` is a Windows transport that discovers the Sage Conda environment in the selected WSL distribution, maps paths with `wslpath`, and runs the worker without a DevShell process. Set `MATH3D_WSL_DISTRO` when the distribution is not `Ubuntu`.

```powershell
python tools/scientific-sage-wsl.py probe
$run = Join-Path $env:TEMP ([guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $run | Out-Null
@{
  schemaVersion = 1
  runId = [guid]::NewGuid().ToString('N')
  runtimeId = 'sage-wsl'
  recipeId = 'sage.exact.v1'
  operation = 'rational.add'
  parameters = @{
    left = @{ numerator = '1'; denominator = '3' }
    right = @{ numerator = '1'; denominator = '6' }
  }
} | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 (Join-Path $run 'request.json')
python tools/scientific-sage-wsl.py run --request (Join-Path $run 'request.json')
Get-Content (Join-Path $run 'results.json')
```

The adapter writes `worker-request.json` with the WSL working directory. A run has one immutable `results.json` and a bounded `full.log`; use a new directory for each request. The worker rejects unknown fields and operations, malformed exact values, zero denominators, zero leading coefficients, non-square or singular matrices, and oversized requests. Integers are decimal strings; rationals are canonical numerator/positive-denominator pairs in results. Polynomial coefficients are in ascending degree order. Matrix dimensions are 1–6, polynomial degree is 1–6, and source integer strings are at most 18 digits. No Python or Sage expression text is evaluated from the request.

The result repeats the versioned envelope and contains `state`, `exitCode`, `versions`, typed `result`, diagnostics with error codes, and no file artifacts. The adapter imposes a 120-second default timeout, kills its owned process tree on timeout or interruption, and saves a typed transport failure if WSL cannot run. The `probe` handshake reports the resolved Sage/Python executables and available operations.

The three operations are **worker candidates**. Successful calls do not grant L4–L9 qualification, broker discovery, or MATH3D promotion. DS-SCI-017 must add managed positive/rejection records, fingerprints, and scientific acceptance for each capability.
