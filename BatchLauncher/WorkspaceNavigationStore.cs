using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace BatchLauncher;

internal sealed record WorkspaceFileReference(string ProjectId, string RepositoryId, string Path, string Kind);
internal sealed record WorkspaceFileLink(WorkspaceFileReference Source, WorkspaceFileReference Output);
internal sealed class WorkspaceNavigationState
{
    public int Version { get; set; } = 1;
    public List<WorkspaceFileReference> Recent { get; set; } = new();
    public List<WorkspaceFileReference> Pinned { get; set; } = new();
    public List<WorkspaceFileLink> Links { get; set; } = new();
}

internal static class WorkspaceNavigationStore
{
    internal const int MaxRecent = 30, MaxPinned = 40, MaxLinks = 40;
    internal static readonly JsonSerializerOptions Options = new() { PropertyNamingPolicy = JsonNamingPolicy.CamelCase, WriteIndented = true };
    internal static string Identity(WorkspaceFileReference reference) => reference.ProjectId + ":" + reference.RepositoryId + ":" + reference.Path.ToLowerInvariant();

    internal static WorkspaceFileReference? NormalizeReference(WorkspaceFileReference? reference, WorkspaceConfig workspace)
    {
        if (reference == null || string.IsNullOrWhiteSpace(reference.Path) || !WorkspaceTabsStore.IsRelativePath(reference.Path) || reference.Path.Split('/').Any(string.IsNullOrWhiteSpace)) return null;
        var project = workspace.Projects?.FirstOrDefault(item => item.Id == reference.ProjectId);
        if (project?.Repositories?.Any(item => item.Id == reference.RepositoryId) != true) return null;
        var kind = WorkspaceFiles.KindOfFile(reference.Path);
        return kind == "file" ? null : reference with { Kind = kind };
    }

    internal static WorkspaceNavigationState Normalize(WorkspaceNavigationState state, WorkspaceConfig workspace)
    {
        List<WorkspaceFileReference> References(List<WorkspaceFileReference>? input, int limit)
        {
            var seen = new HashSet<string>(); var result = new List<WorkspaceFileReference>();
            foreach (var item in (input ?? new()).Take(limit * 2))
            {
                var reference = NormalizeReference(item, workspace);
                if (reference != null && seen.Add(Identity(reference))) result.Add(reference);
                if (result.Count >= limit) break;
            }
            return result;
        }
        var result = new WorkspaceNavigationState { Recent = References(state.Recent, MaxRecent), Pinned = References(state.Pinned, MaxPinned) };
        var seenLinks = new HashSet<string>();
        foreach (var link in (state.Links ?? new()).Take(MaxLinks * 2))
        {
            var source = NormalizeReference(link?.Source, workspace); var output = NormalizeReference(link?.Output, workspace);
            if (source == null || output == null || Identity(source) == Identity(output)) continue;
            if (seenLinks.Add(Identity(source) + "=>" + Identity(output))) result.Links.Add(new(source, output));
            if (result.Links.Count >= MaxLinks) break;
        }
        return result;
    }

    private static string StatePath(string profileId)
    {
        var key = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(profileId)));
        return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "DevShellLauncher", "file-navigation", key + ".json");
    }

    internal static WorkspaceNavigationState Load(string profileId, WorkspaceConfig workspace)
    {
        try
        {
            var path = StatePath(profileId);
            if (!File.Exists(path) || new FileInfo(path).Length > 256 * 1024) return new();
            var state = JsonSerializer.Deserialize<WorkspaceNavigationState>(File.ReadAllText(path), Options);
            return state?.Version == 1 ? Normalize(state, workspace) : new();
        }
        catch { return new(); }
    }

    internal static void Save(string profileId, WorkspaceNavigationState state, WorkspaceConfig workspace)
    {
        var path = StatePath(profileId); Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        var temporary = path + ".tmp";
        File.WriteAllText(temporary, JsonSerializer.Serialize(Normalize(state, workspace), Options));
        File.Move(temporary, path, true);
    }

    internal static void Remember(WorkspaceNavigationState state, WorkspaceFileReference reference)
    {
        var identity = Identity(reference);
        state.Recent = state.Recent.Where(item => Identity(item) != identity).Prepend(reference).Take(MaxRecent).ToList();
    }
}
