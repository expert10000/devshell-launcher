# Scientific mesh workbench roadmap

Updated 2026-11-15. The six-capability evidence release at `0b4a656` proves guarded operations and a bounded shared inspection scope. It does not make every installed algorithm or arbitrary imported mesh qualified. The workbench is a product surface for selecting an object, choosing an operation, running a managed job, and reviewing geometry and recorded facts.

## Product shape

Use a dedicated **Workbench** tab in DevShell Scientific Runtimes, with the selected provider visible in the left rail. A detached operating-system window would need a second native bridge and independent job ownership; the tab keeps one profile, one cancel action, and the existing History/artifact checks. MATH3D `main` was pulled for design review at `030d13b0` and already has a separate `MeshOperationsPanel`; later product handoff should pass a saved artifact and provenance into that workspace instead of pretending the two operation engines have identical behavior.

The workbench has three steps: **Object** (registered local copy, hash, format and validation), **Operation** (provider, feature, parameters, scope and run/cancel), and **Result** (input/output 3D layers, counts, bounds, topology, diagnostics, log and artifact hashes). Switching operation must preserve the object only when its format is accepted. Each run writes a fresh directory and History record. Failed or cancelled runs must not advertise successful geometry. Opening or switching the tab performs no computation.

## Provider and operation contract

| Provider | First operations in the workbench | Boundary |
|---|---|---|
| CGAL | Validate, guarded isotropic remesh, orientation repair, bounded hole fill | Existing `cgal-recipe` adapter and OBJ output; closed/open input rules shown per operation |
| VTK | Inspect, simplify, compute normals | Existing `recipe` adapter and VTP output; topology and auto-orientation restrictions shown per operation |
| Gmsh | Next: registered surface and volume generation | Separate dimensional input and cell-preserving output; never present a boundary surface as the volume result |
| Python/SciPy, SageMath | Next: typed numeric or exact-result workspace panels | No mesh operation is implied by the provider being installed |

The operation catalog in this first slice is a UI projection of already registered native actions. Native allowlists, dataset hashes, output paths, timeouts and owned process cancellation remain authoritative. The UI must never construct a shell command or interpret an arbitrary file as executable code. Capability labels must distinguish **available action**, **qualified scope**, **current evidence**, and **unsupported input**.

## Delivery sequence

1. **Integrated desktop slice (started here).** Add the Workbench tab for CGAL and VTK. Reuse registered copies, managed adapters, History and the existing 3D/text artifact inspector. Accept explicit import through the current CGAL-validated registration path. Verify the React production build and native action routing. This slice does not claim live desktop acceptance at the new HEAD.
2. **Provider-neutral object intake.** Let VTK register OBJ/STL/PLY independently; add VTP when a bounded parser and preview gate are ready. Show the input mesh in 3D before running, retain its original and copied hashes, and make format/topology rejection visible before submission where the policy is known. Test changed files, large files, malformed files, cancellation and restart.
3. **Typed operations and result review.** Move the catalog to a versioned contract shared with the native allowlist. Add provider-specific parameter validation, result panels for topology/volume/quality/normal arrays, before/after camera synchronization, full versus sampled geometry labels, export and saved operation presets. Gate each new operation with positive, pathological, cancellation, drift and History evidence. Keep user choice explicit when CGAL and VTK semantics differ.
4. **MATH3D handoff and broader providers.** Pull MATH3D at the target commit, map verified output into its mesh document and operation history, and re-open saved documents. Add Gmsh surface/volume workflows as separate typed cases. Add SciPy and Sage result viewers only for their actual numeric/exact outputs. Rebuild the multi-capability release and signed portable evidence after live desktop and broker acceptance on the merged HEAD.

## Acceptance before calling this complete

- Import/select an object, switch CGAL/VTK operations, run and cancel from DevShell, then reopen each result through History.
- Verify the same input/output hash and geometry counts in the 3D and textual views; reject changed artifacts and invalid parameter or format combinations.
- Exercise a successful output, an expected rejection, cancellation, restart, and saved-document reload in the real desktop app.
- Keep qualified class boundaries and ranking abstention visible. Do not promote support based on an attractive preview or an unverified worker result.
