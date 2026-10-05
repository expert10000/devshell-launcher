using System.Text.Json;

namespace BatchLauncher;

public partial class Form1
{
    private Task HandleWorkspaceFilesAsync(JsonElement payload)
    {
        var profileId = payload.GetProperty("profileId").GetString();
        var requestId = payload.GetProperty("requestId").GetString();
        if (profileId != _activeWorkspaceProfileId) return Task.CompletedTask;
        string? action = null;
        try
        {
            var projectId = payload.GetProperty("projectId").GetString();
            var repositoryId = payload.GetProperty("repositoryId").GetString();
            action = payload.GetProperty("action").GetString();
            var path = payload.TryGetProperty("path", out var folder) ? folder.GetString() ?? "" : "";
            var project = _workspace.Projects?.FirstOrDefault(item => item.Id == projectId) ?? throw new InvalidOperationException("Project not found.");
            var repo = project.Repositories?.FirstOrDefault(item => item.Id == repositoryId) ?? throw new InvalidOperationException("Repository not found.");
            var root = ExpandProjectValue(project, repo.Path);
            if (action == "artifacts")
            {
                // Capture request values before leaving the JSON document's dispatch lifetime.
                var configuration = new WorkspaceRepository { OutputDirectory = repo.OutputDirectory, PdfDirectory = repo.PdfDirectory, PdfPath = repo.PdfPath };
                return InspectWorkspaceArtifactsAsync(profileId, requestId, root, configuration);
            }
            if (action == "list") SendMessage(new { type = "workspace.files.result", profileId, requestId, listing = WorkspaceFiles.List(root, path) });
            else if (action == "preview") SendMessage(new { type = "workspace.files.result", profileId, requestId, preview = WorkspaceFiles.Preview(root, path) });
            else if (action == "image") SendMessage(new { type = "workspace.files.result", profileId, requestId, image = WorkspaceFiles.ImagePreview(root, path) });
            else if (action == "output")
            {
                var output = WorkspaceFiles.FindOutputDirectory(root, repo);
                SendMessage(new { type = "workspace.files.opened", profileId, projectId, repositoryId, filePath = output, listing = WorkspaceFiles.List(root, output) });
            }
            else throw new ArgumentException("Unknown file browser action.");
        }
        catch (Exception error)
        {
            SendMessage(new { type = "workspace.files.result", profileId, requestId, error = error.Message });
            if (action == "output") SendMessage(new { type = "workspace.tabs.error", profileId, message = error.Message });
        }
        return Task.CompletedTask;
    }

    private async Task InspectWorkspaceArtifactsAsync(string? profileId, string? requestId, string root, WorkspaceRepository repo)
    {
        try
        {
            var artifacts = await Task.Run(() => WorkspaceArtifacts.Scan(root, repo));
            if (!IsDisposed && profileId == _activeWorkspaceProfileId) SendMessage(new { type = "workspace.files.result", profileId, requestId, artifacts });
        }
        catch (Exception error)
        {
            if (!IsDisposed && profileId == _activeWorkspaceProfileId) SendMessage(new { type = "workspace.files.result", profileId, requestId, error = error.Message });
        }
    }
}
