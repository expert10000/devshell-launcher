# Local scientific environments

## This workstation: installed 2026-10-09

| Component | CGAL environment | VTK environment |
| --- | --- | --- |
| Prefix | `G:\master\.conda\devshell-cgal` | `G:\master\.conda\devshell-vtk` |
| Python | 3.11.17 | 3.11.17 |
| Runtime bindings / C++ SDK | CGAL 6.0.1 / 6.0.1 | VTK 9.6.1 / 9.6.1 |
| NumPy / SciPy | 2.4.6 / 1.17.1 | 2.4.6 / 1.17.1 |
| CMake / Ninja | 4.4.4 / 1.13.2 | 4.4.4 / 1.13.2 |

CGAL dependencies include Boost 1.88.0, GMP 6.3.0, MPFR 4.2.2, and Eigen 5.0.1. Visual Studio 2022 Community has the x64 MSVC 14.44.35207 toolset installed. These are recorded local package/tool facts, not compile-test results.

Passed: Python, NumPy/SciPy imports, CGAL Point_3, VTK version/vtkPolyData, CMake/Ninja version commands, and SDK header/CMake-config presence. C++ compilation/linking and VTK rendering are untested; readiness is partial. Exact Conda package locks were saved locally as `.scientific/locks/cgal-win-64-explicit.txt` and `.scientific/locks/vtk-win-64-explicit.txt`.

## Install missing components

Run from the DevShell repository with PowerShell 7. Supply an existing workspace root and the actual Conda executable, not an activation alias.

```powershell
./tools/Install-ScientificRuntimes.ps1 `
  -WorkspaceRoot 'G:\master' `
  -CondaExecutable '<absolute-path-to-conda.exe>' `
  -Kind both `
  -PublishToLauncher
```

The installer creates separate workspace-local `.conda/devshell-cgal` and `.conda/devshell-vtk` environments. It does not change existing `math3d-cgal`, base Python packages, system PATH, WSL, or Docker. Conda downloads may use its existing package cache. Environments are intentionally outside the OneDrive checkout.

When every required package is already present, installation is skipped without upgrading the environment. Missing packages may require Conda to resolve compatible dependencies inside that dedicated environment. A non-Conda directory at the target prefix is rejected rather than overwritten.

CGAL includes Python bindings, `cgal-cpp`, Boost/GMP/MPFR dependencies, Eigen, NumPy/SciPy, CMake, and Ninja. Conda resolves compatible binding/SDK versions; their version numbers must be reported separately rather than assumed to be the newest release. VTK includes Python/SDK packages and their dependencies, NumPy/SciPy, CMake, and Ninja.

Package provenance: [CGAL C++ on conda-forge](https://anaconda.org/conda-forge/cgal-cpp), [VTK on conda-forge](https://anaconda.org/conda-forge/vtk). Compiler/toolchain requirements: [CGAL dependencies](https://doc.cgal.org/latest/Manual/thirdparty.html).

## Refresh local information

```powershell
./tools/Inspect-ScientificRuntimes.ps1 `
  -RuntimeRoot 'G:\master\.conda' `
  -PublishToLauncher
```

This explicit action runs bounded interpreter/import probes and local tool version commands. It collects:

- Environment root, executable, Python version, and architecture.
- Conda/Python package inventory, versions, builds, and sanitized package channels.
- CGAL Point_3 or VTK version/vtkPolyData import evidence, plus NumPy/SciPy imports.
- SDK header and CMake config locations, reported SDK package versions.
- Environment-local CMake/Ninja versions and executable paths.
- Installed MSVC toolchain path/version, without running a compiler build.
- Probe outcome, duration, and recorded timestamp.

Interpreter subprocesses have a 60-second timeout and environment-local DLL search paths. Tool version commands have 10-second timeouts. No generated/user code, C++ builds, linking, or rendering is run. The report marks those capabilities untested and overall readiness partial.

The machine-local report is `.scientific/runtime-report.json`, ignored by Git. `-PublishToLauncher` copies it into existing launcher UI directories; it does not rebuild or launch the application. The published report is also ignored by Git.

## UI

After building the report-capable UI, open **RUNTIMES / Scientific**, then **Load local report**. Choose CGAL or VTK:

- Health: recorded probe results, durations, and explicit untested checks.
- Environment: actual installed paths and expandable compiler/SDK/tool evidence.
- Packages: full recorded package inventory and provenance.
- Integration: the structured worker request contract, not a submitted job.

Report loading reads only the already-generated local snapshot. It does not run probes, install packages, or make Internet requests. Changing a profile definition invalidates its readiness label; old report evidence remains clearly associated with its original installed environment. Switching profiles clears loaded report state, and stale asynchronous responses are ignored.

Next: explicit C++ compile/link smoke tests, geometry artifacts, VTK rendering/offscreen checks, and a managed native recipe runner with ownership, cancellation, and scoped results. Until those tests pass, do not label mesh operations, compiler integration, or rendering Ready.
