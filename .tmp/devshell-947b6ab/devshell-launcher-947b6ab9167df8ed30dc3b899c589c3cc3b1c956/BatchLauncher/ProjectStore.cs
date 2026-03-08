using System.Text.Json;

namespace BatchLauncher;

internal static class ProjectStore
{
    private static readonly JsonSerializerOptions Options = new()
    {
        PropertyNameCaseInsensitive = true
    };

    public static List<ProjectDefinition> LoadProjects()
    {
        var path = AppPaths.ScriptsPath;
        if (!File.Exists(path))
        {
            return new List<ProjectDefinition>();
        }

        try
        {
            var json = File.ReadAllText(path);
            using var doc = JsonDocument.Parse(json);
            if (doc.RootElement.ValueKind != JsonValueKind.Object)
            {
                return new List<ProjectDefinition>();
            }

            if (!doc.RootElement.TryGetProperty("projects", out var projectsElement))
            {
                return new List<ProjectDefinition>();
            }

            if (projectsElement.ValueKind != JsonValueKind.Array)
            {
                return new List<ProjectDefinition>();
            }

            return JsonSerializer.Deserialize<List<ProjectDefinition>>(projectsElement.GetRawText(), Options)
                ?? new List<ProjectDefinition>();
        }
        catch
        {
            return new List<ProjectDefinition>();
        }
    }
}
