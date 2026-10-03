using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace BatchLauncher;

internal sealed class WorkspaceTabsState
{
    public int Version { get; set; } = 1;
    public List<WorkspaceViewTab> Tabs { get; set; } = new();
    public string? ActiveId { get; set; }
}

internal sealed class WorkspaceViewTab
{
    public string Id { get; set; } = Guid.NewGuid().ToString();
    public string Kind { get; set; } = "logs";
    public string? ProjectId { get; set; }
    public string? RepositoryId { get; set; }
    public string? FilePath { get; set; }
    public string? Side { get; set; }
    public string? Url { get; set; }
    public string? ServicePath { get; set; }
    public int? Page { get; set; }
}

internal static class WorkspaceTabsStore
{
    public const int MaxTabs = 24;
    private static readonly JsonSerializerOptions Options = new() { PropertyNamingPolicy = JsonNamingPolicy.CamelCase, WriteIndented = true };

    private static string StatePath(string profileId)
    {
        var key = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(profileId)));
        return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "DevShellLauncher", "workspace-tabs", key + ".json");
    }

    public static string? CleanWebUrl(string? url)
    {
        if (!Uri.TryCreate(url, UriKind.Absolute, out var uri) || uri.Scheme is not ("http" or "https")) return null;
        // Persist a reopening target, never authentication data or arbitrary query values.
        return new UriBuilder(uri) { UserName = "", Password = "", Query = "", Fragment = "" }.Uri.AbsoluteUri;
    }

    internal static bool IsRelativePath(string? path) => path != null && path.Length <= 2048 &&
        !Path.IsPathRooted(path) && !path.Contains('\\') && !path.Contains(':') && !path.Contains('\0') &&
        !path.Split('/').Any(part => part is "." or ".." || part.Equals(".git", StringComparison.OrdinalIgnoreCase));

    public static WorkspaceTabsState Normalize(WorkspaceTabsState state, WorkspaceConfig workspace)
    {
        var result = new WorkspaceTabsState(); var ids = new HashSet<string>(); var identities = new HashSet<string>();
        foreach (var tab in (state.Tabs ?? new()).Take(MaxTabs))
        {
            if (tab == null || !Guid.TryParse(tab.Id, out _) || !ids.Add(tab.Id)) continue;
            var project = workspace.Projects?.FirstOrDefault(item => item.Id == tab.ProjectId);
            var repo = project?.Repositories?.FirstOrDefault(item => item.Id == tab.RepositoryId);
            if (tab.Kind is "logs" or "diff")
            {
                if (repo == null || tab.FilePath != null && !IsRelativePath(tab.FilePath)) continue;
                var identity = tab.Kind + ":" + project!.Id + ":" + repo.Id;
                if (!identities.Add(identity)) continue;
                result.Tabs.Add(new() { Id = tab.Id, Kind = tab.Kind, ProjectId = project.Id, RepositoryId = repo.Id,
                    FilePath = tab.Kind == "diff" ? tab.FilePath : null, Side = tab.Kind == "diff" ? tab.Side == "staged" ? "staged" : "working" : null });
            }
            else if (tab.Kind == "pdf")
            {
                if (repo == null || (tab.FilePath == null ? repo.PdfDirectory == null : !PdfFile.IsRelativePdf(tab.FilePath))) continue;
                if (!identities.Add("pdf:" + project!.Id + ":" + repo.Id + ":" + tab.FilePath)) continue;
                result.Tabs.Add(new() { Id = tab.Id, Kind = "pdf", ProjectId = project.Id, RepositoryId = repo.Id,
                    FilePath = tab.FilePath, Page = Math.Clamp(tab.Page ?? 1, 1, 1000000) });
            }
            else if (tab.Kind == "jupyter")
            {
                if (project?.Service == null || tab.ServicePath != null && !IsRelativePath(tab.ServicePath)) continue;
                if (!identities.Add("jupyter:" + project.Id + ":" + tab.ServicePath)) continue;
                result.Tabs.Add(new() { Id = tab.Id, Kind = "jupyter", ProjectId = project.Id, ServicePath = tab.ServicePath });
            }
            else if (tab.Kind == "browser")
            {
                var url = CleanWebUrl(tab.Url);
                if (url == null || url.Length > 4096 || tab.ProjectId != null && project == null) continue;
                if (!identities.Add("browser:" + url)) continue;
                result.Tabs.Add(new() { Id = tab.Id, Kind = "browser", ProjectId = project?.Id, RepositoryId = repo?.Id, Url = url });
            }
        }
        result.ActiveId = result.Tabs.Any(tab => tab.Id == state.ActiveId) ? state.ActiveId : null;
        return result;
    }

    public static WorkspaceTabsState Load(string profileId, WorkspaceConfig workspace)
    {
        try
        {
            var path = StatePath(profileId);
            if (!File.Exists(path) || new FileInfo(path).Length > 128000) return new();
            var state = JsonSerializer.Deserialize<WorkspaceTabsState>(File.ReadAllText(path), Options);
            return state?.Version == 1 ? Normalize(state, workspace) : new();
        }
        catch { return new(); }
    }

    public static void Save(string profileId, WorkspaceTabsState state, WorkspaceConfig workspace)
    {
        var path = StatePath(profileId); Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        var temporary = path + ".tmp";
        File.WriteAllText(temporary, JsonSerializer.Serialize(Normalize(state, workspace), Options));
        File.Move(temporary, path, true);
    }
}
