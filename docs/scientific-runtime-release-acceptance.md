# Scientific runtime release acceptance

The 200-image review archive is recorded UI evidence. Run
`python tools/scientific-broker/verify_runtime_review.py --archive <zip>` to check it
against the source-controlled manifest and digest. A screenshot does not prove an
operation, installed application, or current-source release gate.

| Gate | Existing evidence | Required next evidence |
| --- | --- | --- |
| Six qualified capabilities | Signed `46067b6` bundle; `447c1ca` release running | Complete same-source desktop and broker gates; sign and verify the bundle offline |
| CGAL Boolean with distinct meshes | Managed Boolean action and transformed self-cube fixture tests | Two independently registered source hashes, closed-solid validation, independent volume/topology checks and rejection cases |
| Gmsh after Boolean | Qualified standalone volume workflow | Typed Boolean-surface intake, dimensional and physical-group fidelity, positive element-quality evidence |
| VTK analysis | Qualified inspect/read scopes | Gmsh output conversion, measured topology/geometry change, offscreen result evidence |
| Python/SciPy measurement | Branch inventory detects Python / SciPy and runs a bounded float64 ABI smoke; the captured UI predates this change | Managed measurement with units, tolerances, input hash and artifact lineage |
| MATH3D handoff | Workbench saved-result handoff tested with MATH3D `12e87f93` | Typed multi-provider lineage, save/export, cold reopen and identity verification |
| Installed desktop | Isolated source-build desktop acceptance | Installer/executable hashes, offline/upgrade and clean-profile journeys |

The end-to-end target is: select or create a known mesh; validate A and B; run
CGAL Boolean on distinct inputs; mesh with Gmsh; inspect with VTK; compute a
SciPy measurement; import typed artifacts into MATH3D; save/export; cold reopen;
verify source, consumer, artifact hashes, units, frames, generation and lineage.
Unavailable stages must report `blocked` with an explicit reason. They cannot be
marked successful by a later provider or inferred from the screenshot archive.

Run the local inventory with PowerShell 7 (`pwsh -File tools/Inspect-ScientificRuntimes.ps1 -RuntimeRoot <conda-root>`). The Python / SciPy row uses `devshell-scientific`; `partial` means its import and ABI smoke passed, not that a measurement capability is qualified.
