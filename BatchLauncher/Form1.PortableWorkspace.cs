using System.Text.Json;

namespace BatchLauncher;

public partial class Form1
{
    private static WorkspaceRootStore RootSettings => new(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "DevShellLauncher", "workspace-roots.json"));
    private WorkspaceConfig ResolveWorkspace(WorkspaceConfig source, string profileId)
    {
        _workspaceResolutionError = null;
        try { return PortableWorkspace.Resolve(source, RootSettings.Get(profileId)); }
        catch (Exception error)
        {
            // Keep the app usable when local settings are damaged, and report the problem in health checks.
            _workspaceResolutionError = error.Message;
            try { return PortableWorkspace.Resolve(source); } catch { return source; }
        }
    }
    private string? _workspaceResolutionError;
    private Task HandleWorkspaceToolsRefreshAsync()
    {
        if (WorkspaceStore.TryLoadWorkspace(_scriptsPath, out var source, out var error))
        {
            _workspace = ResolveWorkspace(source, _activeWorkspaceProfileId);
            SendMessage(new { type = "workspace.tools.refreshed", workspace = _workspace });
        }
        else SendWorkspaceProfileError(error ?? "Could not refresh tools.");
        return Task.CompletedTask;
    }
    private Task HandleWorkspaceRootSaveAsync(JsonElement payload)
    {
        try
        {
            if (_workspace.Globals?.AutoDetectTools != true) throw new InvalidOperationException("Select profile laptop or profile portable to choose one workspace root.");
            if (RepositoryUpdates.Active || _repositoryRunner.Snapshot().Any(job => job.State is "queued" or "building" or "running"))
                throw new InvalidOperationException("Finish or stop active jobs before changing the workspace root.");
            var root = PortableWorkspace.ValidateRoot(payload.GetProperty("path").GetString() ?? "");
            RootSettings.Save(_activeWorkspaceProfileId, root);
            _workspaceResolutionError = null;
            return HandleWorkspaceProfileReloadAsync();
        }
        catch (Exception error) { SendWorkspaceProfileError(error.Message); return Task.CompletedTask; }
    }
    private Task HandleWorkspaceRootPickAsync()
    {
        using var dialog = new FolderBrowserDialog { Description = "Choose the parent folder for this profile's repositories and environments", UseDescriptionForTitle = true,
            SelectedPath = _workspace.Globals?.WorkspaceRoot ?? "" };
        if (dialog.ShowDialog(this) == DialogResult.OK)
        {
            using var payload = JsonDocument.Parse(JsonSerializer.Serialize(new { path = dialog.SelectedPath }));
            return HandleWorkspaceRootSaveAsync(payload.RootElement);
        }
        return Task.CompletedTask;
    }
}
