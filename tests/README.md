Run the Jupyter service integration checks with the profile's Python environment:

```powershell
& 'C:\Users\janko\.venvs\devshell-jupyter\Scripts\python.exe' tests\test_service_control.py
```

The checks use a temporary workspace and an available local port. They verify authenticated startup, server reuse, graceful shutdown, restart, and protection of other workspaces and occupied ports. Test servers are stopped after the checks; browser opening is intercepted.

The desktop-three profile defines a Jupyter `service` (name, Python executable, port) and `pythonEnvironment`. New terminals inside that project's directory inherit its Python environment. Service tasks use `serviceAction` to reach the same controller as the sidebar controls, without sending commands into a busy terminal.

Run Git dashboard integration checks with `dotnet run --project tests/DashboardChecks/DashboardChecks.csproj`. The checks create disposable local repositories and exercise clean status, renamed and Unicode paths, diverged upstream counts, detached HEAD, invalid roots, and missing tools. Add `-- BatchLauncher/profiles/desktop-three.json` to inspect the configured repositories instead.

Repository cards use the project's `repositories` entries and their `buildTask`/`runTask` names. Health checks inspect project/task directories, Git roots, `requiredTools`, `pythonEnvironment`/`pythonModules`, and configured service ports. Counts are based on local upstream refs, without automatically fetching or modifying repositories.

Repository card actions now run as managed PowerShell jobs, with live output under **Logs**, exit status, optional Run after a successful build, and Stop for the entire owned process tree. Closing DevShell stops its repository jobs. Full logs are retained in the user's local application data under `DevShellLauncher/repository-logs`; cards display the latest 24,000 characters. Task-menu actions still use terminals.

Run lifecycle checks with `dotnet run --project tests/RepositoryJobChecks/RepositoryJobChecks.csproj -- <absolute-path-to-pwsh.exe>`. They exercise build/run sequencing, failure gating, persistent logs, duplicate launches, cancellation, and child processes outliving their shell, using isolated temporary working folders.

Repository cards offer Fetch, Pull, and Clone. `url` enables cloning into missing or empty folders and verifies origin before fetching or pulling. Fetch permits local edits; Pull requires a clean checkout on a branch tracking origin and uses fast-forward only. Git actions share the managed job's Stop and Logs controls. Update All processes the active profile's repositories sequentially, reports each result, continues after failures, and skips queued repositories when stopped. It never commits, stashes, resets, or switches branches automatically.

Each repository can declare `requiredTools`, `pythonEnvironment`, `pythonModules`, and relative `dependencyFolders`. Environment checks detect missing declared Node packages, .NET SDKs, Python environments/modules and simple requirements.txt version constraints. Unsupported requirement entries are reported for manual verification. Setup commands are shown without installing packages automatically. The laptop profile checks its configured Node/npm and Python paths, and DevShell's nested frontend and .NET project.

Run sync and environment checks with `dotnet run --project tests/RepositorySyncChecks/RepositorySyncChecks.csproj -- <absolute-path-to-pwsh.exe> tools/Sync-Repository.ps1`. They exercise actual Clone/Fetch/Pull using temporary bare repositories through a process-local HTTPS URL rewrite, including Unicode/quoted paths, dirty trees, divergence, detached HEAD, unexpected origin, occupied folders, queue continuation/cancellation, and dependency diagnostics. These tests do not contact GitHub or change global Git configuration.

Run terminal regression checks with `dotnet run --project tests/TerminalChecks/TerminalChecks.csproj -- <absolute-path-to-pwsh.exe>`. Run with stdout/stderr redirected to exercise the Windows standard-handle duplication failure. The checks verify interactive PowerShell/CMD input, ConPTY output, resize, and exit notification. Theory PDF tasks use `tools/Build-Theory.ps1` to raise MiKTeX memory limits for the build only and set Windows-compatible bibliography paths.
