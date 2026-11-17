# Scientific mesh workbench roadmap

Updated 2026-11-17. The Workbench implementation and a signed six-capability release passed at `46067b6`, with MATH3D pinned to `12e87f93`. The portable bundle independently verified its trusted signature and 163 artifact payloads. That release is historical after the portable-evidence change at `5dffb70`; current support requires a fresh qualification at the eventual source HEAD. The Workbench selects an object, operation, managed job, and verified result; neither installed algorithms nor arbitrary imports acquire qualification through this UI.

## Product shape

Use the **Workbench** tab in DevShell Scientific Runtimes, with the selected provider visible in the left rail. The tab keeps one profile, one cancel action, and the existing History/artifact checks. The tested MATH3D consumer checkout is pinned to `12e87f93`; newer MATH3D commits require renewed consumer evidence. DevShell converts a verified OBJ/VTP result into MATH3D's bounded OBJ intake, embeds source run and consumer identity in the Mesh document origin, then checks document, resource and M3DM reload.

The workbench has three steps: **Object** (registered local copy, hash, format and validation), **Operation** (provider, feature, parameters, scope and run/cancel), and **Result** (synchronized input/output 3D layers, focused metrics, diagnostics, log and artifact hashes). Switching operations preserves the selected object and states when its format is unsupported. Each run writes a fresh directory and History record. Failed or cancelled runs do not advertise successful geometry. Opening or switching the tab starts no operation; after restart it reads registered metadata and saved History.

## Provider and operation contract

| Provider | First operations in the workbench | Boundary |
|---|---|---|
| CGAL | Validate, guarded isotropic remesh, orientation repair, bounded hole fill | Existing `cgal-recipe` adapter and OBJ output; closed/open input rules shown per operation |
| VTK | Inspect, simplify, compute normals | Existing `recipe` adapter and VTP output; topology and auto-orientation restrictions shown per operation |
| Gmsh | Next: registered surface and volume generation | Separate dimensional input and cell-preserving output; never present a boundary surface as the volume result |
| Python/SciPy, SageMath | Next: typed numeric or exact-result workspace panels | No mesh operation is implied by the provider being installed |

The versioned `schemas/scientific-workbench-operations.v1.json` is shared by the UI and native validator. Native allowlists, dataset hashes, output paths, timeouts and owned process cancellation remain authoritative. Capability labels distinguish **available action**, **qualified scope**, **current evidence**, and **unsupported input**. The manual provider choice and inspection ranking abstention remain explicit.

## Delivery sequence

1. **Live desktop slice — done.** CGAL and VTK import, preview, operation, rejection, cancellation, restart, and History were exercised at `a485cb0`; the recovery fix loads saved objects and result links. See `docs/scientific-mesh-workbench-live-acceptance.md`.
2. **Bounded object intake — done for this scope.** VTK registers OBJ/STL/PLY/VTP as hashed copies; VTP uses the v1 safe XML/base64 PolyData policy. CGAL retains OFF, with an explicit preview limitation. Format errors appear before Run and malformed VTP is rejected before registration. See `docs/scientific-workbench-intake-policy.v1.md`.
3. **Typed operations and result review — v1 done.** UI and launcher read one versioned catalog. Worker guards remain narrower; result review shows topology and counts beside synchronized before/after views. Quality and normal-array analysis, export, and operation presets remain future scoped features.
4. **MATH3D handoff — implemented and accepted at `46067b6`.** A managed action reads a verified saved Workbench result, converts bounded OBJ/VTP geometry, binds source and MATH3D Git identity, and reloads the saved Mesh document and M3DM. Desktop and broker gates passed, and a signed portable bundle verified offline for that source commit.
5. **Current source release — running.** The six-capability requalification started at `447c1ca` with MATH3D `12e87f93`. Complete the desktop and broker checkpoints, product smokes, signature and offline verification before recording a passed release. Later source commits make that record historical; source drift must remain visible.
6. **Typed cross-provider journey — contract started.** The v1 journey contract requires two distinct registered source hashes, independent topology validation, CGAL Boolean, Gmsh, VTK, SciPy, pulled MATH3D, save/export and a new-process cold reopen. The offline artifact verifier checks stage order, content hashes, units, coordinate frame, generation, source and consumer identity, and parent links. It does not grant capability support without live gates. See `docs/scientific-typed-journey.v1.md`.
7. **Operation implementation — local chain passed.** A bounded Boolean OBJ to tetrahedral Gmsh bridge retains dimensional and physical-group meaning; its actual tetrahedral boundary is extracted for VTK, and a VTK VTP to SciPy surface-area worker emits a typed unit and tolerance. A live local smoke passed two distinct registered CGAL Boolean sources through Gmsh → VTK → SciPy → pulled MATH3D, then saved and reopened the Mesh document and export in another process. The chain checked intermediate hashes, expected Boolean volume, typed measurement, consumer commit and persisted provenance. Next add managed accepted, rejected, tampered and cancelled desktop and broker gates before exposing actions.
8. **Installed release closure.** Run the complete journey in a clean installed desktop and pulled MATH3D, close both processes, cold-reopen the saved document and export, publish a signed portable bundle, verify it offline, then mark the roadmap gate passed with exact source, build, package and consumer hashes.

## Acceptance before calling this complete

- Import/select an object, switch CGAL/VTK operations, run and cancel from DevShell, then reopen each result through History.
- Verify the same input/output hash and geometry counts in the 3D and textual views; reject changed artifacts and invalid parameter or format combinations.
- Exercise a successful output, an expected rejection, cancellation, restart, and saved-document reload in the real desktop app.
- Keep qualified class boundaries and ranking abstention visible. Do not promote support based on an attractive preview or an unverified worker result.

The local `ScientificArtifactChecks` suite passed 183 checks through the shared catalog and provider handoff allowlist. Live runs are recorded in the Workbench evidence notes. The `46067b6` release and its 163-payload signed bundle are verified historical evidence. Run the current-HEAD release gates again after source or MATH3D consumer drift; a screenshot or historical bundle does not promote newer source support.
