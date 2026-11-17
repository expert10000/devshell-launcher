# Six-capability release record — 2026-11-17

The isolated release run completed at DevShell source `447c1ca7bf22bab6270ddc4381ea125d578168ad` with pulled MATH3D consumer `12e87f93d6d50737553fd3c229b8863481336c60`.

| Gate | Recorded result |
| --- | --- |
| Managed desktop | Six passed: CGAL inspection, orientation repair, remesh, hole repair, Gmsh volume, VTK read |
| Standard broker | The same six passed with source-pinned case profiles |
| Source and consumer identity | Hash-verified Git source snapshot and MATH3D package, build, and consumer source pins |
| Resumability | All release stages completed in the sealed checkpoint; failed or changed prior evidence cannot be promoted |
| Coexistence record | `coexistence-ea35b93c57a748d9abd7012b0b198e34.json`, SHA-256 `27c13cb4150a665db2d49ee5c5a83aea65e1e6ab213c4450b2af5ad1bde49e49` |

The signed inspection publication is a separate gate. Its class scope, shared benchmark, advisor, and MATH3D product stages passed; the managed desktop journey is being resumed from its saved action checkpoint after a page locator timeout. Do not treat the publication as complete until its desktop record, report, signed bundle and independent offline verification pass.

This is a historical source-pinned release record once main advances beyond `447c1ca`. The separate typed cross-provider journey is under draft review. Its local CGAL → Gmsh → VTK → SciPy → MATH3D smoke does not expand the six released capability scopes.
