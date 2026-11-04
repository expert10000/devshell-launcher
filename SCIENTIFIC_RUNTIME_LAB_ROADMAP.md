# Scientific Runtime Lab: architecture extension

Original plan updated 2026-10-16. This extends [SCIENTIFIC_RUNTIMES_ROADMAP.md](SCIENTIFIC_RUNTIMES_ROADMAP.md); it does not replace the existing scientific jobs, CGAL/VTK workers, or their recorded evidence.

## 2026-11-03 expansion and delivery ledger

The [Scientific Runtime Lab architecture and implementation roadmap](docs/SCIENTIFIC_RUNTIME_LAB_ROADMAP_2026-11-03.md) extends this plan with semantic capabilities, L0–L9 qualification, immutable fingerprints, provider-specific suites, a standalone broker contract, and MATH3D promotion gates. Its screenshot observations and 35/35 verdict describe historical review evidence; they do not establish current installation or certification on this machine.

The UI registry now owns the five existing runtime declarations, visible sections, probes, fixed Catalog tests and artifact routes. CGAL Boolean and MATH3D native integration stay with CGAL; Catalog and History show only the selected provider's entries. VTK has its own mesh artifacts and fixed tests. Gmsh, Python/SciPy and Sage show their own probes or an explicit **Not configured** state on unsupported backends. The native registry rejects actions from the wrong provider and checks its versioned runtime manifests. These declarations do not certify a runtime or establish a standalone broker.

| Roadmap item | Current state | Next acceptance target |
|---|---|---|
| DS-SCI-001 runtime plugin contract | UI registry owns five providers' sections, probes, fixed catalog tests, recipe views and artifact routes; versioned native registry scopes managed actions and checks each runtime manifest; desktop provider switching checked | Shared generated UI/backend contract remains follow-up hardening |
| DS-SCI-002 runtime view leakage | Manual desktop switching checked for CGAL, VTK, Gmsh, Python/SciPy, Sage Windows/WSL and Docker; provider Catalog/coverage and locked History observed; historical CGAL 35/35 result opened in DevShell; repeatable CDP desktop check passed on a debug-port launch | Keep the CDP check as the provider-routing regression gate |
| DS-SCI-003 immutable fingerprints | New managed runs save a non-overwritable `fingerprint.json` and result digest. History verifies it and derives separate current/stale/unknown source and environment drift without rewriting evidence. Fingerprints include source, recipe suite revision, Conda package records, relevant toolchain hashes, contract and executed-file identities. Sage/WSL records the provider, system or Conda package inventory, and shell tools. Fresh managed desktop runs and the History drift view were checked on all five providers on 2026-11-04. | Use these identities as DS-SCI-004 qualification inputs; require successful capability evidence before advancing any level |
| DS-SCI-004 qualification records and current levels | Successful managed runs with verified fingerprints save immutable per-capability records pinned to their run, suite revision, registered probe/recipe and contract. History verifies each file and derives current/stale/unknown status and reasons. A provider-scoped summary selects the highest current level per capability across saved runs and links to supporting runs; non-successful, stale and unknown evidence cannot raise a level. Fresh CGAL/VTK run-scoped C++ configure/build/link recipes added L4 records; Gmsh remains unqualified. | Extend gates through L5–L9 and add richer fixture/artifact contracts |
| DS-SCI-005–007 qualification foundations | Planned | Add provider-specific suites, versioned worker/artifact contracts and higher-level evidence gates |
| DS-SCI-008–010 comparisons and export | Planned | Compare pinned run inputs and fingerprints; export redacted, hash-verifiable evidence bundles |
| DS-SCI-011–025 provider and MATH3D path | Existing narrow probes; broader qualification planned | Expand real VTK/Sage/Gmsh suites and qualify typed broker-to-MATH3D artifact round trips |

Do not mark an item complete from a passing package probe or a UI declaration. Each later change needs a named run, fingerprint, fixture revision, contract version and evidence link before its qualification level can advance.

### DS-SCI-003 local evidence audit (2026-11-04)

The debug-port desktop run created these local `.scientific/runs` records. `tests/scientific-fingerprint-live-ui-checks.mjs` started each managed recipe and checked its saved digest and package identity. `tests/scientific-fingerprint-history-ui-checks.mjs` reopened each result through History, where source and package/toolchain drift are derived from current files. All five package/toolchain comparisons read **current** immediately after the run; this does not certify the provider's capabilities.

| Provider | Run ID | Recipe / result | Package identity |
|---|---|---|---|
| CGAL / Windows | `6cb8ae98072544acb19489dca0084e81` | `version` / succeeded | 54 Conda records |
| VTK / Windows | `1a89b77e096a468e804842578c308142` | `version` / succeeded | 159 Conda records |
| Gmsh / Windows | `9ba9f86062004919a35ccc6dc953bf06` | `lab.probe` / failed: `gmsh` module missing | 104 shared Conda records; Python probe passed |
| Python/SciPy / Windows | `bc184fc009aa41709448d1dcc847ea9e` | `lab.probe` / succeeded | 104 shared Conda records |
| SageMath / WSL Ubuntu | `2bfe3dc2745f4691836af685058c104c` | `sage.version` / succeeded | WSL system package inventory digest; provider and shell hashes |

The current Windows comparison checks the package inventory, Python executable, runtime-lab, OS and architecture; CGAL/VTK also check CMake, Ninja and MSVC. Opening a Sage result performs a bounded, read-only WSL identity probe. Missing current evidence is **unknown**, and a changed recorded hash is **stale**. Gmsh's failed capability probe remains failed even though its environment identity is current. The five run folders are local evidence, not committed fixtures.

### DS-SCI-004 local qualification audit (2026-11-04)

`qualifications.json` is written once per eligible successful run and referenced by a digest in `results.json`. Each record names one capability, level, probe or recipe, run fingerprint, suite revision, and contract. History verifies the file before listing the run, then derives status and stale reasons from source, environment and contract comparison. L0 means package inventory was recorded during a successful managed invocation; L1–L3 apply only to the explicit probe or Sage operation shown. They are not provider-wide certification.

| Provider | Run ID | Qualification scope |
|---|---|---|
| CGAL / Windows | `7c4b46da9b5b4a96a95753cf750a3464` | L0 inventory; L1 Python executable; L2 CGAL import; L3 Point_3 smoke |
| VTK / Windows | `729433c7ffaf45fa8a24dd953f5b4201` | L0 inventory; L1 Python executable; L2 VTK import; L3 vtkPolyData construction |
| Python/SciPy / Windows | `3e689f99b26748f29a077354227128b2` | L0 inventory; L1 Python executable; L2 SciPy import; L3 dense solve and expected singular rejection |
| SageMath / WSL Ubuntu | `da6fafe7c12d4004ac76edab2ab2793f` / `6a7da47c86884525ad69e817287aa241` | L0 inventory and L1 executable version; L2 Sage binding and L3 exact factorization |
| Gmsh / Windows | `8136a3e04be945109bbed32e27cb7e7e` | Failed because the `gmsh` module is missing; **zero qualification records** |

The opt-in `tests/scientific-qualification-live-ui-checks.mjs` started these L0–L3 runs and reopened each successful result in History. The focused artifact/qualification checks cover manifest gating, immutable records, stale reasons and tamper rejection. The run folders remain local evidence; the check does not install Gmsh.

### Current-level rollup and L4 C++ evidence (2026-11-04)

History now shows the highest **current** record for each capability of the selected provider, with buttons that open its supporting runs. The summary recomputes source, package/toolchain and contract status when requested; it omits stale, unknown and non-successful evidence. Earlier records made stale by this implementation change do not raise a level. The desktop summary check reopened current L3 evidence for CGAL (`36c830ad6eeb4022ad2f7c807e6195d3`), VTK (`a333be18336c4d598c05afd85b30b6a0`), Python/SciPy (`bf80663b3b214f36ade2c6270b1ec731`) and Sage (`abf255e826f542c6897ef98f8a637d0a`).

| Provider | Fresh L4 run ID | Recorded scope |
|---|---|---|
| CGAL / Windows | `b24ae95145ba4b249c9b0d6e568ac080` | Run-scoped CMake configure and MSVC build/link of the CGAL smoke executable; linked binary SHA-256 pinned |
| VTK / Windows | `804ef09b7c4d470b91efc9ea565d48cd` | Run-scoped CMake configure and MSVC build/link of the VTK smoke executable; linked binary SHA-256 pinned |

Both L4 records were verified through History and their summary links. L4 proves the named C++ smoke target compiled and linked in that run; it does not establish worker recipes, rendering, or broader scientific correctness. The latest Gmsh probe (`b5f780faecc44bc594c8b2d146f6b50a`) still failed because the `gmsh` module is missing and produced no qualification record. The focused checks reject a changed linked executable and confirm that stale or failed runs cannot raise the cross-run level.

## Boundary

DevShell is the control plane. `runtime-lab` is a separate process supervising runtime adapters. CGAL, VTK, and future native libraries stay in child processes, never in DevShell's UI process. MATH3D can later consume the same versioned request/result contract rather than DevShell UI code.

```
DevShell UI -> native bridge -> runtime-lab -> isolated adapter child
                                  |                |
                                  +-- results.json +-- stdout/stderr
```

The shipped first slice is `tools/runtime-lab/RuntimeLab.csproj` and the checked-in `runtimes/{cgal-win-conda,vtk-win-conda}/runtime.json` manifests. The supervisor supports `inventory`, `probe`, and a registered `cgal.validate` run recipe. It runs adapters in separately owned processes from an explicit Conda prefix, applies a timeout, kills the process tree on timeout/cancellation, limits retained output, and uses an atomic run-scoped `results.json`. A successful probe or validation run certifies only its recorded scope, not the whole runtime. `BatchLauncher` builds and copies this separate executable and its manifests; no CGAL/VTK assembly is loaded into DevShell.

Example after building (the prefix is intentionally explicit):

```powershell
./tools/runtime-lab/bin/Debug/net8.0/runtime-lab.exe inventory --manifest-root ./runtimes
./tools/runtime-lab/bin/Debug/net8.0/runtime-lab.exe probe cgal-win-conda --manifest-root ./runtimes --prefix G:\master\conda\math3d-cgal --output ./.scientific/lab-runs/manual-cgal
```

These probes are narrower than the existing full installation report. The VTK manifest does not establish C++ SDK, OpenGL, or offscreen rendering readiness. The CGAL validation recipe records one mesh-worker result and artifact; it does not establish remeshing, all geometry operations, or broad reproducibility.

## Delivery stages

- [x] Separate executable, checked-in manifests, isolated child probes, bounded output, timeout/kill, per-run result and environment snapshot.
- [x] Connect DevShell Scientific Runtimes to `runtime-lab` through a managed native action, with live logs, Stop, and History using the existing job service. Probes run only when clicked, not on workspace opening.
- [ ] Add declarative `run`, `test`, and `bench` recipes with typed parameters, validated input/output paths, immutable invocation records, and reproducible artifacts. Keep argv execution; never substitute shell command strings.
- [ ] Implement readiness levels L0-L9 as evidence gates. Health and Commands now load the newest saved managed probe from History and prefer a live result when present; functional L5-L9 evidence gates remain pending.
- [ ] Extend the CGAL adapter with C++ SDK/compiler/CMake checks, compile/link, Surface_mesh, mesh validate/remesh/repair/boolean/simplify, and geometry AABB/distance/intersection recipes as implementations become available.
- [ ] Extend VTK independently across Python, C++ SDK, polydata I/O, interactive rendering, and offscreen rendering. Store a render image as an artifact, not just an exit code.
- [ ] Add Gmsh, SageMath, and Python/SciPy manifests only with working adapters and truthfully scoped capability evidence. Support Windows Native, WSL, and Docker as separate execution profiles rather than assuming path compatibility.
- [ ] Add a Test Matrix keyed by runtime/profile/recipe/dataset, with captured versions, environment fingerprint, pass/fail/skip, timings, and artifact links. The first CGAL validation slice declares three fixture expectations and reads saved results; more runtimes and cases remain. No cached result should masquerade as a live check.
- [ ] Add interoperability cases CGAL -> VTK -> MATH3D and reverse where meaningful, with explicit file formats, topology/units/orientation checks, and round-trip tolerances.
- [ ] Add repeatable benchmarks with warmup, multiple samples, environment snapshot, baseline comparison, and memory/time metrics. Keep benchmarks separate from health checks.
- [ ] Define the MATH3D worker/backend API on the same schema-versioned invocation/result contract. MATH3D imports contract and artifacts, not DevShell internals; DevShell remains a laboratory and observability client.

## Safety and ownership rules

- Manifests are repository-controlled declarations, not arbitrary user shell scripts. Runtime IDs and paths are validated by the supervisor; child arguments are passed as argv.
- Every run owns an output directory and `results.json`. Never reuse an output directory for a concurrent run or silently overwrite evidence from a prior run.
- Successful exit means the declared probes passed; it is not a blanket claim that all CGAL or VTK features are ready.
- Result records omit inherited environment variables and secrets. Extend snapshots only with explicit allowlisted fields.
- Test data is duplicated into local controlled sets; originals remain unchanged and upstream licenses remain applicable.

## MATH3D integration and artifact preview (2026-10-16)

- The fresh managed MATH3D native Boolean integration run passed all four contract checks. Saved run ID: `0285d78f3af24d91be5a5fa89ca6682a`. History records one output artifact for this run; an older zero-artifact entry remains historical evidence.
- History now opens native `.m3dm` output through a bounded, read-only preview parser. It validates the M3DM header, version, exact byte length, vertex/triangle counts, finite coordinates, and face indices before returning the existing mesh-preview schema. The tested output displayed four points and four triangles.
- History's Compare action accepts the integration output. A live UI check rendered its `.m3dm` mesh beside a successful CGAL validation `.obj` output, each with four points and four triangles. This is a visual comparison, not a numeric mesh diff or a CGAL validation reproducibility check.
- React/Vite and Windows Release builds passed; the rebuilt DevShell was launched and the focused UI flow completed. Generated UI assets are included. Local run results and runtime profile state stay out of version control.
- Next: compare meaningful same-input MATH3D and CGAL operations with numeric diagnostics and explicit tolerances. The tetrahedron self-union smoke case does not establish broad Boolean correctness or runtime readiness.
