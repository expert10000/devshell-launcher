# Scientific-runtime laboratory for MATH3D

Updated: 2026-10-09

## Execution-contract principle

Anything successfully tested in DevShell should already have the execution contract needed to become a MATH3D worker/backend. Use runtime IDs and capabilities, not host-specific shell snippets, as the integration boundary.

Runtime readiness is evidence, not configuration. A profile or executable path alone must never produce a Ready badge. Package installation, tests, builds, benchmarks, and rendering always require explicit user actions.

## 1. Scientific Runtimes workspace

Status: workspace and local inventory UI built; isolated CGAL/VTK environments installed on 2026-10-09. Bounded inventory plus seven C++/geometry/offscreen smoke checks passed. UI acceptance tests, broader algorithm validation, interactive rendering, persistent profiles, and managed execution adapters remain pending.

- [x] Initial runtime inventory: CGAL, VTK, Gmsh, SageMath, Python/SciPy. Custom-profile editing remains planned.
- [x] Environment selector: Windows native, WSL, Docker; clearly label unsupported execution adapters.
- [x] Health, Environment, Commands, Tests, Benchmarks, Packages, Artifacts, Integration foundation sections.
- [x] Session-only profile details, capability declarations, executable/compiler/CMake paths, and planned probe contracts.
- [x] Passive navigation; no environment creation, imports, commands, rendering, or package/network access on selection.
- [ ] Later connect explicit Health to the bounded probe runner; until then report Not checked, never invented versions/readiness.
- [x] Add explicit local snapshot loading with recorded probe evidence, timestamp, tool/SDK paths, and full package inventory. Frontend/native builds passed; interactive report loading has not been UI-tested.

## 2. Runtime profiles and new CGAL/VTK environments

- [ ] Versioned, validated `RuntimeProfile` configuration, separate from mutable run results.
- [ ] Seed separate `cgal-win-conda` and `vtk-win-conda` definitions; use host/profile overrides, not committed absolute machine paths.
- [ ] Define environment roots, executable/compiler/CMake paths, allowlisted environment keys, capabilities, version recipes, and health probes.
- [ ] Review existing CGAL environment before reuse; create the dedicated VTK environment only through an explicit environment-setup recipe.
- [ ] Capture resolved Python/package/C++ SDK versions and tool provenance; distinguish Python bindings from C++ development libraries.
- [ ] Add explicit export/import with schema validation and secret exclusion.
- [ ] WSL distribution and Docker image/digest profiles; unavailable adapters remain visible but not executable.
- [x] Add workspace-local install-missing and explicit inspection scripts for separate devshell-cgal/devshell-vtk Conda environments, preserving existing MATH3D environments.
- [x] Keep local inventories out of Git; publish snapshots to the launcher only through an explicit script option.
- Installed: separate workspace-local CGAL 6.0.1 bindings/SDK and VTK 9.6.1 bindings/SDK, each with Python 3.11.17, NumPy 2.4.6, SciPy 1.17.1, CMake 4.4.4, and Ninja 1.13.2. Python imports/Point_3/vtkPolyData and SDK files were checked; C++ builds/linking and rendering remain untested. Existing MATH3D environments were not modified.

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

Smoke checks run on 2026-10-09:

- CGAL 6.0.1: MSVC x64 CMake configure, Release compile/link, and Surface_mesh triangle creation passed; OFF and result JSON emitted.
- VTK 9.6.1: MSVC x64 CMake configure, Release compile/link, and sphere VTP write/read passed; VTP and result JSON emitted.
- VTK Python offscreen rendering passed with a nonblank 640x480 PNG. Backend: vtkWin32OpenGLRenderWindow, Intel UHD Graphics 770, OpenGL 4.5.
- The explicit smoke runner has configure/build/run timeouts, owned subprocess cancellation, per-step logs, isolated timestamped run folders, and local report publishing.
- Overall readiness remains partial. Mesh repair/boolean/remesh/distance, interactive rendering, performance, and complete linked-library provenance have not been validated.
- The UI summary currently combines compilation and rendering statuses; these labels need separating to avoid implying that CGAL has a rendering test.

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

## Environment Inspector and recipe workflow: source implementation

Implemented in source; this slice has not yet been rebuilt or tested:

- Separate C++ compilation, linking, and offscreen-rendering status. This supersedes the earlier note about a combined compile/render label.
- Environment Inspector with installed package versions, SDK and binding checks, compiler metadata, selected CMake prefix, and explicit environment loading.
- Open an external runtime terminal, copy the allowlisted environment, run inventory diagnostics, and export an installed runtime definition.
- Registered Version, Configure, Build, Run, and Test all recipes with owned processes, bounded execution, live output, Stop, and full-log/output-folder actions.
- Parameterized VTK mesh inspection, simplification, and normals recipes with structured invocation previews and explicit inputs/outputs.
- Sixteen locally duplicated MATH3D mesh fixtures, including normal, problematic, and importer cases, with provenance and SHA256 hashes. Source meshes are unchanged; copies and generated results stay under ignored `.scientific/`.

Still pending:

- Rebuild and exercise the new Inspector and recipe bridge end to end.
- Validate runner recovery after the source fix that guarantees lock release even when final logging fails.
- Display actual MSVC compiler identification and recorded OpenGL vendor/renderer/version separately from binary metadata and render status.
- Integrate recipe output into persistent workspace Logs tabs and add the existing Run / New tab interaction.
- Implement and validate CGAL worker operations. Remesh, repair, Boolean, AABB, distance, and intersection controls remain explicitly unavailable.
- Expand exported definitions into the full capability/health-check/recipe contract. Exporting a definition is not evidence of readiness.

Existing successful smoke-test evidence does not validate these new UI and recipe paths. Inventory diagnostics do not compile or render and may replace previous report evidence with not-tested values.

## Command recipes and parameter forms: CGAL extension

The frontend and native launcher have been rebuilt successfully with the Environment Inspector and recipe UI. The prior JSX help-text parsing errors and CGAL runner argument-order compilation errors were corrected.

- Commands provides registered Version, Configure, Build, Run, and Test all smoke recipes.
- CGAL adds a dedicated C++ worker and explicit Validate / Isotropic Remesh recipes. Each operation configures and builds that worker using the selected installed SDK before execution.
- The remesh form accepts a copied input, target edge length in mesh units, one to ten iterations, boundary protection, and a safe OBJ output name.
- The UI shows a copyable positional-argv command template and a reusable structured recipe with steps, timeouts, parameters, and artifact declarations. Placeholder paths are resolved by the native runner; command text is not executed through a shell.
- VTK retains parameterized inspect, simplification, and normals operations.
- Jobs share the owned runner gate and cancellation/log mechanisms. Inputs remain unchanged; results, invocation metadata, logs, and geometry go into fresh run directories.

Scope: plain CGAL IO does not silently repair polygon soups. Polygon faces may be triangulated; invalid imports, degenerate triangles, and self-intersections are rejected. Boundary protection can insert vertices when splitting long edges. Input and conservative remeshing budgets bound the laboratory workload.

Still pending: execute the new CGAL algorithms on fixtures and test the UI bridge, cancellation, and recovery end to end; integrate Scientific output with workspace Logs / New tab; implement repair, Boolean, CGAL simplification, AABB, distance, and intersection. Building the launcher is not algorithm validation and does not make these runtimes universally READY.

Build result: the dedicated CGAL C++ worker compiled successfully against the installed Conda SDK. CMake identified MSVC 19.44.35229.0. No validation/remeshing recipes or end-to-end UI tests were executed during this rebuild. Implementation reference: [CGAL isotropic remeshing example](https://doc.cgal.org/latest/Polygon_mesh_processing/Polygon_mesh_processing_2isotropic_remeshing_example_8cpp-example.html).

## Mesh recipe worker tests - 2026-10-09

The approved direct-worker regression suite passed 11/11 checks. Evidence: `.scientific/tests/mesh-20261009-122806-048a4d9a/test-report.json`.

- CGAL: validate polygonal cube, remesh tetrahedron, reject degenerate geometry, reject an over-budget target edge length.
- VTK: inspect tetrahedron, simplify torus, compute cube normals, reject auto orientation of an open surface, reject a truncated PLY with an empty triangulated surface.
- All sixteen copied fixtures are unchanged and all sixteen original source hashes match recorded provenance.

The initial VTK harness used incorrect artifact request fields; those earlier results were invalid and superseded by the corrected suite. Negative cases now require the expected geometry-rejection reason and no output artifact, not merely a nonzero exit.

Reproduce with `./tools/Test-ScientificMeshRecipes.ps1`; this uses the already compiled dedicated CGAL worker under `.scientific/builds/cgal-worker-prebuild/Release/` and the isolated installed VTK Python prefix. It writes a fresh ignored test directory each time.

These are worker-level checks only. The Inspector UI, native recipe bridge, live-log delivery, Stop/cancellation, and cleanup recovery remain unverified. The Windows UI helper failed to launch DevShell; the user has been asked to open the rebuilt app for the remaining UI checks. No push was performed.

### Native UI acceptance checks (2026-10-09)

- Scientific workspace: loaded the local report, switched CGAL/VTK, and confirmed separate installed prefixes and Inspector probe evidence. Loading the workspace did not automatically run recipes.
- CGAL: environment loading enabled Copy environment. Managed cube validation succeeded with live configure/build/worker output. Remesh with edge 0.02, 10 iterations, and protected boundary succeeded (184224 output faces).
- Stop: a running cube remesh with edge 0.01 and 10 iterations transitioned to cancelled (12666 ms). Its owned worker stopped and no completed output OBJ was present.
- Recovery: a new remesh with edge 0.1 succeeded after cancellation (1051 ms; 6144 output faces), demonstrating that the shared job gate was released.
- VTK: Inspector displayed passing SDK/bindings/link/vtkPolyData/offscreen evidence and interactive rendering as not tested. Managed tetrahedron inspection succeeded (454 ms) with live JSON output and a VTP artifact.
- Local evidence: .scientific/runs/a5d931c7f3c842439909012020583da2 (cancelled), 088d04cc449d4bb98e0d1d3fce093034 (retry), 425961a0bc704cb49756ecb3f6344805 (VTK). These files are local ignored artifacts, not repository content.
- Remaining checks: Open full log/Open output folder launch actions, clipboard payload, profile export dialog, timeout and log-write fault injection, interactive rendering, and WSL/Docker execution were not tested in this UI pass. Existing inspector/report evidence is not a new diagnostics run.
- Follow-up UI copy: the candidate-only sidebar and CGAL not-yet-exercised help text are stale after these checks. No application code was changed during acceptance testing. Nothing was pushed.

### Scientific artifact comparison and shared transport (2026-10-14)

Source implemented; this revision has NOT been rebuilt, executed, tested, or pushed.

- Scientific > Artifacts now exposes the current run's mesh outputs. Commands > View artifacts / compare opens the same view. Load comparison explicitly reads registered input and output artifacts; switching pages alone does not run a worker or load meshes.
- OBJ/STL/PLY/VTP use the dedicated VTK reader adapter. Input/output panes share orbit, zoom, fit/reset, and wireframe controls. Read-only previews display at most 12000 uniformly sampled triangles per pane, with explicit sampling labels; statistics and deltas describe full worker meshes. OFF input comparison is unavailable, but its OBJ output can be previewed.
- Native preview access is scoped to the selected profile/runtime/current run, rejects junction/symlink escapes, checks hashes against the recorded result, bounds files and response payloads, and owns the preview subprocess with a 30-second limit. WebGL meshes are transient; they are not saved in profile restoration or fetched from external resources.
- CGAL and VTK use a shared schema-1 request/result envelope with runId, recipeId, operation, parameters, input/output artifact records, SHA-256 hashes, source provenance, versions, normalized points/triangles, diagnostics, durations, stage/step evidence, and full.log reference. request.json and invocation.json contain the resolved request. results.json is finalized by the desktop runner for success, failure, cancellation, and timeout. Cancelled/failed results do not advertise successful geometry artifacts.
- CGAL's JSON adapter wraps the shipped C++ engine; its positional interface remains an internal engine boundary. The VTK adapter uses the same contract module. These adapters do not run shell command strings.
- Inspector labels distinguish recorded readiness from live checks and actual MSVC compiler banners from toolset/file metadata. Refresh inventory explicitly probes cl.exe /Bv without compiling. Load environment can expose saved offscreen render backend and OpenGL capability evidence. Interactive VTK rendering remains not tested; browser WebGL preview is separate evidence, not a VTK rendering acceptance test.
- Next validation: rebuild both targets; run CGAL validate/remesh and VTK inspect/simplify/normals; check identical request/result fields and hashes; test failure/cancellation/timeout results; load dense and small mesh comparisons; test runtime/profile switching, unsupported OFF before-preview, no-WebGL fallback, resized/mobile panes, modified-artifact rejection, and rendering/compiler evidence loading.

### Build and test pass (2026-10-14)

- React/Vite build succeeded (77 modules; existing large-chunk warning). Windows Debug build succeeded with 0 warnings and 0 errors. DevShell was relaunched and its Scientific UI opened.
- Existing scientific mesh regression suite: 11/11 passed. Report: .scientific/tests/mesh-20261014-111202-e1d01d51/test-report.json.
- New shared-contract/artifact suite: final 11/11 passed after approved harness-only fixes (PowerShell case-name shadowing, and recognizing the fixture's earlier manifold-import rejection). Includes CGAL JSON validate/remesh, VTK inspect/simplify/normals, structured rejection results, changed-input hash rejection, small and dense sampled previews, and unchanged copied fixtures. Final report: .scientific/tests/contracts-20261014-131546-f2758c72/test-report.json. Earlier 8/11 harness report is superseded.
- Isolated compiler inventory test passed: actual MSVC 19.44.35229, distinct binary metadata 14.44.35229.0. Saved to .scientific/tests/compiler-inventory-20261014.json; existing smoke/render report was not overwritten.
- Native UI report-loader bug found: Vite clears BatchLauncher/ui, removing scientific-runtime-report.json. Load local report currently reports Failed to fetch although .scientific/runtime-report.json still exists. Requested approval to route desktop report loading through the native bridge; not fixed yet.
- Native dataset bridge successfully loaded 16 copies. Remaining managed-run finalization, mesh canvas interaction, native preview loading, profile switching, cancellation/timeout, and rendering evidence UI checks were not completed. User interaction changed the page during the native recipe check, so automation was stopped rather than overriding the user's work.
- No application fixes were made during this pass; only the new test harness was corrected with approval. No Git actions or push.

### Approved report-loader fix and UI retest (2026-10-14)

- Approved fix: desktop Load local report now uses the profile/request-correlated scientific.runtime report action. Browser-only use retains the bounded static JSON fetch fallback. No probes run when loading the saved report.
- React and Windows Debug rebuilt successfully after the fix; native build has 0 warnings/errors. DevShell was relaunched.
- UI retest passed: the saved CGAL/VTK report loaded despite the generated UI report asset being absent. Sidebar accurately showed recorded partial readiness. Runtime switching updated the correct runtime details.
- Managed VTK tetrahedron inspection succeeded in 569 ms. Run ID 39a334cd8a4c4206aa8fe5369637c7e7; local directory .scientific/runs/9f5c005a9cea4754a0a80dafbe2e1b50. Shared native result finalization enabled View artifacts / compare and recorded capability labels.
- Native Load comparison passed hash/scoped-file checks and displayed OBJ input plus VTP output. Both WebGL views rendered; wireframe toggled both, and a keyboard orbit in the input canvas rotated both cameras. Full statistics showed 4 points/4 triangles before and after, with zero boundary/non-manifold edges.
- Switching to CGAL correctly displayed no managed run rather than showing VTK artifacts. Returning to the cached VTK view was not completed because the target window bounds/overlap changed; no input was sent to the overlapping Codex window.
- Remaining validation: managed CGAL UI pipeline with the JSON wrapper, drag/zoom/reset, profile switching, mobile/no-WebGL fallback, native timeout/cancellation result finalization, modified-artifact UI rejection, and compiler/render evidence UI loading. Standalone suites passed 22/22 before the report-only fix, as recorded above. No push.
