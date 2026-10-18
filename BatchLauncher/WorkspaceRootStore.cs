using System.Text.Json;

namespace BatchLauncher;

public sealed class WorkspaceRootStore(string path)
{
    private Dictionary<string, string> Read()
    {
        if (!File.Exists(path)) return new();
        return JsonSerializer.Deserialize<Dictionary<string, string>>(File.ReadAllText(path)) ?? new();
    }
    public string? Get(string profileId) => Read().GetValueOrDefault(profileId);
    public void Save(string profileId, string root)
    {
        var roots = Read();
        roots[profileId] = PortableWorkspace.ValidateRoot(root);
        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(path))!);
        var temporary = path + ".tmp";
        File.WriteAllText(temporary, JsonSerializer.Serialize(roots, new JsonSerializerOptions { WriteIndented = true }));
        File.Move(temporary, path, true);
    }
}
