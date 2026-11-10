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

**2026-11-07 local delivery:** A standalone Windows-to-WSL adapter discovers Sage without a fixed machine path, reports a versioned handshake and maps run paths through `wslpath`. A bounded exact worker accepts rational addition, polynomial factorization and square matrix solve, returning canonical rational pairs, factor multiplicities or a verified exact solution in version 1 JSON. Real Sage 10.9 round trips and invalid-coefficient/singular-matrix rejections passed on Ubuntu WSL. The worker has no managed qualification record or certified broker capability; see `tools/SCIENTIFIC_SAGE_WORKER.md`.

**DS-SCI-017 — `feat(sage): qualify exact algebra and number-theory operations`**\
Add factorization, number field, splitting, ring/ideal and Galois small fixtures.\
**Acceptance:** positive and expected-rejection tests, exact checks and explicit algorithm limitations are recorded.

**2026-11-07 local delivery:** The desktop Sage Tests button runs nine fixed cases through Ubuntu WSL: four positive exact operations and five expected rejections. The quadratic-field case is limited to Q(√2) and primes 2, 3 and 7; its exact checks cover defining polynomial, discriminant, integral basis, prime splitting, ideal norm and residue degree, and Galois order. Each case retains its request/result hashes and worker identity. Successful managed runs save four separate L3 qualifications with run and fingerprint provenance; History verifies them and assesses current/stale status. The capability catalog records the limits. This does not certify a general number-theory engine or broker capability.

**DS-SCI-018 — `feat(cgal): expand mesh repair, remesh and query suites`**\
Add validation, orientation, repair, remeshing, AABB and distances.\
**Acceptance:** each has scientific invariants, expected-invalid fixtures and artifact replay.

**2026-11-08 scoped delivery:** A separate CGAL 6.0.1 AABB executable answered bounded point-to-triangle-mesh queries without changing the existing certified worker contract. A sealed local suite checked five known squared distances/closest points and rejected degenerate geometry, nonmanifold geometry, non-finite coordinates and out-of-budget coordinates. Eight seeded affine queries preserved the expected squared-distance scaling. A separate Python triangle-distance oracle verified all thirteen positive native results and that their closest points lie on the source surface. This is unsigned surface distance only; repair, orientation, managed qualification and broker certification remain open.

**2026-11-08 orientation delivery:** A separate versioned inward tetrahedron is the exact face reversal of the authored outward fixture, with equal-magnitude negative signed volume. The native CGAL orientation tool inspects open meshes as undetermined and restricts repair to one closed connected nondegenerate volume. Eight fixed cases checked outward/inward inspection, inward-to-outward repair, outward no-op and open/degenerate/nonmanifold refusals. Four seeded affine inward tetrahedra were repaired and reopened with independent signed-volume and topology checks. These are local laboratory records; managed qualification, hole filling and general mesh repair remain open.

**2026-11-08 remesh delivery:** A separate independent OBJ analyzer measures components, boundary loops, Euler characteristic, edge lengths, area, signed volume and bounds. The existing native CGAL remesh worker passed a sealed seven-case local suite: closed tetrahedron and protected unit square positives, plus degenerate, nonmanifold, budget, invalid-iteration and non-finite-target rejections. A linked boundary record confirmed that the 16 output rim edges cover each original square side without gaps, overlaps or excursions. Four seeded affine tetrahedra preserved closed topology and scale covariance of area, edge lengths and signed volume against a baseline. These local checks do not extend the fixed broker certification.

**2026-11-08 remesh follow-up:** Both positive outputs reopened successfully through native validation with independent before/after metrics. Three fresh runs per fixture produced byte-identical output OBJs. Four seeded affine open-square remeshes preserved area, perimeter, topology and every protected rim segment after inverse mapping. A six-setting target-edge/iteration profile measured signed volume against the authored closed tetrahedron. Five settings met a 1e-8 absolute volume gate; target edge 0.5 with two iterations retained closed topology but reduced volume from 1/6 to about 0.12448 (about 25.3% drift), so the profile marks it ineligible for volume-preserving use. This fixture-specific numerical limit requires review before broader remesh qualification.

**2026-11-10 remesh diagnostics:** Independent triangle angles and dimensionless shape scores were linked to all six sealed fidelity cases. Bidirectional vertex-to-triangle distances alone read approximately zero, including the ineligible 0.5/two-iteration case. Adding unique edge midpoints and face centroids exposed maximum sampled surface deviations of about 0.196 from source to output and 0.125 in reverse for that case; the other five settings measured approximately zero. These finite samples do not establish a continuous Hausdorff distance. Topology and minimum angle alone did not reveal the volume loss; broader qualification needs a surface-fidelity gate as well as volume and shape checks.

**2026-11-10 remesh acceptance and counterexample:** A sealed fixture-specific gate combines the existing 1e-8 volume limit with a 1e-8 maximum sampled-surface distance, 20-degree minimum angle and 0.5 minimum shape score. Five of six authored-tetrahedron settings pass; the 0.5/two-iteration setting fails volume and surface gates. Native validation reopened all six outputs, demonstrating that this low-fidelity result is still a valid mesh. Four seeded affine tetrahedra reproduced more than 20% relative volume loss with scale-normalized facet displacement above 0.1. A recorded four-step reduction removed translation, scale and axis permutation while retaining the failure on the untransformed fixture. The gate and counterexample are local laboratory evidence, not managed remesh qualification or a general parameter guarantee.

**2026-11-10 guarded remesh publication:** A separate local runner now retains native candidate geometry and a sealed decision, but writes `accepted.obj` only after bounded closed-topology, relative volume, normalized sampled-surface and triangle-shape checks pass. Its six-setting replay produced five accepted outputs and one rejected candidate with bytes matching the prior native profile. Four seeded affine one-iteration runs were accepted and four two-iteration adverse runs were rejected. A separate export verifies the accepted report before copying the mesh and writes a hash-linked manifest; a rejected report cannot export. The guard applies to outward closed genus-zero triangular inputs within its analysis budget. Finite sampling is not a continuous Hausdorff guarantee, and this local path does not change the broker capability manifest or managed qualification.

**2026-11-10 triangular-hole repair:** A separate CGAL 6.0.1 executable fills only one three-edge boundary on a connected triangle manifold and verifies that the result is a nondegenerate, non-self-intersecting, outward closed volume. A CC0 project-authored one-hole tetrahedron fixture is pinned to the exact omitted face of the original closed tetrahedron in a separate manifest, preserving earlier corpus hashes. The fixed suite restored the original four oriented faces and volume 1/6, and refused a closed mesh, a four-edge open square, a degenerate triangle and a nonmanifold edge without writing outputs. Four seeded affine holes restored the corresponding oriented closed faces and volume scaling, with hash-verifiable evidence and tamper checks. This is narrow hole filling, not arbitrary mesh repair, managed qualification or a broker capability.

**2026-11-10 square-hole repair:** The separate hole-fill executable gained an explicit four-edge operation while retaining the three-edge command. A new CC0 authored unit cube manifest pins the closed twelve-triangle surface and the exact removal of its two top triangles. The native worker closed that square boundary with two outward triangles and restored area 6 and volume 1; CGAL chose a different valid top diagonal. An independent check requires all ten original faces, exactly two patch faces, the complete four-edge top rim and unit patch area. The six-case fixed suite refused a closed cube, flat open square, triangular hole under the wrong operation, degenerate triangle and nonmanifold edge without writing outputs. Four seeded affine cubes preserved inverse-mapped patch coverage and cubic volume scaling. These are local evidence for the named hole classes, not general repair or managed/broker qualification. Earlier saved triangle reports are stale after the shared executable changes; fresh triangle replay passed.

**2026-11-10 two-square-hole repair:** A third CC0 fixture pins exact removal of both top and bottom faces from the authored unit cube, leaving one connected side wall with two four-edge loops. A new explicit native operation re-enumerates remaining boundaries after each fill, records two patch-face counts and writes output only after the closed, outward, non-self-intersecting volume check. The seven-case replay filled both caps with two triangles each, retained all eight original side faces, covered both complete square rims and restored area 6 and volume 1. It refused a one-hole cube, closed cube, triangular hole, wrong operation, degenerate triangle and nonmanifold edge without output. Four seeded affine cubes preserved inverse-mapped cap coverage and cubic volume scaling. A verified local export copies only positive fixed or affine evidence into a hash-linked mesh manifest; rejected fixed cases cannot export. This is bounded local laboratory evidence, not arbitrary repair or managed/broker qualification. The changed worker hash makes earlier saved hole-repair reports stale until replayed.

**2026-11-10 managed repair delivery:** The three explicit native hole fills are registered as CGAL Scientific recipes and exposed in the desktop Repair controls. The managed adapter accepts only registered OBJ copies, checks their request hash and selected boundary scope, and independently measures saved output geometry before returning `mesh.repair` with artifact hashes and repair evidence. The desktop records build and execution in History and includes the repair source, adapter, and executable in fingerprints. A managed replay passed all three positive authored fixtures and rejected both a wrong operation and a changed dataset hash without an output artifact. This is a scoped managed capability; L5–L9 qualification and a general repair algorithm remain open. See `docs/SCIENTIFIC_CGAL_MANAGED_REPAIR.md` for operation and replay instructions.

**DS-SCI-019 — `feat(fixtures): create pathology and regression corpus`**\
Canonical/pathological/generated/real-world fixture layout, metadata and rights checks.\
**Acceptance:** fixture version/seed/hash appears in every relevant run; defects can be promoted into regression cases.

**2026-11-08 scoped delivery:** Four project-authored CC0 OBJ fixtures cover a closed tetrahedron, open square, zero-area triangle and nonmanifold edge. A versioned manifest pins bytes and independent geometric expectations. A local verifier checks rights, file hashes, edge incidence, degeneracy and signed volume. Native CGAL replay saved worker and fixture hashes, accepted two valid meshes, rejected two invalid meshes and detected output tampering. This corpus is standalone; managed run linkage and real-world rights review remain open.

**DS-SCI-020 — `feat(testing): add property-based and metamorphic tests`**\
Geometry invariants, numerical tolerance policy and shrinking.\
**Acceptance:** seeded generated failures reproduce and save minimized fixtures.

**2026-11-08 scoped delivery:** A deterministic seed produces four scaled, translated and axis-permuted authored tetrahedra. Local CGAL validation preserved vertex/face counts, closed topology and signed-volume scaling. The runner seals generated inputs and worker results, records failures and tries neutral scale, translation and axis reductions to save a simpler reproducer. Seed repeatability, shrink ordering and input-tamper rejection passed. Broader properties and an observed failing seed remain open.

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

**2026-11-06 scoped delivery:** `advisor.py` checks deployed certification and exact benchmark record identities against the current host, environment, fixture, suite and collector sources. Two fresh CGAL benchmark runs match one another and provide a cost candidate for each fixed tier. Both remain inconclusive against the older pinned baseline because broker and telemetry sources changed. Advice is sealed and replay-verifiable. With only one certified backend, it returns `insufficient-comparison`, no automatic recommendation, and keeps an explicit manual CGAL choice; Gmsh cannot be selected. Backend ranking awaits another certified provider with comparable operation-level measurements.

**DS-SCI-045 — `feat(scientific): add large-artifact content-addressed cache`**\
Deduplicate artifacts by hash, track references, support retention/pinning and safe cleanup.

**2026-11-06 scoped delivery:** `artifact_cache.py` stores streaming SHA-256 objects once, with transactional SQLite references and named pins. It ingests only verified successful broker artifacts or independently checked MATH3D smoke documents through the integration commands. Read and cleanup verify bytes and size; retention cleanup requires an explicit `--apply` and removes only unreferenced, unpinned objects within the cache root. Live mesh and `.m3dm` ingestion, deduplication, pinning, dry-run cleanup and tamper rejection passed.

**DS-SCI-046 — `feat(scientific): add mathematical result provenance graph`**\
Link exact Sage inputs, derivations, approximations, geometry sampling, mesh generation and final Math3D documents.

**2026-11-06 scoped delivery:** `provenance.py` runs a bounded Sage rational-root derivation of `x²−1` under WSL, constructs the exact fixed tetrahedron vertices and OBJ bytes, and checks them against the certified CGAL fixture. It passes that generated dataset to a fresh broker → MATH3D smoke. A sealed seven-node graph links exact input, derivation, float representation, sampled vertices, OBJ mesh generation, CGAL validation, and the independently reloaded `.m3dm` document, with source job and artifact hashes. The current fixed public path passed; this does not qualify a general Sage mesh worker or claim arbitrary symbolic-to-mesh provenance.

**DS-SCI-047 — `feat(scientific): add interactive artifact inspector`**\
Mesh statistics, numeric diffs, preview renders and exact-math structured viewers without importing full Math3D editing UI.

**2026-11-06 scoped delivery:** Scientific History now shows a read-only artifact inspector alongside its existing interactive mesh preview. It displays full mesh point/triangle counts and bounds, worker topology when saved, recorded artifact hashes, and numeric deltas between two loaded runs. A structured Sage factor panel renders only validated saved probe or smoke evidence. Preview triangles may be sampled; counts and bounds refer to the full output. Numeric equality is not treated as a topology or surface equivalence proof. General exact-math and field viewers remain pending typed workers.

**DS-SCI-048 — `feat(scientific): add compatibility policy for contract migrations`**\
Automated checks between current and previous schema majors/minors with explicit migration rules.

**2026-11-06 scoped delivery:** `contract_migration.py` checks the current capability registry against a frozen 1.0.0 snapshot and saves a hash-checked compatibility report. Additive fields require a minor bump, breaking fields require a major bump, and major migrations require scoped rename/default rules with old and new fixtures that validate under their respective schemas. Tests cover optional minor additions, blocked patch and same-major breaks, a passing fixture-backed major rename, invalid migration fixtures and report tampering. The current unchanged registry passes; other contracts need their own frozen baselines before migration.

**DS-SCI-049 — `feat(scientific): add release-to-release qualification matrix`**\
Compare CGAL, VTK, VTK-m, Sage, Gmsh and Math3D releases with confidence indicators and evidence coverage.

**2026-11-06 scoped delivery:** `release_matrix.py` verifies release reports and inventory hashes, saves six-provider snapshots, and compares versions, L-level coverage, qualification record IDs and source runs with explicit confidence. A MATH3D product contract link is distinguished from a MATH3D release identity; VTK-m has no registered inventory. The observed comparison between two distinct release tags is **inconclusive**: both fresh release certifications are blocked by missing current L9 evidence and the available inventory predates them. The matrix does not label a version change as a scientific regression without qualification evidence.

**DS-SCI-050 — `feat(scientific): add scientific reproducibility report generator`**\
Human-readable Markdown/HTML report containing capabilities, gate verdicts, fixtures, fingerprints, numerical tolerances, regressions and reproducibility instructions.

**2026-11-06 scoped delivery:** `reproducibility_report.py` verifies the sealed release matrix, adapter conformance, contract migration, environment lock and recreation, provenance chain, and a saved-run mesh differential before rendering Markdown and escaped HTML. It records source hashes and seals both outputs; `verify` rechecks the source evidence and exact rendered bytes. The report names the fixed fixtures and artifact hashes, host/run/contract fingerprints, comparator tolerance, product viewer regression, and commands to replay verification. The observed release comparison remains **inconclusive** because both releases lack current L9 evidence and inventory is stale. Historical broker certification and passing conformance do not override those gates. General field/exact differential runs and reviewed failure fixtures were not supplied to this report.

**DS-SCI-051 — `feat(scientific): refresh release qualification evidence`**\
Capture a fresh runtime inventory and rebuild the qualified CGAL mesh evidence chain against one source commit and matching broker/MATH3D contracts. Re-run L0–L9 as needed, attach the actual agent and environment, and produce a release report that either certifies current evidence or gives per-gate blocked reasons. The acceptance case verifies inventory age, contract and run fingerprints, source commit, and a new end-to-end viewer result; no older L9 or historical manifest may be substituted.

**2026-11-06 scoped delivery:** A new local inventory, desktop managed CGAL probe, compile/link, fixed positive and rejection worker cases, artifact reproduction/reload, CGAL → VTK → MATH3D interoperability, resilience, and MATH3D product viewer run produced a fresh L0–L9 chain. The desktop exporter found one current `mesh.interop.vtk-math3d` L9 capability with ten linked supporting records. A new broker config pinned that manifest; a fresh broker → MATH3D viewer and `.m3dm` round-trip smoke passed. Release certification now pins the runtime inventory, records its age, local agent host fingerprint, source commit, and a verdict for each L0–L9 gate. It blocks certification when inventory is stale or the current chain differs. Release matrix snapshots also retain inventory bytes so later captures do not invalidate their evidence. The observed refresh qualified CGAL only; VTK and Gmsh remain unqualified at the release gate. The new reproducibility report links every current gate and supporting run. Release evidence remains local under `.scientific` because it contains host-specific paths and fingerprints.

**DS-SCI-052 — `feat(scientific): qualify a second comparable mesh backend`**\
Extend the VTK mesh path through current L0–L9 worker, round-trip, interoperability, resilience, and product gates under the same typed broker contract. Add matching fixed-tier performance evidence so advisor and release reports can compare two certified providers on the same host/environment policy. Acceptance requires two independently verified capability records with source runs, reproducible artifacts, and comparable measurements; Gmsh remains excluded until its package and probes pass. This ticket is planned, not yet delivered.

**DS-SCI-053 — `feat(scientific): compare certified mesh providers on shared fixtures`**\
Compare CGAL and VTK outputs from the same registered fixture. Bind geometry, topology, orientation and scale verdicts to successful source runs, saved fingerprint and artifact hashes, numerical tolerance and independent current L9 release records. Compare fixed-tier performance only when both certified providers have benchmark runs with the same fixture, host, operation, tiers and policy; otherwise report **inconclusive**. A stale or missing release certification blocks the overall gate even when the meshes agree.

**2026-11-06 scoped delivery:** `cross_provider.py` verifies saved CGAL OBJ and VTK VTP L6 runs, source fingerprints and artifact hashes, then compares the shared tetrahedron at tolerance `1e-6`. Geometry, topology, orientation and scale pass on the observed pair. The sealed report links both run IDs, artifacts and contract fingerprints. Its overall verdict is **blocked**: VTK has no L9 release record, and the prior CGAL broker certification is now stale after the shared worker contract gained Gmsh support. Performance is **inconclusive** because no pair of current provider-certified, matched-policy benchmark runs exists. Verification re-evaluates current broker evidence and rejects changed records or source artifacts. Complete DS-SCI-052 and refresh CGAL after contract drift before asserting a certified cross-provider verdict.

**DS-SCI-054 — `feat(scientific): establish Gmsh qualification foundation`**\
Install the matching Gmsh Python binding, rerun native probes, register a bounded typed 2D worker and establish L0–L4 foundation evidence: manifest/environment discovery, Python and package readiness, positive and expected-rejection probes, C++ compile/link/run. Save fixed fixture, package/toolchain/source hashes, typed result, output artifact and independent reload. Do not export Gmsh to certified capability manifests until its later worker, reproduction, interoperability, resilience and product gates pass.

**2026-11-06 scoped delivery:** The shared Windows scientific Conda prefix already contained Gmsh 4.15.2 native binaries, headers and import library; the missing `gmsh` Python binding was installed at matching version 4.15.2. The native `runtime-lab` probe now passes Python/version, bounded surface meshing and expected missing-file rejection. The registered fixed-square `.geo` worker accepts only a bounded mesh size, writes a typed `.msh` result, and rejects an invalid parameter with no output. A separate Gmsh C++ smoke target compiled, linked and executed; an independent Gmsh import reloaded and checked the saved 2D mesh. `gmsh_foundation.py` saves and verifies sealed local L0–L4 evidence with source, package, toolchain, fixture, request, result and artifact hashes. This foundation record is **not** a desktop L0–L4 qualification chain or a release certification; L5–L9 and MATH3D volume-mesh interoperability remain open. Gmsh remains absent from certified manifests.

**DS-SCI-055 — `feat(scientific): check Gmsh typed worker conformance`**\
Extend the fixed public square worker evidence with bounded positive output, a tampered source fixture and an unsupported parameter. Require typed terminal results, diagnostics, fixture and worker contract hashes, and no artifact for rejected cases. Link the evidence to the verified DS-SCI-054 foundation record.

**2026-11-06 scoped delivery:** `gmsh_progression.py` verifies the foundation's successful typed run and executes fresh tampered-fixture and unknown-parameter rejections. Each case saves a request, result and log with hashes; both failures report diagnostics and leave no `.msh`. The sealed DS-SCI-055 record passed. This is a local worker conformance record, not a desktop L5 qualification.

**DS-SCI-056 — `feat(scientific): reproduce and reload Gmsh surface artifacts`**\
Rerun the fixed 2D worker twice in separate directories under one pinned fixture, source and package environment. Compare the output bytes and independently reload both `.msh` files to check bounded geometry. Save both run IDs and output hashes; reject drift before declaring the local repeat gate passed.

**2026-11-06 scoped delivery:** Two fresh Gmsh 4.15.2 runs produced the same SHA-256 `.msh` bytes and the same independent reload result. The sealed DS-SCI-056 record links both requests/results, output files, the DS-SCI-055 record, and the DS-SCI-054 foundation. Verification repeats the reload and hash checks. This is local L6-style evidence; managed desktop L6 qualification has not been granted.

**DS-SCI-057 — `feat(scientific): test Gmsh 2D mesh consumers`**\
Convert the verified fixed `.msh` surface to a bounded OBJ, feed that artifact to an independent VTK reader and MATH3D's actual mesh importer, then compare point/triangle counts, boundary and nonmanifold topology, bounds, signed XY area and artifact hashes. Add a malformed handoff rejection for both consumers. Link each consumer source and result to the DS-SCI-056 output.

**2026-11-06 scoped delivery:** The observed square had 44 points, 66 triangles, 20 boundary edges, zero nonmanifold edges, unit XY area and bounds `[0,1] × [0,1] × {0}` in Gmsh, VTK 9.6.1 and MATH3D. Both consumers rejected a malformed OBJ. The sealed DS-SCI-057 record links the source `.msh`, converted OBJ, consumer source fingerprints, results and expected rejections. This is a 2D surface importer check, not a viewer, document round trip, volume-mesh gate or release L7 certification. Gmsh remains outside certified manifests.

**DS-SCI-058 — `feat(scientific): save managed Gmsh probe qualifications`**\
Route the installed Gmsh Windows prefix through the provider registry and native `runtime-lab` action. Require a successful bounded probe, matching installed manifest, recorded Python/Gmsh module and package fingerprints, and immutable L0–L3 qualification records visible as current in History. Keep unrelated provider controls out of the Gmsh view.

**2026-11-06 scoped delivery:** Gmsh now has a provider-scoped Commands view and native managed prefix resolution. A fresh desktop probe passed Python 3.12.15, Gmsh 4.15.2, fixed 2D meshing and expected rejection. It saved L0, L1, L2 and L3 records with a run fingerprint, and History displayed the records as current. The L3 capability is `gmsh.surface2d`, leaving semantic `mesh.generate` for the worker gate. This does not certify general Gmsh meshing.

**DS-SCI-059 — `feat(scientific): qualify Gmsh C++ compile and link`**\
Run the registered Gmsh C++ smoke target from the desktop with an owned process, compiler/CMake toolchain fingerprint, linked executable hash and immutable L4 record. Use the available sibling scientific CMake installation when this Gmsh prefix has no own CMake; record the actual executable. A changed source or binary must stale the level.

**2026-11-06 scoped delivery:** The managed `compile-link` action configured and built `devshell_gmsh_smoke.exe` with the sibling CGAL prefix CMake and the Gmsh prefix header/import library. A fresh L4 record pins the two successful build steps, compiler version, executed CMake and linked binary hashes. History displayed it as current. Gmsh's package binding and CMake identities now participate in environment drift checks.

**DS-SCI-060 — `feat(scientific): qualify the fixed Gmsh worker cases`**\
Register a fixed public `.geo` positive case and a changed-geometry rejection case under the Gmsh runtime manifest. Run both through the shared typed worker contract in owned child jobs, link current L0–L4 records, save request/result/fixture/artifact hashes, and grant only `mesh.generate` L5 when both cases and lower evidence verify. Leave L6–L9 and certified manifests untouched.

**2026-11-06 scoped delivery:** The desktop L5 action used separate hash-checked dataset copies, generated a 44-point/66-triangle `.msh` from the fixed square, and rejected the changed rectangle without an artifact. The managed L5 record pins the worker contract, two child results, positive artifact hash and five current lower records. History displayed L5 as current. The earlier DS-SCI-056/057 local repeat and importer evidence remains separate: managed L6 reproduction, L7 interoperability, L8 resilience and L9 viewer/document gates have not been granted. Gmsh is still excluded from release certification and promotion.

**DS-SCI-061 — `feat(scientific): qualify managed Gmsh L6 reproduction and reload`**\
Rerun the fixed positive and rejection cases through owned desktop jobs. Compare the `.msh` bytes with a current L5 run, independently reopen the saved mesh with Gmsh, and verify point/triangle counts, boundary and nonmanifold edges, XY orientation, unit area and bounds. Pin the L5 record, worker contract, environment and reload parser before granting `mesh.generate` L6.

**2026-11-06 delivery:** The new desktop L6 action passed with an exact `.msh` hash match, expected rejection, and independent Gmsh reload of 44 points, 66 triangles, 20 boundary edges, zero nonmanifold edges, unit XY area and `[0,1] × [0,1] × {0}` bounds. Its current History L6 record links the prior managed L5 run. The reload parser and handoff source are included in Gmsh source drift fingerprints.

**DS-SCI-062 — `feat(scientific): qualify managed Gmsh L7 consumer interoperability`**\
Consume a current L6 `.msh` through a checked OBJ export, VTK `vtkOBJReader`, and MATH3D's desktop surface importer. Compare geometry, topology, orientation and scale at each consumer; require both to reject malformed OBJ. Pin each consumer result, source hash, VTK environment and MATH3D importer contract in a managed qualification record.

**2026-11-06 delivery:** The desktop L7 action passed the fixed 2D surface in VTK and MATH3D with 44 points, 66 triangles, 20 boundary edges, positive unit XY area and matching bounds. Both rejected a malformed face. The current L7 record links the L6 artifact and all seven registered handoff files; History assesses importer source and VTK consumer environment drift.

**DS-SCI-063 — `feat(scientific): qualify managed Gmsh L8 resilience`**\
Reread the qualified L7 OBJ through the VTK consumer three times under time and memory budgets, then exercise owned process cancellation, timeout and a forced allocation limit. Save repeat hashes, peak memory, terminal states, absent partial outputs and source L7 record. Grant L8 only when all cases and current lower records verify.

**2026-11-06 delivery:** Three bounded VTK reads produced identical result hashes. The cancellation and one-second timeout stopped their owned children without output; the 128 MiB memory job rejected a 512 MiB allocation with no artifact. The managed L8 record and History's highest-current-level summary passed on a fresh debug-port desktop run. This is fixed 2D consumer resilience, not a Gmsh volume-mesh or MATH3D viewer/document gate. Gmsh remains outside broker certified manifests and promotion until L9 product evidence passes.

**DS-SCI-064 — `feat(scientific): qualify Gmsh fixed-surface L9 product integration`**\
Run a fresh fixed-square typed Gmsh worker job from the managed desktop, verify its `.msh` and converted OBJ against current L7/L8 evidence, and hand the OBJ to MATH3D under a versioned contract. Save Mesh document, resource, viewer regression and source hashes with an immutable L9 record. Grant L9 only while all L0–L8 evidence and the importer/codec contracts are current.

**2026-11-06 delivery:** The managed desktop L9 action passed on a fresh debug-port run. MATH3D imported the 44-point, 66-triangle OBJ, saved a Mesh document/resource, mounted the viewer and captured its render. The L9 record pins the worker `.msh`, converter OBJ, handoff, consumer source, document, viewer and current L8 chain. History reports `mesh.generate` at current L9. The scope is the registered public fixed 2D surface; volume and arbitrary Gmsh meshes are unqualified.

**DS-SCI-065 — `feat(scientific): verify Gmsh native document round trip`**\
Save the MATH3D document as versioned `.m3dm`, reopen it independently of the MATH3D writer, and compare the saved vertices/faces to the verified OBJ. Check format, geometry, topology, XY orientation, area and scale; pin the codec, parser and document hashes in L9 evidence.

**2026-11-06 delivery:** The independent Python parser reloaded the native `.m3dm` and matched 44 vertices, 66 triangles, 20 boundary edges, zero nonmanifold edges, positive unit XY area and `[0,1] × [0,1] × {0}` bounds. The L9 record and broker smoke pin the native document SHA-256, codec source and parser result. A modified saved document fails smoke verification.

**DS-SCI-066 — `feat(scientific): certify and promote the fixed Gmsh broker capability`**\
Export only a current Gmsh L9 fixed-surface capability with ten supporting records and exact worker, converter, artifact, broker and MATH3D source identities. Expose typed broker discovery, job results, progress, cancellation, timeouts and hash-verified transport. Promotion must reject stale evidence, changed input/output and contract drift. Verify a broker job through MATH3D document import and viewer, then publish a release qualification report.

**2026-11-06 delivery:** The exporter published one scoped `gmsh-win-conda mesh.generate` L9 entry with ten current supporting levels. A fresh broker job reproduced the qualified `.msh` and OBJ hashes, completed cleanup, passed promotion, and saved a MATH3D Mesh document, viewer render and independently reloaded `.m3dm`. The sealed smoke verifier passed; tests rejected an invalid input hash, changed source snapshot, modified OBJ and modified native document. The fresh release report found ten current gate verdicts and qualified this fixed 2D capability. The general Gmsh geometry and volume paths remain outside the certified manifest.

**DS-SCI-067 — `feat(scientific): establish typed Gmsh cube-volume worker cases`**\
Register a separate public unit-cube `.geo` fixture and candidate `gmsh.volume3d.cube` worker under the shared typed request/result contract. Bound mesh size, accept tetrahedra only, save a hash-checked `.msh`, and require changed-geometry and invalid-parameter rejections without artifacts. Keep this candidate out of managed qualification and certified manifests.

**2026-11-06 local delivery:** Two owned positive worker invocations and both rejection cases passed. The candidate generated 83 nodes and 204 tetrahedra at mesh size 0.35; the typed result recorded the Gmsh version, input and output hashes, scope and validated candidate capability. Both rejected requests saved diagnostics and no `.msh`. A sealed DS-SCI-067 record links the public fixture, worker contract, requests, results and source commit. This does not grant a volume qualification level.

**DS-SCI-068 — `feat(scientific): reproduce and reload Gmsh tetrahedral volume`**\
Repeat the fixed cube worker case in a separate job, compare exact `.msh` hashes, then reopen the artifact independently with Gmsh. Verify tetrahedron connectivity, closed two-face internal incidence, outward boundary, unit volume, surface area six and unit-cube bounds. Save the parser identity, source runs and immutable candidate evidence.

**2026-11-06 local delivery:** Separate runs produced identical `.msh` bytes. Independent reload found 204 tetrahedra, 156 boundary triangles, zero open or nonmanifold boundary edges, volume 1, surface area 6 and `[0,1]³` bounds. The sealed DS-SCI-068 record chains to DS-SCI-067 and checks source and artifact hashes. This is local reproduction evidence, not a managed L6 record.

**DS-SCI-069 — `feat(scientific): check Gmsh volume-boundary consumers`**\
Extract only the outward triangle boundary from the verified tetrahedral `.msh`, hand a bounded OBJ to VTK and the MATH3D surface importer, and compare point/face counts, bounds, topology, orientation, area and enclosed volume. Require both consumers to reject a deliberately flipped face. Pin each consumer's result, contract source and artifact hash without treating the surface importer as a tetrahedral document editor.

**2026-11-06 local delivery:** The boundary OBJ had 80 points and 156 outward triangles. VTK 9.6.1 and MATH3D matched the unit-cube bounds, closed topology, area 6 and signed volume 1; both rejected a flipped face. The sealed DS-SCI-069 record chains to DS-SCI-068 and rejects changed OBJ evidence. MATH3D consumed the boundary surface only; tetrahedral cells, managed L7–L9, document/viewer round trips and volume certification remain open.

**DS-SCI-070 — `feat(scientific): register a separate Gmsh volume capability`**\
Declare semantic `mesh.generate3d` separately from the certified fixed-surface `mesh.generate` capability. Register the bounded cube worker and public fixture in the provider manifest, and add a genuine 3D probe that grants L3 only when Gmsh generates tetrahedra. Keep the new capability out of certified manifests until its full product chain qualifies.

**2026-11-06 delivery:** The Gmsh manifest declares separate L5/L6 volume recipes and probes tetrahedral generation. Runtime-lab saved the `gmsh.volume3d.cube` L3 result, while the capability registry presents `mesh.generate3d` as a distinct, fixed-cube scope. The fixed 2D `mesh.generate` certificate is unchanged in scope.

**DS-SCI-071 — `feat(scientific): qualify managed Gmsh volume L5 worker evidence`**\
Run the bounded cube worker and both expected rejections from the desktop through an owned job. Register the public fixture and output, save immutable typed results and source hashes, and grant `mesh.generate3d` L5 only when current L0–L4 records and the sealed local worker evidence verify. Show the result and supporting runs in History.

**2026-11-06 delivery:** The desktop L5 action saved a verified `.msh`, the DS-SCI-067 record and the rejection evidence in the managed run directory. History verified the suite, fixture, worker contract, artifact and current lower records before showing `mesh.generate3d` L5. The fixed 2D qualification path was not used as a volume shortcut.

**DS-SCI-072 — `feat(scientific): qualify managed Gmsh volume L6 repeat and reload`**\
Rerun the same cube through a separate managed job, compare its exact `.msh` hash with the current L5 run, and independently reload tetrahedral connectivity, boundary orientation, volume, area and bounds. Pin both runs, parser, suite revision and artifacts in a verified L6 qualification record. A changed or stale baseline must block L6.

**2026-11-06 delivery:** The desktop L6 job reproduced the L5 `.msh` byte hash, independently reopened the tetrahedra, and saved a linked, verified qualification. History reported current L6 for `mesh.generate3d` after checking its L5 baseline and L0–L4 support. L7–L9 and volume promotion remain open; the MATH3D surface importer is only boundary-consumer evidence.

**DS-SCI-073 — `feat(scientific): qualify managed Gmsh volume L7 boundary interoperability`**\
Start from a current managed L6 cube record. Retain the tetrahedral `.msh`, extract its outward OBJ boundary, compare geometry, topology, orientation and scale in VTK and the MATH3D surface importer, and require both to reject a flipped face. Save a sealed, linked L7 record with each consumer's source and result. This is interoperability of the boundary, not tetrahedral document import.

**DS-SCI-074 — `feat(scientific): qualify managed Gmsh volume L8 resilience`**\
Start from current L7 evidence. Run three bounded VTK boundary reads and require identical results; exercise owned cancellation, timeout, memory limit and partial-output cleanup. Save observations, process limits, source hashes and current L0–L7 support in a verified L8 record.

**DS-SCI-075 — `feat(scientific): record Gmsh volume product readiness`**\
Check the current L8 tetrahedral source against an explicit MATH3D volume-consumer contract that preserves cells and declares a native volume document. Save an inspectable blocked verdict and the exact missing product requirement. A surface Mesh document or OBJ viewer cannot grant volume L9; defer L9 certification until native tetrahedral import, document round trip and viewer regression are implemented and verified.

**DS-SCI-076 — `feat(scientific): define a cell-preserving Gmsh-to-MATH3D resource`**\
Export a bounded, versioned `M3DT` resource with all vertex coordinates and tetrahedral indices from the fixed public cube. Require positive cells, exact byte length and SHA-256 transport. Declare a separate MATH3D tetrahedral document contract and importer; derive the outward boundary from saved cells rather than replacing the volume with an OBJ shell.

**DS-SCI-077 — `feat(scientific): independently reload the tetrahedral document`**\
Save the MATH3D document and binary resource, reopen them through its adapter, reject a changed resource, and independently parse the saved bytes in a separate implementation. Compare 83 vertices, 204 tetrahedra, 156 closed boundary triangles, orientation, unit volume and bounds with the source worker artifact. Pin the exporter, parser and consumer source hashes.

**DS-SCI-078 — `feat(scientific): qualify Gmsh volume L9 product integration`**\
Start from current L0–L8 volume evidence and a fresh fixed-cube worker run. Verify the versioned handoff, import the cell-preserving document in MATH3D, reopen it, mount the tetrahedral boundary viewer and capture a regression image. Grant L9 only when the document, resource, independent reload, viewer and consumer contract all verify. Keep volume outside broker certification until a separate manifest/promotion ticket proves transport from this L9 record.

**DS-SCI-079 — `feat(scientific): certify and promote fixed-cube Gmsh volume through broker`**\
Export `mesh.generate3d` only from a current managed L0–L9 chain for the public fixed cube. Keep its tetrahedral product contract, M3DT resource and broker profile separate from the certified 2D surface recipe. Pin the worker, adapter, exporter, Python and package inventory, input, MATH3D consumer sources, L8/L9 records and exact reference output hashes. The broker must verify the typed request/result, transport `.msh` and M3DT artifacts, reject changed inputs or source evidence, and allow promotion only after checking the cell-preserving handoff and current consumer identities. Finish with native MATH3D document save/reopen, independent tetrahedral reload, viewer regression and a fresh release qualification report.

**2026-11-07 scoped delivery:** A current fixed-cube L9 chain exported one `mesh.generate3d` entry. A fresh broker job reproduced the qualified 83-vertex, 204-tetrahedron `.msh` and M3DT hashes, served the resource with hash verification, and passed MATH3D promotion, document reload, viewer and independent parser checks. The saved product smoke and a fresh runtime inventory passed release qualification. Input hash, wrong capability, outside-dataset, source-snapshot and artifact tamper checks were exercised. This certificate covers only the public unit cube at mesh size 0.35 on the recorded Windows Gmsh and MATH3D consumer identities; it does not certify arbitrary tetrahedral meshes or VTK as a second broker backend.

**DS-SCI-080 — `feat(scientific): explain volume certification drift`**\
Expose a read-only exporter audit for `mesh.generate3d`. Show each recent managed L9 candidate's state and reasons, the L0–L8 supporting record states, rejected evidence and final product/consumer eligibility. Return no certificate when shared source, suite, runtime or consumer identities change. Do not rewrite immutable runs or treat an audit as requalification.

**2026-11-08 scoped delivery:** The audit reports the previous fixed-cube L9 evidence as stale after the upstream Sage integration changed shared fingerprint, qualification and runtime source files. The current export correctly contains no certified volume entry. A fresh managed Gmsh chain is needed before republishing the volume profile.

**DS-SCI-081 — `feat(scientific): run gated Gmsh volume requalification`**\
Use the read-only export audit to choose either the full managed volume L0–L9 chain or its L7–L9 suffix. Require a prepared `desktop-five` DevShell CDP session for the existing managed UI check. Afterward, re-audit before exporting, verify the broker, run a fresh cell-preserving MATH3D smoke, capture a current runtime inventory and qualify a release. Save a sealed plan and an execution report; stop on any failed gate.

**2026-11-08 scoped delivery:** Planning selected the full chain for the stale volume evidence and the planner checks passed. A run without a desktop CDP endpoint saved a failed result before changing the broker manifest. Live managed requalification and the refreshed release certificate remain pending.

**DS-SCI-082–083 — `fix(scientific): tighten volume requalification preflight`**\
Require an ordered L0–L8 supporting chain before choosing the short L7–L9 rerun. Accept only a loopback CDP URL with an actual DevShell app page, and require the broker config to name this source checkout. Malformed evidence or mismatched paths must stop before publication.

**DS-SCI-084 — `fix(scientific): stage volume manifest until release qualifies`**\
Export to a candidate manifest and use it for broker verification, MATH3D smoke and release certification. Keep the deployed manifest intact until every gate passes. Detect a concurrent manifest change and restore prior bytes if final verification fails.

**DS-SCI-085 — `fix(scientific): verify release gates by capability`**\
Record the release capability ID and recompute its own L0–L9 gate verdicts during verification, so a current Gmsh surface entry cannot obscure the separately qualified volume chain. Keep historical single-capability release reports verifiable.

**2026-11-08 scoped delivery:** Unit checks passed for ordered resume evidence, CDP URL rejection, manifest publication/rollback and two-capability release verification. Live managed requalification remains pending a prepared `desktop-five` session; the previous fixed-cube certificate is still stale after shared source changes.

**DS-SCI-086–087 — `feat(scientific): capture run-scoped release inventory`**\
Allow release certification to read an explicit inventory path. Capture the volume runner's fresh runtime report inside its output directory, pin its hash in execution evidence and use that exact capture for release qualification.

**DS-SCI-088 — `feat(scientific): bind volume product smoke to release`**\
Require a verified broker/MATH3D smoke record for new volume releases. Pin its file hash, source job and certification record in the qualification report and release manifest; reject drift during release verification.

**DS-SCI-089 — `feat(scientific): verify volume requalification result`**\
Verify a saved execution report against its sealed plan, ordered gates, linked evidence and release. With a broker config, require a passed result to match the current deployed manifest. Permit offline verification of an honestly failed run.

**2026-11-08 scoped delivery:** The new inventory path was exercised against the installed scientific environments. Unit checks covered inventory selection, product-smoke linkage and tamper detection, and failed-result verification. A passed volume release still awaits a prepared `desktop-five` session and a fresh managed L0–L9 chain.

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
