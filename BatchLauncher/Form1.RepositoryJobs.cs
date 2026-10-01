using System.Text;
using System.Text.Json;

namespace BatchLauncher;

public partial class Form1
{
    private readonly RepositoryRunner _repositoryRunner = new();
    private bool _repositoryBrowserEventsHooked;
    private RepositoryUpdateQueue? _repositoryUpdates;
    private RepositoryUpdateQueue RepositoryUpdates => _repositoryUpdates ??= new(_repositoryRunner);
    private static string RepositoryLogDirectory => Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "DevShellLauncher", "repository-logs");
    private RepositoryCommand CreateGitCommand(WorkspaceProject project, WorkspaceRepository repo, string action)
    {
        var shell = _profiles.FirstOrDefault(profile => profile.Id == "pwsh") ?? throw new InvalidOperationException("PowerShell profile missing.");
        if (!_terminalManager.TryResolveProfileCommand(shell, out var command)) throw new InvalidOperationException("PowerShell is unavailable.");
        return RepositoryGitCommand.Create(command.Application, Path.Combine(AppContext.BaseDirectory, "tools", "Sync-Repository.ps1"),
            ExpandProjectValue(project, repo.Path), repo.Url == null ? null : ExpandProjectValue(project, repo.Url), action, AppContext.BaseDirectory);
    }
    private RepositoryCommand CreateRepositoryCommand(WorkspaceProject project, string taskName, string cwd)
    {
        var script = new StringBuilder("$ErrorActionPreference = 'Stop'\n$PSNativeCommandUseErrorActionPreference = $true\ntry {\n");
        var visiting = new HashSet<string>();
        var done = new HashSet<string>();
        string? selectedShell = null;
        void AddTask(string name)
        {
            if (done.Contains(name)) return;
            if (!visiting.Add(name)) throw new InvalidOperationException("Task dependency cycle: " + name);
            if (project.Tasks == null || !project.Tasks.TryGetValue(name, out var task) || task == null) throw new InvalidOperationException("Task not found: " + name);
            WorkspaceTask? template = null;
            if (task.UseTemplate != null && _workspace.Templates?.TryGetValue(task.UseTemplate, out template) != true) throw new InvalidOperationException("Template not found: " + task.UseTemplate);
            var shell = task.Shell ?? template?.Shell ?? _workspace.Globals?.DefaultShell ?? "pwsh";
            if (shell is not ("pwsh" or "powershell")) throw new InvalidOperationException("Managed repository actions currently require a PowerShell task.");
            if (selectedShell != null && selectedShell != shell) throw new InvalidOperationException("Dependencies must use the same shell.");
            selectedShell = shell;
            foreach (var dependency in task.DependsOn ?? template?.DependsOn ?? new()) AddTask(dependency);
            var directory = ExpandProjectValue(project, task.Cwd ?? template?.Cwd ?? cwd);
            if (!Directory.Exists(directory)) throw new InvalidOperationException("Task folder missing: " + directory);
            script.AppendLine("Set-Location -LiteralPath '" + directory.Replace("'", "''") + "'");
            var steps = task.Steps ?? template?.Steps;
            if (steps == null || steps.Count == 0) throw new InvalidOperationException("Repository action has no command steps: " + name);
            foreach (var step in steps)
            {
                script.AppendLine("$global:LASTEXITCODE = 0");
                script.AppendLine(ExpandProjectValue(project, step.Run));
                script.AppendLine("$stepSucceeded = $?; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; if (-not $stepSucceeded) { exit 1 }");
            }
            visiting.Remove(name); done.Add(name);
        }
        AddTask(taskName);
        script.AppendLine("exit 0\n} catch { [Console]::Error.WriteLine($_.ToString()); if ($LASTEXITCODE) { exit $LASTEXITCODE }; exit 1 }");
        var profile = _profiles.FirstOrDefault(p => p.Id == selectedShell) ?? throw new InvalidOperationException("Shell profile missing.");
        if (!_terminalManager.TryResolveProfileCommand(profile, out var command)) throw new InvalidOperationException("Shell is unavailable.");
        return new(command.Application, script.ToString(), cwd);
    }

    private Task HandleRepositoryJobAsync(JsonElement payload)
    {
        var action = payload.GetProperty("action").GetString();
        if (action == "status") { SendRepositoryJobs(); return Task.CompletedTask; }
        if (action is "update-all" or "stop-all")
        {
            try
            {
                if (action == "stop-all") RepositoryUpdates.Stop();
                else
                {
                    var profileId = _activeWorkspaceProfileId;
                    var items = (_workspace.Projects ?? new()).SelectMany(project => (project.Repositories ?? new()).Select(repo =>
                        new RepositoryUpdateItem($"{profileId}:{project.Id}:{repo.Id}", repo.Name, () => CreateGitCommand(project, repo, "sync")))).ToList();
                    // Resolve commands on the UI thread, since shell profiles belong to the form.
                    var commands = new Dictionary<string, RepositoryCommand>();
                    var errors = new Dictionary<string, Exception>();
                    foreach (var item in items) { try { commands[item.Key] = item.Command(); } catch (Exception error) { errors[item.Key] = error; } }
                    RepositoryUpdates.Start(profileId!, items.Select(item => item with { Command = () => commands.TryGetValue(item.Key, out var command) ? command : throw errors[item.Key] }).ToList(), RepositoryLogDirectory);
                }
            }
            catch (Exception error) { SendMessage(new { type = "repository.job.error", key = $"{_activeWorkspaceProfileId}:update-all", message = error.Message }); }
            SendRepositoryJobs();
            return Task.CompletedTask;
        }
        var projectId = payload.GetProperty("projectId").GetString();
        var repositoryId = payload.GetProperty("repositoryId").GetString();
        var key = $"{_activeWorkspaceProfileId}:{projectId}:{repositoryId}";
        try
        {
            if (action == "stop") _repositoryRunner.Stop(key);
            else if (action == "log")
            {
                var job = _repositoryRunner.Snapshot().FirstOrDefault(job => job.Key == key);
                if (job != null && File.Exists(job.LogPath))
                    System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo(job.LogPath) { UseShellExecute = true });
            }
            else if (action is "build" or "run" or "fetch" or "pull" or "clone" or "launch")
            {
                if (RepositoryUpdates.Owns(key)) throw new InvalidOperationException("This repository is reserved by Update All. Stop the queue before starting another action.");
                var project = _workspace.Projects?.FirstOrDefault(p => p.Id == projectId) ?? throw new InvalidOperationException("Project not found.");
                var repo = project.Repositories?.FirstOrDefault(r => r.Id == repositoryId) ?? throw new InvalidOperationException("Repository not found.");
                var cwd = ExpandProjectValue(project, repo.Path);
                var build = action is "build" or "launch" ? CreateRepositoryCommand(project,
                    (action == "launch" ? repo.BrowserBuildTask ?? repo.BuildTask : repo.BuildTask) ?? throw new InvalidOperationException("Build is not configured."), cwd) : null;
                var runAfter = action == "build" && payload.TryGetProperty("runAfter", out var value) && value.GetBoolean();
                var run = action is "fetch" or "pull" or "clone" ? CreateGitCommand(project, repo, action)
                    : action is "run" or "launch" || runAfter ? CreateRepositoryCommand(project,
                        (action == "launch" ? repo.BrowserRunTask ?? repo.RunTask : repo.RunTask) ?? throw new InvalidOperationException("Run is not configured."), cwd) : null;
                RepositoryBrowserLaunch? browser = null;
                if (action == "launch")
                {
                    var url = ExpandProjectValue(project, repo.BrowserUrl ?? throw new InvalidOperationException("Browser URL is not configured."));
                    browser = new(url, (repo.ReadyUrls ?? new()).Select(value => ExpandProjectValue(project, value)).ToArray(), repo.ReadyTimeoutSeconds);
                    if (!_repositoryBrowserEventsHooked)
                    {
                        _repositoryRunner.BrowserReady += OnRepositoryBrowserReady;
                        _repositoryBrowserEventsHooked = true;
                    }
                }
                if (!_repositoryRunner.Start(key, build, run, RepositoryLogDirectory, action, browser)) throw new InvalidOperationException("A repository job is already running.");
            }
        }
        catch (Exception error) { SendMessage(new { type = "repository.job.error", key, message = error.Message }); }
        SendRepositoryJobs();
        return Task.CompletedTask;
    }
    private void OnRepositoryBrowserReady(string key, string url)
    {
        if (IsDisposed || !IsHandleCreated) return;
        try
        {
            BeginInvoke(new Action(async () =>
            {
                if (IsDisposed || !key.StartsWith(_activeWorkspaceProfileId + ":", StringComparison.Ordinal) ||
                    !_repositoryRunner.Snapshot().Any(job => job.Key == key && job.State == "running" && job.BrowserState == "ready" && job.BrowserUrl == url)) return;
                try { await ShowBrowserAsync(url, _activeWorkspaceProfileId); }
                catch (Exception error) { if (!IsDisposed) SendMessage(new { type = "repository.job.error", key, message = "App is ready, but the browser could not open: " + error.Message }); }
                if (!IsDisposed) SendRepositoryJobs();
            }));
        }
        catch (InvalidOperationException) when (IsDisposed || Disposing) { }
    }
    private void SendRepositoryJobs() => SendMessage(new { type = "repository.jobs", jobs = _repositoryRunner.Snapshot(), batches = _repositoryUpdates?.Snapshot() ?? new() });
}
