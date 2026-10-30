namespace BatchLauncher;

public partial class Form1
{
    private string? _pendingManifestPath;
    private string? _pendingManifestProfileId;

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
        var preview = ProjectManifestImporter.Preview(dialog.FileName, _workspace.Projects?.Select(item => item.Id) ?? Array.Empty<string>());
        _pendingManifestPath = preview.ManifestPath;
        _pendingManifestProfileId = _activeWorkspaceProfileId;
        SendMessage(new { type = "project.manifest.preview", preview });
        return Task.CompletedTask;
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
            var imported = ProjectManifestImporter.ImportIntoProfile(_scriptsPath, _pendingManifestPath);
            _pendingManifestPath = null;
            _pendingManifestProfileId = null;
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
}
