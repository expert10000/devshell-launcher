# Scientific mesh workbench roadmap

Updated 2026-11-15. The six-capability evidence release at `0b4a656` is historical. A new signed release must be sealed against the final Workbench HEAD. The Workbench selects an object, operation, managed job, and verified result; neither installed algorithms nor arbitrary imports acquire qualification through this UI.

## Product shape

Use the **Workbench** tab in DevShell Scientific Runtimes, with the selected provider visible in the left rail. The tab keeps one profile, one cancel action, and the existing History/artifact checks. MATH3D `main` was pulled to `19484d0d` for the saved-result handoff. DevShell converts a verified OBJ/VTP result into MATH3D's bounded OBJ intake, embeds source run and consumer identity in the Mesh document origin, then checks document, resource and M3DM reload.

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
4. **MATH3D handoff — implementation ready for final-HEAD acceptance.** A managed action reads a verified saved Workbench result, converts bounded OBJ/VTP geometry, binds source and MATH3D Git identity, and reloads the saved Mesh document and M3DM. Requalify six capabilities, exercise desktop and broker gates, and publish a signed bundle at the final clean HEAD. Gmsh Workbench surface and volume workflows wait for separate typed contracts and acceptance evidence; they are not part of the current operation catalog.

## Acceptance before calling this complete

- Import/select an object, switch CGAL/VTK operations, run and cancel from DevShell, then reopen each result through History.
- Verify the same input/output hash and geometry counts in the 3D and textual views; reject changed artifacts and invalid parameter or format combinations.
- Exercise a successful output, an expected rejection, cancellation, restart, and saved-document reload in the real desktop app.
- Keep qualified class boundaries and ranking abstention visible. Do not promote support based on an attractive preview or an unverified worker result.

The local `ScientificArtifactChecks` suite passes 183 checks through the shared catalog and provider handoff allowlist. Live runs are recorded in the Workbench evidence notes. A final-HEAD desktop handoff, six-capability requalification, broker smokes, and signed portable publication remain required release gates.
