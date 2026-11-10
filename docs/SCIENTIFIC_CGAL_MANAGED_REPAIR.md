# Managed CGAL hole repair and MATH3D handoff

The Scientific CGAL panel can now run four hole-fill recipes on a registered local OBJ copy:

| Recipe | Required boundary | Patch |
| --- | --- | --- |
| `cgal.fill-one-hole` | One three-edge loop | One triangle |
| `cgal.fill-quad-hole` | One four-edge loop | Two triangles |
| `cgal.fill-two-quad-holes` | Two four-edge loops | Four triangles |
| `cgal.fill-bounded-holes` | 1–8 loops, 3–12 edges each, at most 64 boundary edges | Sum of `(edges − 2)` triangles |

Import an OBJ dataset through Scientific, select the installed Windows Native CGAL profile, choose **Repair holes**, then select the boundary shape and input. The runner creates a fresh run directory, checks the registered copy's SHA-256, builds the scoped native executable, and invokes it through the JSON adapter. History keeps the request, full log, result, output OBJ, and run fingerprint. The source dataset is never modified.

The input must be a connected triangle manifold with the selected boundary loops. The worker rejects degenerate faces and self-intersections. The adapter measures the saved OBJ independently and requires the expected face count, closed boundary, one component, positive volume, and agreement with the native evidence before reporting `mesh.repair`. It also verifies that every original oriented triangle remains and the patch covers exactly the original rim. The bounded recipe does not handle arbitrary polygon soup or imply L5–L9 qualification.

## Repair L5 and L6 qualification path

The **Load repair fixtures** action registers the pinned CC0 fixture pack under `scientific/fixtures/cgal-repair-qualification/`. The manifest and five OBJ hashes are checked before registration. **Run repair L5 qualification** requires current CGAL L0–L4 records and registered copies, then runs the four repairs above plus closed-mesh and wrong-operation rejections through the managed adapter. It saves each child request, result, artifact hash and audit, along with the fixture manifest and linked lower-level records. A `mesh.repair@L5` record is issued only when the saved six-case evidence verifies.

**Reproduce repair L6** requires a current repair L5 record and the same current L0–L4 support. It replays all six cases, compares the four output and patch hashes byte-for-byte and checks that both rejections still have no output. The saved verifier reopens the L5 reference and candidate evidence before issuing a `mesh.repair@L6` record. These levels apply only to `mesh.repair`; validation, interoperability and product records are separate. Source changes can make earlier support stale, so the new path must be run on the target machine before claiming a current qualification.

**Check repair L7 consumers** requires a current repair L6 record. It reopens all four saved outputs with an independent OBJ parser, VTK and the MATH3D desktop importer, compares topology, bounds, surface area and signed volume, and requires VTK to reject malformed OBJ input. The saved verifier checks the source L6 record, every report and artifact hash, the consumer source contract, and pinned lower records before issuing `mesh.repair@L7`. A live run is required to establish that record.

**Test repair L8 resilience** requires a current repair L7 record. It repeats each of the four VTK reads three times under a 128 MiB process limit and compares each report to the L7 baseline. Separate owned children must cancel, time out, and stop at the memory limit without output. The saved verifier checks all twelve report hashes, process-limit observations and the linked L7 record before issuing `mesh.repair@L8`. This suite is limited to the authored repair fixtures and the VTK handoff; a live run is required before claiming L8.

For a successful repair in History, **Save and verify MATH3D document** starts a separate managed job. It rechecks the saved source and result hashes, reruns the patch audit, loads the repaired OBJ through MATH3D's actual desktop mesh importer, and compares topology, bounds, area, and volume. It saves a Mesh document, binary resource and `.m3dm`, reopens them with MATH3D, independently parses the M3DM with Python, and mounts the reopened document in the real Mesh viewport. The new run keeps the document, resource, M3DM, JSON evidence and viewer screenshot; the source run remains read-only. This product check is separate from repair L5–L9 qualification and broker certification.

To replay the managed adapter acceptance on a machine with the CGAL prefix and built worker:

```powershell
$CgalPrefix = 'C:\path\to\devshell-cgal'
$Worker = 'C:\path\to\build\Release\devshell_cgal_hole_repair.exe'
$Math3D = 'C:\path\to\Math3D'
python tools/scientific-cgal-managed-repair-acceptance.py `
  --python (Join-Path $CgalPrefix 'python.exe') `
  --worker $Worker `
  --prefix $CgalPrefix `
  --output-root .scientific\reports\cgal-managed-repair `
  --math3d-checkout $Math3D
```

The replay uses copied authored fixtures for all four positive recipes and checks MATH3D import for each. It also checks that a closed mesh, wrong operation and changed dataset hash produce failed managed results without an output artifact. Omit `--math3d-checkout` to test only the managed repair adapter. The report and its run directories remain under the selected output root.

To verify saved MATH3D documents, independent M3DM reload and viewer regression for all four cases, pass that replay's `acceptance.json` to:

```powershell
$ManagedAcceptance = 'C:\path\to\acceptance.json'
python tools/scientific-cgal-repair-product-acceptance.py `
  --managed-acceptance $ManagedAcceptance `
  --checkout $Math3D
```

This product replay also changes one M3DM byte and requires the independent reader to reject it. Its `product-acceptance.json` records each document, M3DM, screenshot and source hash. The run proves these four authored fixtures on this machine; it does not certify arbitrary repairs.
