using System.Text.Json;
using System.Security.Cryptography;

namespace BatchLauncher;

public partial class Form1
{
    private string? _pendingManifestPath;
    private string? _pendingManifestProfileId;
    private string? _pendingManifestRefreshProjectId;
    private string? _pendingManifestFingerprint;

    private Task HandleProjectManifestPickAsync()
    {
        using var dialog = new OpenFileDialog
        {
            Title = "Import DevShell project manifest",
            Filter = "DevShell project manifest (devshell.project.json)|devshell.project.json",
            FileName = "devshell.project.json",
            CheckFileExists = true
        };
        if (dialog.ShowDialog(this) != DialogResult.OK) return Task.CompletedTask;
        ShowProjectManifestPreview(dialog.FileName);
        return Task.CompletedTask;
    }

    private Task HandleProjectManifestFolderPickAsync()
    {
        using var dialog = new FolderBrowserDialog
        {
            Description = "Choose a project folder containing devshell.project.json",
            UseDescriptionForTitle = true,
            SelectedPath = _workspace.Globals?.WorkspaceRoot ?? Environment.GetFolderPath(Environment.SpecialFolder.UserProfile)
        };
        if (dialog.ShowDialog(this) != DialogResult.OK) return Task.CompletedTask;
        ShowProjectManifestPreview(Path.Combine(dialog.SelectedPath, "devshell.project.json"));
        return Task.CompletedTask;
    }

    private void ShowProjectManifestPreview(string path)
    {
        var preview = ProjectManifestImporter.Preview(path, _workspace.Projects?.Select(item => item.Id) ?? Array.Empty<string>());
        _pendingManifestPath = preview.ManifestPath;
        _pendingManifestProfileId = _activeWorkspaceProfileId;
        _pendingManifestRefreshProjectId = null;
        _pendingManifestFingerprint = ManifestFingerprint(preview.ManifestPath);
        SendMessage(new { type = "project.manifest.preview", preview });
    }

    private Task HandleProjectManifestImportAsync()
    {
        if (_pendingManifestPath == null || _pendingManifestProfileId != _activeWorkspaceProfileId)
        {
            SendMessage(new { type = "project.manifest.error", message = "Choose the manifest again for the active profile." });
            return Task.CompletedTask;
        }
        try
        {
            EnsureManifestMutationIdle();
            EnsureManifestPreviewIsCurrent();
            var imported = ProjectManifestImporter.ImportIntoProfile(_scriptsPath, _pendingManifestPath);
            _pendingManifestPath = null;
            _pendingManifestProfileId = null;
            _pendingManifestRefreshProjectId = null;
            _pendingManifestFingerprint = null;
            _workspace = ResolveWorkspace(WorkspaceStore.LoadWorkspace(_scriptsPath), _activeWorkspaceProfileId);
            SendWorkspaceProfileChanged();
            SendMessage(new { type = "project.manifest.imported", projectId = imported.Id, name = imported.Name });
        }
        catch (Exception error)
        {
            SendMessage(new { type = "project.manifest.error", message = error.Message });
        }
        return Task.CompletedTask;
    }

    private Task HandleProjectManifestRefreshPreviewAsync(JsonElement payload)
    {
        try
        {
            EnsureManifestProfile(payload);
            var projectId = payload.GetProperty("projectId").GetString() ?? throw new InvalidOperationException("Choose a project.");
            var preview = ProjectManifestImporter.PreviewRefresh(_scriptsPath, projectId);
            _pendingManifestPath = preview.ManifestPath;
            _pendingManifestProfileId = _activeWorkspaceProfileId;
            _pendingManifestRefreshProjectId = projectId;
            _pendingManifestFingerprint = ManifestFingerprint(preview.ManifestPath);
            SendMessage(new { type = "project.manifest.preview", preview });
        }
        catch (Exception error) { SendMessage(new { type = "project.manifest.error", message = error.Message }); }
        return Task.CompletedTask;
    }

    private Task HandleProjectManifestRefreshApplyAsync()
    {
        if (_pendingManifestRefreshProjectId == null || _pendingManifestProfileId != _activeWorkspaceProfileId)
        {
            SendMessage(new { type = "project.manifest.error", message = "Preview the manifest again for the active profile." });
            return Task.CompletedTask;
        }
        try
        {
            EnsureManifestMutationIdle();
            EnsureManifestPreviewIsCurrent();
            var project = ProjectManifestImporter.RefreshInProfile(_scriptsPath, _pendingManifestRefreshProjectId);
            _pendingManifestRefreshProjectId = null;
            _pendingManifestPath = null;
            _pendingManifestProfileId = null;
            _pendingManifestFingerprint = null;
            _workspace = ResolveWorkspace(WorkspaceStore.LoadWorkspace(_scriptsPath), _activeWorkspaceProfileId);
            SendWorkspaceProfileChanged();
            SendMessage(new { type = "project.manifest.refreshed", projectId = project.Id, name = project.Name });
        }
        catch (Exception error) { SendMessage(new { type = "project.manifest.error", message = error.Message }); }
        return Task.CompletedTask;
    }

    private Task HandleProjectManifestOverridesSaveAsync(JsonElement payload)
    {
        try
        {
            EnsureManifestProfile(payload);
            EnsureManifestMutationIdle();
            var projectId = payload.GetProperty("projectId").GetString() ?? throw new InvalidOperationException("Choose a project.");
            var overrides = payload.GetProperty("overrides").Deserialize<WorkspaceManifestOverrides>(_jsonOptions) ?? new();
            var project = ProjectManifestImporter.SaveOverrides(_scriptsPath, projectId, overrides);
            _workspace = ResolveWorkspace(WorkspaceStore.LoadWorkspace(_scriptsPath), _activeWorkspaceProfileId);
            SendWorkspaceProfileChanged();
            SendMessage(new { type = "project.manifest.overrides.saved", projectId = project.Id });
        }
        catch (Exception error) { SendMessage(new { type = "project.manifest.error", message = error.Message }); }
        return Task.CompletedTask;
    }

    private void EnsureManifestMutationIdle()
    {
        if (RepositoryUpdates.Active || _repositoryRunner.Snapshot().Any(job => job.State is "queued" or "building" or "running"))
            throw new InvalidOperationException("Finish or stop active jobs before changing this project.");
    }

    private void EnsureManifestProfile(JsonElement payload)
    {
        if (!payload.TryGetProperty("profileId", out var profile) || profile.GetString() != _activeWorkspaceProfileId)
            throw new InvalidOperationException("The active profile changed. Reopen this project before saving.");
    }

    private static string? ManifestFingerprint(string path) => File.Exists(path)
        ? Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))) : null;

    private void EnsureManifestPreviewIsCurrent()
    {
        if (_pendingManifestPath == null || _pendingManifestFingerprint == null ||
            ManifestFingerprint(_pendingManifestPath) != _pendingManifestFingerprint)
            throw new InvalidOperationException("Source manifest changed or disappeared after preview. Preview it again before applying.");
    }
}
