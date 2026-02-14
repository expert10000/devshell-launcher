namespace BatchLauncher;

public sealed class ProjectDefinition
{
    public string Id { get; set; } = string.Empty;
    public string Name { get; set; } = string.Empty;
    public string? Root { get; set; }
    public ProjectLayout? Layout { get; set; }
}

public sealed class ProjectLayout
{
    public string Type { get; set; } = "tabs";
    public string? Direction { get; set; }
    public List<ProjectLayout>? Panes { get; set; }
    public List<ProjectLayoutItem>? Items { get; set; }
}

public sealed class ProjectLayoutItem
{
    public string Title { get; set; } = string.Empty;
    public string? ProfileId { get; set; }
    public string? TaskId { get; set; }
    public string? Cwd { get; set; }
    public bool? AutoRun { get; set; }
    public int? StartOrder { get; set; }
}
