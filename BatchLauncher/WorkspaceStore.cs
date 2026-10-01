using System.Text.Json;

namespace BatchLauncher;

internal static class WorkspaceStore
{
    private static readonly JsonSerializerOptions Options = new()
    {
        PropertyNameCaseInsensitive = true
    };

    public static WorkspaceConfig LoadWorkspace()
    {
        return LoadWorkspace(AppPaths.ScriptsPath);
    }

    public static WorkspaceConfig LoadWorkspace(string path)
    {
        return TryLoadWorkspace(path, out var workspace, out _)
            ? workspace
            : new WorkspaceConfig();
    }

    public static bool TryLoadWorkspace(
        string path,
        out WorkspaceConfig workspace,
        out string? error)
    {
        workspace = new WorkspaceConfig();
        error = null;
        if (!File.Exists(path))
        {
            error = $"Configuration file not found: {path}";
            return false;
        }

        try
        {
            var json = File.ReadAllText(path);
            workspace = JsonSerializer.Deserialize<WorkspaceConfig>(json, Options)
                ?? new WorkspaceConfig();
            DiscoverProjectRepositories(workspace);
            return true;
        }
        catch (Exception ex)
        {
            error = ex.Message;
            return false;
        }
    }

    private static void DiscoverProjectRepositories(WorkspaceConfig workspace)
    {
        foreach (var project in workspace.Projects ?? new())
        {
            if (project.Repositories?.Count > 0 || string.IsNullOrWhiteSpace(project.Root)) continue;
            var root = project.Root;
            var variables = new Dictionary<string, string>(workspace.Globals?.Vars ?? new());
            foreach (var pair in project.Vars ?? new()) variables[pair.Key] = pair.Value;
            foreach (var pair in variables) root = root.Replace("${vars." + pair.Key + "}", pair.Value);
            if (!Path.IsPathFullyQualified(root) || !Directory.Exists(root)) continue;
            try
            {
                for (var directory = new DirectoryInfo(root); directory != null; directory = directory.Parent)
                {
                    var marker = Path.Combine(directory.FullName, ".git");
                    if (!Directory.Exists(marker) && !File.Exists(marker)) continue;
                    project.Repositories = new() { new WorkspaceRepository { Id = "project-root", Name = directory.Name, Path = directory.FullName } };
                    break;
                }
            }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
        }
    }
}
