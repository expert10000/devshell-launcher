# Workbench operation catalog v1

`schemas/scientific-workbench-operations.v1.json` is the shared desktop contract for operation IDs, provider, accepted input extensions, output extension, defaults, and parameter bounds. The React Workbench renders controls from it. The native launcher reads the same file and rejects wrong providers, formats, output names, missing or unknown parameters, and values outside bounds before a worker can claim success. Workers retain their narrower geometry guards.

The catalog corrects guarded `cgal.remesh` intake to OBJ. Validation still accepts OBJ/STL/PLY/OFF; orientation and bounded hole repair require OBJ. VTK inspection, simplification, and normals accept OBJ/STL/PLY/VTP. Each managed result records `operationCatalogVersion` in provenance; the catalog and renderer are part of the source drift fingerprint for these operations.

The result panel highlights output size, triangle change, topology, surface area or signed volume when recorded, and observed simplification reduction. Before and after geometry open in separate views with a shared camera, zoom, clip plane, and scale; the combined view remains selectable. Text describes full worker geometry even when the preview samples triangles. Provider selection remains manual in the runtime rail. Inspection advisor abstention and its qualified scope are unchanged by this catalog.

Live desktop check on 2026-11-15: the catalog-backed VTK `mesh.inspect` run `c61f9cf5305747058744e39229394a60` succeeded on the imported VTP, saved catalog version 1 in request and result provenance, showed 4 output points and 4 triangles with zero boundary/non-manifold edges, and opened synchronized Input and Result 3D views.
