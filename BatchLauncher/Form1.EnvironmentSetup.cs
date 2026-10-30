using System.Text.Json;

namespace BatchLauncher;

public partial class Form1
{
    private RepositoryPreparation CreateRepositoryPreparation(WorkspaceProject project, WorkspaceRepository repo)
    {
        var resolved = ResolveRepository(project, repo);
        var profileId = _activeWorkspaceProfileId;
        var tools = EnvironmentTools();
        var root = _workspace.Globals?.WorkspaceRoot ?? Path.GetDirectoryName(resolved.Path)!;
        var basePython = _workspace.Globals?.Vars?.GetValueOrDefault("basePython");
        var shell = _profiles.FirstOrDefault(profile => profile.Id == "pwsh") ?? throw new InvalidOperationException("PowerShell profile missing.");
        if (!_terminalManager.TryResolveProfileCommand(shell, out var command)) throw new InvalidOperationException("PowerShell is unavailable.");
        var servicePython = project.Service?.Kind != "jupyter" ? null : ExpandProjectValue(project, project.Service.Python);
        var serviceRoot = project.Service == null ? null : ExpandProjectValue(project, project.Root ?? "");
        async Task<List<HealthCheck>> Inspect(CancellationToken token)
        {
            foreach (var pair in PortableWorkspace.DiscoverTools(root))
                if (!tools.TryGetValue(pair.Key, out var existing) || !File.Exists(existing)) tools[pair.Key] = pair.Value;
            return await RepositoryEnvironment.InspectRepository(project.Id, repo.Id, resolved, tools, token).WaitAsync(token);
        }
        return new(async token =>
        {
            if (project.Service?.Kind == "jupyter" && File.Exists(servicePython))
            {
                await _serviceGate.WaitAsync(token);
                try
                {
                    var status = await DashboardInspector.Run(servicePython!, new[] { Path.Combine(AppContext.BaseDirectory, "service_control.py"), "status", "--root", serviceRoot!, "--port", project.Service.Port.ToString() }, cancellationToken: token).WaitAsync(token);
                    using var result = JsonDocument.Parse(status.Output);
                    if (status.Code != 0 || result.RootElement.GetProperty("state").GetString() != "stopped")
                        throw new InvalidOperationException("Stop this project's service before Prepare & Launch.");
                }
                finally { _serviceGate.Release(); }
            }
            var checks = await Inspect(token);
            var blocked = checks.Where(check => check.State == "error").ToArray();
            var manual = blocked.Where(check => check.FixTarget is null or "clone").ToArray();
            if (manual.Length > 0) throw new InvalidOperationException("Prepare & Launch needs a manual step: " + string.Join("; ", manual.Select(check => check.Detail)));
            var targets = blocked.Select(check => check.FixTarget!).Distinct().ToArray();
            if (targets.Length == 0) return null;
            var plan = EnvironmentSetup.Plan(resolved, root, tools, basePython, targets);
            return EnvironmentSetup.Command(command.Application, Path.Combine(AppContext.BaseDirectory, "tools", "Setup-Environment.ps1"), plan, AppContext.BaseDirectory);
        }, async token =>
        {
            var errors = (await Inspect(token)).Where(check => check.State == "error").ToArray();
            if (errors.Length > 0) throw new InvalidOperationException("Environment still needs attention: " + string.Join("; ", errors.Select(check => check.Detail)));
        }, token =>
        {
            var completion = new TaskCompletionSource<(RepositoryCommand, RepositoryCommand)>(TaskCreationOptions.RunContinuationsAsynchronously);
            BeginInvoke(new Action(async () =>
            {
                try
                {
                    token.ThrowIfCancellationRequested();
                    if (IsDisposed || profileId != _activeWorkspaceProfileId) throw new OperationCanceledException(token);
                    if (_workspace.Globals?.AutoDetectTools == true) await HandleWorkspaceToolsRefreshAsync();
                    var currentProject = _workspace.Projects!.First(item => item.Id == project.Id);
                    var currentRepo = currentProject.Repositories!.First(item => item.Id == repo.Id);
                    var cwd = ExpandProjectValue(currentProject, currentRepo.Path);
                    completion.TrySetResult((CreateRepositoryCommand(currentProject, currentRepo.BrowserBuildTask ?? currentRepo.BuildTask!, cwd),
                        CreateRepositoryCommand(currentProject, currentRepo.BrowserRunTask ?? currentRepo.RunTask!, cwd)));
                }
                catch (Exception error) { completion.TrySetException(error); }
            }));
            return completion.Task;
        });
    }

    private bool _environmentSetupChecking;
    private async Task HandleEnvironmentSetupAsync(JsonElement payload)
    {
        payload = payload.Clone();
        var profileId = _activeWorkspaceProfileId;
        var projectId = payload.GetProperty("projectId").GetString();
        var repositoryId = payload.GetProperty("repositoryId").GetString();
        var action = payload.GetProperty("action").GetString();
        var key = $"{profileId}:{projectId}:{repositoryId}";
        var serviceLocked = false;
        var checkingOwned = false;
        try
        {
            if (_environmentSetupChecking) throw new InvalidOperationException("Another environment repair is being checked. Wait for it to finish.");
            _environmentSetupChecking = checkingOwned = true;
            SendMessage(new { type = "repository.setup.checking", key, checking = true });
            var project = _workspace.Projects?.FirstOrDefault(p => p.Id == projectId) ?? throw new InvalidOperationException("Project not found.");
            var repo = repositoryId == "environment" ? new WorkspaceRepository { Path = project.Root ?? "", PythonEnvironment = project.PythonEnvironment,
                PythonModules = project.PythonModules, PythonPackages = project.PythonPackages } : project.Repositories?.FirstOrDefault(r => r.Id == repositoryId) ?? throw new InvalidOperationException("Repository not found.");
            IReadOnlyCollection<string>? targets = null;
            if (action is "fix" or "fix-plan")
            {
                var requested = payload.TryGetProperty("targets", out var values) ? values.EnumerateArray().Select(value => value.GetString() ?? "").Distinct().ToArray() : Array.Empty<string>();
                var checks = await RepositoryEnvironment.InspectRepository(project.Id, repositoryId!, ResolveRepository(project, repo), EnvironmentTools());
                var available = checks.Where(check => check.State == "error" && check.FixTarget is not (null or "clone")).Select(check => check.FixTarget!).Distinct().ToArray();
                targets = requested.Length == 0 ? available : requested.Intersect(available).ToArray();
                if (requested.Except(checks.Where(check => check.FixTarget != null).Select(check => check.FixTarget!)).Any())
                    throw new InvalidOperationException("This repair is no longer declared by the repository. Recheck its environment.");
                if (targets.Count == 0) throw new InvalidOperationException("No automatic repair is needed. Recheck the environment for any remaining manual steps.");
            }
            if (IsDisposed || profileId != _activeWorkspaceProfileId) return;
            var plan = CreateSetupPlan(project, repo, targets);
            SendMessage(new { type = "repository.setup.plan", key, setupPlan = plan });
            if (action is "setup" or "fix")
            {
                if (RepositoryUpdates.Active || _repositoryChangesPaths.Count > 0 || _repositoryRunner.Snapshot().Any(job => job.State is "queued" or "building" or "running"))
                    throw new InvalidOperationException("Finish or stop active repository jobs before repairing dependencies.");
                // A service can be running even when its last UI status is stale.
                if (project.Service?.Kind == "jupyter")
                {
                    serviceLocked = await _serviceGate.WaitAsync(0);
                    if (!serviceLocked) throw new InvalidOperationException("A service operation is in progress. Retry when it finishes.");
                    var python = ExpandProjectValue(project, project.Service.Python);
                    if (File.Exists(python))
                    {
                        var status = await DashboardInspector.Run(python, new[] { Path.Combine(AppContext.BaseDirectory, "service_control.py"), "status", "--root",
                            ExpandProjectValue(project, project.Root ?? ""), "--port", project.Service.Port.ToString() });
                        if (status.Code != 0) throw new InvalidOperationException("Could not check the service. Stop it before repairing its environment.");
                        using var result = JsonDocument.Parse(status.Output);
                        if (result.RootElement.GetProperty("state").GetString() != "stopped")
                            throw new InvalidOperationException("Stop this project's service before repairing its environment.");
                    }
                }
                if (IsDisposed || profileId != _activeWorkspaceProfileId) return;
                if (RepositoryUpdates.Active || _repositoryChangesPaths.Count > 0 || _repositoryRunner.Snapshot().Any(job => job.State is "queued" or "building" or "running"))
                    throw new InvalidOperationException("A repository job started during the environment check. Retry after it finishes.");
                var shell = _profiles.FirstOrDefault(profile => profile.Id == "pwsh") ?? throw new InvalidOperationException("PowerShell profile missing.");
                if (!_terminalManager.TryResolveProfileCommand(shell, out var resolvedShell)) throw new InvalidOperationException("PowerShell is unavailable.");
                var command = EnvironmentSetup.Command(resolvedShell.Application, Path.Combine(AppContext.BaseDirectory, "tools", "Setup-Environment.ps1"), plan, AppContext.BaseDirectory);
                _repositoryActionPaths[key] = Path.GetFullPath(ExpandProjectValue(project, repo.Path)).TrimEnd('\\', '/');
                if (!_repositoryRunner.Start(key, null, command, RepositoryLogDirectory, "setup", stepCount: plan.Steps.Count)) throw new InvalidOperationException("An environment repair is already running.");
            }
        }
        catch (Exception error) { if (!IsDisposed) SendMessage(new { type = "repository.job.error", key, message = error.Message }); }
        finally
        {
            if (serviceLocked) _serviceGate.Release();
            if (checkingOwned)
            {
                _environmentSetupChecking = false;
                if (!IsDisposed) SendMessage(new { type = "repository.setup.checking", key, checking = false });
            }
            if (!IsDisposed) { SendRepositoryJobs(); _ = HandleDashboardRequestAsync(); }
        }
    }
}
