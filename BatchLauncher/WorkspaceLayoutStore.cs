using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace BatchLauncher;

internal sealed class WorkspaceNamedLayout
{
    public string Id { get; set; } = Guid.NewGuid().ToString();
    public string Name { get; set; } = "";
    public string Direction { get; set; } = "right";
    public double Ratio { get; set; } = 50;
    public string Focused { get; set; } = "primary";
    public List<WorkspaceViewTab> Tabs { get; set; } = new();
}

internal static class WorkspaceLayoutStore
{
    internal const int MaxLayouts = 12;
    private static readonly JsonSerializerOptions Options = new() { PropertyNamingPolicy = JsonNamingPolicy.CamelCase, WriteIndented = true };
    internal static WorkspaceNamedLayout? Normalize(WorkspaceNamedLayout layout, WorkspaceConfig workspace)
    {
        var name = (layout.Name ?? "").Trim();
        if (!Guid.TryParse(layout.Id, out _) || name.Length is < 1 or > 48 || name.Any(char.IsControl) || layout.Direction is not ("right" or "below")) return null;
        var descriptors = WorkspaceTabsStore.Normalize(new() { Tabs = (layout.Tabs ?? new()).Take(2).ToList() }, workspace).Tabs;
        if (descriptors.Count != 2) return null;
        return new() { Id = layout.Id, Name = name, Direction = layout.Direction, Ratio = double.IsFinite(layout.Ratio) ? Math.Clamp(layout.Ratio, 20, 80) : 50,
            Focused = layout.Focused == "secondary" ? "secondary" : "primary", Tabs = descriptors };
    }

    private static List<WorkspaceNamedLayout> NormalizeAll(List<WorkspaceNamedLayout> input, WorkspaceConfig workspace)
    {
        var result = new List<WorkspaceNamedLayout>(); var names = new HashSet<string>(StringComparer.OrdinalIgnoreCase); var ids = new HashSet<string>();
        foreach (var layout in input.Take(MaxLayouts * 2))
        {
            var safe = layout == null ? null : Normalize(layout, workspace);
            if (safe != null && names.Add(safe.Name) && ids.Add(safe.Id)) result.Add(safe);
            if (result.Count >= MaxLayouts) break;
        }
        return result;
    }

    private static string StatePath(string profileId)
    {
        var key = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(profileId)));
        return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "DevShellLauncher", "workspace-layouts", key + ".json");
    }

    internal static List<WorkspaceNamedLayout> Load(string profileId, WorkspaceConfig workspace)
    {
        try
        {
            var path = StatePath(profileId);
            if (!File.Exists(path) || new FileInfo(path).Length > 256 * 1024) return new();
            return NormalizeAll(JsonSerializer.Deserialize<List<WorkspaceNamedLayout>>(File.ReadAllText(path), Options) ?? new(), workspace);
        }
        catch { return new(); }
    }

    internal static void Save(string profileId, List<WorkspaceNamedLayout> layouts, WorkspaceConfig workspace)
    {
        var path = StatePath(profileId); Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        var temporary = path + ".tmp";
        File.WriteAllText(temporary, JsonSerializer.Serialize(NormalizeAll(layouts, workspace), Options));
        File.Move(temporary, path, true);
    }
}
