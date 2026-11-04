# Scientific Runtime Broker (DS-SCI-021/022)

This is a separate localhost process. It uses the existing version 1 CGAL worker request/result contract and emits the version 1 `math3d.mesh-product-handoff` consumed by `tools/math3d-l9-product-handoff.mjs`. The renderer does not load CGAL or link its SDK.

## Export current certification

Build and run the exporter with five explicit paths:

```powershell
dotnet run --project tools/scientific-broker/ScientificBroker.csproj -- export <devshell-repo> <installed-launcher-root> <math3d-checkout> <profile-id> <manifest.json>
```

The exporter rereads successful runs, verifies fingerprints and immutable qualification files, assesses source, environment, dependency, and MATH3D consumer drift, then exports the newest current L9 CGAL mesh record. If no current L9 record remains, `certifiedCapabilities` is empty. Gmsh and all other unqualified capabilities are excluded. The manifest and its `.sha256` sidecar are a deployment snapshot; export again after qualification or environment changes. The hash detects mismatches, but is not an authenticity signature.

## Configure and run

Create a local JSON file with absolute deployment paths:

```json
{
  "schemaVersion": 1,
  "manifest": "<manifest.json>",
  "runtimeManifest": "<cgal runtime.json>",
  "adapter": "<scientific-cgal-worker.py>",
  "workerContract": "<scientific_worker_contract.py>",
  "python": "<dedicated CGAL python.exe>",
  "worker": "<devshell_cgal_worker.exe>",
  "prefix": "<dedicated CGAL conda prefix>",
  "datasetRoot": "<registered local dataset root>",
  "jobsRoot": "<broker-owned output directory>",
  "math3dRoot": "<MATH3D checkout for promotion>",
  "sourceRoot": "<optional DevShell Git checkout; defaults to the broker source checkout>",
  "maxConcurrentJobs": 4,
  "memoryLimitMiB": 2048
}
```

Deploy the manifest, worker scripts, runtime manifest, environment, and compiled worker at these paths. The broker needs no DevShell desktop process. It verifies their hashes and the conda package inventory when it starts, when it discovers providers, and before each job. `maxConcurrentJobs` defaults to 4 (range 1–8); a saturated broker rejects new submissions with a retry reason. `memoryLimitMiB` is optional (range 1–65536) and enforces a sampled process-tree resident-memory budget when `psutil` is installed. The API listens only on `127.0.0.1`; remote transport and authentication are outside this local deployment.

```powershell
python tools/scientific-broker/broker.py verify --config <config.json>
python tools/scientific-broker/broker.py serve --config <config.json> --port 8765
```

## Version 1 API

- `GET /v1/providers`: certified provider and capability discovery.
- `POST /v1/jobs`: accept `schemaVersion`, `runtimeId`, `capabilityId`, `input: {path, sha256}`, and optional `timeoutSeconds` (1–120). The input must be a bounded OBJ inside `datasetRoot` with the exact hash of the qualified L9 fixture.
- `GET /v1/jobs/{id}`: state (`running`, `succeeded`, `partial`, `failed`, `cancelled`, `timed-out`, `resource-exhausted`), stage, progress, diagnostics, and verified artifact metadata.
- `GET /v1/jobs/{id}/telemetry`: hash-verified CPU, RAM, GPU and VRAM measurements after finalization. Every metric includes a collector, unit, scope, availability and sample count.
- `GET /v1/jobs/{id}/source`: hash-verified Git commit, tree, branch, worktree and dirty-content identities captured at submission. Non-Git deployments record an explicit unavailable reason.
- `POST /v1/jobs/{id}/cancel`: terminate the owned worker process tree.
- `POST /v1/jobs/{id}/promote`: save an immutable allow/block decision with reasons. It requires a successful job, a current matching L0–L9 certification chain, unchanged worker/package and MATH3D consumer identities, and a verified version 1 handoff. `math3dRoot` is required for an allowed decision.
- `GET /v1/jobs/{id}/artifacts/{name}`: serve only a registered artifact from a successful job after rechecking its hash. Current names are `l5-positive.obj` and `handoff.json`.

Completed job results survive broker restarts. MATH3D can consume `handoff.json` after an allowed promotion; the handoff pins the worker request, result, output, L8 record, and contract. The broker requires the worker output hash to match the fixed L9 reference artifact. The current implementation covers the qualified CGAL mesh path only.

## Promoted document and smoke evidence (DS-SCI-023–025)

```powershell
python tools/scientific-broker/smoke.py --config <config.json>
python tools/scientific-broker/smoke.py --config <config.json> --verify-job <32-character-job-id>
```

The smoke starts the broker API on a temporary localhost port, submits the fixed CGAL job, requests promotion, imports the handoff into a saved MATH3D Mesh document, mounts the viewer, and writes `qualified-mesh.m3dm` through MATH3D's native codec. `check_m3dm_roundtrip.py` independently reloads the binary with Python `struct` and checks exact triangle topology/winding, finite coordinates, closed orientation, volume and scale against the worker OBJ. The immutable `document-qualification.json` pins the source L9 record, codec/parser sources, promotion, format, scene and artifact hashes. `smoke-result.json` records the source job, promotion decision, contract version, scene/resource/viewer and round-trip hashes; `--verify-job` checks those saved files again. A failure saves its stage, source job and reason to the same job directory. The scope is the fixed tetrahedron mesh; volume meshes and exact mathematical documents remain unqualified.

## Persistent benchmarks and telemetry (DS-SCI-026/027)

```powershell
python tools/scientific-broker/benchmark.py run --config <config.json> --repetitions 3
python tools/scientific-broker/benchmark.py history --config <config.json>
python tools/scientific-broker/benchmark.py compare --config <config.json> --baseline <record.json> --candidate <record.json>
python tools/scientific-broker/benchmark.py pin --config <config.json> --run-id <32-character-benchmark-run-id>
```

The benchmark uses the **same qualified tetrahedron input** in fixed tiers of 1, 3 and 5 sequential jobs per batch. It captures the first job after a fresh broker instance as its cold sample, runs one warmup batch and then the requested measured batches. OS caches are not reset. First use pins an immutable baseline record; `pin` deliberately selects a later record while archiving the prior pointer. History retains every run. Host, package/toolchain, suite, broker source, input or policy mismatches produce an **inconclusive** warning. These results are performance observations and do not grant qualification or promotion. Larger mesh size tiers need separate fixture qualification.

Each broker job saves `telemetry.json` and its hash. `psutil` samples CPU seconds and peak resident bytes across the worker process tree. `nvidia-smi` supplies GPU utilization and VRAM used for the **host**, with that scope recorded explicitly; those values are not attributed to the CGAL job. Unsupported or missed measurements have `state: unavailable`, a reason and a null value.

## Cancellation and cleanup gate (DS-SCI-028)

```powershell
python tools/scientific-broker/qualify_cleanup.py --config <config.json>
```

The suite cancels the real CGAL adapter, then uses a test-only child process to exercise forced cancellation, timeout and orphan recovery. It verifies status mapping, removed partial mesh/handoff outputs, promotion blocking and absence of live children. The diagnostic adapter never receives capability qualification. The broker finalizes terminal status after child cleanup; an unverified cleanup cannot count as success. `psutil` is required for this cleanup gate.

## Concurrency and repository evidence (DS-SCI-029–031)

```powershell
python tools/scientific-broker/qualify_concurrency.py --config <config.json>
python tools/scientific-broker/compare_commits.py --repo <devshell-repo> --baseline <git-ref> --candidate <git-ref> --output-root <local-evidence-directory>
```

The concurrency suite runs the qualified CGAL fixture twice at 1, 2, 4 and 8 concurrent jobs when available RAM permits. A suite-only release barrier starts each batch after all workers are ready; hashed adapter timing records must show the requested peak overlap. It checks unique job directories, each request/result/handoff identity, verified artifact hashes, cleanup, throughput and tail latency. A short launch gate lets telemetry observe the process tree before the adapter starts. A test-only held worker checks capacity rejection, and a real CGAL job under a 1 MiB sampled memory budget checks the `resource-exhausted` state, artifact cleanup and blocked promotion. The suite writes immutable local evidence under the broker diagnostics directory. These are broker resilience checks for the fixed CGAL path, not new runtime qualification levels.

Each new broker job writes `source-snapshot.json` before the worker starts. It records the full Git commit and tree, branch/worktree identity, tracked patch hash, hashes of untracked files and an aggregate dirty digest. The broker request and result pin the snapshot hash, and promotion refuses a tampered snapshot. Source capture only reads Git state and files; a missing Git checkout is recorded as unavailable. Old run snapshots remain inspectable after a branch advances.

The commit comparison creates temporary detached Git worktrees for two distinct commits, then runs the same .NET broker build, independent mesh reload tests and fixed tetrahedron OBJ inspection in each. It saves both exact commit/tree identities, suite revisions, host/tool environment, logs, geometry evidence and an evidence diff. Build or test failure yields `inconclusive`, so infrastructure failures are never presented as scientific regressions. The worktrees are removed after execution; saved evidence remains under `output-root`. This source matrix does not qualify a worker binary or grant broker promotion.

## Bisect and cross-runtime differences (DS-SCI-032/033)

```powershell
python tools/scientific-broker/bisect_commits.py --repo <devshell-repo> --good <known-good-commit> --bad <known-bad-commit> --output-root <local-evidence-directory>
python tools/scientific-broker/differential.py --left-result <cgal-results.json> --left-artifact <registered.obj> --right-result <vtk-results.json> --right-artifact <registered.vtp> --output-root <local-evidence-directory>
```

The bisect runner accepts a linear first-parent range. It executes the fixed DS-SCI-031 build/test/mesh matrix in temporary detached worktrees. Build or setup errors classify `skip`; a scientific test assertion or validated mesh contract mismatch classifies `bad`. Skipped commits between the last good and first bad yield an inconclusive boundary, never a claimed first bad. Every examined commit has a saved classification and exact source/environment evidence. The current repository has no declared bad endpoint; comparing two known-good commits returns `invalid-endpoints`.

The differential tool verifies saved successful run, registered artifact and fingerprint identities before comparing OBJ/VTP surfaces. It checks component topology, sampled surface deviation in both directions, orientation, bounds, area and signed volume. The library also compares numeric field samples by canonical ID and unit and exact rational/polynomial results using normalized fractions. Alternate triangulations can be equivalent even when artifact hashes differ. Mesh comparison is bounded to 500 triangles per side and uses samples rather than a full exact surface proof. Caller-supplied field/exact descriptors have schema version, kind, runtime/run IDs and data; they are comparison inputs, not new qualification evidence.
