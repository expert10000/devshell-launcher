using System.Text.Json.Serialization;

namespace BatchLauncher;

public sealed class TerminalProfile
{
    public string Id { get; set; } = string.Empty;
    public string Name { get; set; } = string.Empty;
    public string Command { get; set; } = string.Empty;
    public string? Arguments { get; set; }
    public string? WorkingDirectory { get; set; }
    public Dictionary<string, string>? Environment { get; set; }
    public string? Icon { get; set; }
    public int? DefaultCols { get; set; }
    public int? DefaultRows { get; set; }
    public bool IsBuiltin { get; set; }
    public bool IsAvailable { get; set; } = true;
    public bool IsTemplate { get; set; }

    [JsonIgnore]
    public string? ResolvedCommand { get; set; }
}
