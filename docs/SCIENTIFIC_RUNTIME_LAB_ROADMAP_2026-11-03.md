# DevShell Scientific Runtime Lab — Architecture and Implementation Roadmap

**Project:** MATH3D / DevShell\
**Date:** 2026-11-03\
**Scope:** Scientific development environments, repositories, native/WSL/Container execution, integration and qualification of CGAL, VTK, VTK-m, SageMath, Gmsh, Python, and future providers.\
**Status:** Proposed implementation roadmap based on DevShell scientific review screenshots (2026-11-03).\

> **Architectural principle:** DevShell installs, discovers, develops, builds, probes, tests, benchmarks, diagnoses, compares and certifies scientific runtimes. MATH3D consumes stable, versioned, typed scientific capabilities and artifacts. MATH3D must not depend on DevShell's local paths, environment management UI or repository-management internals.

---

## 0. Executive direction

DevShell is already more than a command launcher. Its existing CGAL-centric workflow includes runtime profiles, health checks, environment information, executable recipes, positive and expected-rejection tests, package inventory, saved history, artifacts, `.m3dm` handoffs, numerical comparisons and a recorded 35/35 Math3D-native integration verdict. The useful next move is **not** to keep adding isolated runtime-specific tabs. It is to extract a durable **Scientific Runtime Lab** that qualifies every operation through a common capability model.

The intended development lifecycle is:

```text
Discover environment
    ↓
Fingerprint toolchain and source
    ↓
Build or select runtime worker
    ↓
Run minimal probes
    ↓
Run scientific acceptance suite
    ↓
Run interoperability / contract tests
    ↓
Run performance and failure-mode qualification
    ↓
Save immutable evidence + artifacts
    ↓
Compare against pinned baseline
    ↓
Certify selected capabilities
    ↓
Publish a versioned capability manifest
    ↓
MATH3D consumes certified provider(s)
```

### 0.1. Main project outcomes

1. A **runtime-plugin framework** that prevents CGAL concepts and text leaking into VTK, Sage, Gmsh or Python views.
2. A common, **semantic capability registry**, independent of library-specific vocabulary.
3. Distinct plugins for **VTK and VTK-m**, with CPU/GPU device qualification for VTK-m.
4. **Immutable environment/source/build fingerprints** and per-run evidence.
5. A formal **L0–L9** maturity model, with distinct PASS/WARN/FAIL/STALE/BLOCKED/UNSUPPORTED status.
6. Cross-runtime and Math3D **differential, metamorphic and regression testing**.
7. A typed, versioned **scientific job and artifact contract** that Sage, CGAL, VTK, VTK-m and Gmsh can implement.
8. A **baseline, performance and repository comparison** laboratory, including scientific git bisect.
9. Reusable **pathological geometry and algebra fixture corpora**.
10. A gated **Promote to Math3D** workflow using verified, signed or hashed evidence/manifests rather than direct environment assumptions.

### 0.2. What remains where

| Concern | DevShell / Scientific Lab | Shared worker/broker layer | Math3D |
|---|---|---|---|
| Install or configure Sage, CGAL, VTK, compilers and CUDA | Owns | Reads resolved providers | Does not own |
| Repository / worktree management | Owns | Receives resolved source snapshot | No dependency |
| Build and probe a worker | Owns | Runs worker through adapter | Calls capabilities |
| Scientific acceptance tests / baselines | Owns | Executes test requests | Optional smoke test target |
| Worker protocol and job lifecycle | Tests and configures | Owns runtime execution protocol | Stable client |
| Capability definitions and schemas | Authors/qualifies | Advertises supported versions | Consumes |
| Native library implementation | Builds/tests | Encapsulates | Not linked into UI |
| `.m3dm`, geometry, mesh, graph and exact-math artifacts | Produces and validates | Transfers and validates | Imports, views, edits |
| User-facing geometry/math workflows | No | No | Owns |
| Interactive editing / visualization | Evidence previews only | No | Owns |

**Boundary rule:** DevShell is not a required dependency for MATH3D at runtime. Any necessary runtime configuration must be exportable to a standalone broker/worker configuration usable by desktop, server or CI deployments.

---

## 1. Observed baseline and near-term corrections

The screenshot review indicates a relatively mature CGAL qualification surface, a usable VTK profile, Sage/WSL probe capabilities, and additional Gmsh/Python profiles. Treat these as a **review snapshot**, not evidence of every operation functioning on every machine.

### 1.1. Existing assets to preserve

- Runtime selection, health and environment panels.
- Human-readable command recipes with inspectable command details.
- Test lists, individual test verdicts and saved execution results.
- Package discovery and integration screens.
- CGAL Boolean fixtures, expected rejection cases and `.m3dm` artifacts.
- Existing CGAL ↔ MATH3D numerical/native comparison and its recorded **35/35** result.
- Saved history and links between runs, logs, commands, tests and artifacts.
- Sage via WSL probes and Python environment management.

### 1.2. Immediate correctness fixes

**Issue A — Runtime-specific view leakage.** VTK integration UI appears to reuse CGAL/Boolean-specific labels or tests. Generic runtime screens should not claim inappropriate capabilities.

**Issue B — Placeholder descriptions.** Some Gmsh, Sage and Python views contain generic descriptions based on other scientific tools. Replace descriptions with plugin-provided capability declarations; display `Not configured` rather than presenting unrelated test controls.

**Issue C — Qualification is not the same as installation.** Clearly distinguish detected packages, a successful probe, a qualified scientific implementation and a fully certified MATH3D contract.

**Issue D — Evidence may not follow changes.** Toolchain, worker source, adapter and contract changes must invalidate relevant evidence, rather than preserve an unqualified green status.

**Issue E — Whole-runtime status is too coarse.** One CGAL operation may be L9 PASS while another is L5 PASS or UNTESTED. Promotion must be per capability and per provider/build fingerprint.

Acceptance criteria:

- Switching runtime never displays an unrelated runtime's test names, package metadata, artifact types or previous verdict as a current verdict.
- All runtime data has explicit `runtimeId`, `profileId`, `providerId` and source provenance.
- Unavailable functionality appears as `UNSUPPORTED`, `NOT_CONFIGURED` or `UNTESTED`, not `PASS` or generic `partial`.
- Existing CGAL 35/35 evidence stays intact and can be inspected as a historical run; it is not silently rewritten by the new model.

---

## 2. System architecture

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DevShell desktop UI                               │
│                                                                             │
│ Repositories │ Worktrees │ Profiles │ Environments │ Commands │ History     │
│ Scientific Runtime Matrix │ Qualification │ Comparison │ Benchmarks │ CI    │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                         DevShell application service
                                   │
             ┌─────────────────────┼──────────────────────────┐
             │                     │                          │
     Repository service      Runtime plugin registry     Evidence store
             │                     │                          │
     Source snapshots        Capabilities/recipes       Runs/artifacts/baselines
             │                     │                          │
             └─────────────────────┼──────────────────────────┘
                                   │
                       Scientific Runtime Broker
                                   │
             ┌──────────┬──────────┼────────────┬────────────┐
             │          │          │            │            │
         CGAL worker  VTK worker VTK-m worker Sage/WSL     Gmsh
             │          │          │            │            │
             └──────────┴──────────┼────────────┴────────────┘
                                   │
                  Typed results + scientific artifacts
                                   │
                       Contracts and qualification
                                   │
                  Versioned certified capability manifest
                                   │
                         MATH3D desktop / backend
```

### 2.1. Architectural packages (suggested; adjust to existing monorepo conventions)

```text
packages/
  scientific-contracts/
    src/jobs/
    src/capabilities/
    src/exact-math/
    src/geometry/
    src/artifacts/
    schemas/
  scientific-broker/
    src/registry/
    src/process/
    src/wsl/
    src/container/
    src/remote/
    src/security/
    src/telemetry/
  scientific-lab-core/
    src/profiles/
    src/fingerprints/
    src/qualification/
    src/evidence/
    src/baselines/
    src/benchmarks/
    src/fixtures/
    src/comparisons/
    src/repositories/
  scientific-runtime-plugins/
    cgal/
    vtk/
    vtkm/
    sage/
    gmsh/
    python/
apps/
  devshell/
  math3d/
scientific-fixtures/
  geometry/
  algebra/
  graphs/
  visualization/
  regression/
```

Avoid moving existing code prematurely: first introduce interfaces and adapters around the current CGAL path; migrate other profiles one at a time. The architecture must not require importing any scientific native SDK into Electron's renderer or linking heavyweight libraries into its app binary.

### 2.2. Runtime plugin model

```ts
interface ScientificRuntimePlugin {
  id: string;
  displayName: string;
  version: string;
  supportedBackends: ExecutionBackendKind[];
  environmentSchema: RuntimeEnvironmentSchema;
  discover(ctx: DiscoveryContext): Promise<RuntimeInstallation[]>;
  fingerprint(ctx: RuntimeContext): Promise<RuntimeFingerprint>;
  listProbes(ctx: RuntimeContext): ProbeDefinition[];
  listCapabilities(ctx: RuntimeContext): CapabilityProviderDefinition[];
  listRecipes(ctx: RuntimeContext): RecipeDefinition[];
  listSuites(ctx: RuntimeContext): QualificationSuite[];
  listBenchmarks(ctx: RuntimeContext): BenchmarkDefinition[];
  listArtifactViewers(): ArtifactViewerDescriptor[];
  listIntegrationTargets(): IntegrationTargetDescriptor[];
}
```

The plugin declares **what can be run and how it is interpreted**. The shared core controls process lifecycle, safety, persistence, timing, evidence, policy and UI presentation.

### 2.3. Stable identifiers

Use immutable, namespaced IDs:

```text
runtime.cgal
runtime.vtk
runtime.vtkm
runtime.sage
runtime.gmsh
runtime.python

provider.cgal.windows.native
provider.cgal.windows.python
provider.vtk.windows.python
provider.vtkm.cuda
provider.vtkm.tbb
provider.sage.wsl
provider.gmsh.windows.cli
```

Each operation must carry a capability ID and schema version, e.g. `mesh.boolean.union@1`.

---

## 3. Scientific Runtime Matrix dashboard

This is a top-level overview, complementing the existing detailed runtime selector.

Illustrative state, **not a claim about current installations**:

| Runtime | Windows native | WSL | Docker | Certified operations | Current issues |
|---|---|---|---|---|---|
| CGAL | Detected | — | Planned | Boolean subset | Expand mesh operations |
| VTK | Detected | Optional | Planned | Pending suites | Dedicated integration UI |
| VTK-m CPU | To probe | To probe | Optional | Pending | Device identification |
| VTK-m CUDA | To probe | To probe | Optional | Pending | CUDA/driver/build match |
| SageMath | — | Detected | Optional | Probe-level | Typed worker contract |
| Gmsh | To probe | Optional | Optional | Pending | Mesh pipelines |
| Python | Detected | Optional | Optional | Profile-level | Reproducibility |

Provide filters by machine, OS, repository snapshot, provider, execution backend, capability, qualification level and evidence freshness.

Recommended metrics:

- Runtime installations discovered versus usable.
- Capabilities at L3, L6, L9.
- Latest certified fingerprint and date.
- Passing, warning, failing, stale, blocked or unsupported capabilities.
- Correctness regressions and performance regressions.
- Backend/device coverage (Windows/WSL/container; CPU/GPU).

### 3.1. Distinguish four evidence classes

- **INVENTORY:** package/binary/source is present.
- **PROBE:** a minimal executable/API call was performed.
- **QUALIFIED:** a defined scientific test suite passed with the recorded conditions.
- **INTEGRATED:** a versioned MATH3D contract and import path passed.

Separate recency states: **LIVE**, **RECORDED**, **STALE**. Never infer that the currently installed environment matches the environment that produced a historical PASS without comparing fingerprints.

---

## 4. Runtime and environment lifecycle

### 4.1. Immutable runtime fingerprint

Every qualification run references a fingerprint containing:

- Runtime and provider versions.
- Native / WSL / Docker / remote backend identity.
- OS, architecture and OS/runtime build.
- CPU, GPU, driver and relevant accelerator backend.
- Python interpreter and environment identity (Conda/venv).
- Compiler, linker, CMake, Ninja/MSBuild, C++ standard and ABI-sensitive options.
- CUDA toolkit and accelerator versions when relevant.
- Package names, versions, builds and channels for explicitly used dependencies.
- Repository URL or local identity, branch, full commit hash and dirty state.
- For dirty worktrees: patch/content digest or declared untracked-input list.
- Worker binary hash, source hash and adapter hash.
- Worker contract and artifact-schema versions.
- Whitelisted environment variables affecting execution.
- Runtime profile definition and configuration hash.
- Fixture corpus and acceptance-suite revision.

Do not store credentials, access tokens, private environment variables or absolute personal paths in portable evidence. Keep local path mapping in a separate redacted/non-portable configuration section.

### 4.2. Profiles and execution backends

A profile binds a runtime installation to a runnable provider:

```text
ScientificProfile
  id
  runtimeId
  executionBackendId
  environmentId
  workerId
  repositoryBinding (optional)
  toolchainBinding
  resourceLimits
  expectedCapabilities
```

Backend implementations:

- Windows process with restricted argument-template execution.
- WSL distro command execution with explicit path translation.
- Docker/OCI image execution with pinned digest.
- Remote agent (future), authenticated and scoped.

### 4.3. Safety and process management

- Structured command + argument arrays; no untrusted shell string concatenation.
- Fixed working-directory and artifact-root policies.
- Time, CPU, RAM, GPU and disk usage budgets where enforceable.
- Cancellation terminates process trees, including WSL and container descendants where possible.
- Detect and report partial output, crashes, malformed results and resource exhaustion.
- Separate `stdout` as a data channel only where specified; use stderr or a dedicated channel for logs.
- Sanitize exported environment variables and redact secrets in logs/evidence.
- Block uncontrolled deletion or modification of repository files by default; destructive recipes require explicit authorization and a scoped workspace.

---

## 5. Formal L0–L9 qualification model

Each qualification entry is keyed by `(capability, provider, profile, build fingerprint, contract version, suite revision)` rather than by runtime name alone.

| Gate | Required evidence | Example |
|---|---|---|
| L0 — Inventory | Runtime/package discovery evidence | `sage` found inside chosen WSL distro |
| L1 — Executable | Invocation, exit code, version result | `sage --version` exits successfully |
| L2 — API/binding | A language/API call returns expected structured data | Python imports VTK and constructs a dataset |
| L3 — Scientific smoke | One positive operation and validated semantics | CGAL intersection of simple solids |
| L4 — SDK/build | Configure, compile, link and execute target (where applicable) | CMake builds CGAL worker; for interpreted runtimes record N/A with a justified substitute |
| L5 — Managed recipe | Run through broker/recipe with timeouts and provenance | `mesh.boolean.union` job succeeds |
| L6 — Artifact round trip | Save, validate, reload and compare output | `.m3dm` mesh round trip |
| L7 — Interoperability | Independent parser/consumer or cross-provider semantic verification | VTK-generated mesh consumed by Math3D importer |
| L8 — Performance/resilience | Defined benchmark and failure-mode gates | Cancellation, memory cap, repeated runs |
| L9 — Product integration | Versioned MATH3D contract, integration and regression suite | Worker produces valid scene artifact opened by MATH3D |

### 5.1. Gate states

`UNTESTED`, `RUNNING`, `PASS`, `WARN`, `FAIL`, `STALE`, `BLOCKED`, `UNSUPPORTED`, `NOT_APPLICABLE`.

**Important:** Gates may not all be meaningful for all implementations. A Sage interpreted worker should not be forced to compile native C++; it should carry a documented `NOT_APPLICABLE` rationale and an alternate environment reproducibility test. A capability is L9 only when its **applicable** prerequisites and defined integration suite pass; skipping a required test cannot produce a PASS.

### 5.2. Evidence invalidation

- Library version change → invalidate affected provider qualification.
- Worker binary or adapter change → invalidate relevant managed recipe and integration tests.
- Artifact schema change → invalidate artifact round trips and consumer integration.
- Compiler/ABI-sensitive dependency change → invalidate native builds and downstream qualification.
- Fixture or tolerance revision → invalidate tests depending on that suite.
- MATH3D client contract version change → invalidate only affected L9 integrations.

Present exact reasons and an **affected-capabilities requalify** action.

---

## 6. Semantic capability registry

Organize what MATH3D can **do**, not merely which library can be invoked.

### 6.1. Geometry and mesh families

```text
mesh.read                 mesh.write
mesh.validate             mesh.repair
mesh.orient               mesh.self-intersections
mesh.boolean.union        mesh.boolean.intersection
mesh.boolean.difference   mesh.remesh.isotropic
mesh.simplify             mesh.subdivide
mesh.normals              mesh.curvature
mesh.components           mesh.hole-fill
mesh.surface-area         mesh.volume
mesh.aabb                 mesh.ray-intersection
mesh.distance             mesh.hausdorff
mesh.generate.surface     mesh.generate.volume
geometry.convex-hull      geometry.intersection
geometry.distance         geometry.triangulate
```

### 6.2. Visualization and field analysis

```text
field.gradient            field.divergence
field.statistics          field.resample
field.contour             field.clip
field.threshold           field.streamline
visualization.offscreen   visualization.volume-render
```

### 6.3. Algebra, number theory, analysis and graphs

```text
math.symbolic.simplify    math.symbolic.solve
math.polynomial.factor    math.groebner-basis
math.matrix.exact         math.matrix.canonical-form
math.number-theory.factor
math.number-theory.primality
math.number-theory.number-field
math.number-theory.prime-decomposition
math.number-theory.class-group
math.number-theory.units
math.number-theory.galois
math.analysis.derivative  math.analysis.integral
math.analysis.series      math.analysis.ode
graph.invariants          graph.connectivity
graph.coloring            graph.spectrum
```

### 6.4. Provider declarations

```text
mesh.boolean.union
  - CGAL/native
  - CGAL/Python (only if actual binding supports the operation)

mesh.normals
  - CGAL/native
  - VTK/Python
  - VTK-m/CPU
  - VTK-m/CUDA (where available)

field.contour
  - VTK/Python
  - VTK-m/CPU
  - VTK-m/CUDA

math.number-theory.factor
  - Sage/WSL
```

Do not infer provider support from a package name. A provider appears as **available** only after discovery and a declared capability probe; it appears as **certified** only after the required gates pass.

### 6.5. Provider selection policy

Initially use explicit provider selection for qualification. Later support broker policies:

- User-selected provider.
- Certified first.
- CPU fallback when GPU unavailable.
- Memory-budget-aware selection.
- Preferred backend based on measured benchmark, with reproducibility and correctness gates.

Record the **actual provider selected**, not just requested preference, in every result. Do not silently switch an intended CUDA job to CPU while reporting a CUDA success.

---

## 7. Shared scientific job and artifact contract

### 7.1. Job request envelope

```json
{
  "contract": "math3d.scientific.job/v1",
  "jobId": "job-001",
  "capability": "mesh.boolean.union@1",
  "requestedProvider": "provider.cgal.windows.native",
  "inputs": [
    {"artifactId": "mesh-a", "mediaType": "application/vnd.math3d.mesh+json"},
    {"artifactId": "mesh-b", "mediaType": "application/vnd.math3d.mesh+json"}
  ],
  "parameters": {},
  "resources": {"timeoutSeconds": 120, "maxMemoryMiB": 4096}
}
```

### 7.2. Job result envelope

```json
{
  "contract": "math3d.scientific.result/v1",
  "jobId": "job-001",
  "status": "success",
  "actualProvider": "provider.cgal.windows.native",
  "fingerprintId": "sha256:...",
  "outputs": [
    {"artifactId": "result-mesh", "mediaType": "application/vnd.math3d.mesh+json"}
  ],
  "metrics": {"wallTimeMs": 80},
  "diagnostics": []
}
```

Define standard statuses such as `success`, `invalid-input`, `unsupported`, `cancelled`, `timeout`, `resource-exhausted`, `worker-error`, `contract-error`. Capture progress, heartbeat, cancellation acknowledgement and artifact provenance. Store large binary artifacts separately from JSON result envelopes, with content hashes and typed media descriptors.

### 7.3. Versioning rules

- Version job, result, capability-parameter and artifact schemas separately.
- Include advertised supported versions in worker handshake.
- Fail explicitly on unsupported major versions; do not silently coerce.
- Maintain compatibility adapters for planned migrations and test both current and previous supported versions.
- Validate all inputs and outputs against schema and semantic validators.

---

## 8. Runtime plugin: CGAL

### 8.1. Preserve the strong existing base

Keep Boolean positive and negative cases, capability-specific verdicts, `.m3dm` artifacts, numeric tolerances and the recorded 35/35 Math3D-native comparison. Re-express them through the common plugin and evidence contracts without changing scientific semantics.

### 8.2. Planned CGAL qualification families

1. Mesh validation: closedness, manifoldness, triangle validity, connected components.
2. Orientation: outward/inward, component orientation, consistent face orientation.
3. Repair: duplicate cleanup, stitching, non-manifold detection/handling.
4. Self-intersection diagnosis with robust test fixtures.
5. Isotropic remeshing with edge-length and quality checks.
6. Edge-collapse simplification with error bounds and topology checks.
7. Subdivision and vertex/face count expectations.
8. AABB trees and spatial queries.
9. Point-to-mesh / mesh-to-mesh distance.
10. Ray-triangle and ray-mesh intersections.
11. Discrete curvature estimates, with documented conventions and limitations.
12. Component extraction and hole filling.
13. Convex hull and degeneracy handling.
14. Surface mesh generation where supported by selected CGAL packages.
15. Tetrahedral/volume meshing with domain validity and element-quality metrics.
16. Boolean operations under near-coplanar, tangent, touching and sliver configurations.

### 8.3. Core metrics

`inputVertices`, `inputFaces`, `outputVertices`, `outputFaces`, `closed`, `manifold`, `components`, `boundaryEdges`, `selfIntersections`, `surfaceArea`, `signedVolume`, `absoluteVolume`, `bbox`, `minEdgeLength`, `minTriangleArea`, `quality`, `hausdorffEstimate`, `timeMs`, `peakMemoryMiB`.

### 8.4. Acceptance examples

- Union of disjoint solids preserves combined volume within scale-aware tolerance.
- `A − A` yields empty output according to explicit empty-mesh contract.
- Expected-invalid inputs produce a typed rejection and never false success.
- Remeshing preserves surface geometry to bounded distance and records topology changes.
- Repair operations enumerate what changed; no silent modification of input artifacts.

---

## 9. Runtime plugin: VTK

**Do not make VTK a second CGAL screen.** Its identity is pipelines, readers/writers, geometric filters, data arrays and visualization.

### 9.1. VTK pipeline model

```text
Read → Inspect → Transform → Filter → Analyze → Render → Export
```

### 9.2. Recipes and suites

- `vtkPolyData` and `vtkUnstructuredGrid` loading and round trips.
- File format readers/writers and mixed array type preservation.
- Triangle filter; cleaning and duplicate point removal.
- Normals; curvature; mass properties.
- Connectivity and component extraction.
- Decimation; smoothing; feature preservation.
- Clip, slice, threshold and contour.
- Image/field resampling and probing.
- Streamlines and vector field handling.
- Offscreen rendering, camera, lighting and background fixtures.
- Pipeline error reporting and invalid input cases.

### 9.3. Visual regression tests

Save a reference image, current image and difference image. Compare with a robust metric such as mean absolute difference, changed-pixel ratio and structural similarity, after controlling image size, camera, projection, fonts and rendering backend. Expect GPU/driver/platform variation; never require exact PNG hashes for general render correctness. Keep geometry/data-array assertions separate from pixel assertions.

### 9.4. VTK-specific qualification

- Validate point/cell counts, topology, bounds, array names, array types, value ranges and missing-data semantics.
- Verify field associations (point data vs cell data).
- Test deterministic pipeline behavior where reasonable.
- Validate `.m3dm` and other exported artifacts with an independent consumer.

---

## 10. Runtime plugin: VTK-m (distinct from VTK)

VTK-m must be independently discoverable and qualified. Do not treat a working Python `vtk` import as proof that VTK-m device execution works.

### 10.1. Backend/device profiles

Potential targets depending on the installed VTK-m version and build configuration:

- Serial CPU.
- TBB CPU.
- CUDA GPU.
- Other explicitly supported device adapters/builds, if verified.

Because VTK-m device support, component naming and integration options may vary by version, obtain the **actual compiled backend list** from introspection/probes and record it in the fingerprint; do not hardcode GPU availability.

### 10.2. Target operations

- Contour/isosurface.
- Clip and threshold.
- Normals and gradients.
- Connected components/field transformations where supported.
- Statistics and resampling.
- Streamline/particle advection where available.

### 10.3. CPU/GPU differential tests

For common inputs, compare:

- Dataset structure and point/cell counts.
- Field values within declared float tolerances.
- Topology and mesh output after canonicalization where meaningful.
- Execution time (warm/cold).
- Host/device transfer time where instrumentable.
- GPU time, peak VRAM and fallback diagnostics.

**Hard requirement:** every GPU verdict records actual device/backend execution. A CUDA-requested job that falls back to CPU must be reported separately and cannot certify CUDA performance.

### 10.4. Scalability

Use controlled dataset sizes from small to stress; inspect scaling, memory pressure, device OOM behavior and cancellation. Require correctness before speed claims.

---

## 11. Runtime plugin: SageMath / WSL

Current Sage/WSL probes provide a useful foundation. The next milestone is a **typed scientific service**, not merely shell execution.

### 11.1. Worker lifecycle

```text
DevShell profile → WSL distro / Sage env → Sage worker
                                      ↓
                            handshake + health
                                      ↓
                             typed job request
                                      ↓
                               typed result
                                      ↓
                           evidence + artifacts
```

Prefer a persistent bounded worker for repeated jobs, with an isolated process mode for untrusted or expensive computation. Maintain timeout and cancellation coverage for both. Do not use `eval` on arbitrary user strings in a privileged long-lived Sage interpreter without a trusted execution model and explicit policy.

### 11.2. Typed exact-value serialization

Support at minimum:

- Arbitrary-precision integers as decimal strings.
- Rational numbers as numerator/denominator strings.
- Algebraic numbers and explicit parent ring/field metadata.
- Real and complex numbers with precision and rounding/error metadata.
- Univariate/multivariate polynomials with explicit coefficient ring and monomial encoding.
- Polynomial factorization with factors and multiplicities.
- Matrices/vectors with element domain and dimensions.
- Finite fields, number fields, ideals and embeddings where relevant.
- Permutations/groups using finite, explicit representations or stable references.
- Graphs with labeled vertices, edges and attributes.
- Symbolic expressions in a restricted AST schema, not only a printed text string.

Example:

```json
{
  "type": "rational",
  "numerator": "355",
  "denominator": "113"
}
```

For nontrivial algebraic structures, avoid inventing a universal flat JSON representation: define a versioned schema per mathematical domain, preserving the parent structure and coercion/embedding context.

### 11.3. Sage qualification suites

**Algebra:** polynomial factorization, Gröbner bases, ideals, quotient rings, exact matrix operations, canonical forms, minimal/characteristic polynomial.

**Number theory:** integer factorization, primality, modular arithmetic, finite fields, quadratic fields, number fields, integral bases, rings of integers, prime decomposition, ramification indices/inertia degrees, class groups, units, explicit Galois groups for tractable examples.

**Analysis:** symbolic derivatives, simplification, integrals, limits, series and ODE examples where support is verified.

**Graph theory:** graph construction, connectivity, invariants, colorings and spectra.

### 11.4. Exactness and proof obligations

- Verify algebraic identity by exact substitution or independent methods where feasible.
- Record parent rings and embeddings in results.
- For number field splitting, assert consistency such as `sum(e_i * f_i) = [K:Q]` for appropriately qualified examples, with careful treatment of the stated setting.
- Distinguish proven results, computations relying on algorithms, heuristic/conditional outputs and unknown outcomes.
- Do not claim a printed symbolic expression is the unique canonical form.

### 11.5. MATH3D handoff

Exact mathematical results should be available to Number Theory, Algebra, Graph and Workbook/Notes modules through typed documents. Surface/curve-generation results may also produce sampled geometry, but retain the exact mathematical source separately.

---

## 12. Runtime plugin: Gmsh

Move from generic profile/probe to a real geometry-to-mesh pipeline.

### 12.1. Recipes

- `.geo` → 1D mesh.
- `.geo` → 2D triangle or mixed surface mesh.
- `.geo`/CAD → 3D tetrahedral mesh.
- STEP/BREP import and meshing where supported by the selected build.
- Physical group and boundary tag preservation.
- Mesh-size fields and local refinement.
- Surface mesh repair/remeshing flows where available.
- Quality diagnostics and element-family inspection.

### 12.2. Evidence and validation

- Node/element counts and element type distribution.
- Geometric/physical groups and tags.
- Bounds, surface area and volume where computable.
- Inverted or degenerate elements.
- Element-quality distributions (with metric definitions).
- Size-field/refinement effect.
- Stable reader/exporter compatibility, especially `.msh` variants.

### 12.3. Integration route

```text
CAD/STEP/BREP/.geo
      ↓
    Gmsh
      ↓
  .msh + tags
      ↓
typed mesh converter
      ↓
MATH3D volume-mesh document / .m3dm artifact
      ↓
MATH3D viewer and analysis
```

Do not discard boundary tags, element types or volume connectivity when converting to surface-only display geometry; a distinct volume-mesh representation is preferable to pretending all meshes are triangle surfaces.

---

## 13. Python environment provider

Python is both a standalone runtime and an execution substrate for Sage/VTK/Gmsh adapters. Keep separate identities for:

- Interpreter/package environment.
- Scientific capability provider that uses the interpreter.
- Notebook/Jupyter kernel.
- Python worker process.

### 13.1. Qualification

- Interpreter version and architecture.
- Conda/venv identity and package lock evidence.
- Import and ABI checks for compiled wheels.
- Script/module execution.
- Jupyter kernel handshake where configured.
- Reproducible package solve/install from locked inputs in a disposable environment.
- Out-of-process sandbox/resource testing.

### 13.2. Dependency risk detection

Warn on Python version changes, inconsistent NumPy/SciPy/VTK/QuTiP ABI combinations, conflicting environment activation and unexpected PATH resolution. Record the exact interpreter path locally, but redact user-specific path roots in portable exports.

---

## 14. Scientific fixture corpus

```text
scientific-fixtures/
  geometry/
    canonical/
    pathological/
    generated/
    real-world/
  algebra/
    exact/
    number-fields/
    symbolic/
  graphs/
  visualization/
  regression/
    M3D-1842/
```

### 14.1. Canonical geometry

Cube, sphere, torus, tetrahedron, cylinder, icosphere, overlapping spheres/cubes, disjoint solids and tangent-contact cases.

### 14.2. Pathological geometry

- Nonmanifold edges/vertices.
- Duplicate and reversed faces.
- Self-intersections.
- Tiny or zero-area triangles.
- Near-coplanar and tangent intersections.
- Open boundaries/holes.
- Disconnected components.
- Thin slivers and needle triangles.
- Isolated vertices.
- Extremely large and small coordinate scales.
- Adversarial surface orientation.

### 14.3. Real-world meshes

Stanford Bunny, Armadillo, Dragon, 3DBenchy and CAD exports when licensing, origin and file distribution rights are clear. Avoid bundling assets without checking redistribution permissions; use downloadable fixture manifests as appropriate.

### 14.4. Fixture metadata

Every fixture declares source, license, units, coordinate system, topology expectations, valid intended operations, expected failure classes, tolerances, hashes and fixture revision. Generated fixtures additionally record PRNG seed and generator version.

### 14.5. Regression capture

Every meaningful scientific defect should be convertible into a small reproducible fixture plus expected verdict. Regression fixtures must be reviewed for data privacy and retained against future releases.

---

## 15. Differential, property-based and metamorphic testing

### 15.1. Cross-runtime comparison

Run semantically equivalent capabilities via multiple providers, e.g. CGAL vs VTK for normals, bounds, area or connectivity; VTK CPU vs VTK-m CPU/CUDA for field operations; Sage vs independent small-case reference computations where feasible.

Comparison can include:

- Counts, bounds, area and volume.
- Topological invariants and component counts.
- Approximate point-to-surface distance / Hausdorff estimates.
- Field-array values and precision.
- Equality modulo element order, orientation or mesh representation.
- Timing, memory and artifact size.

**Avoid false comparisons:** different algorithms may produce distinct but equally valid triangulations. Do not require identical vertices/faces if geometric or field equivalence is the meaningful invariant.

### 15.2. Boolean invariants

```text
A ∪ A ≈ A
A ∩ A ≈ A
A − A = ∅
A ∪ B ≈ B ∪ A
A ∩ B ≈ B ∩ A
V(A ∪ B) ≈ V(A) + V(B) − V(A ∩ B)
```

State hypotheses: compatible closed solid inputs, well-defined regularized solid operations, valid volume and appropriate numerical tolerances. Nonmanifold/open inputs may instead have an **expected rejection**.

### 15.3. Transform and scale invariants

- Translating a mesh should preserve volume, area and topology.
- Rigid rotation should preserve distance and measure.
- Scaling by factor `s` changes lengths by `|s|`, areas by `s²`, volumes by `|s|³`.
- Repeat under `s = 0.001`, `1`, `1000` to detect conditioning problems.

### 15.4. Property-based generation and shrinking

Generate cases with fixed seeds and bounded input complexity. When a case fails, automatically minimize/shrink the counterexample where scientifically safe. Save the minimized case and seed as a regression fixture.

### 15.5. Numerical tolerance policy

Each assertion declares absolute/relative/scale-aware tolerance and rationale. Avoid blanket `1e-6` for all mesh scales, data types and algorithms. Record whether the result is exact, floating point, heuristic or approximate.

---

## 16. Evidence store, immutable history and export

### 16.1. Run record

Each run stores:

```text
runId
recipeId / testSuiteId
capabilityId + version
provider + profile
runtime fingerprint
repository snapshot
start/end timestamps
result status
exit code / error code
stdout/stderr refs
input and output artifact hashes
metrics and diagnostics
app/worker/contract versions
suite revision and tolerances
```

### 16.2. Evidence bundle export

```text
scientific-evidence.zip
  manifest.json
  fingerprint.json
  request.json
  result.json
  stdout.log
  stderr.log
  diagnostics.json
  timings.json
  packages.json
  tests.json
  provenance.json
  input/
  output/
  previews/
```

Integrity: SHA-256 each included file and produce a manifest of hashes. Store original results as immutable records; derived annotations or later adjudications should be appended and linked, not overwrite original facts. Bundle import verifies the hashes and schema versions before displaying a recorded verdict.

### 16.3. Privacy and portability

Redact secrets, local usernames, private repository URLs if needed, personal paths and unrelated environment variables. Offer strict `portable`, `internal`, and `full-local` export policies. Never export private source files automatically unless a user has selected that evidence scope.

### 16.4. Run comparison

Provide first-class comparisons:

- Run vs run.
- Commit vs commit.
- Runtime version vs runtime version.
- CPU vs GPU.
- Windows vs WSL vs Docker.
- Local vs CI.
- Provider vs provider.

Diff correctness, scientific metrics, environment changes, package/toolchain changes, wall time, peak RAM/VRAM, output artifact summaries and visual outputs.

---

## 17. Baselines, regressions and selective requalification

### 17.1. Baseline types

- Local working baseline.
- Project/team baseline.
- Release qualification baseline.
- CI-published baseline.

Release baselines must be immutable and identified by full fingerprint and evidence bundle digest.

### 17.2. Difference verdicts

`UNCHANGED`, `IMPROVED`, `PERFORMANCE_REGRESSION`, `CORRECTNESS_REGRESSION`, `INCOMPARABLE`, `STALE_BASELINE`, `MISSING_EVIDENCE`.

Do not compare timing from inconsistent CPU/GPU, thermal, concurrency or host configurations as if it were a controlled regression. Display comparability warnings.

### 17.3. Dependency graph

```text
CGAL worker code change
  ├── mesh.validate
  ├── mesh.boolean.*
  └── mesh.remesh.*

.m3dm serializer change
  ├── CGAL → MATH3D round trips
  ├── VTK → MATH3D round trips
  └── Gmsh → MATH3D round trips
```

Generate an **affected suite set** from a versioned dependency graph. Conservative invalidation is preferable to falsely preserving certifications.

---

## 18. Benchmark laboratory

### 18.1. Measurements

- Cold and warm wall time.
- CPU time and CPU utilization.
- Peak resident memory.
- GPU execution time where measurable.
- GPU memory and host↔device transfer time where measurable.
- Input/output bytes and object sizes.
- Throughput (e.g. triangles/s, elements/s, field samples/s).
- Iteration count and numerical convergence metrics.
- Host, load, power/thermal context if available.

### 18.2. Data sizes

Use configurable `tiny`, `small`, `medium`, `large`, `stress` tiers, e.g. 10k, 100k, 1M, 10M triangles **where the provider and host can safely handle them**. Provide explicit resource budgets and skip-with-reason rather than crashing or exhausting the development machine.

### 18.3. Benchmark hygiene

- Warm-up policy stated.
- Repeated measurements with median and dispersion.
- Input data cached or generated under documented policy.
- Same contract versions and comparable environment for regressions.
- Outliers retained as evidence; do not silently delete them.
- Correctness verification required before presenting speedups as improvements.

---

## 19. Failure, cancellation and concurrency qualification

### 19.1. Failure modes

- User cancellation.
- Worker timeout.
- Worker crash and process exit.
- Invalid input.
- Invalid JSON or artifact schema.
- Data channel polluted by logs.
- Partial writes or corrupt artifact.
- Memory budget exceeded.
- Disk full / artifact storage failure (simulated).
- Missing runtime/package at execution time.
- CUDA OOM, driver mismatch or unavailable backend.
- Worker restart and broker recovery.

### 19.2. Process cleanup assertions

After cancellation: no orphan process tree, no live locked temporary artifacts and no successful final status for an incomplete job. Any retained partial artifact must have an explicit incomplete marker.

### 19.3. Concurrency suites

Test 1, 2, 4 and 8 simultaneous jobs when machine limits permit. Validate isolation, deterministic artifact IDs, shared-library thread safety, memory pressure, WSL/container process tracking, and GPU-device scheduling. Report throughput and tail latency separately from single-job runtime.

---

## 20. Repository and worktree integration

Bind scientific runs to source snapshots rather than a mutable repository path alone.

### 20.1. Repository-qualified execution

```text
Repository: Math3D
Worktree: scientific-mesh
Commit: <full SHA>
Dirty digest: <optional patch hash>
Runtime profile: CGAL native
Suite: integration.math3d.mesh-boolean
```

### 20.2. Compare two commits

Run identical suites and comparable profiles on two commits. Display capability correctness, numerical diffs, ABI/build differences and performance measurements.

### 20.3. Scientific git bisect

Given known-good and known-bad commits:

1. Create or use an isolated worktree.
2. Build selected worker or app integration target.
3. Execute deterministic qualification recipe.
4. Classify `good`, `bad` or `skip` for build/infrastructure failures.
5. Record each examined commit and its evidence.
6. Report candidate first-bad commit with a reproducible replay command.

Require a clean, dedicated worktree and disallow implicit destructive changes to the user's active repository.

### 20.4. Useful UI addition: Repository + Runtime workspace

Display repository/branch/commit, bound profiles, tests, regressions, recent evidence, worker builds and published capability manifests on one screen.

---

## 21. Math3D integration and promotion

### 21.1. Broker boundary

```text
Math3D client
     ↓
ScientificJob (typed)
     ↓
Scientific Runtime Broker
     ├── CGAL native
     ├── VTK Python
     ├── VTK-m CPU/CUDA
     ├── Sage WSL
     └── Gmsh
     ↓
Typed output + artifact metadata
     ↓
Math3D document import/view
```

MATH3D should not embed `C:\...\conda\...`, WSL distro names or DevShell repository paths in its domain documents. Deployment-specific profiles belong to broker configuration.

### 21.2. Promotion gate

`Promote capability` becomes enabled only when required qualification gates pass on the selected fingerprint and contract versions. Promotion exports a manifest entry:

```json
{
  "capability": "mesh.boolean.union@1",
  "provider": "provider.cgal.windows.native",
  "workerContract": "math3d.scientific.job/v1",
  "status": "certified",
  "fingerprintDigest": "sha256:...",
  "evidenceBundleDigest": "sha256:...",
  "certifiedAt": "2026-11-03T00:00:00Z"
}
```

The timestamp above is an illustrative schema value, not a real certification event. A real promotion should use the actual time and verified evidence.

### 21.3. End-to-end UI smoke

- Worker executes input fixture.
- Broker validates output.
- Artifact round trip passes.
- Math3D creates/imports a document.
- Viewer loads expected scene or data.
- Numerical properties and key UI status are verified.

A small smoke suite can use automated Electron tests or an independent document-import harness. Heavy graphics render tests should be a separate, controlled CI lane.

### 21.4. Preserve Math3D modularity

The main app remains a consumer. DevShell's plugin UI, test suites and benchmark database need not ship with MATH3D. Keep worker deployment optional and capability-driven, including graceful reporting when a provider is unavailable.

---

## 22. Future scientific pipeline builder

Add only **after** worker contracts, capability registry, artifact schemas and qualification semantics are stable.

### 22.1. Geometry pipeline

```text
Import STEP
   ↓
Gmsh tetrahedralize
   ↓
VTK inspect
   ↓
VTK-m compute field
   ↓
CGAL validate extracted surface
   ↓
.m3dm / typed artifact exporter
   ↓
Open in MATH3D
```

Note that volume/surface conversions must be explicit and loss-aware.

### 22.2. Algebra-to-geometry pipeline

```text
Sage generate exact curve or surface definition
   ↓
Python/Sage numeric sample with precision policy
   ↓
CGAL triangulate/validate
   ↓
VTK normals/field generation
   ↓
Math3D geometry + exact source document
```

### 22.3. Pipeline guarantees

- DAG typed ports and artifact type checking.
- Per-node capability/provider/version provenance.
- Cached deterministic outputs keyed by input/parameter/fingerprint hash.
- Cancellation and retries.
- Human-readable errors when type conversion loses exactness, dimensionality, topology or metadata.
- Replay from manifest and pipeline revision.

---

## 23. Remote agents and CI (later)

### 23.1. Remote execution

Remote Windows, Linux and GPU agents can expose the same broker protocol. Require authenticated transport, scoped execution permissions, artifact integrity verification and explicit machine identities. Show remote runs independently from local evidence.

### 23.2. CI matrix

Possible lanes:

- Fast PR smoke.
- Native CGAL/VTK builds and contract suites.
- Sage WSL/Linux suites.
- Gmsh conversion and volume-mesh suites.
- GPU VTK-m lane on an actual supported accelerator.
- Nightly pathological/large-fixture tests.
- Release L9 certification.

CI imports evidence bundles into the DevShell History screen. The release pipeline should never assert a GPU qualification from a CPU-only runner.

---

## 24. UI / UX improvements by screen

### 24.1. Runtime overview

Runtime matrix, status, profiles, last current PASS, stale evidence reasons, candidate requalification tasks.

### 24.2. Health

Group findings into `Discovered`, `Callable`, `Bindings`, `Worker`, `Integration`, and `Certification`. Attach evidence links to each claim.

### 24.3. Environment

Fingerprint comparison, toolchain resolver graph, package version provenance, PATH precedence, WSL distribution mapping, compiler and CUDA checks.

### 24.4. Commands

Filter recipes by purpose and scope. Show parsed command arguments, side effects, worktree target, expected artifacts, resource budget and replay command. Dry-run mode for destructive or repository-mutating actions.

### 24.5. Tests

Group by capability and gate, with positive/negative/timeout/cancellation/property/metamorphic categories. Allow targeted re-run, run suite and affected-only re-run.

### 24.6. Packages

Installation inventory + dependency/ABI warnings + lockfile and reproducibility status. Avoid equating package presence with capability support.

### 24.7. Integration

Render plugin-specific contracts and handoffs; no VTK page showing CGAL Boolean results. Display worker protocol version and current MATH3D consumer version explicitly.

### 24.8. History

Save and filter run evidence, attach baselines, compare two runs, inspect numeric/visual diffs, export/import evidence and view regression lineage.

### 24.9. Benchmarks

Graphs over time, comparable cohort selection, controlled hardware tags, cold/warm distributions and memory telemetry. Flag inconclusive comparisons.

### 24.10. Advanced features

Repository+Runtime dashboard, capability provider chooser, scientific pipeline editor and CI certification viewer only once foundational contracts are stable.

---

## 25. Delivery phases and dependencies

### Phase P0 — Correct architecture and reliable evidence

**Goal:** Make existing CGAL/VTK/Sage/Gmsh/Python surfaces truthful, modular and reproducible.

**Deliverables:** runtime plugin interface, corrected pages, fingerprint IDs, evidence schemas, L0–L9 statuses, capability registry, worker contract versions, baseline and comparison primitives.

**Exit gate:** existing CGAL 35/35 evidence imports without mutation; runtime panels do not leak data; a fresh CGAL suite produces traceable, fingerprinted evidence; stale fingerprints are clearly detected.

### Phase P1A — Scientific provider expansion

**Goal:** Meaningful dedicated suites rather than generic smoke checks.

**Deliverables:** VTK pipelines, VTK-m CPU/CUDA discovery and tests, Gmsh volume-mesh flow, Sage typed worker, expanded CGAL repair/remesh/query suites, pathology corpus.

**Exit gate:** each provider declares only tested capabilities, returns typed errors and artifacts, and has at least one representative end-to-end scenario.

### Phase P1B — Product integration

**Goal:** Certified functionality can be safely consumed by Math3D.

**Deliverables:** broker, versioned manifests, promotion workflow, `.m3dm`/typed document round trips, Math3D smoke suite.

**Exit gate:** one capability each from CGAL and Sage plus one mesh/field path from VTK or Gmsh runs through the broker and validates in the intended Math3D module. Extend the set as providers become ready.

### Phase P2 — Scientific development laboratory

**Goal:** Regression detection and controlled comparative development.

**Deliverables:** benchmark baselines, resource telemetry, failure/concurrency tests, repository snapshots, commit comparison, scientific bisect, differential tests, selective retesting.

**Exit gate:** a deliberate scientific regression is detected, attributed and replayable with evidence; performance regression warnings require comparable test conditions.

### Phase P3 — Orchestration and scale

**Goal:** Workflows composed of certified capabilities, CI and remote agents.

**Deliverables:** DAG pipeline builder, remote execution, CI evidence exchange, release certification and regression corpus promotion.

**Exit gate:** a multi-provider pipeline replays with complete provenance, clear failures, schema-safe handoffs and preserved source artifacts.

### 25.1. Dependency chain

```text
Plugin contracts + run evidence + fingerprints
              ↓
Capability schemas + L0–L9 semantics
              ↓
Broker protocol + artifact schema
              ↓
Provider-specific acceptance suites
              ↓
MATH3D qualification + promotion
              ↓
Cross-runtime comparison + benchmarks
              ↓
Pipelines, remote agents and release certification
```

**Parallelizable work:** fixture corpus, VTK-specific tests, CGAL expansions and Sage exact-type schema prototyping can begin once the minimum common interfaces are agreed.

---

## 26. Commit-by-commit implementation plan

Each commit title is a suggested atomic scope; split large work further when needed. Every commit should include or update tests and documentation, and avoid claiming certification from a smoke-only implementation.

### P0 — Architecture, correctness, reproducibility

**DS-SCI-001 — `feat(scientific): introduce runtime-plugin contract`**\
Implement plugin identity, supported backends, environment schema, probes, capabilities, recipes, suites and viewers. Wrap existing CGAL behavior with a compatibility adapter.\
**Acceptance:** CGAL profile behaves as before; registry unit tests cover unknown/missing plugins and duplicate IDs.

**DS-SCI-002 — `refactor(scientific): remove runtime view leakage`**\
Replace hardcoded CGAL/VTK/Sage/Gmsh descriptions and integration widgets with plugin-supplied content.\
**Acceptance:** cross-runtime navigation never displays a different runtime's current verdict or suite.

**DS-SCI-003 — `feat(scientific): add immutable runtime fingerprints`**\
Capture toolchain, packages, backend, repo, source/worker hashes and policy versions.\
**Acceptance:** repeated identical discovery yields stable digest after canonicalization; critical changes create a new digest.

**DS-SCI-004 — `feat(scientific): formalize L0-L9 qualification states`**\
Model gate state, applicable prerequisites, evidence links and reasons.\
**Acceptance:** PASS, WARN, FAIL, STALE, BLOCKED, UNSUPPORTED and N/A display correctly; inapplicable checks cannot silently bypass required gates.

**DS-SCI-005 — `feat(scientific): introduce semantic capability registry`**\
Define versioned capability IDs, parameter/output schemas, providers and capability discovery.\
**Acceptance:** one capability can have multiple providers without losing provider-specific limitations.

**2026-11-04 scoped delivery:** `schemas/scientific-capabilities.v1.json` is the shared catalog. React uses it for provider declarations and acceptance-row limits; the desktop and standalone broker embed the same file. Desktop `capabilities` discovery returns the version, scoped providers, limitations and parameter/result schema objects. CGAL and VTK share `mesh.read` with distinct limits. This is declaration and discovery only; saved run evidence still determines qualification and certification. Worker request validation and version negotiation remain DS-SCI-007.

**DS-SCI-006 — `feat(scientific): invalidate stale qualification evidence`**\
Build fingerprint and dependency-based staleness calculations and a requalify action.\
**Acceptance:** worker or contract changes mark the appropriate historical certificate as stale without altering its original run.

**DS-SCI-007 — `feat(scientific): version worker and artifact contracts`**\
Add schema validation, version negotiation and typed errors.\
**Acceptance:** unsupported major versions fail clearly; tests reject malformed artifacts.

**DS-SCI-008 — `feat(history): compare scientific runs`**\
Add environment, correctness, metrics and artifact comparison with comparability warnings.\
**Acceptance:** differences are grounded in recorded inputs and fingerprints, not current machine state.

**DS-SCI-009 — `feat(history): pin certification baselines`**\
Create local/project/release/CI baselines with immutable release records.\
**Acceptance:** release baseline cannot be overwritten; subsequent runs compare to pinned evidence.

**DS-SCI-010 — `feat(evidence): export verifiable evidence bundles`**\
Manifest, logs, metrics, hashes, input/output selection and redaction policies.\
**Acceptance:** export/import verifies file hashes; private paths and secrets are excluded in portable mode.

### P1 — Scientific provider coverage

**DS-SCI-011 — `feat(vtk): add dedicated VTK qualification suites`**\
Build VTK-specific data pipeline fixtures and checks for readers, filters, topology and arrays.\
**Acceptance:** VTK Integration no longer inherits Boolean wording; at least one real VTK L7 handoff is validated.

**DS-SCI-012 — `feat(vtk): add offscreen visual-regression tests`**\
Reference renders, difference images, tolerant metrics and backend metadata.\
**Acceptance:** changed camera/geometry is detected; benign backend variations can be separately classified.

**DS-SCI-013 — `feat(vtkm): introduce independent VTK-m plugin`**\
Discover actual builds, device adapters, CLI/worker entry points and capability versions.\
**Acceptance:** VTK-m can be absent or unsupported without affecting VTK profile health.

**DS-SCI-014 — `feat(vtkm): qualify CPU and CUDA operations`**\
Execute supported operations on actual devices, compare numeric output and record fallbacks.\
**Acceptance:** CUDA certification requires recorded GPU execution; CPU fallback is not misreported.

**DS-SCI-015 — `feat(gmsh): qualify geometry-to-volume-mesh pipeline`**\
Test `.geo`, CAD inputs where supported, `.msh` exports, physical groups and quality checks.\
**Acceptance:** tagged 3D mesh is validated and preserved in a typed downstream artifact.

**DS-SCI-016 — `feat(sage): introduce typed Sage worker protocol`**\
WSL handshake, job envelope, exact serialization, resource lifecycle and typed errors.\
**Acceptance:** rational, polynomial and matrix round trips preserve mathematical structure.

**DS-SCI-017 — `feat(sage): qualify exact algebra and number-theory operations`**\
Add factorization, number field, splitting, ring/ideal and Galois small fixtures.\
**Acceptance:** positive and expected-rejection tests, exact checks and explicit algorithm limitations are recorded.

**DS-SCI-018 — `feat(cgal): expand mesh repair, remesh and query suites`**\
Add validation, orientation, repair, remeshing, AABB and distances.\
**Acceptance:** each has scientific invariants, expected-invalid fixtures and artifact replay.

**DS-SCI-019 — `feat(fixtures): create pathology and regression corpus`**\
Canonical/pathological/generated/real-world fixture layout, metadata and rights checks.\
**Acceptance:** fixture version/seed/hash appears in every relevant run; defects can be promoted into regression cases.

**DS-SCI-020 — `feat(testing): add property-based and metamorphic tests`**\
Geometry invariants, numerical tolerance policy and shrinking.\
**Acceptance:** seeded generated failures reproduce and save minimized fixtures.

### P1 — MATH3D integration

**DS-SCI-021 — `feat(broker): introduce Scientific Runtime Broker`**\
Provider discovery, job lifecycle, progress, timeout, cancellation and artifact transport.\
**Acceptance:** no native SDK linked into renderer; jobs have typed completion/partial/failure semantics.

**2026-11-04 scoped delivery:** `tools/scientific-broker/broker.py` runs independently of the DevShell desktop process on localhost. It discovers the current certified CGAL mesh path, owns worker jobs with progress/cancellation/timeouts and typed outcomes, and serves only verified output and handoff artifacts. The current contract accepts the fixed qualified OBJ fixture; broader input and provider support require fresh qualification.

**DS-SCI-022 — `feat(integration): publish certified capability manifest`**\
Export verified provider/contract/evidence identities and support standalone broker deployment.\
**Acceptance:** unqualified provider cannot appear as certified; manifest verification catches mismatched hashes.

**2026-11-04 scoped delivery:** the standalone exporter re-assesses saved L0–L9 records and drift before publishing the current CGAL L9 mesh identity. The broker checks the manifest digest, contract, runtime manifest, worker files, Python, Conda package inventory and output hashes. Gmsh is excluded. The digest provides integrity checking; signed deployment identities remain future work.

**DS-SCI-023 — `feat(integration): add Promote to Math3D workflow`**\
Gate promotion by current applicable L0–L9 evidence and version compatibility.\
**Acceptance:** stale, incomplete and failed capabilities are blocked with explanation.

**2026-11-04 scoped delivery:** the broker's `POST /v1/jobs/{id}/promote` saves an immutable allow/block decision with reasons. It checks the exported current L0–L9 chain, successful job, version 1 handoff, worker artifact, and MATH3D consumer source fingerprints. The fixed CGAL mesh path is eligible; stale/failed runs and Gmsh are blocked.

**DS-SCI-024 — `feat(integration): qualify m3dm and typed-document round trips`**\
Extend artifacts to mesh, volume mesh and exact mathematical outputs as applicable.\
**Acceptance:** independent parser validates format and scientific invariants after round trip.

**2026-11-04 scoped delivery:** MATH3D's native codec saves a promoted tetrahedron mesh as version 1 `.m3dm`; an independent Python parser reloads it and checks the header, exact triangles and winding, finite coordinates, closed orientation, signed volume and scale against the broker OBJ. The saved Mesh document/resource also reopens in MATH3D. An immutable document qualification record pins the source L9 record, promotion, codec/parser, contract, scene and artifact hashes. Volume and exact mathematical documents remain future work.

**DS-SCI-025 — `feat(integration): add Math3D end-to-end smoke suite`**\
Broker worker → validated result → document import → viewer/workbook module smoke.\
**Acceptance:** named fixture produces expected document/scene; failures are traceable to the originating job.

**2026-11-04 scoped delivery:** `tools/scientific-broker/smoke.py` drives the broker API, promotion, MATH3D Mesh document import and viewer, `.m3dm` writer and independent reload. It saves a hash-verifiable result keyed to the source job; rejected promotion saves the failed stage and reason. Workbook and other provider/module smokes remain future work.

### P2 — Performance and robustness

**DS-SCI-026 — `feat(benchmarks): add persistent performance baselines`**\
Benchmark IDs, tiered input sizes, controlled repetitions, cold/warm policy and historical trends.\
**Acceptance:** inconsistent host/fingerprint comparisons are warned as inconclusive.

**2026-11-04 scoped delivery:** the fixed CGAL tetrahedron benchmark records first-run cold observations, warmup and repeated batches of 1/3/5 qualified inputs. It pins an immutable baseline, retains history, supports explicit re-pinning, and warns that host, environment, source, fixture or policy differences are inconclusive. Batch size is the current tier dimension; larger mesh fixtures require separate qualification.

**DS-SCI-027 — `feat(benchmarks): collect CPU, RAM, GPU and VRAM telemetry`**\
Best-effort resource measurements with explicit supported/unavailable statuses.\
**Acceptance:** every measurement names its collector, units and availability; metrics are not fabricated.

**2026-11-04 scoped delivery:** broker jobs save hash-verified `telemetry.json`. `psutil` samples CPU time and peak resident memory of the worker tree. `nvidia-smi` samples host GPU utilization and VRAM, explicitly marked as host-wide rather than job-attributed. Unavailable readings have a reason and null value.

**DS-SCI-028 — `feat(testing): qualify cancellation and process cleanup`**\
Timeout, kill, orphan detection, partial artifact cleanup and status mapping.\
**Acceptance:** cancelled jobs cannot be marked successful and cannot silently leave active children.

**2026-11-04 scoped delivery:** broker finalization inspects observed descendants, kills surviving children, removes partial mesh/handoff outputs and withholds success when cleanup cannot be verified. The cleanup suite passes real CGAL cancellation plus test-only forced cancellation, timeout and orphan cases; each blocked artifact transport and MATH3D promotion. Wider provider and operating-system qualification remains future work.

**DS-SCI-029 — `feat(testing): qualify concurrent scientific workers`**\
Concurrent recipes, artifact isolation, memory pressure and scheduling tests.\
**Acceptance:** repeated jobs produce isolated results and report resource-related failures clearly.

**2026-11-04 scoped delivery:** the standalone broker caps concurrent workers and optionally enforces sampled process-tree resident memory. A launch gate attaches process observation before the adapter starts. Live suite `ea42c05bef1641b68db00c947379f1fb` passed two batches at each of 1, 2, 4 and 8 real CGAL jobs (30 total), verifying the requested peak adapter overlap with per-job timing hashes, unique directories, own-run request/result/handoff identities, fixed output hashes and cleanup. A held diagnostic job produced a clear capacity rejection; a real CGAL job exceeded a 1 MiB test budget, ended `resource-exhausted`, cleaned up and could not be promoted. This covers the fixed qualified CGAL path on the local Windows host, not every provider or GPU scheduling.

### P2 — Repositories, comparisons, retesting

**DS-SCI-030 — `feat(repos): bind scientific runs to commits and worktrees`**\
Source snapshot and dirty-state evidence with safe read-only default.\
**Acceptance:** historical run remains attributable after branch advances.

**2026-11-04 scoped delivery:** each new broker job captures a hash-verified `source-snapshot.json` before worker launch. It records full Git commit/tree, branch and worktree identities, tracked patch digest, hashed untracked files and aggregate dirty digest for DevShell and the configured MATH3D checkout. Request, job result and promotion link to the snapshot; tampering blocks promotion. A missing Git checkout has an explicit unavailable status. A focused test advances a branch and verifies that the earlier commit remains attributable.

**DS-SCI-031 — `feat(repos): compare scientific results across commits`**\
Two-source build/test matrix and evidence diff.\
**Acceptance:** baseline and candidate each identify exact sources and environments.

**2026-11-04 scoped delivery:** `compare_commits.py` runs the same broker .NET build, independent OBJ/VTP reload tests and fixed tetrahedron geometry inspection from two isolated, detached Git worktrees. It requires nonzero test counts and the fixed tetrahedron geometry contract, including orientation and scale. It saves exact commit/tree and suite hashes, one shared host/tool environment fingerprint, stage logs and a geometry/source evidence diff. Local matrix `229dc6be05ff4de7b005402bafda1833` compared `cb0ae57` to `2496d5e`: both built and passed tests, and geometry was equivalent while the broker project revision changed. Worktrees were removed; the immutable local report remains. This source matrix does not certify a new binary or grant promotion.

**DS-SCI-032 — `feat(repos): add automated scientific git bisect`**\
Isolated worktree bisect runner with good/bad/skip classification.\
**Acceptance:** builds or infrastructure failures cannot be incorrectly classified as scientific bad commits.

**2026-11-04 scoped delivery:** `bisect_commits.py` checks a linear first-parent range in temporary detached worktrees using the DS-SCI-031 build, reload tests and fixed tetrahedron contract. Build, test setup, missing suite and inspection infrastructure failures classify `skip`; a scientific assertion or validated geometry mismatch classifies `bad`. It reports a first bad commit only with adjacent good/bad evidence, otherwise an inconclusive boundary, and saves exact commit/tree, environment, logs, classifications and replay command. An isolated-worktree test found a synthetic first bad commit; a live check of known-good `cb0ae57` and `2496d5e` saved report `5bcffecdbdf14b87953b790f6450d996` with `invalid-endpoints`, correctly naming no regression.

**DS-SCI-033 — `feat(scientific): add cross-runtime differential testing`**\
Canonical comparator library for mesh/field/exact math results.\
**Acceptance:** equivalent-but-differently-triangulated meshes can pass geometric equivalence checks.

**2026-11-04 scoped delivery:** `differential.py` compares bounded OBJ/VTP surfaces with topology invariants, symmetric sampled point-to-triangle deviation, orientation, bounds, area and signed volume; scalar/vector fields by canonical sample ID, unit and tolerance; and rational/polynomial exact values by normalized fractions. Alternate square triangulations pass while reversed orientation and changed scale fail. Historical successful CGAL OBJ and VTK VTP L6 runs, each checked against its registered artifact and fingerprint, produced equivalent tetrahedron geometry in local report `a45bf36ae44643bfbe04d9f352e96d54`. The sampled mesh method is explicitly bounded and does not certify new provider capabilities.

**DS-SCI-034 — `feat(scientific): add runtime-matrix dashboard`**\
Summarize provider availability, qualified capabilities, stale verdicts and regressions.\
**Acceptance:** every dashboard verdict drills down to specific evidence.

**2026-11-04 scoped delivery:** the desktop Scientific Runtimes **Matrix** section combines the recorded local inventory, each provider's verified current qualification summary, stale/unknown reasons from recent saved run results and failure-after-success review candidates. Availability opens the provider's recorded State checks; capability and stale entries open the source run in History; candidate failures link both runs. A CDP desktop check showed all five providers, Gmsh without a current qualification, a CGAL stale run drill-down, and evidence navigation. At this checkout the CGAL summary reports 163 stale records and no current level because saved source and suite fingerprints differ from present files; the dashboard does not promote them. This is a read-only dashboard over saved evidence; failure-after-success is labelled as a review candidate rather than an established scientific regression.

**DS-SCI-035 — `feat(scientific): add selective retest dependency graph`**\
Versioned graph of suites and source/schema/toolchain dependencies.\
**Acceptance:** affected changes trigger conservative relevant requalification without blindly rerunning all suites.

**2026-11-05 scoped delivery:** `schemas/scientific-retest-graph.v1.json` maps 18 provider and local suites to source patterns, environment keys and downstream dependencies. `retest.py` takes Git refs or explicit changed paths/keys, plans only affected suites, selects all for unmapped code changes, saves the graph hash and reasons, and can run selected allowlisted local unit suites. Managed qualification suites are reported as `requires-managed-run`; this planner does not itself grant or refresh desktop L0–L9 records. Gmsh probes remain unqualified.

### P3 — Orchestration, remote execution and release

**DS-SCI-036 — `feat(pipelines): add typed scientific pipeline composer`**\
DAG nodes based on qualified capabilities, typed ports, artifact caching and replay.\
**Acceptance:** incompatible artifact types are rejected before execution; every node records provenance.

**2026-11-05 scoped delivery:** `pipeline.py` preflights an entire version 1 DAG against three allowlisted node kinds for the certified CGAL fixture: broker mesh validation, independent OBJ inspection, and MATH3D promotion. It rejects wrong ports, incompatible types, cycles, unqualified capabilities and mixed promotion sources before launching a worker. Each node saves input/output hashes and certification provenance; mesh inspection has a hash-sealed cache, and replay verifies saved artifacts and reruns the same specification. This is a fixed CGAL pilot, not general provider orchestration.

**DS-SCI-037 — `feat(remote): add authenticated remote runtime agents`**\
Remote execution profiles, resource policies, identity and integrity checks.\
**Acceptance:** remote and local results remain clearly distinguished; no arbitrary unauthenticated code execution.

**2026-11-05 scoped delivery:** `remote_agent.py` serves the fixed qualified CGAL job over TLS. A client checks the certificate chain and hostname plus pinned agent, host and certified-manifest identities; the server requires a token and accepts only the qualified fixture and bounded timeout. The broker enforces its worker capacity and optional memory budget. A remote result carries `executionLocation: remote`, source job and transport hashes, and its artifact bytes are verified again after download. Remote evidence does not raise local qualification. The deployment needs separately provisioned certificate, token and client trust files; the loopback integration test covers rejection and tamper cases.

**DS-SCI-038 — `feat(ci): add scientific CI evidence import and export`**\
Exchange bundles, reconcile suite revisions and expose CI matrices in DevShell.\
**Acceptance:** imported CI verdict references its actual agent/environment; GPU evidence requires a GPU agent.

**2026-11-06 scoped delivery:** `ci_evidence.py` exports a path-redacted, HMAC-authenticated bundle for a terminal certified CGAL broker job. It pins the source job, agent and host fingerprint, suite revision, environment, certification, source snapshot, telemetry and any verified fixed OBJ output. Import requires a trusted agent key and host identity, verifies every archive member, rejects GPU qualification from CPU agents, compares the suite and deployment identities, and saves an immutable local summary and bundle. The desktop Matrix displays those CI records separately from local qualification, with source job and bundle identity. A mismatched suite is inconclusive. The trusted key proves the configured agent's publication, not an independent attestation of its physical hardware; GPU qualification remains unavailable for this fixed CPU capability.

**DS-SCI-039 — `feat(release): introduce scientific release certification`**\
Lock evidence into release capability manifests and produce a release qualification report.\
**Acceptance:** published release manifests only refer to verified, applicable current evidence.

**2026-11-06 scoped delivery:** `release_certification.py` invokes the desktop exporter afresh and requires exactly one current L9 CGAL mesh capability whose complete entry matches the deployed broker certification. It saves a sealed qualification report and the fresh export; only a passing gate writes a sealed release capability manifest with the L0–L9 chain, contract, suite, environment and source commit. On this checkout the real fresh export contains no current L9 capability, so the observed report is **blocked** and no release manifest was written. Gmsh is absent.

**DS-SCI-040 — `feat(regression): promote qualified failures to regression fixtures`**\
One-click reviewed bug fixture creation with traceability from source evidence.\
**Acceptance:** new regression tests replay deterministically and do not expose private inputs without approval.

**2026-11-06 scoped delivery:** `regression_fixtures.py` accepts only a failed run of the currently certified fixed CGAL capability and stores a draft containing hashes and the registered public fixture ID, without raw input, log or local path. A named review and explicit public-fixture approval precede two fresh replays; only identical expected terminal states with no artifacts produce a sealed regression fixture. Fixture verification can run another replay. The 1 MiB resource-limit failure passed this flow. Private inputs are rejected by scope rather than exported automatically; broader reviewed data support remains future work.

---

## 27. Suggested additional commits beyond the first 40

These are useful extensions once P0/P1 foundations are stable:

**DS-SCI-041 — `feat(scientific): add environment drift diagnostic wizard`**\
Explain mismatched interpreter, PATH, WSL path mapping, driver, compiler and package conflicts; recommend specific requalification steps rather than silently altering environments.

**2026-11-06 scoped delivery:** History now has a read-only drift diagnosis panel for a verified run. It explains source/suite, interpreter, Conda package, compiler/CMake/Ninja, WSL distro/path-mapping and optional GPU driver evidence, including unknown components and explicit next requalification steps. New fingerprints capture a bounded `nvidia-smi` driver-version hash when available; older runs remain inspectable without it. The panel never edits PATH, WSL, packages or qualification records.

**DS-SCI-042 — `feat(scientific): add reproducible environment manifests`**\
Generate lockable Conda/venv/container/CMake presets and record whether exact dependency builds can be recreated in disposable sandboxes.

**2026-11-06 scoped delivery:** `environment_manifest.py` saves a sealed exact Conda explicit lock with package URL/build/checksum identities, a version-pinned pip inventory, a Windows container compatibility preset and a CMake preset. It states when wheel hashes, a compatible pinned container base or a matching compiler are still needed. An offline `conda create` in a disposable prefix verifies the full package-build identity, saves a hash-checked attempt log and removes the sandbox. The current CGAL prefix's 54-package lock recreated successfully; this result does not claim exact venv or container recreation.

**DS-SCI-043 — `feat(scientific): add adapter conformance harness`**\
Run contract-level tests against every provider, especially errors, cancellation, progress, typed values and artifact hash behavior.

**2026-11-06 scoped delivery:** `adapter_conformance.py` records all five providers against the same contract dimensions. The fixed certified CGAL broker path passed contract, early rejection, cancellation/cleanup, progress, typed status and artifact hashes. VTK passed its worker contract, rejection, typed mesh and artifact checks; progress and cancellation acknowledgement are explicitly unavailable. Python/SciPy and Sage passed typed/rejection probes but have no version 1 artifact worker; Gmsh probes remain unavailable because the package is missing. These incomplete verdicts do not grant qualification, and Gmsh stays unqualified.

**DS-SCI-044 — `feat(scientific): add operation-level cost and backend advisor`**\
Offer provider suggestions only from certified comparable benchmark data, while preserving manual choice and deterministic replay.

**DS-SCI-045 — `feat(scientific): add large-artifact content-addressed cache`**\
Deduplicate artifacts by hash, track references, support retention/pinning and safe cleanup.

**DS-SCI-046 — `feat(scientific): add mathematical result provenance graph`**\
Link exact Sage inputs, derivations, approximations, geometry sampling, mesh generation and final Math3D documents.

**DS-SCI-047 — `feat(scientific): add interactive artifact inspector`**\
Mesh statistics, numeric diffs, preview renders and exact-math structured viewers without importing full Math3D editing UI.

**DS-SCI-048 — `feat(scientific): add compatibility policy for contract migrations`**\
Automated checks between current and previous schema majors/minors with explicit migration rules.

**DS-SCI-049 — `feat(scientific): add release-to-release qualification matrix`**\
Compare CGAL, VTK, VTK-m, Sage, Gmsh and Math3D releases with confidence indicators and evidence coverage.

**DS-SCI-050 — `feat(scientific): add scientific reproducibility report generator`**\
Human-readable Markdown/HTML report containing capabilities, gate verdicts, fixtures, fingerprints, numerical tolerances, regressions and reproducibility instructions.

---

## 28. Priority selection: what to implement first

### Immediate batch (highest return)

1. **001–002:** plugin interfaces and runtime-specific UI correction.
2. **003–007:** fingerprints, qualification levels, registry, staleness and contracts.
3. **008–010:** run comparisons, pinned baselines and evidence bundle export.
4. **016:** typed Sage WSL worker (initial minimal exact-math subset).
5. **011:** genuine VTK integration suites.
6. **021–025:** broker and MATH3D qualification on a carefully chosen first few capabilities.

### Following batch

- CGAL mesh operations and pathology corpus.
- Gmsh volume-mesh path.
- VTK-m CPU then actual CUDA tests.
- Metamorphic/differential suite.
- Benchmark and process robustness infrastructure.

### Defer until the above is trustworthy

- Full visual pipeline editor.
- Automatic provider selection based on benchmark score.
- Remote agent farm.
- Large CI/release certification matrix.

**Reason:** without stable contracts and evidence semantics, each new runtime increases the number of UI special cases and weakens traceability. With those foundations, adding runtime providers becomes relatively modular.

---

## 29. Definition of Done and quality bar

### 29.1. Per feature

- Typed capability and clear schema/version.
- Positive, negative and unsupported cases.
- Evidence attached to every asserted status.
- Worker/run fingerprint and source provenance.
- Correct cancellation/error semantics.
- UI handling for unconfigured and stale states.
- Tests and developer documentation.

### 29.2. Per provider

- Discovery and health check.
- Recorded supported backend/device list.
- Reproducible environment/toolchain fingerprint.
- At least one qualified scientific operation and invalid-input case.
- Contract conformance and artifact verification where relevant.
- Runtime-specific UI, not copy-pasted capabilities.

### 29.3. For MATH3D promotion

- All applicable mandatory gate requirements PASS on current evidence.
- Certified capability and output schema versions match consumer.
- Manifest references an immutable evidence digest.
- Input/output and artifact round trips validated.
- Known limitations and numeric tolerances documented.
- User-facing MATH3D gracefully handles absent or failed provider.

### 29.4. For release

- Pinned qualification baseline.
- Reproducible build/source fingerprint.
- Regressions adjudicated.
- Required CI platform/device coverage completed.
- Signed or integrity-verified manifest and evidence archive.
- Clear unsupported and deferred capability list.

---

## 30. Key engineering decisions to resolve early

| Decision | Preferred initial choice | Rationale |
|---|---|---|
| Runtime integration | External workers, no native SDK in renderer | Keeps DevShell and Math3D small and isolated |
| Registry | Semantic versioned capabilities | Multiple providers without library-specific UI coupling |
| Execution | Explicit provider in tests | Reproducible comparisons |
| Artifact storage | Content-hashed immutable blobs + metadata index | Deduplication and auditability |
| Evidence | Per-run immutable records | Reliable historical comparison |
| Contracts | JSON metadata + typed binary artifacts as required | Exactness and large-object performance |
| WSL | Dedicated Sage worker adapter | Avoid embedding WSL paths in Math3D |
| VTK-m | Separate plugin from VTK | Device execution deserves independent qualification |
| L9 | Product contract + import verification | Stronger than a successful command |
| Promotion | Per capability/provider/fingerprint | Prevents one good operation certifying a whole library |
| CI | Fast smoke and heavyweight separate lanes | Cost and runtime control |
| Security | Allowlisted recipes and scoped resources | Safe native and cross-OS execution |

---

## 31. Future example qualification scenarios

### Scenario A — CGAL mesh repair to MATH3D

1. Load pathological surface fixture.
2. Validate and capture defects.
3. Run repair recipe.
4. Validate repaired topology, geometry and audit of changed elements.
5. Export `.m3dm`.
6. Independently parse and compare.
7. Open in Math3D viewer.
8. Record evidence and certify `mesh.repair@1` on the chosen provider.

### Scenario B — VTK-m GPU contour

1. Discover VTK-m build/device set.
2. Generate field fixture and CPU reference.
3. Execute contour on CPU and CUDA.
4. Verify actual CUDA execution.
5. Compare geometry, field values and bounds.
6. Measure device time, transfer cost and VRAM.
7. Test memory-pressure and cancellation paths.
8. Produce separate CPU and CUDA qualification entries.

### Scenario C — Sage number field computation

1. Submit a typed number field specification.
2. Compute integral basis and selected prime decompositions.
3. Serialize exact ideals, factors, exponents and residue degrees.
4. Validate basic algebraic identities on small reference cases.
5. Import result into Math3D Number Theory / Workbook document.
6. Preserve parent field, embeddings, proof/algorithm status and exact values.
7. Certify only the tested capability family and schema versions.

### Scenario D — Gmsh volume-mesh generation

1. Import `.geo`/STEP geometry.
2. Generate tetrahedra and physical groups.
3. Inspect element-quality distributions.
4. Export `.msh` and convert to typed Math3D volume-mesh artifact.
5. Check node/connectivity/tag preservation.
6. Open in Math3D with the appropriate volume visualization workflow.
7. Save evidence for the conversion and integration path.

### Scenario E — Regression across MATH3D commits

1. Pin known-good commit and evidence.
2. Select candidate commit in isolated worktree.
3. Build selected worker/adapter.
4. Run the same scientific suite.
5. Compare correctness and controlled benchmark metrics.
6. If regression confirmed, run scientific git bisect.
7. Save the first-bad candidate and minimized reproducer.

---

## 32. Final architecture rule

The success criterion is **not** the number of installed scientific libraries or the number of tabs in DevShell. It is whether an operation is:

1. **Discoverable** on the selected machine.
2. **Runnable** through a controlled worker.
3. **Scientifically correct** on defined fixtures and invariants.
4. **Reproducible** from its source and environment fingerprint.
5. **Inspectable** via logs, diagnostics, artifacts and numeric evidence.
6. **Comparable** across providers, versions and commits.
7. **Resilient** to invalid inputs, cancellation, resource limits and concurrency.
8. **Compatible** with a versioned MATH3D contract.
9. **Promotable** with verifiable evidence.
10. **Maintainable** without expanding the main Math3D app into an environment manager.

**Recommended implementation sequence:** establish plugin boundaries and fingerprints → semantic capabilities and L0–L9 evidence → genuine provider-specific suites → typed broker and Math3D handoff → differential/benchmark/regression tooling → pipelines and remote infrastructure.

This approach keeps the strongest current DevShell features, especially the CGAL qualification model, while allowing Sage, CGAL, VTK, VTK-m, Gmsh, Python and future scientific systems to join under one coherent, testable architecture.
