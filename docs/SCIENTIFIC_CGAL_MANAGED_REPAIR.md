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

**Run repair L9 products** requires current repair L8 support and the pinned `product-contract.v1.json`. It makes four fresh managed repairs, checks their output hashes against the L7 consumer baseline, and runs the existing MATH3D importer, document save/reopen, independent M3DM reload and viewer on each result. It also changes one M3DM byte and requires the independent reader to reject it without a reload report. The job saves all child requests, products, consumer reports and screenshots. A `mesh.repair@L9` record is issued only when the saved L8 chain, four products, nine artifacts per case, consumer sources, and rejection evidence verify. History marks it stale when the MATH3D source or product contract changes.

The broker's read-only `audit-repair` command checks saved repair records and reports current eligibility, rejected L9 runs, and a managed requalification recipe plan:

```powershell
dotnet tools/scientific-broker/bin/Release/net8.0/ScientificBroker.dll audit-repair `
  <devshell-repo> <installed-root> <math3d-checkout> <profile-id>
```

This audit does not write a manifest or raise a capability. `export` includes the scoped `mesh.repair@L9` entry only when the saved four-case record, all nine supporting levels, fixture hashes, MATH3D source hashes, and worker identity still match. The entry carries four fixed recipe/input/output references. An unqualified host exports no repair capability.

A separate broker profile can use that manifest with `capabilityId: mesh.repair`, `adapter: tools/scientific-cgal-hole-repair-worker.py`, and the matching `devshell_cgal_hole_repair.exe`. `tools/New-CgalRepair-BrokerProfile.ps1 -Worktree <path> -Math3DCheckout <path>` selects the worker by its certified hash, writes an isolated config beside the export, and runs broker verification. Run the broker and smoke with a host Python that has `psutil` for process-tree cleanup verification; the config's `python` field still points to the pinned CGAL worker environment. The profile script checks the host Python and accepts `-BrokerPython` when it is not the default `python`. Submit a typed `caseId` (`triangle`, `square`, `two-squares`, or `pentagon`) and a registered OBJ input with the certified fixture hash. The broker derives the repair recipe and output name from the manifest and checks the exact repaired OBJ hash before serving it.

Promotion rechecks the saved worker result, patch audit, exact case output, L9 manifest reference, MATH3D consumer sources, and process cleanup. `python tools/scientific-broker/repair_smoke.py run --config <repair-config.json>` runs all four broker cases, promotes each, then saves and reopens each in MATH3D, independently reloads M3DM, and mounts the Mesh viewer. The resulting `repair-smoke.json` has a hash sidecar and can be checked with the script's `verify` command.

For end-to-end release verification, start an isolated `desktop-five` DevShell session with a WebView2 debug port and set `DEVSHELL_CDP_URL`. Run `node tests/scientific-cgal-repair-managed-ui-checks.mjs` to produce the managed L0–L9 repair chain. Re-run `audit-repair`, export a candidate manifest, configure a separate repair broker against that manifest, and run `repair_smoke.py`. The release gate requires that verified four-case smoke record:

`tools/Run-CgalRepair-Acceptance.ps1 -Math3DCheckout <path>` builds and starts a short-path isolated Git worktree and drives that managed chain. It retains the worktree and saved runs for inspection. Use `-ExistingWorktree <path> -SkipBuild -ResumeFrom L6` (or L7–L9) only when its earlier records are still current. Rebuilding the desktop executable changes the pinned runtime-lab identity, so a code change requires a new full run. `audit-repair` now lists each level's current, stale, unknown, or missing state and the earliest level to rerun.

```powershell
python tools/scientific-broker/release_certification.py certify `
  --config <repair-config.json> --installed-root <launcher-install-root> `
  --profile-id desktop-five --release-tag <tag> `
  --smoke-record <job/repair-smoke.json> --output-root .scientific/releases
python tools/scientific-broker/release_certification.py verify `
  --config <repair-config.json> --report <release/qualification-report.json>
```

A qualified repair release links the fresh export, current runtime inventory, complete L0–L9 chain, all four promoted broker jobs, and MATH3D product evidence. With no current L9 chain, `audit-repair` reports `eligible: false` and the exporter omits repair.

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
