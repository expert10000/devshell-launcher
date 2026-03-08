namespace BatchLauncher;

public sealed class WorkspaceConfig
{
    public int Version { get; set; } = 1;
    public WorkspaceGlobals? Globals { get; set; }
    public Dictionary<string, WorkspaceTask>? Templates { get; set; }
    public List<WorkspaceProject>? Projects { get; set; }
    public List<WorkspaceLaunch>? Workspaces { get; set; }
}

public sealed class WorkspaceGlobals
{
    public string? DefaultShell { get; set; }
    public WorkspaceTerminalSettings? Terminal { get; set; }
    public Dictionary<string, string>? Vars { get; set; }
}

public sealed class WorkspaceTerminalSettings
{
    public int? FontSize { get; set; }
    public int? Scrollback { get; set; }
}

public sealed class WorkspaceTask
{
    public string? Group { get; set; }
    public string? Shell { get; set; }
    public string? Cwd { get; set; }
    public List<WorkspaceTaskStep>? Steps { get; set; }
    public List<string>? DependsOn { get; set; }
    public bool? RunInNewTab { get; set; }
    public bool? FocusTab { get; set; }
    public string? UseTemplate { get; set; }
}

public sealed class WorkspaceTaskStep
{
    public string Run { get; set; } = string.Empty;
}

public sealed class WorkspaceProject
{
    public string Id { get; set; } = string.Empty;
    public string Name { get; set; } = string.Empty;
    public string? Root { get; set; }
    public bool? Pinned { get; set; }
    public Dictionary<string, string>? Vars { get; set; }
    public WorkspaceTask? Bootstrap { get; set; }
    public Dictionary<string, WorkspaceTask>? Tasks { get; set; }
    public List<string>? QuickTasks { get; set; }
    public ProjectLayout? Layout { get; set; }
}

public sealed class WorkspaceLaunch
{
    public string Id { get; set; } = string.Empty;
    public string Name { get; set; } = string.Empty;
    public string ProjectId { get; set; } = string.Empty;
    public List<WorkspaceLaunchTab>? OpenTabs { get; set; }
}

public sealed class WorkspaceLaunchTab
{
    public string Task { get; set; } = string.Empty;
    public string? Title { get; set; }
}
