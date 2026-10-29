using System.Text.Json;

namespace BatchLauncher;

public partial class Form1
{
    private Task HandleShellSetupAsync(JsonElement payload)
    {
        var profileId = _activeWorkspaceProfileId;
        var toolId = payload.TryGetProperty("toolId", out var toolProperty) ? toolProperty.GetString()
            : payload.TryGetProperty("profileId", out var profileProperty) ? profileProperty.GetString() : null;
        var key = $"{profileId}:shell:{toolId}";
        try
        {
            if (toolId == null || !EnvironmentSetup.InstallableTools.Contains(toolId) || payload.GetProperty("action").GetString() != "install")
                throw new InvalidOperationException("This tool does not support managed installation.");

            if (toolId == "pwsh" && _profiles.FirstOrDefault(profile => profile.Id == "pwsh") is { } pwsh &&
                _terminalManager.TryResolveProfileCommand(pwsh, out _))
            {
                SendProfiles();
                return Task.CompletedTask;
            }
            var root = _workspace.Globals?.WorkspaceRoot ?? AppPaths.ConfigDirectory;
            RefreshInstalledToolPath(toolId);
            if (PortableWorkspace.DiscoverTools(root).ContainsKey(toolId))
            {
                SendProfiles();
                _ = HandleWorkspaceToolsRefreshAsync();
                _ = HandleDashboardRequestAsync();
                return Task.CompletedTask;
            }
            if (_repositoryRunner.Snapshot().Any(job => job.State is "queued" or "building" or "running"))
                throw new InvalidOperationException("Finish or stop the active job before installing another tool.");
            if (DashboardInspector.FindTool("winget") == null)
                throw new InvalidOperationException("WinGet is unavailable. Install this tool manually, then select Detect tools.");

            var installerProfiles = toolId == "pwsh" ? new[] { "powershell", "pwsh" } : new[] { "pwsh", "powershell" };
            string? shell = null;
            foreach (var id in installerProfiles)
            {
                var candidate = _profiles.FirstOrDefault(profile => profile.Id == id);
                if (candidate != null && _terminalManager.TryResolveProfileCommand(candidate, out var resolved))
                {
                    shell = resolved.Application;
                    break;
                }
            }
            if (shell == null)
                throw new InvalidOperationException("A PowerShell shell is unavailable. Install this tool manually, then select Detect tools.");
            Directory.CreateDirectory(root);
            var displayName = toolId switch { "git" => "Git", "pwsh" => "PowerShell 7", "node" => "Node.js", "npm" => "npm", "python" => "Python", "dotnet" => ".NET SDK", "code" => "VS Code", _ => toolId };
            var plan = new EnvironmentSetupPlan(root, PortableWorkspace.DiscoverTools(root),
                new List<EnvironmentSetupStep> { new($"Install {displayName}", "tool", root, toolId, Target: $"tool:{toolId}") },
                new List<string>()) { Targets = new List<string> { $"tool:{toolId}" } };
            var command = EnvironmentSetup.Command(shell,
                Path.Combine(AppContext.BaseDirectory, "tools", "Setup-Environment.ps1"), plan, AppContext.BaseDirectory);
            if (!_repositoryRunner.Start(key, null, command, RepositoryLogDirectory, "setup", stepCount: 1))
                throw new InvalidOperationException($"{displayName} setup is already running.");
            SendRepositoryJobs();
            _ = Task.Run(async () =>
            {
                await _repositoryRunner.Completion(key);
                if (IsDisposed || !IsHandleCreated) return;
                BeginInvoke(new Action(async () =>
                {
                    if (IsDisposed || profileId != _activeWorkspaceProfileId) return;
                    RefreshInstalledToolPath(toolId);
                    SendProfiles();
                    if (_workspace.Globals?.AutoDetectTools == true) await HandleWorkspaceToolsRefreshAsync();
                    _ = HandleDashboardRequestAsync();
                    SendRepositoryJobs();
                }));
            });
        }
        catch (Exception error)
        {
            SendMessage(new { type = "repository.job.error", key, message = error.Message });
        }
        return Task.CompletedTask;
    }

    private static void RefreshInstalledToolPath(string toolId)
    {
        var paths = new[] {
            Environment.GetEnvironmentVariable("PATH", EnvironmentVariableTarget.Machine),
            Environment.GetEnvironmentVariable("PATH", EnvironmentVariableTarget.User),
            Environment.GetEnvironmentVariable("PATH")
        }.Where(path => !string.IsNullOrWhiteSpace(path))
            .SelectMany(path => path!.Split(';', StringSplitOptions.RemoveEmptyEntries))
            .Distinct(StringComparer.OrdinalIgnoreCase).ToList();
        if (toolId == "git")
        {
            var git = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "Git", "cmd");
            if (File.Exists(Path.Combine(git, "git.exe")))
            {
                paths.RemoveAll(path => string.Equals(path.TrimEnd('\\'), git, StringComparison.OrdinalIgnoreCase));
                paths.Insert(0, git);
            }
        }
        Environment.SetEnvironmentVariable("PATH", string.Join(';', paths));
    }
}
