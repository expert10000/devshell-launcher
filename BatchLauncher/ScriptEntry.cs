namespace BatchLauncher;

public class ScriptEntry
{
    public string Name { get; set; }
    public string Path { get; set; }
    public string Args { get; set; }
    public string WorkingDirectory { get; set; }
    public bool? UseTerminal { get; set; }
}
