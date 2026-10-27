using System.Text.Json;

namespace BatchLauncher;

public partial class Form1
{
    private Task HandleShellSetupAsync(JsonElement payload)
    {
        var profileId = _activeWorkspaceProfileId;
        var key = $"{profileId}:shell:pwsh";
        try
        {
            if (payload.GetProperty("profileId").GetString() != "pwsh" ||
                payload.GetProperty("action").GetString() != "install")
                throw new InvalidOperationException("Only PowerShell 7 installation is supported here.");

            var pwsh = _profiles.FirstOrDefault(profile => profile.Id == "pwsh")
                ?? throw new InvalidOperationException("The PowerShell 7 profile is missing from profile.json.");
            if (_terminalManager.TryResolveProfileCommand(pwsh, out _))
            {
                SendProfiles();
                return Task.CompletedTask;
            }
            if (_repositoryRunner.Snapshot().Any(job => job.State is "queued" or "building" or "running"))
                throw new InvalidOperationException("Finish or stop the active job before installing PowerShell 7.");
            if (DashboardInspector.FindTool("winget") == null)
                throw new InvalidOperationException("WinGet is unavailable. Install PowerShell 7, then select Recheck shells.");

            var windowsPowerShell = _profiles.FirstOrDefault(profile => profile.Id == "powershell")
                ?? throw new InvalidOperationException("Windows PowerShell is required to install PowerShell 7.");
            if (!_terminalManager.TryResolveProfileCommand(windowsPowerShell, out var shell))
                throw new InvalidOperationException("Windows PowerShell is unavailable. Install PowerShell 7 manually, then recheck shells.");
            var root = _workspace.Globals?.WorkspaceRoot ?? AppPaths.ConfigDirectory;
            if (!Directory.Exists(root)) throw new DirectoryNotFoundException($"Workspace folder is missing: {root}");
            var plan = new EnvironmentSetupPlan(root, PortableWorkspace.DiscoverTools(root),
                new List<EnvironmentSetupStep> { new("Install PowerShell 7", "tool", root, "pwsh", Target: "tool:pwsh") },
                new List<string>()) { Targets = new List<string> { "tool:pwsh" } };
            var command = EnvironmentSetup.Command(shell.Application,
                Path.Combine(AppContext.BaseDirectory, "tools", "Setup-Environment.ps1"), plan, AppContext.BaseDirectory);
            if (!_repositoryRunner.Start(key, null, command, RepositoryLogDirectory, "setup", stepCount: 1))
                throw new InvalidOperationException("PowerShell 7 setup is already running.");
            SendRepositoryJobs();
            _ = Task.Run(async () =>
            {
                await _repositoryRunner.Completion(key);
                if (IsDisposed || !IsHandleCreated) return;
                BeginInvoke(new Action(async () =>
                {
                    if (IsDisposed || profileId != _activeWorkspaceProfileId) return;
                    SendProfiles();
                    if (_workspace.Globals?.AutoDetectTools == true) await HandleWorkspaceToolsRefreshAsync();
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
}
