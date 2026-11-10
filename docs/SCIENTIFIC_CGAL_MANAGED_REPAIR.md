# Managed CGAL hole repair and MATH3D handoff

The Scientific CGAL panel can now run three explicit hole fills on a registered local OBJ copy:

| Recipe | Required boundary | Patch |
| --- | --- | --- |
| `cgal.fill-one-hole` | One three-edge loop | One triangle |
| `cgal.fill-quad-hole` | One four-edge loop | Two triangles |
| `cgal.fill-two-quad-holes` | Two four-edge loops | Four triangles |
| `cgal.fill-bounded-holes` | 1–8 loops, 3–12 edges each, at most 64 boundary edges | Sum of `(edges − 2)` triangles |

Import an OBJ dataset through Scientific, select the installed Windows Native CGAL profile, choose **Repair holes**, then select the boundary shape and input. The runner creates a fresh run directory, checks the registered copy's SHA-256, builds the scoped native executable, and invokes it through the JSON adapter. History keeps the request, full log, result, output OBJ, and run fingerprint. The source dataset is never modified.

The input must be a connected triangle manifold with the selected boundary loops. The worker rejects degenerate faces and self-intersections. The adapter measures the saved OBJ independently and requires the expected face count, closed boundary, one component, positive volume, and agreement with the native evidence before reporting `mesh.repair`. It also verifies that every original oriented triangle remains and the patch covers exactly the original rim. The bounded recipe does not handle arbitrary polygon soup or imply L5–L9 qualification.

For a successful repair in History, **Check in MATH3D importer** starts a separate managed job. It rechecks the saved source and result hashes, reruns the patch audit, loads the repaired OBJ through MATH3D's actual desktop mesh importer, and compares topology, bounds, area, and volume. The handoff report and consumer result are saved in the new job directory; the source run remains read-only. This is importer evidence, not a `.m3dm` document or viewer certification.

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

The replay uses copied authored fixtures for all four positive recipes and checks MATH3D import for each. It also checks that a wrong operation and a changed dataset hash produce failed managed results without an output artifact. Omit `--math3d-checkout` to test only the managed repair adapter. The report and its run directories remain under the selected output root.
