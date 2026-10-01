using System.Text.Json;

namespace BatchLauncher;

public partial class Form1
{
    private async Task HandleRepositoryChangesAsync(JsonElement payload, string action)
    {
        // The dispatcher disposes its JsonDocument when this handler first yields.
        payload = payload.Clone();
        var profileId = _activeWorkspaceProfileId;
        var requestId = payload.GetProperty("requestId").GetString();
        string? lockedPath = null;
        try
        {
            if (payload.GetProperty("profileId").GetString() != profileId) throw new InvalidOperationException("Profile changed. Reopen Changes.");
            var projectId = payload.GetProperty("projectId").GetString();
            var repositoryId = payload.GetProperty("repositoryId").GetString();
            var project = _workspace.Projects?.FirstOrDefault(item => item.Id == projectId) ?? throw new InvalidOperationException("Project not found.");
            var repo = project.Repositories?.FirstOrDefault(item => item.Id == repositoryId) ?? throw new InvalidOperationException("Repository not found.");
            var key = $"{profileId}:{projectId}:{repositoryId}";
            var path = Path.GetFullPath(ExpandProjectValue(project, repo.Path)).TrimEnd('\\', '/');
            EnsureRepositoryIdle(key, path);
            _repositoryChangesPaths.Add(path); lockedPath = path;
            var snapshot = await RepositoryChanges.Read(path);
            RepositoryFileDiff? diff = null;
            if (action == "file-diff") diff = await RepositoryChanges.Diff(path, snapshot, payload.GetProperty("path").GetString()!, payload.GetProperty("side").GetString()!);
            if (action is "stage" or "unstage")
            {
                if (IsDisposed || profileId != _activeWorkspaceProfileId) return;
                var paths = payload.GetProperty("paths").EnumerateArray().Select(item => item.GetString()!).ToArray();
                snapshot = await RepositoryChanges.ChangeIndex(path, snapshot, payload.GetProperty("token").GetString()!, action, paths);
            }
            if (!IsDisposed && profileId == _activeWorkspaceProfileId)
                SendMessage(new { type = "repository.changes", profileId, requestId, snapshot, diff });
        }
        catch (Exception error)
        {
            if (!IsDisposed) SendMessage(new { type = "repository.changes", profileId, requestId, error = error.Message });
        }
        finally { if (lockedPath != null) _repositoryChangesPaths.Remove(lockedPath); }
    }
}
