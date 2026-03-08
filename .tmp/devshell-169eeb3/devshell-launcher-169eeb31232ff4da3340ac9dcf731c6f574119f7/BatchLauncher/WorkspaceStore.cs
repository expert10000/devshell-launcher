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
        var path = AppPaths.ScriptsPath;
        if (!File.Exists(path))
        {
            return new WorkspaceConfig();
        }

        try
        {
            var json = File.ReadAllText(path);
            return JsonSerializer.Deserialize<WorkspaceConfig>(json, Options) ?? new WorkspaceConfig();
        }
        catch
        {
            return new WorkspaceConfig();
        }
    }
}
