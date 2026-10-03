using System.Text.Json;

namespace BatchLauncher;

internal static class WorkspaceStore
{
    private static readonly JsonSerializerOptions Options = new()
    {
        PropertyNameCaseInsensitive = true
    };

    public static WorkspaceConfig LoadWorkspace()
    {
        return LoadWorkspace(AppPaths.ScriptsPath);
    }

    public static WorkspaceConfig LoadWorkspace(string path)
    {
        return TryLoadWorkspace(path, out var workspace, out _)
            ? workspace
            : new WorkspaceConfig();
    }

    public static bool TryLoadWorkspace(
        string path,
        out WorkspaceConfig workspace,
        out string? error)
    {
        workspace = new WorkspaceConfig();
        error = null;
        if (!File.Exists(path))
        {
            error = $"Configuration file not found: {path}";
            return false;
        }

        try
        {
            var json = File.ReadAllText(path);
            workspace = JsonSerializer.Deserialize<WorkspaceConfig>(json, Options)
                ?? new WorkspaceConfig();
            // Existing Theory profiles already use this output; new repositories can configure pdfPath explicitly.
            foreach (var repo in (workspace.Projects ?? new()).SelectMany(project => project.Repositories ?? new()))
                if (repo.RunLabel == "Open PDF" && repo.PdfPath == null) repo.PdfPath = "build/main.pdf";
            ConfigureMathPdfActions(workspace);
            DiscoverProjectRepositories(workspace);
            return true;
        }
        catch (Exception ex)
        {
            error = ex.Message;
            return false;
        }
    }

    private static void ConfigureMathPdfActions(WorkspaceConfig workspace)
    {
        // Upgrade existing desktop profiles in memory without rewriting machine-specific JSON or changing VS Code actions.
        foreach (var project in workspace.Projects ?? new())
        foreach (var repo in project.Repositories ?? new())
        {
            if (repo.Id != "math" || repo.RunTask != "Math - Open in VS Code") continue;
            repo.PdfDirectory ??= "build/pdf";
            repo.PdfOpenTask ??= "Math - Open PDF";
            repo.BuildTask ??= "Math - Build PDFs";
            repo.RunLabel = "Open in VS Code";
            repo.RequiredTools ??= new();
            foreach (var tool in new[] { "latexmk", "pdflatex", "python" })
                if (!repo.RequiredTools.Contains(tool, StringComparer.OrdinalIgnoreCase)) repo.RequiredTools.Add(tool);
            project.Tasks ??= new();
            project.Tasks.TryAdd("Math - Build PDFs", new WorkspaceTask { Shell = "pwsh", Cwd = repo.Path, Group = "Build",
                Steps = new() { new() { Run = "& './BUILD_ALL.ps1' -FailFast" } } });
            // Routed by the UI into the PDF collection, never a shell command.
            project.Tasks.TryAdd(repo.PdfOpenTask, new WorkspaceTask { Cwd = repo.Path, Group = "Browse", Steps = new() });
            project.QuickTasks ??= new();
            foreach (var name in new[] { "Math - Build PDFs", repo.PdfOpenTask })
                if (!project.QuickTasks.Contains(name)) project.QuickTasks.Add(name);
        }
    }

    private static void DiscoverProjectRepositories(WorkspaceConfig workspace)
    {
        foreach (var project in workspace.Projects ?? new())
        {
            if (project.Repositories?.Count > 0 || string.IsNullOrWhiteSpace(project.Root)) continue;
            var root = project.Root;
            var variables = new Dictionary<string, string>(workspace.Globals?.Vars ?? new());
            foreach (var pair in project.Vars ?? new()) variables[pair.Key] = pair.Value;
            foreach (var pair in variables) root = root.Replace("${vars." + pair.Key + "}", pair.Value);
            if (!Path.IsPathFullyQualified(root) || !Directory.Exists(root)) continue;
            try
            {
                for (var directory = new DirectoryInfo(root); directory != null; directory = directory.Parent)
                {
                    var marker = Path.Combine(directory.FullName, ".git");
                    if (!Directory.Exists(marker) && !File.Exists(marker)) continue;
                    project.Repositories = new() { new WorkspaceRepository { Id = "project-root", Name = directory.Name, Path = directory.FullName } };
                    break;
                }
            }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
        }
    }
}
