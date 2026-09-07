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
            return true;
        }
        catch (Exception ex)
        {
            error = ex.Message;
            return false;
        }
    }
}
