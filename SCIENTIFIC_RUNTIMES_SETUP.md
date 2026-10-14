# Local scientific environments

## This workstation: installed 2026-10-09

| Component | CGAL environment | VTK environment |
| --- | --- | --- |
| Prefix | `G:\master\.conda\devshell-cgal` | `G:\master\.conda\devshell-vtk` |
| Python | 3.11.17 | 3.11.17 |
| Runtime bindings / C++ SDK | CGAL 6.0.1 / 6.0.1 | VTK 9.6.1 / 9.6.1 |
| NumPy / SciPy | 2.4.6 / 1.17.1 | 2.4.6 / 1.17.1 |
| CMake / Ninja | 4.4.4 / 1.13.2 | 4.4.4 / 1.13.2 |

CGAL dependencies include Boost 1.88.0, GMP 6.3.0, MPFR 4.2.2, and Eigen 5.0.1. Visual Studio 2022 Community has the x64 MSVC 14.44.35207 toolset installed. These are recorded local package/tool facts, not compile-test results.

Passed: Python, NumPy/SciPy imports, CGAL Point_3, VTK version/vtkPolyData, CMake/Ninja version commands, and SDK header/CMake-config presence. C++ compilation/linking and VTK rendering are untested; readiness is partial. Exact Conda package locks were saved locally as `.scientific/locks/cgal-win-64-explicit.txt` and `.scientific/locks/vtk-win-64-explicit.txt`.

## Install missing components

Run from the DevShell repository with PowerShell 7. Supply an existing workspace root and the actual Conda executable, not an activation alias.

```powershell
./tools/Install-ScientificRuntimes.ps1 `
  -WorkspaceRoot 'G:\master' `
  -CondaExecutable '<absolute-path-to-conda.exe>' `
  -Kind both `
  -PublishToLauncher
```

The installer creates separate workspace-local `.conda/devshell-cgal` and `.conda/devshell-vtk` environments. It does not change existing `math3d-cgal`, base Python packages, system PATH, WSL, or Docker. Conda downloads may use its existing package cache. Environments are intentionally outside the OneDrive checkout.

When every required package is already present, installation is skipped without upgrading the environment. Missing packages may require Conda to resolve compatible dependencies inside that dedicated environment. A non-Conda directory at the target prefix is rejected rather than overwritten.

CGAL includes Python bindings, `cgal-cpp`, Boost/GMP/MPFR dependencies, Eigen, NumPy/SciPy, CMake, and Ninja. Conda resolves compatible binding/SDK versions; their version numbers must be reported separately rather than assumed to be the newest release. VTK includes Python/SDK packages and their dependencies, NumPy/SciPy, CMake, and Ninja.

Package provenance: [CGAL C++ on conda-forge](https://anaconda.org/conda-forge/cgal-cpp), [VTK on conda-forge](https://anaconda.org/conda-forge/vtk). Compiler/toolchain requirements: [CGAL dependencies](https://doc.cgal.org/latest/Manual/thirdparty.html).

## Refresh local information

```powershell
./tools/Inspect-ScientificRuntimes.ps1 `
  -RuntimeRoot 'G:\master\.conda' `
  -PublishToLauncher
```

This explicit action runs bounded interpreter/import probes and local tool version commands. It collects:

- Environment root, executable, Python version, and architecture.
- Conda/Python package inventory, versions, builds, and sanitized package channels.
- CGAL Point_3 or VTK version/vtkPolyData import evidence, plus NumPy/SciPy imports.
- SDK header and CMake config locations, reported SDK package versions.
- Environment-local CMake/Ninja versions and executable paths.
- Installed MSVC toolchain path/version, without running a compiler build.
- Probe outcome, duration, and recorded timestamp.

Interpreter subprocesses have a 60-second timeout and environment-local DLL search paths. Tool version commands have 10-second timeouts. No generated/user code, C++ builds, linking, or rendering is run. The report marks those capabilities untested and overall readiness partial.

The machine-local report is `.scientific/runtime-report.json`, ignored by Git. `-PublishToLauncher` copies it into existing launcher UI directories; it does not rebuild or launch the application. The published report is also ignored by Git.

## UI

After building the report-capable UI, open **RUNTIMES / Scientific**, then **Load local report**. Choose CGAL or VTK:

- Health: recorded probe results, durations, and explicit untested checks.
- Environment: actual installed paths and expandable compiler/SDK/tool evidence.
- Packages: full recorded package inventory and provenance.
- Integration: the structured worker request contract, not a submitted job.

Report loading reads only the already-generated local snapshot. It does not run probes, install packages, or make Internet requests. Changing a profile definition invalidates its readiness label; old report evidence remains clearly associated with its original installed environment. Switching profiles clears loaded report state, and stale asynchronous responses are ignored.

## Explicit smoke tests

```powershell
./tools/Test-ScientificRuntimes.ps1 -RuntimeRoot 'G:\master\.conda' -PublishToLauncher
```

Run on 2026-10-09: all seven checks passed. CGAL configured/compiled/linked and constructed a Surface_mesh triangle. VTK configured/compiled/linked and wrote/read sphere polydata. VTK Python rendered a nonblank 640x480 PNG using vtkWin32OpenGLRenderWindow on Intel UHD Graphics 770 / OpenGL 4.5.

Per-run `.scientific/smoke/<timestamp-id>` directories contain configure/build/run logs, `triangle.off`, `sphere.vtp`, `vtk-offscreen.png`, and result JSON. The refreshed report includes successful checks and only the capabilities actually exercised. Running the inventory-only inspector later replaces that snapshot with inventory-only evidence.

Next: complete linked-library provenance, broader geometry algorithms, interactive rendering, benchmarks, and a managed native recipe runner. These smoke tests do not make every declared mesh/rendering capability Ready. The UI's combined compilation/rendering summary label still needs separating; the detailed SDK fields and probe results record these independently.

## Using the new Inspector and recipe workflow

The following workflow is implemented in source but has not yet been rebuilt or tested in this slice.

1. Open Scientific Runtimes and load the local report. Select CGAL or VTK under Windows Native.
2. Open Environment and choose Load environment for the selected installed prefix. Open terminal starts an external PowerShell session using that prefix; it is not a Visual Studio developer shell.
3. Copy environment copies only the explicitly selected runtime environment keys. Export profile saves an installed runtime definition, not a validated worker contract.
4. Open Commands. Version probes the runtime. Configure, Build, and Run are separate actions; Test all runs the registered smoke sequence, including VTK offscreen rendering when applicable.
5. Choose Load duplicated test sets to use the sixteen copied MATH3D meshes. Select a VTK operation, fixture, and output filename, inspect the generated invocation, then choose Run.
6. Follow live output in the Scientific panel. Stop cancels the owned job; Open full log and Open output folder expose its recorded results.

VTK mesh inspection reports topology counts, not exhaustive validation or self-intersection detection. Simplification and normals are explicit worker operations; CGAL algorithms remain planned and disabled. Output files use a fresh run directory and do not overwrite source meshes. No recipes run merely from selecting a profile or loading an inventory report.

The duplicated fixtures live in `.scientific/datasets/math3d/`; their manifest records source paths, hashes, categories, and expected problematic cases. Local duplication is not a license grant for redistribution. Originals remain unchanged.

C++ compilation, linking, and offscreen rendering are now distinct status labels in source. This supersedes the earlier combined-label limitation. The current compiler display uses binary/toolset metadata; actual MSVC identification and detailed OpenGL provenance are follow-up work.

The reported log-error cleanup path is fixed in source: the runner lock is released even when final logging fails. Rebuild/test this slice before using the new runner. The previous successful CGAL/VTK smoke checks do not establish that the new UI bridge and parameterized recipes are verified.

## CGAL Validate and Isotropic Remesh recipes

After rebuilding, open Scientific Runtimes, select CGAL / Windows Native, and load the local report. Open Commands, choose Load duplicated test sets, and select Validate or Isotropic Remesh.

For remeshing, choose a copied OBJ/STL/PLY/OFF fixture, set Target edge length in the mesh's own units, Iterations (1-10), and Protect boundary curve. Set a new OBJ output filename and choose Run remesh recipe. The runner configures/builds the dedicated worker before running it; the initial compile can take longer than later incremental runs. Quick Configure / Build / Run remain the independent shipped smoke-test sequence.

The command template and structured recipe show the execution contract. Copy command template does not resolve placeholder paths; the actual executable and paths are recorded in the job log. Copy recipe includes registered steps, parameters, timeouts, and expected artifacts.

Open full log and Open output folder expose the run. `invocation.json` records the request; `results.json` records operation status, CGAL version, duration, before/after mesh counts, triangulation, and validation results. A successful operation writes the requested OBJ. Failure preserves diagnostics but is not a completed geometry result.

The importer deliberately avoids automatic soup repair. Validation checks graph import, degeneracy, and self-intersections; it is not a universal geometry certification. Protected boundaries can gain vertices through edge splitting. The conservative edge-length budget may reject small targets; use a larger value rather than bypassing it.

The launcher frontend and native application now build. The new CGAL recipe operations and UI bridge have not yet been run as behavioral tests. Repair, Boolean, CGAL Simplify, AABB, Distance, and Intersection stay disabled. Scientific recipe output currently stays in its live panel; persistent workspace output tabs are still follow-up work.

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
