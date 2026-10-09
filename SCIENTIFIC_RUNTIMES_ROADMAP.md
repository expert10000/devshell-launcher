# Scientific-runtime laboratory for MATH3D

Updated: 2026-10-09

## Execution-contract principle

Anything successfully tested in DevShell should already have the execution contract needed to become a MATH3D worker/backend. Use runtime IDs and capabilities, not host-specific shell snippets, as the integration boundary.

Runtime readiness is evidence, not configuration. A profile or executable path alone must never produce a Ready badge. Package installation, tests, builds, benchmarks, and rendering always require explicit user actions.

## 1. Scientific Runtimes workspace

Status: initial workspace implemented in source, not built or tested. Native probes, persistent profiles, environment installation, and execution adapters remain planned.

- [x] Initial runtime inventory: CGAL, VTK, Gmsh, SageMath, Python/SciPy. Custom-profile editing remains planned.
- [x] Environment selector: Windows native, WSL, Docker; clearly label unsupported execution adapters.
- [x] Health, Environment, Commands, Tests, Benchmarks, Packages, Artifacts, Integration foundation sections.
- [x] Session-only profile details, capability declarations, executable/compiler/CMake paths, and planned probe contracts.
- [x] Passive navigation; no environment creation, imports, commands, rendering, or package/network access on selection.
- [ ] Later connect explicit Health to the bounded probe runner; until then report Not checked, never invented versions/readiness.

## 2. Runtime profiles and new CGAL/VTK environments

- [ ] Versioned, validated `RuntimeProfile` configuration, separate from mutable run results.
- [ ] Seed separate `cgal-win-conda` and `vtk-win-conda` definitions; use host/profile overrides, not committed absolute machine paths.
- [ ] Define environment roots, executable/compiler/CMake paths, allowlisted environment keys, capabilities, version recipes, and health probes.
- [ ] Review existing CGAL environment before reuse; create the dedicated VTK environment only through an explicit environment-setup recipe.
- [ ] Capture resolved Python/package/C++ SDK versions and tool provenance; distinguish Python bindings from C++ development libraries.
- [ ] Add explicit export/import with schema validation and secret exclusion.
- [ ] WSL distribution and Docker image/digest profiles; unavailable adapters remain visible but not executable.

CGAL target capabilities: mesh read/write, validation, repair, boolean operations, simplify/remesh, AABB, distance. VTK target capabilities: polydata, filters, mesh IO, rendering, offscreen rendering. Declarations are candidates until corresponding tests pass.

## 3. Environment inspector and bounded probes

- [ ] CGAL, Boost, GMP, MPFR, Eigen, CMake, Ninja, MSVC/other compiler, and vcpkg provenance.
- [ ] CGAL include/link/Surface_mesh compiler tests and recorded linked libraries.
- [ ] VTK C++ SDK and Python binding checks reported independently.
- [ ] vtkPolyData, rendering, OpenGL, offscreen rendering probes; do not conflate import success with rendering readiness.
- [ ] Python/SciPy and optional Gmsh/Sage probes.
- [ ] Timeouts, cancellation, owned subprocesses, bounded stdout/stderr, redacted environment previews, duration and exit status.
- [ ] No silent compiler/package installation, PATH mutation, or termination of unrelated processes.

## 4. Command recipes

- [ ] Recipes reference runtime IDs, argv-based steps, cwd, declared environment, timeout, inputs, and artifacts.
- [ ] Configure -> Build -> Run -> Validate sequencing with failure gating and cancellation.
- [ ] CGAL smoke tests, VTK smoke tests, mesh and geometry examples.
- [ ] Existing Run/New tab/Logs UI routes through the same managed execution contract.
- [ ] Commands, Tests, and Benchmarks stay explicit; no arbitrary imported commands execute on load.

## Worker/backend contract

Each invocation carries `schemaVersion`, `runId`, `runtimeId`, `recipeId`, `operation`, typed parameters, scoped input artifacts, working directory, timeout, and requested output artifacts.

Each result carries state/exit code, duration, resolved runtime/tool versions, validated capabilities, bounded diagnostics, log reference, and output artifact references. Output geometry and result JSON live in a scoped run directory; worker transport must not depend on terminal presentation.

Use JSON-compatible requests/results so the same recipe can later run through a Windows, WSL, Docker, or MATH3D worker adapter. Paths crossing adapters need explicit mapping; stdout is not the protocol.

## Acceptance and follow-up

- [ ] Fixtures verify malformed profiles, missing tools, conflicting packages, Unicode paths, cancellation, timeout, isolated environments, and passive restoration.
- [ ] Reproducible CGAL and VTK smoke tests produce inspectable geometry plus machine-readable results.
- [ ] Benchmark metadata records input size, hardware/runtime versions, timing method, and output validity.
- [ ] Artifact viewers open outputs without executing generated HTML/scripts.
- [ ] MATH3D Integration maps tested capabilities to backend selection and consumes the same request/result schema.

No environment has been installed or verified merely by adding this roadmap.
