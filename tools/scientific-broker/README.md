# Scientific Runtime Broker (DS-SCI-021/022)

The separate Sage exact worker, WSL adapter and managed L3 qualification suite are documented in [SCIENTIFIC_SAGE_WORKER.md](../SCIENTIFIC_SAGE_WORKER.md). These scoped operations are not exported as certified broker capabilities.

This is a separate localhost process. It uses the existing version 1 CGAL worker request/result contract and emits the version 1 `math3d.mesh-product-handoff` consumed by `tools/math3d-l9-product-handoff.mjs`. The renderer does not load CGAL or link its SDK.

## Export current certification

Build and run the exporter with five explicit paths:

```powershell
dotnet run --project tools/scientific-broker/ScientificBroker.csproj -- export <devshell-repo> <installed-launcher-root> <math3d-checkout> <profile-id> <manifest.json>
```

The exporter rereads successful runs, verifies fingerprints and immutable qualification files, assesses source, environment, dependency, and MATH3D consumer drift, then exports current scoped L9 CGAL and Gmsh capabilities. Gmsh's fixed 2D `mesh.generate` and fixed-cube tetrahedral `mesh.generate3d` entries are independent. A stale or unavailable chain is omitted. The manifest and its `.sha256` sidecar are a deployment snapshot; export again after qualification or environment changes. The hash detects mismatches, but is not an authenticity signature.

## Configure and run

The guarded `mesh.remesh` profile requires a current managed L5–L9 chain. It pins policy v2, eight allowlisted accepted and volume-loss cases, the worker, and six MATH3D consumer sources. Inspect readiness with `audit-remesh` using the same four paths as `export`.

The dedicated `mesh.orient` profile requires current managed orientation v2 L5–L9 records. Its twelve typed cases pin eight accepted outward OBJ results and four rejected pathological inputs. The broker checks the case manifest, qualification and broker sources, dedicated worker, runtime package inventory, and six MATH3D consumer files. Accepted jobs transport `oriented.obj`, `scope.json`, and `handoff.json`; rejected jobs publish no mesh. Promotion rechecks those bytes and the L9/L8 record identities. Run the opt-in HTTP acceptance with `DEVSHELL_ORIENTATION_BROKER_CONFIG=<config.json> python tests/test_scientific_orientation_broker.py`; it exercises accepted, rejected, tampered, and cancelled jobs. `orientation_broker_smoke.py run --config <config.json>` verifies all twelve broker decisions and eight MATH3D document/viewer round trips.

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

For `mesh.remesh`, `POST /v1/jobs` also requires `caseId` and `timeoutSeconds`. The case fixes the edge target, iteration count, input hash, and expected guard decision. Accepted jobs transport `remeshed.obj`, `guarded.json`, and `handoff.json`; volume-loss cases end `rejected` with no published mesh. Promotion checks current certification, saved guard and handoff, output hash, and MATH3D source identity. Run the opt-in live check with `DEVSHELL_REMESH_BROKER_CONFIG=<config.json> python tests/test_scientific_remesh_broker.py`.

## Three-capability release

`three_capability_release.py run --math3d-root <checkout>` creates one short, isolated Git worktree at the current commit. It builds DevShell, requalifies remesh, repair and fixed-cube volume through the managed desktop actions, exports their current L9 records, runs each broker/MATH3D smoke, and writes a hash-sealed coexistence record under that worktree's `.scientific/three-capability-release`. The worktree and evidence remain for later verification. Run `three_capability_release.py verify --record <coexistence.json>` to re-export from the same checkout and refuse source, environment, lower-support, broker, product, or artifact drift.

## Four-capability release

`four_capability_release.py run --math3d-root <checkout>` builds one isolated worktree at the current commit, runs the managed orientation, remesh, hole repair, and fixed-cube volume L0–L9 actions, exports one fresh certification manifest, and runs all four broker/MATH3D product smokes. It writes a SHA-256-sealed `scientific.four-capability-release` coexistence record under `.scientific/four-capability-release` in that worktree. `four_capability_release.py verify --record <coexistence.json>` re-exports from that same checkout and rejects changed source commit, missing or stale lower records, source and consumer drift, changed broker config, smoke, product, or artifacts. The earlier three-capability record remains historical and does not cover the merged orientation source.

## VTK read broker profile

The `vtk-win-conda` `mesh.read` profile requires the separate managed version 2 VTK L5–L9 chain. Its nine typed cases pin six accepted OBJ reads, including open and disconnected surfaces, and three malformed OBJ/PLY/VTP rejections. Accepted jobs transport the exact L9 VTP, independently reloaded OBJ, scope guard and handoff; rejected jobs transport no mesh. Promotion rechecks the current chain, worker and source hashes, both mesh artifacts, MATH3D consumers and the saved request/result. Run `vtk_read_broker_smoke.py run --config <config.json>` for all cases and MATH3D products, and set `DEVSHELL_VTK_READ_BROKER_CONFIG` for `python tests/test_scientific_vtk_read_broker.py` to exercise accepted, rejected, tampered and cancelled HTTP jobs.

## Five-capability release

### Current six-capability release

`six_capability_release.py run --math3d-root <checkout> --cgal-prefix <prefix> --vtk-prefix <prefix> --scientific-prefix <prefix>` creates one isolated worktree at the current commit, runs managed desktop L0–L9 for CGAL inspection, orientation, remesh and hole repair, Gmsh volume and VTK read, then runs all six broker/MATH3D smokes. It prints a `CHECKPOINT` path before building. Each build, desktop, export, broker and finalization gate is saved atomically with a content seal. After interruption, use `six_capability_release.py resume --checkpoint <checkpoint.json>`; resume verifies the same Git HEAD, MATH3D identity, desktop build, current saved L0–L9 support, certified manifest and completed broker smokes before continuing. An interrupted scenario restarts from L0 so a failed L9 action cannot inherit unverified prior levels; completed scenarios retain their checkpoints. The desktop launcher rejects occupied CDP ports and waits for Playwright to attach the app target before taking action. Tampered checkpoints, changed source, changed artifacts and stale support block resume. `verify --record <coexistence.json>` re-exports support and rejects source, environment, consumer, broker and product drift. The old five-capability release is historical.

`schemas/scientific-mesh-inspect.v2.json` pins six matched closed OBJ tiers, from 4 through 1,026 points and 2,048 triangles. The CGAL and VTK case packs are versioned separately. `comparable_inspect.py run --release <six-release.json> --output-root <directory>` requires both current broker profiles and live desktop support, then checks accepted promotion and equivalent geometry/topology. It randomizes provider order across repeated same-host jobs and reports medians, p10/p90, MAD and deterministic bootstrap intervals for startup-inclusive broker worker time. Ranking applies only to these exact pinned fixtures while the record verifies.

`schemas/scientific-mesh-inspect-classes.v2.json` retains three tiny uniform-transform classes and adds outward, single-component closed surface tiers of 64–128, 256–512 and 1,024–2,048 triangles. The larger holdouts are deterministic icospheres independently triangulated from the registered UV-sphere bases. Their policy checks bounded OBJ bytes and coordinates, oriented two-face edges, connectivity, Euler characteristic, per-face outward direction, area, radius and volume; six new pathological fixtures pin rejections. These classes remain outside advisor scope until both current desktop L5–L9 records and matched CGAL/VTK broker jobs promote under the new policy. The version 1 class policy and its records remain historical.

`math3d_inspect_product.py preview|run --shared-record <shared-inspect.json> --input <OBJ> --math3d-checkout <checkout> --output <directory> [--manual-provider cgal-win-conda|vtk-win-conda]` verifies scope before choosing a broker. Supply `--class-record <classes.json>` instead for a bounded class input; the selected broker receives a typed `classId` request for the actual OBJ. The selection record and HTML rationale show recommendation, abstention, paired uncertainty, manual choice and fallback reason. Run reopens the promoted OBJ in MATH3D's saved Mesh document and M3DM formats and mounts its viewport. Stale or out-of-scope evidence falls back to direct MATH3D import. `verify --record <selection.json> --input <OBJ>` rechecks selection and product files with the matching evidence argument. DevShell's Scientific Runtimes → CGAL → Integration panel exposes the same preview and managed run, with Stop and History controls.

`publish_six_inspect.py run --release-record <six-release.json> --math3d-root <pulled-build> --signing-key <private.pem> --key-id <id> --output-root <directory>` verifies the same release and MATH3D identity, qualifies bounded classes with paired broker jobs, measures exact tiers, creates advisor and product records, runs the four-role managed desktop journey, rebuilds the matrix/report, and signs a portable bundle. Every completed stage is saved in a hash-sealed `checkpoint.json`. Use `publish_six_inspect.py resume --checkpoint <checkpoint.json> --signing-key <private.pem>` after interruption; resume re-verifies the source, consumer and each completed stage before continuing. The private key is never written to the checkpoint. The desktop journey uses `Run-Scientific-Desktop-Acceptance.ps1 -Scenario CgalInspect -ExistingWorktree <release-worktree> -SkipBuild -ProductJourney ...`; `desktop_inspect_journey.py create|verify` seals automatic choice, manual override, direct fallback, cancellation and saved-document/viewport reload to the release and MATH3D identity. `portable_six_evidence.py verify --bundle <zip> --trust-store schemas/scientific-evidence-trust.v1.json` checks the Ed25519 signature and every payload and link without the worktree. After the final source commit and its current release have been pushed to remote main, `publish_inspection_asset.py --publication <publication.json> --repo <worktree>` uploads the ZIP under a SHA-256 filename to a source-pinned GitHub release, downloads it and checks the signature offline. The `devshell-six-2026-11-b` public key is trusted from 2026-11-12; the earlier key remains for historical bundles. Private keys stay outside Git and synchronized folders.

### Historical five-capability flow

`five_capability_release.py run --math3d-root <checkout> --cgal-prefix <prefix> --vtk-prefix <prefix> --scientific-prefix <prefix>` builds one isolated worktree at the current commit and requalifies orientation, remesh, hole repair, fixed-cube volume and VTK read through the managed desktop L0–L9 actions. It requires exactly those five current certified entries, runs every broker/MATH3D product smoke, then writes one SHA-256-sealed coexistence record under `.scientific/five-capability-release` in that worktree. The three runtime prefixes may instead be supplied with `DEVSHELL_CGAL_PREFIX`, `DEVSHELL_VTK_PREFIX` and `DEVSHELL_SCIENTIFIC_PREFIX`. `five_capability_release.py verify --record <coexistence.json>` re-exports from the isolated checkout and rejects source commit drift, stale support, changed broker config, smoke or product artifacts.

`portable_evidence.py export --record <coexistence.json> --output <bundle.zip> --signing-key <private.pem> --key-id <id>` first runs the live five-capability verifier, then copies the certified manifest, release and smoke records, supporting managed runs, fingerprints and qualifications. Every supporting artifact becomes a SHA-256-named object; the manifest links its run-relative name and original hash to the portable object's hash. The format policy permits path-redacted JSON and UTF-8 text, metadata-stripped PNG, and the fixed MD3M/M3DM/M3DT v1 native mesh formats. Unknown formats, malformed headers, executable files and files over 64 MiB fail export. A portable copy of path-bearing JSON is review evidence with the original hash preserved, not a byte-identical replay input. Export fails if any artifact is omitted.

The version 2 manifest is signed with Ed25519. `portable_evidence.py verify --bundle <bundle.zip> --trust-store schemas/scientific-evidence-trust.v1.json` checks the signature, every content-addressed object, format policy and all L0–L9 support links without the original worktree. Obtain the trust-store file from a trusted DevShell source checkout or release channel, separate from the ZIP; a public key packed inside an untrusted ZIP is not an authority. The checked-in trust store pins the current public key ID, activation and expiry. Keep the private key outside Git and outside synchronized folders, restrict access to release operators, and never distribute it with a bundle. `portable_evidence.py keygen --private-key <private.pem> --public-key <public.bin>` creates a new identity; add its public key under a new ID in the trust store before its first release. Rotation can overlap keys: retain old public keys until historical bundles no longer need verification, and stop signing with an expired key. Set `revokedAtUtc` when a key is compromised; verification rejects that key immediately, including previously signed bundles, so a trusted release channel must reissue affected evidence. A manifest hash alone detects accidental changes but does not authenticate a publisher. The verifier's verdict is historical evidence and does not requalify the current installation.

The five-capability release also captures a distinct MATH3D identity after a current `npm run build:core`: Git commit, package manifests and lockfile, `dist` desktop build files, every renderer distribution file, and the seven mesh/volume consumer contract sources. Each product smoke gets a hash-sealed sidecar binding its smoke hash to the same identity. Release verification recomputes the identity and rejects changed sources, build files or package files. A dirty MATH3D checkout is allowed only as the exact pinned content; the identity records the build's dirty declaration. The current checkout must be rebuilt after any consumer change before sealing another release. Portable bundles carry the product-smoke identity links as historical evidence.

`schemas/scientific-mesh-inspect.v2.json` defines six exact shared `mesh.inspect` tiers from 4 through 2048 points. `comparable_inspect.py run --release <current-six-release.json> --output-root <local-output>` requires current desktop L0–L9 evidence, both current broker profiles, successful allowlisted jobs and promotion, equivalent inspected surfaces, one warmup and at least five randomized paired same-host runs per provider/tier. Each sample retains typed request, worker result, broker result, telemetry, and artifact hashes. The v4 record separates cold broker invocation from microsecond-resolution worker read/inspect/write time for both providers and derives startup overhead. `verify --record <shared-inspect.json>` rechecks the source, operation, geometry, paired samples, timing and memory. `schemas/scientific-inspect-ranking.v2.json` allows `advisor.py advise-shared` to recommend only when cold and warm paired 95% intervals agree, both show at least 10% median advantage, and all timing and memory limits pass. Missing or rounded warm timing abstains. Manual selection remains authoritative. The bounded classes are documented in `docs/SCIENTIFIC_INSPECT_CLASSES.md`; each needs current desktop and broker holdout evidence before `advisor.py advise-class` can rank it.

The DevShell MATH3D inspection control runs the broker bridge with the managed `devshell-scientific` Python. `Install-ScientificRuntimes.ps1 -Kind gmsh` installs `psutil` there, and the runtime-lab probe verifies its isolated import before qualification. Broker process-tree cleanup cannot promote a job without it.

`five_capability_report.py build --record <coexistence.json> --output-root <directory>` verifies the five-capability release, runs CGAL `cgal.validate` and VTK `mesh.inspect` on the same pinned tetrahedron and host (one warmup, five measured runs each), and seals a current five-capability matrix plus Markdown/HTML reproducibility report. `five_capability_report.py verify --record <report.json>` rechecks the release, supporting result/artifact hashes, geometry and timing summary. These operations have different semantics, so their timings are diagnostic and do not rank backends.

- `GET /v1/providers`: certified provider and capability discovery.
- `POST /v1/jobs`: accept `schemaVersion`, `runtimeId`, `capabilityId`, `input: {path, sha256}`, and optional `timeoutSeconds` (1–120). The input must be a bounded registered dataset with the exact hash of the selected L9 fixture: OBJ for CGAL or `.geo` for Gmsh.
- `GET /v1/jobs/{id}`: state (`running`, `succeeded`, `partial`, `failed`, `cancelled`, `timed-out`, `resource-exhausted`), stage, progress, diagnostics, and verified artifact metadata.
- `GET /v1/jobs/{id}/telemetry`: hash-verified CPU, RAM, GPU and VRAM measurements after finalization. Every metric includes a collector, unit, scope, availability and sample count.
- `GET /v1/jobs/{id}/source`: hash-verified Git commit, tree, branch, worktree and dirty-content identities captured at submission. Non-Git deployments record an explicit unavailable reason.
- `POST /v1/jobs/{id}/cancel`: terminate the owned worker process tree.
- `POST /v1/jobs/{id}/promote`: save an immutable allow/block decision with reasons. It requires a successful job, a current matching L0–L9 certification chain, unchanged worker/package and MATH3D consumer identities, and a verified version 1 handoff. `math3dRoot` is required for an allowed decision.
- `GET /v1/jobs/{id}/artifacts/{name}`: serve only a registered artifact from a successful job after rechecking its hash. Names depend on the certified profile; the volume profile serves `cube.msh`, `volume.m3dt`, `exporter.json` and `handoff.json`.

Completed job results survive broker restarts. MATH3D can consume `handoff.json` after an allowed promotion; the handoff pins the worker request, result, output, L8 record, and contract. The broker requires the worker output hash to match the fixed L9 reference artifact. Each broker configuration selects one certified capability profile.

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

## Selective retesting (DS-SCI-035)

```powershell
python tools/scientific-broker/retest.py --base HEAD~1 --head HEAD --output-root .scientific/retest --execute-local
python tools/scientific-broker/retest.py --changed tools/scientific-cgal-worker.py --environment-changed cgal.packages --output-root .scientific/retest
```

The version 1 graph in `schemas/scientific-retest-graph.v1.json` records suite source patterns, environment keys and dependencies. A plan has the graph hash, changed paths, affected suites and reasons. Unmapped code or environment changes select every suite; documentation changes select none. `--execute-local` runs only fixed local unittest commands. The broker and pipeline integration tests need `SCIENTIFIC_BROKER_CONFIG` set to a local broker configuration; without it those checks report `requires-broker-config`. Desktop-managed suites report `requires-managed-run` and still need fresh managed qualification records. A plan is never qualification evidence by itself. For a MATH3D checkout change outside this repository, pass the changed file as an explicit `--changed math3d/...` path.

## Typed pipeline pilot (DS-SCI-036)

```powershell
python tools/scientific-broker/pipeline.py run --config .scientific/broker/config.json --spec schemas/scientific-pipeline-example.v1.json
python tools/scientific-broker/pipeline.py verify --record <pipeline-result.json>
python tools/scientific-broker/pipeline.py replay --config .scientific/broker/config.json --record <pipeline-result.json>
```

Version 1 accepts a DAG with only `qualified.cgal.mesh.validate` (no input, `mesh.obj.v1` and `math3d.handoff.v1` outputs), `mesh.inspect` (`mesh.obj.v1` to `mesh.metrics.v1`) and `math3d.promote` (the same worker's mesh and handoff to `math3d.promotion.v1`). Preflight checks the entire graph, types, cycles and the deployed certified manifest before a job starts. The worker uses the fixed qualified tetrahedron fixture. Each node records source job, contract, certification, typed inputs and output hashes. The independent inspection cache is keyed by mesh and parser source hashes and sealed with a hash sidecar. The pipeline record and artifact hashes are checked before replay; replay compares worker and inspection output hashes. Only a successful current broker promotion counts as an allowed MATH3D handoff. The deployment manifest is a certification snapshot, so re-export it when the desktop's current evidence changes.

## Authenticated remote agent pilot (DS-SCI-037)

Provision a server certificate with a hostname that the client can validate, a private key, a trusted CA file on the client, and a random token in a protected file on both hosts. Server profile JSON:

```json
{"schemaVersion":1,"agentId":"lab-agent-1","hostId":"lab-host-1","brokerConfig":"<absolute broker config>","certFile":"<certificate PEM>","keyFile":"<private key PEM>","tokenFile":"<token file>","bindHost":"127.0.0.1","maxTimeoutSeconds":120}
```

Client profile JSON:

```json
{"url":"https://lab-agent.example:8766","agentId":"lab-agent-1","hostId":"lab-host-1","manifestSha256":"<certified manifest SHA-256>","caFile":"<trusted CA PEM>","tokenFile":"<token file>"}
```

```powershell
python tools/scientific-broker/remote_agent.py serve --config <server-profile.json> --port 8766
python tools/scientific-broker/remote_agent.py profile --config <client-profile.json>
python tools/scientific-broker/remote_agent.py run --config <client-profile.json> --output-root <local-evidence-directory>
python tools/scientific-broker/remote_agent.py verify --record <remote-evidence.json>
```

TLS validates the server certificate and hostname; the client also pins the agent, host and manifest identity. All routes require the bearer token. The server accepts no command, path or arbitrary input bytes from the client. It runs only the certified CGAL fixture, with a bounded timeout, the broker's worker capacity and optional memory budget. Cancellation is available at `POST /v1/jobs/{id}/cancel`. Returned OBJ and handoff bytes are checked against the registered job hashes and certified reference. Saved remote transport evidence is hash sealed and explicitly marked `remote`; it cannot be substituted for local L0–L9 qualification. Protect the key and token files with OS permissions and expose the server only on an intended trusted interface.

## CI evidence exchange (DS-SCI-038)

Configure each CI agent with a protected random signing key and its actual `host_fingerprint()` from `telemetry.py`:

```json
{"schemaVersion":1,"agentId":"ci-agent-1","hostFingerprintSha256":"<64 hex>","gpuCapable":false,"keyFile":"<protected key file>"}
```

The import host has a trusted registry: `{"schemaVersion":1,"agents":[<agent profile>]}`. The registry points to the same secret key through a local protected path; the key is never placed in the bundle.

```powershell
python tools/scientific-broker/ci_evidence.py export --config <broker-config.json> --job-id <terminal-job-id> --agent <agent-profile.json> --output <new-bundle.zip>
python tools/scientific-broker/ci_evidence.py import --bundle <bundle.zip> --trusted-agents <trusted.json> --config <local-broker-config.json> --output-root .scientific/ci-imports
```

The bundle includes only a redacted job summary, hashes, telemetry and, for success, the fixed public OBJ. It excludes raw requests, handoff paths, logs, source files, tokens and private input. Import verifies the HMAC signature, archive member hashes, agent and host identity, certified reference output and current suite/environment/manifest applicability. A drifted bundle remains inspectable with an `inconclusive` reason; it does not change local qualification. The desktop Scientific Runtime Matrix reads hash-checked summaries from `.scientific/ci-imports`. Reimport after local suite or environment changes to reassess applicability. The fixed CGAL CPU capability cannot claim GPU qualification, including when a GPU collector happens to run on its host.

## Release certification (DS-SCI-039)

```powershell
python tools/scientific-broker/release_certification.py certify --config <broker-config.json> --installed-root <launcher-install-root> --profile-id <profile-id> --release-tag <tag> --output-root .scientific/releases
python tools/scientific-broker/release_certification.py verify --config <broker-config.json> --report <qualification-report.json>
```

The command reruns the desktop L0–L9 exporter against saved managed runs and current source, package and MATH3D consumer state. A release manifest is written only when that fresh single CGAL L9 entry exactly matches the deployed broker certification. A blocked attempt saves the report and fresh export without a release manifest. The observed attempt on 2026-11-06 was blocked because the fresh desktop export has no current L9 CGAL record. This gate does not upgrade imported CI results or qualify Gmsh. `verify` with `--config` additionally checks that the saved release evidence still matches the deployed broker.

## Reviewed regression fixtures (DS-SCI-040)

```powershell
python tools/scientific-broker/regression_fixtures.py draft --config <broker-config.json> --job-id <failed-certified-job-id> --output-root .scientific/regressions
python tools/scientific-broker/regression_fixtures.py promote --config <broker-config.json> --draft <draft.json> --reviewed-by <reviewer-id> --approve-public-fixture --output-root .scientific/regressions
python tools/scientific-broker/regression_fixtures.py replay --config <broker-config.json> --fixture <fixture.json>
```

Only failures of the currently certified fixed CGAL fixture are eligible. A draft contains the fixture ID and hash, source job, contract, qualification and resource policy; raw input, paths and logs stay local. Promotion needs a named review and explicit approval of the public fixture scope, then requires two fresh runs with the same failed terminal state and no artifacts. A mismatch saves a blocked review and no fixture. The immutable fixture links to the source run, draft, review and both replay jobs; verification can run it again. Private inputs and other providers are not exported or promoted by this pilot.

## Environment drift diagnosis (DS-SCI-041)

Open a verified Scientific History run and choose **Diagnose drift**. The read-only panel compares its saved source and environment fingerprint with the current checkout, then lists concrete requalification steps for interpreter, PATH, Conda packages, compiler tools, WSL mapping and GPU driver evidence. Driver collection is optional; an unavailable collector is reported as unknown, not as a passing driver match. After correcting a mismatch, rerun the affected managed probes and recipes and inspect fresh qualification records.

## Reproducible environment manifests (DS-SCI-042)

For a registered Windows Conda provider, use its dedicated prefix:

```powershell
python tools/scientific-broker/environment_manifest.py capture --runtime-id cgal-win-conda --prefix <cgal-prefix> --output-root .scientific/environment-locks
python tools/scientific-broker/environment_manifest.py verify --manifest <environment-manifest.json>
python tools/scientific-broker/environment_manifest.py recreate --manifest <environment-manifest.json> --conda-exe <conda.exe> --output-root .scientific/environment-recreation
python tools/scientific-broker/environment_manifest.py verify-recreation --manifest <environment-manifest.json> --record <recreation-record.json>
```

Capture seals an exact Conda explicit lock, package-build identity, pip version inventory, container compatibility preset and CMake preset. Recreation runs `conda create` offline in a disposable prefix, checks every installed package identity against the lock, records the attempt and log hashes, and removes the prefix. The current CGAL 54-package lock passed this test. Pip wheel hashes and a pinned compatible Windows container base are still needed for exact venv or container recreation. Unsafe package URLs are rejected before saving a lock.

## Adapter conformance matrix (DS-SCI-043)

```powershell
python tools/scientific-broker/adapter_conformance.py --config .scientific/broker/config.json --runtime-report .scientific/runtime-report.json --output-root .scientific/conformance
python tools/scientific-broker/adapter_conformance.py --verify <conformance.json>
```

The sealed report checks provider contracts, expected rejection, cancellation, progress, typed values and output hashes. It records `passed`, `failed` or `unavailable` for every dimension and computes a provider verdict. The certified CGAL path passes all six. VTK passes contract, rejection, typed result and artifact hashing, while its current adapter lacks versioned cancellation and progress acknowledgement. Python/SciPy and Sage have typed and rejection probes but no version 1 artifact worker. Gmsh remains unavailable because its package is missing. A conformance report cannot grant qualification or promote Gmsh.

## Cost advice (DS-SCI-044)

```powershell
python tools/scientific-broker/advisor.py advise --config .scientific/broker/config.json --capability-id mesh.interop.vtk-math3d --tier single --manual-provider cgal-win-conda --output-root .scientific/advice
python tools/scientific-broker/advisor.py verify --config .scientific/broker/config.json --record <advice.json>
```

The advisor reads sealed benchmark identities for the selected operation and tier. Current host, environment, certification, fixture, suite and collector identities must match, and two benchmark runs must be comparable before a cost appears. A manual provider must itself be certified. The fixed CGAL capability has two current runs comparable with each other; both are inconclusive against the older pinned baseline after broker and telemetry sources changed. One provider cannot support a backend ranking, so the current decision has no automatic recommendation. Save the advice record with the chosen run for deterministic replay.

## Content-addressed artifacts (DS-SCI-045)

```powershell
python tools/scientific-broker/artifact_cache.py ingest-broker --root .scientific/artifact-cache --config .scientific/broker/config.json --job-id <job-id> --name l5-positive.obj
python tools/scientific-broker/artifact_cache.py ingest-document --root .scientific/artifact-cache --config .scientific/broker/config.json --job-id <smoke-job-id>
python tools/scientific-broker/artifact_cache.py get --root .scientific/artifact-cache --digest <sha256>
python tools/scientific-broker/artifact_cache.py pin --root .scientific/artifact-cache --digest <sha256> --owner release:<id>
python tools/scientific-broker/artifact_cache.py gc --root .scientific/artifact-cache --older-than-days 30
python tools/scientific-broker/artifact_cache.py gc --root .scientific/artifact-cache --older-than-days 30 --apply
```

Objects are keyed by SHA-256, streamed to disk and verified on every read. Each ingestion creates a named reference; `unreference` and `unpin` need the same digest and owner. Cleanup lists candidates by default, then deletes only old objects with no references or pins when `--apply` is given. A changed object blocks cleanup. Do not treat a cache object as qualification evidence without its source job and certification record.

## Exact-to-document provenance (DS-SCI-046)

```powershell
python tools/scientific-broker/provenance.py build --config .scientific/broker/config.json --output-root .scientific/provenance
python tools/scientific-broker/provenance.py verify --config .scientific/broker/config.json --record <provenance.json>
```

The fixed public workflow derives roots `-1` and `1` in Sage WSL, represents the exact tetrahedron coordinates, generates the byte-identical certified OBJ in the registered dataset root, runs that input through the qualified CGAL broker, and exercises MATH3D scene import, viewer regression and independent `.m3dm` reload. The graph links seven typed stages to the source job and saved hashes. This is a fixed example; general Sage-derived meshes need their own typed worker and qualification.

## Interactive artifact inspection (DS-SCI-047)

Open a saved run in Scientific History. **Preview mesh** loads a hash-checked OBJ/STL/PLY/VTP/M3DM into the existing interactive viewer. The inspector shows full output counts and bounds, saved worker topology and the artifact SHA-256. Select two runs under **Compare saved outputs** and load both previews for numeric count and bound differences. Sage History displays verified factor coefficients and multiplicities from a saved managed probe or factor smoke. Rendered triangles may be sampled for large meshes; numeric equality is not a mesh equivalence proof.

## Contract compatibility gate (DS-SCI-048)

```powershell
python tools/scientific-broker/contract_migration.py check --policy schemas/scientific-contract-migrations.v1.json --output-root .scientific/contract-migrations
python tools/scientific-broker/contract_migration.py verify --policy schemas/scientific-contract-migrations.v1.json --record <compatibility-report.json>
```

The policy retains a shared capability registry 1.0.0 baseline; the current registry is 1.2.0 after adding Sage exact and quadratic-field capabilities. Update `currentVersion` when its structure changes. Optional additions need a minor bump; removals, required additions, type changes and provider removals need a major bump and explicit migration rules. A `rename-field` or `set-default` rule must include valid old and new fixtures. A blocked check exits nonzero and never silently upgrades saved runs. Other worker and product contracts require their own baselines before migration.

## Release qualification matrix (DS-SCI-049)

```powershell
python tools/scientific-broker/release_matrix.py snapshot --release-report <release-A/qualification-report.json> --inventory <release-A/runtime-report.json> --output-root .scientific/release-matrix
python tools/scientific-broker/release_matrix.py snapshot --release-report <release-B/qualification-report.json> --inventory <release-B/runtime-report.json> --output-root .scientific/release-matrix
python tools/scientific-broker/release_matrix.py compare --left <snapshot-A.json> --right <snapshot-B.json> --output-root .scientific/release-matrix
python tools/scientific-broker/release_matrix.py verify --record <matrix.json>
python tools/scientific-broker/release_matrix.py render --record <matrix.json>
```

Use an inventory captured within 24 hours before each release. The six rows are CGAL, VTK, VTK-m, Sage, Gmsh and MATH3D. Each row links to its release report, qualification record and source run where available; missing or old evidence has reduced confidence. A blocked release supplies no certified capability, even when an older broker manifest exists. MATH3D's product contract is distinct from its release version. The current two-release observation is inconclusive because both release reports are blocked and the available runtime inventory is stale.

## Reproducibility report (DS-SCI-050)

```powershell
python tools/scientific-broker/reproducibility_report.py generate --matrix <release-matrix.json> --conformance <conformance.json> --contract <compatibility-report.json> --environment <environment-manifest.json> --recreation <environment-recreation.json> --provenance <provenance.json> --differential <saved-mesh-differential.json> --config .scientific/broker/config.json --output-root .scientific/reproducibility
python tools/scientific-broker/reproducibility_report.py verify --record <reproducibility-report.json>
```

The generator requires all seven evidence sources and verifies each before writing the report. It emits a sealed JSON record and hash-bound Markdown and HTML beside it. Verification checks source identities, the underlying evidence, and exact rendered bytes. A blocked release remains blocked even if a historical broker manifest and product smoke passed. The report describes only the supplied saved-run mesh differential and the fixed provenance/product regression; it does not infer a release regression or certify Gmsh. Treat local paths as traceability links and keep private inputs out of report bundles.

## Fresh release evidence (DS-SCI-051)

Capture `tools/Inspect-ScientificRuntimes.ps1` into `.scientific/runtime-report.json`. In the desktop Scientific Runtimes → CGAL → Commands page, run **Probe in runtime-lab**, **Compile & link**, then the L5, L6, L7, L8 and L9 buttons in order. Each gate must succeed before starting the next. Export current qualifications with `ScientificBroker.csproj export` into a new manifest path; require exactly one CGAL L9 capability with ten supporting records. Point a new broker config at this manifest, preserving old configs for historical runs. Run `broker.py verify`, `smoke.py`, and `provenance.py build` with the new config, then `release_certification.py certify` and `verify`. The release report pins the inventory captured within 24 hours, the source commit, local agent identity and L0–L9 gate records. A stale inventory or missing chain blocks the release. Save a new release matrix snapshot and DS-SCI-050 report from the verified evidence. Matrix snapshots retain their inventory bytes so subsequent inventory captures cannot alter the historical comparison. Gmsh stays outside the certified manifest.

## Shared-provider mesh comparison (DS-SCI-053)

```powershell
python tools/scientific-broker/cross_provider.py compare --cgal-release <CGAL-release/qualification-report.json> --vtk-release <VTK-release/qualification-report.json> --cgal-config <current-CGAL-broker-config.json> --vtk-config <current-VTK-broker-config.json> --cgal-result <CGAL-L6/results.json> --vtk-result <VTK-L6/results.json> --cgal-benchmark <CGAL-benchmark.json> --vtk-benchmark <VTK-benchmark.json> --output-root .scientific/cross-provider
python tools/scientific-broker/cross_provider.py verify --record <comparison.json>
```

Use source runs that registered the same tetrahedron input hash. The report checks saved output and run fingerprint hashes and compares geometry, topology, orientation and scale at a declared tolerance. Both release reports and live broker configs must verify the exact current L9 records to pass. A missing or stale certification blocks the verdict. Performance is inconclusive until two benchmark records use current qualification IDs, the same host, fixture, tier sizes and policy. The current local pair is geometrically equivalent; VTK lacks L9 and the earlier CGAL contract hash is stale after the Gmsh worker extension.

## Gmsh local foundation (DS-SCI-054)

```powershell
G:\master\.conda\devshell-scientific\python.exe -m pip install --no-deps gmsh==4.15.2
python tools/scientific-broker/gmsh_foundation.py run --prefix G:\master\.conda\devshell-scientific --cmake G:\master\.conda\devshell-cgal\Library\bin\cmake.exe --output-root .scientific/gmsh-foundation
python tools/scientific-broker/gmsh_foundation.py verify --record <foundation.json>
```

Run only with a matching native Gmsh package, header and import library in the prefix. The registered `gmsh.mesh2d` worker accepts the fixed public square and a bounded mesh size, saves a typed `.msh` result and rejects invalid parameters. The local suite records L0–L4 probe and compile/link evidence, source and package hashes, a positive output, expected rejection and an independent artifact reload. This local record does not enter desktop qualification History or the broker certified manifest; L5–L9 remain open.

## Gmsh local worker, repeat and consumer checks (DS-SCI-055–057)

```powershell
python tools/scientific-broker/gmsh_progression.py run --foundation <foundation.json> --vtk-python G:\master\.conda\devshell-vtk\python.exe --math3d-checkout G:\master\Math3D --output-root .scientific/gmsh-progression
python tools/scientific-broker/gmsh_progression.py verify --record <DS-SCI-055.json>
python tools/scientific-broker/gmsh_progression.py verify --record <DS-SCI-056.json>
python tools/scientific-broker/gmsh_progression.py verify --record <DS-SCI-057.json>
```

The first record binds a successful foundation run and two fresh worker rejections. The second pins two separate fixed-square `.msh` worker runs, equal byte hashes and independent Gmsh reloads. The third exports a bounded OBJ and checks VTK and MATH3D importer geometry, triangle connectivity, boundary topology, XY orientation, unit area and scale; both consumers reject malformed OBJ. Records pin their source, runtime, importer and artifact hashes and chain to the prior stage. These are local fixed 2D checks. They do not create managed desktop L5–L7 records, inspect a MATH3D viewer/document, qualify volume meshes, or add Gmsh to certified manifests.

## Managed Gmsh L0–L5 (DS-SCI-058–060)

Build the React UI and Windows launcher, then open Scientific Runtimes → Gmsh → Commands with the `desktop-five` profile. Run **Probe in runtime-lab**, **Compile & link**, and **Run L5 worker check** in that order. Open each run in History and require current qualification records. The probe grants only `runtime.inventory` L0, `python.version` L1, `gmsh.version` L2 and fixed `gmsh.surface2d` L3. Compile/link grants Gmsh C++ L4. The fixed worker grants `mesh.generate` L5 only after its typed positive and rejection cases pass against current lower records. The Gmsh prefix uses the sibling `devshell-cgal` CMake when its own prefix has no CMake, and the fingerprint records the actual tool. The managed run saves a registered local `.geo` copy and a verified `.msh` artifact. `node tests/scientific-gmsh-managed-ui-checks.mjs` exercises the three actions on a debug-port desktop build.

The local DS-SCI-056/057 files remain separate evidence. Managed L6–L9 are available as subsequent Commands actions. L6 reruns and reloads the fixed `.msh`; L7 verifies `.msh` → OBJ → VTK/MATH3D, including malformed rejection; L8 repeats the consumer under limits and checks cancellation, timeout and memory cleanup. L9 runs a fresh worker, verifies the native and converted artifacts against lower evidence, imports the OBJ into MATH3D, mounts the viewer, saves a native `.m3dm` and independently reloads it. Run these in order with current lower records; `node tests/scientific-gmsh-managed-ui-checks.mjs` exercises the full L0–L9 chain on a debug-port desktop build. Only the registered public fixed 2D square qualifies; arbitrary and volume meshes remain unqualified.

## Gmsh fixed-surface broker and release (DS-SCI-064–066)

Export the certified manifest after a current desktop L0–L9 chain. Configure a separate broker profile with `runtimeId: gmsh-win-conda`, its installed runtime manifest, the Gmsh Conda Python, `gmsh_adapter.py`, `scientific-gmsh-worker.py`, the fixed dataset root and the MATH3D checkout. The exporter requires all ten current supporting records plus unchanged worker, converter, MATH3D importer and document codec sources. The broker accepts only the registered fixed `.geo` SHA-256 and transports both `.msh` and OBJ with verified hashes. Promotion rechecks source snapshot, worker result, artifacts, contract and deployed sources.

```powershell
python tools/scientific-broker/broker.py verify --config <gmsh-broker-config.json>
python tools/scientific-broker/gmsh_smoke.py run --config <gmsh-broker-config.json>
python tools/scientific-broker/gmsh_smoke.py verify --config <gmsh-broker-config.json> --record <job/gmsh-smoke.json>
python tools/scientific-broker/release_certification.py certify --config <gmsh-broker-config.json> --installed-root <desktop-build> --profile-id desktop-five --release-tag gmsh-fixed2d-l9 --output-root <release-output>
python tools/scientific-broker/release_certification.py verify --config <gmsh-broker-config.json> --report <release/qualification-report.json>
```

The smoke runs broker job → verified native/OBJ transport → promotion → MATH3D document and viewer → independent `.m3dm` reload. `SCIENTIFIC_GMSH_BROKER_CONFIG=<gmsh-broker-config.json> python -m unittest discover -s tests -p test_scientific_gmsh_broker.py` exercises the path and rejects altered source, OBJ and native document evidence. Host-specific config, run artifacts and release reports stay under ignored `.scientific` paths.

## Gmsh candidate cube volume (DS-SCI-067–069)

The volume path is separate from the certified fixed 2D worker. It uses a public unit-cube fixture, a typed `gmsh.volume3d.cube` worker, two exact `.msh` repeat runs, independent Gmsh reload, and an outward boundary OBJ consumed by VTK and MATH3D's **surface** importer. Both consumers must reject a flipped boundary face. The suite saves linked, sealed local records and explicitly marks volume promotion unavailable.

```powershell
python tools/scientific-broker/gmsh_volume.py run --gmsh-python G:/master/.conda/devshell-scientific/python.exe --vtk-python G:/master/.conda/devshell-vtk/python.exe --math3d-checkout G:/master/Math3D --output-root .scientific/gmsh-volume
python tools/scientific-broker/gmsh_volume.py verify --record <run/DS-SCI-067.json>
python tools/scientific-broker/gmsh_volume.py verify --record <run/DS-SCI-068.json>
python tools/scientific-broker/gmsh_volume.py verify --record <run/DS-SCI-069.json>

## Managed Gmsh volume L3–L6 (DS-SCI-070–072)

The registered `mesh.generate3d` capability has its own fixed-cube scope, separate from the certified 2D `mesh.generate` path. The Gmsh runtime probe generates tetrahedra for L3. On the desktop `desktop-five` profile, run **Probe in runtime-lab**, **Compile & link**, **Run L5 volume worker check**, and **Run L6 volume repeat check** in order. L5 owns a fresh positive job and expected rejections, pins its public fixture and typed `.msh`, and requires current L0–L4 support. L6 owns a second job, compares its `.msh` bytes with L5, independently reloads tetrahedra and links the L5 record. History verifies the sealed local suite, artifact, source and lower records before granting each level.

For a debug-port acceptance run, set `DEVSHELL_CDP_URL` and `DEVSHELL_GMSH_VOLUME_ONLY=1`, then run `node tests/scientific-gmsh-managed-ui-checks.mjs`. The full script checks both fixed 2D L0–L9 and the separate volume path. Native tetrahedral MATH3D documents and volume L9/promotion remain open. The exporter publishes only current fixed 2D `mesh.generate` L9 evidence.

## Managed Gmsh volume L7–L8 and product readiness (DS-SCI-073–075)

Run **cube volume L7** after current L6. The managed job preserves the source `.msh`, extracts an outward OBJ boundary, checks the VTK and MATH3D surface consumers, and saves both flipped-face rejections. History verifies the sealed local DS-SCI-069 record, registered artifacts, current L6 baseline and the source and consumer hashes before granting `mesh.generate3d` L7. Run **cube volume L8** to repeat the boundary consumer three times under an owned memory limit, then check cancellation, timeout and memory failure cleanup; History checks its linked L7 support.

**Check volume product readiness** saves an owned result linked to current L8 and the tetrahedral MSH. The required MATH3D contract is `scientific/volume-consumer.v1.json` declaring `mesh.tetrahedral`, `math3d.tetrahedral-mesh-document` and cell preservation. An absent contract blocks the gate; a present contract makes it ready for L9 qualification, which still requires import, independent reload and viewer evidence. The existing OBJ surface importer drops tetrahedral connectivity, so it cannot grant volume L9.

## Gmsh tetrahedral MATH3D document and managed L9 (DS-SCI-076–078)

The fixed-cube worker now exports `M3DT` v1: a 16-byte header, three little-endian float64 coordinates per vertex and four little-endian uint32 indices per positively oriented tetrahedron. MATH3D's separate `math3d.tetrahedral-mesh-document` stores an identity and SHA-256 resource reference. Its adapter validates the saved cells and derives the closed outward boundary for `TetrahedralMeshViewport`; the boundary viewer never replaces the cell resource. A separate Python parser reloads the saved document and resource without using MATH3D's writer and checks topology, orientation, unit volume, bounds and exact hashes. The MATH3D adapter also rejects a modified resource.

Run **cube volume L9 product** after current L0–L8 evidence. The managed job reruns the public cube worker, requires the qualified `.msh` hash, exports `M3DT`, checks a version 1 broker-to-MATH3D handoff, saves and reopens the tetrahedral document, mounts the real boundary viewer in headless Edge and pins the screenshot and independent reload. History grants `mesh.generate3d` L9 only when the current lower chain and every product artifact verify. This gate covers the fixed public cube.

## Fixed-cube volume broker certification (DS-SCI-079)

Export with the MATH3D checkout that owns the tetrahedral consumer. Configure a separate broker profile with `runtimeId: gmsh-win-conda`, `capabilityId: mesh.generate3d`, the exported manifest, `gmsh_volume_adapter.py`, `scientific-gmsh-volume-worker.py`, the matching Gmsh Python environment and `datasetRoot` containing `gmsh/fixed-cube.geo`. The volume entry also pins the broker source hash. The adapter runs only `gmsh.volume3d.cube` at mesh size 0.35 and exports the fixed cube to M3DT. The broker checks exact `.msh` and M3DT reference hashes. `GET /v1/jobs/{id}/artifacts/volume.m3dt` serves the hash-verified cell-preserving resource; `cube.msh`, `exporter.json` and `handoff.json` are also registered.

```powershell
python tools/scientific-broker/broker.py verify --config <volume-config.json>
python tools/scientific-broker/gmsh_volume_smoke.py run --config <volume-config.json>
python tools/scientific-broker/release_certification.py certify --config <volume-config.json> --installed-root <launcher-install-root> --profile-id desktop-five --release-tag <tag> --smoke-record <job/volume-smoke.json> --output-root .scientific/releases
```

The smoke saves and verifies a broker job, promotion, MATH3D tetrahedral document, viewer image and independent round trip. New volume release reports and manifests pin that smoke record. A fresh runtime inventory within 24 hours is required for a qualified release; pass `--inventory <captured-report.json>` to use a run-local capture. Run `test_scientific_gmsh_volume_broker.py` with `SCIENTIFIC_GMSH_VOLUME_BROKER_CONFIG` and optionally `SCIENTIFIC_GMSH_VOLUME_RELEASE_REPORT` to check the HTTP resource transport and tamper gates. Re-export after source, package, runtime-manifest, worker or MATH3D consumer changes. The certificate is limited to the registered public unit cube; it does not authorize arbitrary volume meshes.

To inspect a missing volume certificate without replacing the deployed manifest, run `dotnet run --project tools/scientific-broker/ScientificBroker.csproj -- audit-volume <repo> <installed-root> <math3d-root> <profile-id>`. The JSON report lists recent L9 candidates, their current/stale/unknown state, supporting L0–L8 record states and rejected L9 evidence. It reports the reason an otherwise current candidate failed the final artifact or consumer check. An audit does not requalify a run or publish a capability.

Use `gmsh_volume_requalify.py plan` with the volume broker config, installed launcher root, tetrahedral MATH3D checkout and an output directory to save a hash-sealed plan. It selects the full managed chain when early evidence has drifted and the L7–L9 suffix when only late consumer/product evidence has drifted. `run` requires a separately launched DevShell `desktop-five` session exposed at `--cdp-url http://127.0.0.1:<port>`. It executes the existing managed UI check, re-audits the chain, exports a candidate broker manifest, runs the product smoke, captures a fresh runtime inventory in the run directory and writes a release qualification report from that inventory. Only a qualified release replaces the deployed manifest; final verification can restore its prior bytes. Every stage is gated; a failed stage saves a failure record. The command does not launch or stop the desktop app.

For a fresh isolated qualification without a deployed volume profile, run `tools/Run-GmshVolume-Acceptance.ps1 -Math3DCheckout <path>`, export the current manifest, then use `tools/New-GmshVolume-BrokerProfile.ps1 -Worktree <path> -Math3DCheckout <path> -Manifest <candidate.json> -Output <config.json>`. The profile generator checks the four source hashes pinned by the candidate and verifies the broker with a host Python that has `psutil`; its config still points the worker to the Gmsh Conda Python.

`tools/Invoke-GmshVolume-Release.ps1 -Worktree <path> -Math3DCheckout <path> -ReleaseTag <tag>` performs that candidate export, broker/MATH3D smoke, fresh run-scoped inventory, and release verification in a new deployment directory. It writes `qualified.json` only after every gate passes, preserving existing broker profiles. The marker pins the source commit, L9 record and hashes of the candidate manifest, config, inventory, smoke and release report. Requalification of an existing deployed manifest continues to use `gmsh_volume_requalify.py` and its rollback path.

After both repair and volume have been qualified in the same worktree, `coexistence.py certify` accepts their separate configs and release reports plus the worktree, installed root and MATH3D checkout. It freshly exports the checkout, requires exactly the two scoped L9 entries, re-verifies both releases and saves a hash-sealed combined record. `coexistence.py verify --record <path>` repeats those checks; the live regression test uses `SCIENTIFIC_COMBINED_RELEASE_RECORD=<path> python tests/test_scientific_coexistence.py -v`.

```powershell
python tools/scientific-broker/gmsh_volume_requalify.py plan --config <volume-config.json> --installed-root <launcher-install-root> --math3d-root <tetrahedral-math3d-checkout> --output-root .scientific/gmsh-requalification
python tools/scientific-broker/gmsh_volume_requalify.py run --config <volume-config.json> --installed-root <launcher-install-root> --math3d-root <tetrahedral-math3d-checkout> --cdp-url http://127.0.0.1:9244 --output-root .scientific/gmsh-requalification
python tools/scientific-broker/gmsh_volume_requalify.py verify --record <run-result.json> --config <volume-config.json>
```

The result verifier checks the sealed plan, ordered gates and linked artifact hashes. With `--config`, a passed run must still match the deployed manifest and qualified release. A failed run can be verified as saved evidence without a desktop session.
