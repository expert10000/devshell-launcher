# Scientific Runtime Lab: architecture extension

Updated 2026-10-16. This extends [SCIENTIFIC_RUNTIMES_ROADMAP.md](SCIENTIFIC_RUNTIMES_ROADMAP.md); it does not replace the existing scientific jobs, CGAL/VTK workers, or their recorded evidence.

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
