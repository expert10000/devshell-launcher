using System.Text.Json;

namespace BatchLauncher;

internal sealed class BrowserWorkspaceState
{
    public bool Visible { get; set; }
    public string? ActiveTabId { get; set; }
    public List<PersistedBrowserTab> Tabs { get; set; } = new();
}

internal sealed class PersistedBrowserTab
{
    public string Id { get; set; } = Guid.NewGuid().ToString("N");
    public string Title { get; set; } = "New tab";
    public string? Url { get; set; }
}

internal static class BrowserWorkspaceStore
{
    public const int MaxTabs = 24;
    private static readonly JsonSerializerOptions Options = new() { PropertyNamingPolicy = JsonNamingPolicy.CamelCase, WriteIndented = true };
    private static readonly HashSet<string> SecretParameters = new(StringComparer.OrdinalIgnoreCase)
        { "token", "access_token", "refresh_token", "api_key", "apikey", "auth", "password", "code" };

    public static BrowserWorkspaceState Load(string path)
    {
        try
        {
            if (!File.Exists(path)) return new();
            var state = JsonSerializer.Deserialize<BrowserWorkspaceState>(File.ReadAllText(path), Options) ?? new();
            state.Tabs = (state.Tabs ?? new()).Where(tab => tab != null && (tab.Url == null || BrowserPane.IsWebUrl(tab.Url)))
                .Take(MaxTabs).Select(tab => new PersistedBrowserTab { Id = tab.Id, Title = tab.Title ?? "New tab", Url = tab.Url == null ? null : CleanUrl(tab.Url) }).ToList();
            return state;
        }
        catch { return new(); }
    }

    public static string CleanUrl(string url)
    {
        var uri = new Uri(url);
        var query = uri.Query.TrimStart('?').Split('&', StringSplitOptions.RemoveEmptyEntries).Where(part =>
            !SecretParameters.Contains(Uri.UnescapeDataString(part.Split('=', 2)[0])));
        var clean = new UriBuilder(uri) { UserName = "", Password = "", Query = string.Join("&", query) };
        if (uri.Fragment.Contains("token", StringComparison.OrdinalIgnoreCase) || uri.Fragment.Contains("password", StringComparison.OrdinalIgnoreCase)) clean.Fragment = "";
        return clean.Uri.AbsoluteUri;
    }

    public static void Save(string path, BrowserWorkspaceState state)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        foreach (var tab in state.Tabs) if (tab.Url != null) tab.Url = CleanUrl(tab.Url);
        var temporary = path + ".tmp";
        File.WriteAllText(temporary, JsonSerializer.Serialize(state, Options));
        File.Move(temporary, path, true);
    }
}
