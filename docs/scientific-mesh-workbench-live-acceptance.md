# Mesh Workbench live acceptance at `a485cb0`

Run on Windows on 2026-11-15 in an isolated `a485cb0` worktree with the recorded CGAL 6.0.1 and VTK 9.6.1 Conda runtimes. The frontend and native launcher were built in that worktree. The local `.scientific` records are ignored by Git; the IDs below identify the observed evidence, not a portable release qualification.

| Journey | Live observation | Managed run |
| --- | --- | --- |
| VTK import | Native file picker copied a 116-byte closed tetrahedron to a content-addressed registered path; original stayed in place. | `3eb3d642aa9b4df9a19e36d1ec83683b` succeeded |
| Input preview | Selected the registered tetrahedron; VTK rendered 4 points and 4 triangles after verifying its copy hash. | Read-only preview |
| VTK operation | `mesh.inspect` returned a VTP artifact, 4 points, 4 triangles, 0 boundary edges, and 0 non-manifold edges; comparison rendered in the Workbench. | `0b140ea1e53c4426804d1e29580b9ecf` succeeded |
| CGAL cancellation | Selected the same registered tetrahedron, started `cgal.validate`, then cancelled during the native build. No successful artifact was advertised. | `a40819d9a5ca4b0497ea5a62fe9a5937` cancelled |
| CGAL operation | Retried after a desktop restart; `cgal.validate` completed on the registered tetrahedron. | `11f0ef47cc6d4b7cb05c5c9b27fc24e3` succeeded |
| VTK rejection | Imported an intentionally malformed OBJ through the picker. Registration recorded unvalidated bytes; `mesh.inspect` rejected the empty/invalid surface and exposed worker diagnostics. | Import `1cb3e3dca6b74f5c87e95291f5cd579d` succeeded; `a9ee83f55e7940f59ba2364b24a56dff` failed |
| Restart and History | Killed and relaunched the isolated desktop process. History listed the accepted, failed, and cancelled runs without rerunning them. | Read-only History |

The restart exposed a product recovery gap: the Workbench loaded with an empty dataset list until **Load registered objects** was clicked, and it offered no direct route to the last saved result. The first commit loads the registered metadata and History on Workbench entry and provides saved-result links. These read only local metadata; opening the Workbench still starts no operation. The History copy now describes failed and cancelled records accurately.

The original run snapshots were captured at `a485cb0` while generated frontend assets in the isolated worktree were dirty. Treat them as live diagnostic evidence. Release qualification is rebuilt later at the final clean HEAD.
