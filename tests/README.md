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
