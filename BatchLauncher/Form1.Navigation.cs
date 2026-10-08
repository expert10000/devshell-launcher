using System.Text.Json;

namespace BatchLauncher;

public partial class Form1
{
    private object NavigationPayload(WorkspaceNavigationState state)
    {
        object Describe(WorkspaceFileReference reference)
        {
            var project = _workspace.Projects?.FirstOrDefault(item => item.Id == reference.ProjectId);
            var repository = project?.Repositories?.FirstOrDefault(item => item.Id == reference.RepositoryId);
            return new { reference.ProjectId, reference.RepositoryId, reference.Path, reference.Kind, projectName = project?.Name ?? reference.ProjectId, repositoryName = repository?.Name ?? reference.RepositoryId };
        }
        return new { recent = state.Recent.Select(Describe).ToList(), pinned = state.Pinned.Select(Describe).ToList(), links = state.Links.Select(link => new { source = Describe(link.Source), output = Describe(link.Output) }).ToList() };
    }

    private WorkspaceFileReference ValidateNavigationFile(JsonElement element)
    {
        var input = JsonSerializer.Deserialize<WorkspaceFileReference>(element.GetRawText(), WorkspaceNavigationStore.Options);
        var reference = WorkspaceNavigationStore.NormalizeReference(input, _workspace) ?? throw new ArgumentException("Select a supported file in a configured repository.");
        var project = _workspace.Projects!.First(item => item.Id == reference.ProjectId);
        var repo = project.Repositories!.First(item => item.Id == reference.RepositoryId);
        WorkspaceFiles.Locate(ExpandProjectValue(project, repo.Path), reference.Path);
        return reference;
    }

    private void HandleWorkspaceNavigation(JsonElement payload, string profileId, string? requestId)
    {
        var operation = payload.GetProperty("operation").GetString();
        var state = WorkspaceNavigationStore.Load(profileId, _workspace);
        if (operation == "pin")
        {
            var reference = ValidateNavigationFile(payload.GetProperty("file"));
            if (!state.Pinned.Any(item => WorkspaceNavigationStore.Identity(item) == WorkspaceNavigationStore.Identity(reference)))
            {
                if (state.Pinned.Count >= WorkspaceNavigationStore.MaxPinned) throw new InvalidOperationException("Unpin a file first (limit: 40 pinned references).");
                state.Pinned.Insert(0, reference);
            }
        }
        else if (operation == "unpin")
        {
            var reference = JsonSerializer.Deserialize<WorkspaceFileReference>(payload.GetProperty("file").GetRawText(), WorkspaceNavigationStore.Options) ?? throw new ArgumentException("Select a pinned reference.");
            state.Pinned.RemoveAll(item => WorkspaceNavigationStore.Identity(item) == WorkspaceNavigationStore.Identity(reference));
        }
        else if (operation == "link")
        {
            var source = ValidateNavigationFile(payload.GetProperty("source")); var output = ValidateNavigationFile(payload.GetProperty("output"));
            if (WorkspaceNavigationStore.Identity(source) == WorkspaceNavigationStore.Identity(output)) throw new ArgumentException("Choose two different files.");
            if (!state.Links.Any(link => WorkspaceNavigationStore.Identity(link.Source) == WorkspaceNavigationStore.Identity(source) && WorkspaceNavigationStore.Identity(link.Output) == WorkspaceNavigationStore.Identity(output)))
            {
                if (state.Links.Count >= WorkspaceNavigationStore.MaxLinks) throw new InvalidOperationException("Remove a link first (limit: 40 source/output links).");
                state.Links.Add(new(source, output));
            }
        }
        else if (operation == "unlink")
        {
            var source = JsonSerializer.Deserialize<WorkspaceFileReference>(payload.GetProperty("source").GetRawText(), WorkspaceNavigationStore.Options) ?? throw new ArgumentException("Select a source reference.");
            var output = JsonSerializer.Deserialize<WorkspaceFileReference>(payload.GetProperty("output").GetRawText(), WorkspaceNavigationStore.Options) ?? throw new ArgumentException("Select an output reference.");
            state.Links.RemoveAll(link => WorkspaceNavigationStore.Identity(link.Source) == WorkspaceNavigationStore.Identity(source) && WorkspaceNavigationStore.Identity(link.Output) == WorkspaceNavigationStore.Identity(output));
        }
        else if (operation == "clear-recent") state.Recent.Clear();
        else if (operation != "load") throw new ArgumentException("Unknown file navigation action.");
        if (operation != "load") WorkspaceNavigationStore.Save(profileId, state, _workspace);
        var navigation = NavigationPayload(state);
        SendMessage(new { type = "workspace.files.result", profileId, requestId, navigation });
        if (operation != "load") SendMessage(new { type = "workspace.navigation.changed", profileId, navigation });
    }

    private void RememberWorkspaceFile(string? projectId, string? repositoryId, string path, string kind)
    {
        if (string.IsNullOrEmpty(_activeWorkspaceProfileId) || projectId == null || repositoryId == null) return;
        try
        {
            var reference = WorkspaceNavigationStore.NormalizeReference(new(projectId, repositoryId, path, kind), _workspace);
            if (reference == null) return;
            var state = WorkspaceNavigationStore.Load(_activeWorkspaceProfileId, _workspace);
            WorkspaceNavigationStore.Remember(state, reference);
            WorkspaceNavigationStore.Save(_activeWorkspaceProfileId, state, _workspace);
            SendMessage(new { type = "workspace.navigation.changed", profileId = _activeWorkspaceProfileId, navigation = NavigationPayload(state) });
        }
        catch (Exception error)
        {
            // Bookmark storage must never prevent a successfully read file from being previewed.
            SendMessage(new { type = "workspace.navigation.changed", profileId = _activeWorkspaceProfileId, error = "Recent file reference could not be saved: " + error.Message });
        }
    }
}
