namespace BatchLauncher;

public class ScriptEntry
{
    public string? Id { get; set; }
    public string Name { get; set; } = string.Empty;
    public string? Path { get; set; }
    public string? Command { get; set; }
    public string? Args { get; set; }
    public string? WorkingDirectory { get; set; }
    public string? Cwd { get; set; }
    public string? ProfileId { get; set; }
    public bool? UseTerminal { get; set; }
    public bool? AutoRun { get; set; }
}
