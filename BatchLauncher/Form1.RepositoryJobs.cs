using System.Text;
using System.Text.Json;

namespace BatchLauncher;

public partial class Form1
{
    private readonly RepositoryRunner _repositoryRunner = new();
    private readonly Dictionary<string, string> _repositoryActionPaths = new();
    private readonly HashSet<string> _repositoryChangesPaths = new(StringComparer.OrdinalIgnoreCase);
    private bool _repositoryBrowserEventsHooked;
    private RepositoryUpdateQueue? _repositoryUpdates;
    private RepositoryUpdateQueue RepositoryUpdates => _repositoryUpdates ??= new(_repositoryRunner);
    private static string RepositoryLogDirectory => Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "DevShellLauncher", "repository-logs");
    private RepositoryCommand CreateGitCommand(WorkspaceProject project, WorkspaceRepository repo, string action)
    {
        if (_repositoryChangesPaths.Contains(Path.GetFullPath(ExpandProjectValue(project, repo.Path)).TrimEnd('\\', '/')))
            throw new InvalidOperationException("This checkout is busy in the Changes panel. Retry after it finishes.");
        _repositoryActionPaths[$"{_activeWorkspaceProfileId}:{project.Id}:{repo.Id}"] = Path.GetFullPath(ExpandProjectValue(project, repo.Path)).TrimEnd('\\', '/');
        var shell = _profiles.FirstOrDefault(profile => profile.Id == "pwsh") ?? throw new InvalidOperationException("PowerShell profile missing.");
        if (!_terminalManager.TryResolveProfileCommand(shell, out var command)) throw new InvalidOperationException("PowerShell is unavailable.");
        if (action is "diff" or "history")
            return RepositoryGitCommand.CreateInspection(command.Application, ExpandProjectValue(project, repo.Path), action, AppContext.BaseDirectory);
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
        if (action is "changes" or "file-diff" or "stage" or "unstage") return HandleRepositoryChangesAsync(payload, action);
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
        if (action == "github") return OpenRepositoryGithubAsync(projectId, repositoryId, key);
        if (action is "commit" or "push") return HandleRepositoryWriteAsync(projectId, repositoryId, key, action);
        try
        {
            if (action == "stop") _repositoryRunner.Stop(key);
            else if (action == "log")
            {
                var job = _repositoryRunner.Snapshot().FirstOrDefault(job => job.Key == key);
                if (job != null && File.Exists(job.LogPath))
                    System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo(job.LogPath) { UseShellExecute = true });
            }
            else if (action is "build" or "run" or "fetch" or "pull" or "clone" or "launch" or "diff" or "history")
            {
                if (RepositoryUpdates.Owns(key)) throw new InvalidOperationException("This repository is reserved by Update All. Stop the queue before starting another action.");
                var project = _workspace.Projects?.FirstOrDefault(p => p.Id == projectId) ?? throw new InvalidOperationException("Project not found.");
                var repo = project.Repositories?.FirstOrDefault(r => r.Id == repositoryId) ?? throw new InvalidOperationException("Repository not found.");
                if (action == "run" && repo.PdfPath != null)
                    return OpenWorkspacePdfAsync(_activeWorkspaceProfileId, project.Id, repo.Id);
                var cwd = ExpandProjectValue(project, repo.Path);
                EnsureRepositoryIdle(key, cwd);
                _repositoryActionPaths[key] = Path.GetFullPath(cwd).TrimEnd('\\', '/');
                var build = action is "build" or "launch" ? CreateRepositoryCommand(project,
                    (action == "launch" ? repo.BrowserBuildTask ?? repo.BuildTask : repo.BuildTask) ?? throw new InvalidOperationException("Build is not configured."), cwd) : null;
                var runAfter = action == "build" && payload.TryGetProperty("runAfter", out var value) && value.GetBoolean();
                var pdfAfter = runAfter && (repo.PdfPath != null || repo.PdfDirectory != null);
                var run = action is "fetch" or "pull" or "clone" or "diff" or "history" ? CreateGitCommand(project, repo, action)
                    : action is "run" or "launch" || runAfter && !pdfAfter ? CreateRepositoryCommand(project,
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
                if (action == "build" && (repo.PdfPath != null || repo.PdfDirectory != null))
                    _ = ObservePdfBuildAsync(key, _activeWorkspaceProfileId, project.Id, repo.Id, pdfAfter);
            }
        }
        catch (Exception error) { SendMessage(new { type = "repository.job.error", key, message = error.Message }); }
        SendRepositoryJobs();
        return Task.CompletedTask;
    }
    private async Task OpenRepositoryGithubAsync(string? projectId, string? repositoryId, string key)
    {
        var profileId = _activeWorkspaceProfileId;
        try
        {
            var project = _workspace.Projects?.FirstOrDefault(item => item.Id == projectId) ?? throw new InvalidOperationException("Project not found.");
            var repo = project.Repositories?.FirstOrDefault(item => item.Id == repositoryId) ?? throw new InvalidOperationException("Repository not found.");
            var url = repo.Url == null ? null : ExpandProjectValue(project, repo.Url);
            if (url == null)
            {
                var status = await DashboardInspector.Inspect(project.Id, repo.Id, ExpandProjectValue(project, repo.Path));
                url = (status.Remotes.FirstOrDefault(remote => remote.Name == "origin" && remote.Direction == "fetch")
                    ?? status.Remotes.FirstOrDefault(remote => remote.Direction == "fetch"))?.Url;
            }
            if (url == null) throw new InvalidOperationException("Repository has no remote URL.");
            if (url.StartsWith("git@", StringComparison.Ordinal) && url.Contains(':')) url = "https://" + url[4..].Replace(':', '/');
            if (Uri.TryCreate(url, UriKind.Absolute, out var ssh) && ssh.Scheme == "ssh") url = new UriBuilder("https", ssh.Host) { Path = ssh.AbsolutePath }.Uri.AbsoluteUri;
            if (!BrowserPane.IsWebUrl(url)) throw new InvalidOperationException("Configure an HTTP or HTTPS repository URL to open it in DevShell.");
            var target = new UriBuilder(url) { Query = "", Fragment = "" };
            if (target.Path.EndsWith(".git", StringComparison.OrdinalIgnoreCase)) target.Path = target.Path[..^4];
            await ShowBrowserAsync(target.Uri.AbsoluteUri, profileId, "browser", project.Id, repo.Id);
        }
        catch (Exception error) { if (!IsDisposed) SendMessage(new { type = "repository.job.error", key, message = error.Message }); }
    }
    private void EnsureRepositoryIdle(string key, string path)
    {
        path = Path.GetFullPath(path).TrimEnd('\\', '/');
        if (_repositoryChangesPaths.Contains(path)) throw new InvalidOperationException("This checkout is busy in the Changes panel.");
        if (RepositoryUpdates.Owns(key) || _repositoryActionPaths.Any(pair => pair.Value.Equals(path, StringComparison.OrdinalIgnoreCase) && RepositoryUpdates.Owns(pair.Key)))
            throw new InvalidOperationException("This checkout is reserved by Update All. Stop the queue before starting another action.");
        if (_repositoryRunner.Snapshot().Any(job => job.State is "queued" or "building" or "running" &&
            (job.Key == key || _repositoryActionPaths.TryGetValue(job.Key, out var other) && other.Equals(path, StringComparison.OrdinalIgnoreCase))))
            throw new InvalidOperationException("This checkout already has an active job, possibly in another project/profile.");
    }

    private async Task HandleRepositoryWriteAsync(string? projectId, string? repositoryId, string key, string action)
    {
        var profileId = _activeWorkspaceProfileId;
        try
        {
            var project = _workspace.Projects?.FirstOrDefault(item => item.Id == projectId) ?? throw new InvalidOperationException("Project not found.");
            var repo = project.Repositories?.FirstOrDefault(item => item.Id == repositoryId) ?? throw new InvalidOperationException("Repository not found.");
            var path = ExpandProjectValue(project, repo.Path);
            EnsureRepositoryIdle(key, path);
            var preview = await RepositoryWriteActions.Preview(path, action);
            if (IsDisposed || profileId != _activeWorkspaceProfileId) return;
            string? message = null;
            if (action == "commit") { message = RepositoryWriteConfirmation.ConfirmCommit(this, preview); if (message == null) return; }
            else if (!RepositoryWriteConfirmation.ConfirmPush(this, preview)) return;
            EnsureRepositoryIdle(key, path);
            var shell = _profiles.FirstOrDefault(item => item.Id == "pwsh") ?? throw new InvalidOperationException("PowerShell profile missing.");
            if (!_terminalManager.TryResolveProfileCommand(shell, out var command)) throw new InvalidOperationException("PowerShell is unavailable.");
            var write = RepositoryWriteActions.CreateCommand(command.Application, Path.Combine(AppContext.BaseDirectory, "tools", "Manage-Repository.ps1"), preview, action, message);
            _repositoryActionPaths[key] = preview.Path;
            if (!_repositoryRunner.Start(key, null, write, RepositoryLogDirectory, action)) throw new InvalidOperationException("A repository job is already running.");
        }
        catch (Exception error) { if (!IsDisposed) SendMessage(new { type = "repository.job.error", key, message = error.Message }); }
        finally { if (!IsDisposed) SendRepositoryJobs(); }
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
                var parts = key.Split(':');
                try { await ShowBrowserAsync(url, _activeWorkspaceProfileId, "browser", parts.Length > 1 ? parts[1] : null, parts.Length > 2 ? parts[2] : null); }
                catch (Exception error) { if (!IsDisposed) SendMessage(new { type = "repository.job.error", key, message = "App is ready, but the browser could not open: " + error.Message }); }
                if (!IsDisposed) SendRepositoryJobs();
            }));
        }
        catch (InvalidOperationException) when (IsDisposed || Disposing) { }
    }
    private void SendRepositoryJobs() => SendMessage(new { type = "repository.jobs", jobs = _repositoryRunner.Snapshot(), batches = _repositoryUpdates?.Snapshot() ?? new() });
}
