# Managed CGAL hole repair

The Scientific CGAL panel can now run three explicit hole fills on a registered local OBJ copy:

| Recipe | Required boundary | Patch |
| --- | --- | --- |
| `cgal.fill-one-hole` | One three-edge loop | One triangle |
| `cgal.fill-quad-hole` | One four-edge loop | Two triangles |
| `cgal.fill-two-quad-holes` | Two four-edge loops | Four triangles |

Import an OBJ dataset through Scientific, select the installed Windows Native CGAL profile, choose **Repair holes**, then select the boundary shape and input. The runner creates a fresh run directory, checks the registered copy's SHA-256, builds the scoped native executable, and invokes it through the JSON adapter. History keeps the request, full log, result, output OBJ, and run fingerprint. The source dataset is never modified.

The input must be a connected triangle manifold with the selected boundary loops. The worker rejects degenerate faces and self-intersections. The adapter measures the saved OBJ independently and requires the expected face count, closed boundary, one component, positive volume, and agreement with the native evidence before reporting `mesh.repair`. These three recipes do not constitute general mesh repair or an L5–L9 qualification.

To replay the managed adapter acceptance on a machine with the CGAL prefix and built worker:

```powershell
$CgalPrefix = 'C:\path\to\devshell-cgal'
$Worker = 'C:\path\to\build\Release\devshell_cgal_hole_repair.exe'
python tools/scientific-cgal-managed-repair-acceptance.py `
  --python (Join-Path $CgalPrefix 'python.exe') `
  --worker $Worker `
  --prefix $CgalPrefix `
  --output-root .scientific\reports\cgal-managed-repair
```

The replay uses copied authored fixtures for all three positive recipes. It also checks that a wrong operation and a changed dataset hash produce failed managed results without an output artifact. The report and its run directories remain under the selected output root.
