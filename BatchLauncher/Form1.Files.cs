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
            action = payload.GetProperty("action").GetString();
            if (action == "navigation")
            {
                HandleWorkspaceNavigation(payload, profileId!, requestId);
                return Task.CompletedTask;
            }
            var path = payload.TryGetProperty("path", out var folder) ? folder.GetString() ?? "" : "";
            var project = _workspace.Projects?.FirstOrDefault(item => item.Id == projectId) ?? throw new InvalidOperationException("Project not found.");
            if (action == "search")
            {
                var query = payload.GetProperty("query").GetString() ?? "";
                var repositories = (project.Repositories ?? new List<WorkspaceRepository>())
                    .Select(item => new WorkspaceSearchRepository(item.Id, item.Name, ExpandProjectValue(project, item.Path))).ToList();
                return SearchWorkspaceFilesAsync(profileId, requestId, repositories, query);
            }
            var repositoryId = payload.GetProperty("repositoryId").GetString();
            var repo = project.Repositories?.FirstOrDefault(item => item.Id == repositoryId) ?? throw new InvalidOperationException("Repository not found.");
            var root = ExpandProjectValue(project, repo.Path);
            if (action == "artifacts")
            {
                // Capture request values before leaving the JSON document's dispatch lifetime.
                var configuration = new WorkspaceRepository { OutputDirectory = repo.OutputDirectory, PdfDirectory = repo.PdfDirectory, PdfPath = repo.PdfPath };
                return InspectWorkspaceArtifactsAsync(profileId, requestId, root, configuration);
            }
            if (action == "list") SendMessage(new { type = "workspace.files.result", profileId, requestId, listing = WorkspaceFiles.List(root, path) });
            else if (action == "locate")
            {
                var location = WorkspaceFiles.Locate(root, path);
                SendMessage(new { type = "workspace.files.result", profileId, requestId, listing = location.Listing, entry = location.Entry });
            }
            else if (action == "preview")
            {
                var preview = WorkspaceFiles.Preview(root, path);
                RememberWorkspaceFile(projectId, repositoryId, preview.Path, WorkspaceFiles.KindOfFile(preview.Path));
                SendMessage(new { type = "workspace.files.result", profileId, requestId, preview });
            }
            else if (action == "image")
            {
                var image = WorkspaceFiles.ImagePreview(root, path);
                RememberWorkspaceFile(projectId, repositoryId, image.Path, "image");
                SendMessage(new { type = "workspace.files.result", profileId, requestId, image });
            }
            else if (action == "remember-pdf")
            {
                PdfFile.Resolve(root, path);
                RememberWorkspaceFile(projectId, repositoryId, path, "pdf");
                SendMessage(new { type = "workspace.files.result", profileId, requestId, remembered = true });
            }
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

    private async Task SearchWorkspaceFilesAsync(string? profileId, string? requestId, List<WorkspaceSearchRepository> repositories, string query)
    {
        try
        {
            // All request/config values are captured before JSON dispatch returns.
            var search = await Task.Run(() => WorkspaceFileSearch.Search(repositories, query));
            if (!IsDisposed && profileId == _activeWorkspaceProfileId) SendMessage(new { type = "workspace.files.result", profileId, requestId, search });
        }
        catch (Exception error)
        {
            if (!IsDisposed && profileId == _activeWorkspaceProfileId) SendMessage(new { type = "workspace.files.result", profileId, requestId, error = error.Message });
        }
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
