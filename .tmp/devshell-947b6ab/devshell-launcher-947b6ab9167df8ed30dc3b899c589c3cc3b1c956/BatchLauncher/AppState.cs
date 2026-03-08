namespace BatchLauncher;

public sealed class AppState
{
    public List<PersistedTab> Tabs { get; set; } = new();
    public string? ActiveTabId { get; set; }
    public bool RestoreSessions { get; set; } = false;
    public string? Theme { get; set; }
    public string? FontFamily { get; set; }
    public double? FontSize { get; set; }
    public bool AutoFit { get; set; } = true;
    public bool CopyOnSelect { get; set; }
    public bool RightClickPaste { get; set; } = true;
    public List<string> FavoriteFolders { get; set; } = new();
}

public sealed class PersistedTab
{
    public string Id { get; set; } = Guid.NewGuid().ToString("N");
    public string Title { get; set; } = "Tab";
    public List<PersistedPane> Panes { get; set; } = new();
    public string? ActivePaneId { get; set; }
    public List<PersistedGroup> Groups { get; set; } = new();
    public string? ActiveGroupId { get; set; }
    public bool Split { get; set; }
    public string? SplitDirection { get; set; }
    public double SplitRatio { get; set; } = 0.5;
}

public sealed class PersistedGroup
{
    public string Id { get; set; } = Guid.NewGuid().ToString("N");
    public string Title { get; set; } = "Group";
    public List<PersistedPane> Tabs { get; set; } = new();
    public string? ActiveTabId { get; set; }
}

public sealed class PersistedPane
{
    public string Id { get; set; } = Guid.NewGuid().ToString("N");
    public string ProfileId { get; set; } = "powershell";
    public string Title { get; set; } = "Shell";
    public string? Cwd { get; set; }
    public int? Cols { get; set; }
    public int? Rows { get; set; }
}
