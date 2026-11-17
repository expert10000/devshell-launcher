# Six-capability release record — 2026-11-17

The isolated release run completed at DevShell source `447c1ca7bf22bab6270ddc4381ea125d578168ad` with pulled MATH3D consumer `12e87f93d6d50737553fd3c229b8863481336c60`.

| Gate | Recorded result |
| --- | --- |
| Managed desktop | Six passed: CGAL inspection, orientation repair, remesh, hole repair, Gmsh volume, VTK read |
| Standard broker | The same six passed with source-pinned case profiles |
| Source and consumer identity | Hash-verified Git source snapshot and MATH3D package, build, and consumer source pins |
| Resumability | All release stages completed in the sealed checkpoint; failed or changed prior evidence cannot be promoted |
| Coexistence record | `coexistence-ea35b93c57a748d9abd7012b0b198e34.json`, SHA-256 `27c13cb4150a665db2d49ee5c5a83aea65e1e6ab213c4450b2af5ad1bde49e49` |
| Signed publication | `publication.json`, SHA-256 `91bafbf856c4b4e6887740b4d6e95323792b53bf6692d1d06119bc03abcb55da` |
| Portable bundle | [Download the source-pinned ZIP](https://github.com/expert10000/devshell-launcher/releases/download/scientific-six-447c1ca7bf22/six-capability-e81cd6e407241fa443c37ae70d4b9c94d17fa049152577ca0887482fcccf41b3.zip), SHA-256 `e81cd6e407241fa443c37ae70d4b9c94d17fa049152577ca0887482fcccf41b3` |
| Manifest and trust | Manifest SHA-256 `738932a5c43f4e1ae6656d937d8d5de12e1b97f53d5c3f9eb87bf99bf7996c7e`; trusted Ed25519 key `devshell-six-2026-11`; 163 verified artifact payloads |
| Offline verdict | `verified-historical-evidence`; the downloaded ZIP matched the local bundle digest and independently passed signature, manifest, payload and release-link verification |

The signed inspection publication completed its class scope, shared benchmark, advisor, MATH3D product, managed desktop journey, report, bundle, and independent offline verification. The desktop journey resumed safely after a page locator timeout: it preserved five completed actions, then finished manual selection, fallback, cancellation, and the torus and star manual paths. The downloaded archive passed the same offline verifier as the local archive.

To verify the downloaded bundle without the release worktree, run `python tools/scientific-broker/portable_six_evidence.py verify --bundle <zip> --trust-store schemas/scientific-evidence-trust.v1.json` with the source-pinned verifier and trust store. The release tag targets `447c1ca7bf22bab6270ddc4381ea125d578168ad`.

This is a historical source-pinned release record once main advances beyond `447c1ca`. The separate typed cross-provider journey is under draft review. Its local CGAL → Gmsh → VTK → SciPy → MATH3D smoke does not expand the six released capability scopes.
