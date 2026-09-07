using System.Text.Json;

namespace BatchLauncher;

internal sealed record WorkspaceProfileInfo(string Id, string Name, string Path);

internal static class WorkspaceProfileStore
{
    private static readonly JsonSerializerOptions Options = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        WriteIndented = true
    };

    public static List<WorkspaceProfileInfo> GetProfiles()
    {
        AppPaths.EnsureWorkspaceProfilesDirectory();
        var profiles = Directory
            .EnumerateFiles(AppPaths.WorkspaceProfilesDirectory, "*.json", SearchOption.TopDirectoryOnly)
            .OrderBy(path => path, StringComparer.OrdinalIgnoreCase)
            .Select(path =>
            {
                var id = System.IO.Path.GetFileNameWithoutExtension(path);
                return new WorkspaceProfileInfo(id, id.Replace('-', ' '), path);
            })
            .ToList();

        if (profiles.Count == 0 && File.Exists(AppPaths.ScriptsPath))
        {
            profiles.Add(new WorkspaceProfileInfo("default", "default", AppPaths.ScriptsPath));
        }

        return profiles;
    }

    public static WorkspaceProfileInfo? ResolveInitialProfile(
        IReadOnlyList<WorkspaceProfileInfo> profiles)
    {
        var selectedId = LoadSelection();
        return profiles.FirstOrDefault(profile =>
                   profile.Id.Equals(selectedId, StringComparison.OrdinalIgnoreCase))
               ?? profiles.FirstOrDefault(profile =>
                   profile.Id.Equals("desktop-main", StringComparison.OrdinalIgnoreCase))
               ?? profiles.FirstOrDefault();
    }

    public static void SaveSelection(string profileId)
    {
        AppPaths.EnsureLocalSettingsDirectory();
        var json = JsonSerializer.Serialize(new { activeProfileId = profileId }, Options);
        File.WriteAllText(AppPaths.WorkspaceProfileSelectionPath, json);
    }

    private static string? LoadSelection()
    {
        if (!File.Exists(AppPaths.WorkspaceProfileSelectionPath))
        {
            return null;
        }

        try
        {
            using var document = JsonDocument.Parse(
                File.ReadAllText(AppPaths.WorkspaceProfileSelectionPath));
            return document.RootElement.TryGetProperty("activeProfileId", out var value)
                ? value.GetString()
                : null;
        }
        catch
        {
            return null;
        }
    }
}
