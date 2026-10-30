using System.Text.Json;

namespace BatchLauncher;

public partial class Form1
{
    private readonly SemaphoreSlim _dashboardGate = new(1, 1);
    private bool _dashboardPending;

    private async Task HandleDashboardRequestAsync()
    {
        if (!await _dashboardGate.WaitAsync(0)) { _dashboardPending = true; return; }
        var profileId = _activeWorkspaceProfileId;
        var projects = _workspace.Projects?.ToList() ?? new();
        var globals = new Dictionary<string, string>(_workspace.Globals?.Vars ?? new());
        string Expand(WorkspaceProject project, string value)
        {
            var variables = new Dictionary<string, string>(globals);
            foreach (var pair in project.Vars ?? new()) variables[pair.Key] = pair.Value;
            return PortableWorkspace.Expand(value, variables);
        }
        var checks = new List<HealthCheck>();
        var repositories = new List<RepositoryStatus>();
        void Publish() => SendMessage(new { type = "dashboard.result", profileId, repositories, checks, checkedAt = DateTimeOffset.Now.ToString("O") });
        try
        {
            if (_workspaceResolutionError != null) checks.Add(new("Workspace settings", "error", _workspaceResolutionError));
            var tools = new HashSet<string>(StringComparer.OrdinalIgnoreCase) { "git", "pwsh" };
            foreach (var project in projects)
            {
                foreach (var tool in project.RequiredTools ?? new()) tools.Add(Expand(project, tool));
                var path = Expand(project, project.Root ?? "");
                checks.Add(new(project.Name + " folder", Directory.Exists(path) ? "ok" : "error", path));
                foreach (var cwd in (project.Tasks?.Values ?? Enumerable.Empty<WorkspaceTask>())
                             .Where(task => !string.IsNullOrWhiteSpace(task.Cwd)).Select(task => Expand(project, task.Cwd!)).Distinct())
                    checks.Add(new(project.Name + " task folder", Directory.Exists(cwd) ? "ok" : "error", cwd));
                foreach (var repo in project.Repositories ?? new())
                {
                    var status = await DashboardInspector.Inspect(project.Id, repo.Id, Expand(project, repo.Path));
                    repositories.Add(status);
                    checks.Add(new(repo.Name + " repository", status.Error == null ? "ok" : "error", status.Error ?? status.Path));
                    foreach (var task in new[] { repo.BuildTask, repo.RunTask, repo.BrowserBuildTask, repo.BrowserRunTask }.Where(task => task != null))
                        if (project.Tasks?.ContainsKey(task!) != true) checks.Add(new(repo.Name + " action", "error", $"Missing task: {task}", project.Id, repo.Id, Guidance: "Define this task in the profile or correct the repository action name."));
                    checks.AddRange(await RepositoryEnvironment.InspectRepository(project.Id, repo.Id, ResolveRepository(project, repo), EnvironmentTools()));
                    Publish();
                }
                if (project.PythonEnvironment != null)
                {
                    var repo = new WorkspaceRepository { Path = project.Root ?? "", PythonEnvironment = project.PythonEnvironment,
                        PythonModules = project.PythonModules, PythonPackages = project.PythonPackages };
                    checks.AddRange(await RepositoryEnvironment.InspectRepository(project.Id, "environment", ResolveRepository(project, repo), EnvironmentTools()));
                }
                if (project.Service != null)
                {
                    try
                    {
                        if (project.Service.Kind == "process")
                        {
                            var executable = project.Service.Command == null ? null : DashboardInspector.FindTool(Expand(project, project.Service.Command));
                            checks.Add(new(project.Service.Name + " worker", executable == null ? "error" : "ok",
                                executable ?? "Worker command is unavailable. Configure command or install the executable."));
                        }
                        else
                        {
                            var result = await DashboardInspector.Run(Expand(project, project.Service.Python), new[] {
                                Path.Combine(AppContext.BaseDirectory, "service_control.py"), "status", "--root", path, "--port", project.Service.Port.ToString() });
                            if (result.Code != 0) throw new InvalidOperationException("Service status check failed; verify the Python environment.");
                            using var document = JsonDocument.Parse(result.Output);
                            var state = document.RootElement.GetProperty("state").GetString();
                            checks.Add(new(project.Service.Name + " port " + project.Service.Port,
                                state is "running" or "stopped" ? "ok" : "error",
                                state == "stopped" ? "Port available; service stopped" : document.RootElement.GetProperty("message").GetString() ?? state ?? "Unknown"));
                        }
                    }
                    catch (Exception error) { checks.Add(new(project.Service.Name, "error", error.Message)); }
                }
            }
            foreach (var tool in tools)
            {
                var resolved = DashboardInspector.FindTool(_workspace.Globals?.Tools?.GetValueOrDefault(tool) ?? tool);
                checks.Add(new(tool, resolved == null ? "error" : "ok", resolved ?? "Not found. Install the tool or update its configured path."));
            }
        }
        catch (Exception error) { checks.Add(new("Profile check", "error", error.Message)); }
        finally
        {
            Publish();
            _dashboardGate.Release();
            if (_dashboardPending) { _dashboardPending = false; _ = HandleDashboardRequestAsync(); }
        }
    }
}
