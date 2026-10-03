using System.Diagnostics;
using System.Text.Json;

namespace BatchLauncher;

public partial class Form1
{
    private PdfPane? _pdfPane;
    private bool _pdfPaneActive;

    private Task HandleWorkspacePdfAsync(JsonElement payload)
    {
        // Extract values before the dispatcher's JSON document is released.
        var profileId = payload.GetProperty("profileId").GetString();
        if (profileId != _activeWorkspaceProfileId) return Task.CompletedTask;
        var projectId = payload.GetProperty("projectId").GetString();
        var repositoryId = payload.GetProperty("repositoryId").GetString();
        var action = payload.GetProperty("action").GetString() ?? "open";
        var path = payload.TryGetProperty("filePath", out var file) ? file.GetString() : null;
        var page = payload.TryGetProperty("page", out var number) && number.TryGetInt32(out var value) ? value : 1;
        var requestId = payload.TryGetProperty("requestId", out var request) ? request.GetString() : null;
        return OpenWorkspacePdfAsync(profileId!, projectId, repositoryId, action, path, page, requestId);
    }

    private async Task OpenWorkspacePdfAsync(string profileId, string? projectId, string? repositoryId,
        string action = "open", string? filePath = null, int page = 1, string? requestId = null, bool notifyOpen = true)
    {
        if (IsDisposed || profileId != _activeWorkspaceProfileId) return;
        try
        {
            if (action is not ("open" or "refresh" or "external" or "list")) throw new ArgumentException("Unknown PDF action.");
            if (page is < 1 or > 1000000) throw new ArgumentException("Page must be between 1 and 1000000.");
            var project = _workspace.Projects?.FirstOrDefault(item => item.Id == projectId) ?? throw new InvalidOperationException("Project not found.");
            var repo = project.Repositories?.FirstOrDefault(item => item.Id == repositoryId) ?? throw new InvalidOperationException("Repository not found.");
            var root = ExpandProjectValue(project, repo.Path);
            if (action == "open" && filePath == null && repo.PdfPath == null && repo.PdfDirectory != null)
            {
                SendMessage(new { type = "workspace.pdf.opened", profileId, kind = "pdf", projectId, repositoryId, page });
                return;
            }
            if (action == "list")
            {
                var directory = PdfFile.ResolveDirectory(root, repo.PdfDirectory ?? throw new InvalidOperationException("PDF collection is not configured."));
                var files = Directory.Exists(directory) ? Directory.EnumerateFiles(directory, "*.pdf", SearchOption.TopDirectoryOnly)
                    .Where(path => (File.GetAttributes(path) & FileAttributes.ReparsePoint) == 0)
                    .OrderBy(path => path, StringComparer.OrdinalIgnoreCase).Take(256)
                    .Select(path => Path.GetRelativePath(root, path).Replace('\\', '/')).ToArray() : Array.Empty<string>();
                SendMessage(new { type = "workspace.pdf.result", profileId, projectId, repositoryId, requestId, action, files });
                return;
            }
            var relative = filePath ?? repo.PdfPath ?? throw new InvalidOperationException("Configure this repository's pdfPath first.");
            var path = PdfFile.Resolve(root, relative);
            if (action == "external") Process.Start(new ProcessStartInfo(path) { UseShellExecute = true });
            else
            {
                await _browserGate.WaitAsync();
                try
                {
                    if (IsDisposed || profileId != _activeWorkspaceProfileId) return;
                    ExpandBrowserHost();
                    if (_pdfPane == null)
                    {
                        var created = new PdfPane(); _pdfPane = created;
                        created.HideRequested += (_, _) => HideBrowserPane();
                        created.CloseRequested += (_, _) =>
                        {
                            if (_pdfPane != created) return;
                            _pdfPane = null; _pdfPaneActive = false; created.Dispose(); HideBrowserPane();
                        };
                        created.ActionRequested += async next =>
                        {
                            if (_pdfPane == created && !created.IsDisposed)
                                await OpenWorkspacePdfAsync(profileId, created.ProjectId, created.RepositoryId, next, created.FilePath, created.Page);
                        };
                        created.Failed += error =>
                        {
                            if (!IsDisposed && _pdfPane == created && profileId == _activeWorkspaceProfileId)
                                SendMessage(new { type = "workspace.pdf.error", profileId, projectId = created.ProjectId, repositoryId = created.RepositoryId, filePath = created.FilePath, error });
                        };
                        _browserHost.Panel2.Controls.Add(created);
                    }
                    var pane = _pdfPane;
                    await pane.OpenAsync(Path.Combine(BrowserStoragePath(profileId), "pdf"), project.Id, repo.Id, root, relative, page);
                    if (IsDisposed || pane.IsDisposed || profileId != _activeWorkspaceProfileId) return;
                    _pdfPaneActive = true;
                    if (_browserPane != null) { _browserPane.Visible = false; _browserPane.SetWorkspaceVisible(false); }
                    pane.Visible = true; pane.BringToFront(); pane.Focus();
                }
                finally { _browserGate.Release(); }
                if (notifyOpen) SendMessage(new { type = "workspace.pdf.opened", profileId, kind = "pdf", projectId, repositoryId, filePath = relative, page });
            }
            if (IsDisposed || profileId != _activeWorkspaceProfileId) return;
            var info = new FileInfo(path);
            SendMessage(new { type = "workspace.pdf.result", profileId, projectId, repositoryId, filePath = relative, page, requestId, action,
                size = info.Length, modified = info.LastWriteTimeUtc.ToString("O") });
        }
        catch (Exception error)
        {
            if (IsDisposed || profileId != _activeWorkspaceProfileId) return;
            SendMessage(new { type = "workspace.pdf.result", profileId, projectId, repositoryId, filePath, requestId, error = error.Message });
            if (requestId == null) SendMessage(new { type = "repository.job.error", key = $"{profileId}:{projectId}:{repositoryId}", message = error.Message });
        }
    }

    private async Task ObservePdfBuildAsync(string key, string profileId, string projectId, string repositoryId, bool openAfter)
    {
        var result = await _repositoryRunner.Completion(key);
        if (result.State != "succeeded" || result.BuildState != "succeeded" || IsDisposed || !IsHandleCreated) return;
        try
        {
            BeginInvoke(new Action(async () =>
            {
                if (IsDisposed || profileId != _activeWorkspaceProfileId) return;
                if (openAfter) await OpenWorkspacePdfAsync(profileId, projectId, repositoryId);
                else if (_pdfPaneActive && !_browserHost.Panel2Collapsed && _pdfPane is { } pane &&
                    pane.ProjectId == projectId && pane.RepositoryId == repositoryId)
                    await OpenWorkspacePdfAsync(profileId, projectId, repositoryId, "refresh", pane.FilePath, pane.Page, notifyOpen: false);
            }));
        }
        catch (InvalidOperationException) when (IsDisposed || Disposing) { }
    }
}
