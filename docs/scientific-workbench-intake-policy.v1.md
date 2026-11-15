# Workbench intake policy v1

The desktop picker registers up to 16 local files per action, at most 32 MiB each. Registration copies bytes under a content-addressed path, verifies the source did not change while copying, and records the copy hash. Later previews and operations verify the registered copy again. Changed originals may be imported as a new identity; changed registered copies are rejected. No original is rewritten.

| Provider | Registered inputs | Intake check | Preview |
| --- | --- | --- | --- |
| VTK | OBJ, STL, PLY, VTP | Size, regular file, copied hash. VTP additionally requires well-formed local XML PolyData. | OBJ, STL, PLY, VTP through the dedicated VTK preview reader. |
| CGAL | OBJ, STL, PLY, OFF | Size, regular file, copied hash, then CGAL validation. | OBJ, STL, PLY through VTK; OFF has no input 3D preview. |

VTP v1 permits XML/base64 PolyData with a `Piece`. It rejects DTDs, processing instructions, XML namespaces/includes, external-reference attributes, unknown `DataArray` formats, and raw appended data. Its XML reader resolves no external resources and is limited to the 32 MiB document bound. Geometric validity is checked by the VTK operation, and import never claims mesh qualification. The Workbench leaves a selected object visible when the operation cannot read its format and disables Run with an explicit accepted-format message.

Live VTP acceptance on 2026-11-15: a saved four-triangle `mesh-result.vtp` was imported, previewed as 4 points / 4 triangles, and inspected successfully in managed run `9d6354636fcf4f53affcf089a39fe363`. Import of the malformed `invalid.vtp` fixture failed in managed run `b8ee0770638b4eb59e3bd4778ab504d7` with a parse diagnostic; it did not enter the registry. Unit checks cover malformed XML, DTD, external reference, raw appended data, provider format separation, changed copies, empty and oversized files, and cancellation. The local runs are diagnostic evidence; final release qualification is a separate gate.
