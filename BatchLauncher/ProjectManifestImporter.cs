using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.Json.Serialization;
using System.Text.RegularExpressions;

namespace BatchLauncher;

internal sealed record ProjectManifestPreview(string ManifestPath, WorkspaceProject? Project, List<string> Errors, List<string> Warnings,
    string Mode = "import", string? TargetProjectId = null, List<string>? Changes = null);

internal static class ProjectManifestImporter
{
    private static readonly JsonSerializerOptions Options = new() { PropertyNameCaseInsensitive = true, UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow };
    private static readonly Regex IdPattern = new("^[a-zA-Z][a-zA-Z0-9._-]*$", RegexOptions.Compiled);

    public static ProjectManifestPreview Preview(string manifestPath, IEnumerable<string> existingIds)
    {
        var errors = new List<string>();
        var warnings = new List<string>();
        WorkspaceProject? project = null;
        var fullPath = Path.GetFullPath(manifestPath);
        if (!File.Exists(fullPath)) return new(fullPath, null, new() { $"Manifest not found: {fullPath}" }, warnings);
        if (!Path.GetFileName(fullPath).Equals("devshell.project.json", StringComparison.OrdinalIgnoreCase))
            return new(fullPath, null, new() { "Choose a file named devshell.project.json." }, warnings);

        try
        {
            using var document = JsonDocument.Parse(File.ReadAllText(fullPath));
            var root = document.RootElement;
            if (root.ValueKind == JsonValueKind.Object)
                foreach (var property in root.EnumerateObject())
                    if (property.Name is not ("version" or "project" or "$schema")) errors.Add($"Unknown manifest field '{property.Name}'.");
            if (root.ValueKind != JsonValueKind.Object || !root.TryGetProperty("version", out var version) || version.ValueKind != JsonValueKind.Number || version.GetInt32() != 1)
                errors.Add("Manifest version must be 1.");
            if (!root.TryGetProperty("project", out var projectElement) || projectElement.ValueKind != JsonValueKind.Object)
                errors.Add("Manifest must contain a project object.");
            else project = projectElement.Deserialize<WorkspaceProject>(Options);
            if (project != null)
            {
                if (string.IsNullOrWhiteSpace(project.Id) || !IdPattern.IsMatch(project.Id)) errors.Add("project.id must start with a letter and contain only letters, numbers, dots, underscores, or hyphens.");
                if (string.IsNullOrWhiteSpace(project.Name)) errors.Add("project.name is required.");
                if (project.ManifestSource != null || project.ManifestOverrides != null)
                    errors.Add("manifestSource and manifestOverrides belong in the local profile, not in a shared manifest.");
                if (existingIds.Contains(project.Id, StringComparer.OrdinalIgnoreCase)) errors.Add($"A project with id '{project.Id}' already exists in this profile.");
                var sourceDir = Path.GetDirectoryName(fullPath)!;
                var projectRoot = ResolvePath(project.Root ?? ".", sourceDir, "project.root", errors);
                if (projectRoot != null)
                {
                    project.Root = projectRoot;
                    if (!Directory.Exists(projectRoot)) warnings.Add($"Project folder does not exist: {projectRoot}");
                    foreach (var repo in project.Repositories ?? new())
                    {
                        if (string.IsNullOrWhiteSpace(repo.Id) || !IdPattern.IsMatch(repo.Id)) errors.Add("Each repository needs a valid id.");
                        if (string.IsNullOrWhiteSpace(repo.Name)) errors.Add($"Repository '{repo.Id}' needs a name.");
                        if (repo.PythonEnvironment != null) errors.Add($"Repository '{repo.Id}' pythonEnvironment belongs in the local profile, not in a shared manifest.");
                        repo.Path = ResolvePath(repo.Path, projectRoot, $"repository '{repo.Id}' path", errors) ?? repo.Path;
                        if (!Directory.Exists(repo.Path)) warnings.Add($"Repository folder does not exist: {repo.Path}");
                        ValidateRepositoryPath(repo.PythonRequirements, repo.Path, $"repository '{repo.Id}' pythonRequirements", errors);
                        ValidateRepositoryPath(repo.OutputDirectory, repo.Path, $"repository '{repo.Id}' outputDirectory", errors);
                        ValidateRepositoryPath(repo.PdfPath, repo.Path, $"repository '{repo.Id}' pdfPath", errors);
                        ValidateRepositoryPath(repo.PdfDirectory, repo.Path, $"repository '{repo.Id}' pdfDirectory", errors);
                        foreach (var folder in repo.DependencyFolders ?? new()) ValidateRepositoryPath(folder, repo.Path, $"repository '{repo.Id}' dependencyFolders", errors);
                        CheckTaskReference(repo.BuildTask, project, $"repository '{repo.Id}' buildTask", errors);
                        CheckTaskReference(repo.RunTask, project, $"repository '{repo.Id}' runTask", errors);
                        CheckTaskReference(repo.BrowserBuildTask, project, $"repository '{repo.Id}' browserBuildTask", errors);
                        CheckTaskReference(repo.BrowserRunTask, project, $"repository '{repo.Id}' browserRunTask", errors);
                        CheckUrl(repo.BrowserUrl, $"repository '{repo.Id}' browserUrl", errors, warnings);
                        foreach (var url in repo.ReadyUrls ?? new()) CheckUrl(url, $"repository '{repo.Id}' readyUrls", errors, warnings);
                    }
                    foreach (var duplicate in (project.Repositories ?? new()).GroupBy(repo => repo.Id, StringComparer.OrdinalIgnoreCase).Where(group => group.Count() > 1))
                        errors.Add($"Repository id '{duplicate.Key}' is duplicated.");
                    if (project.Service?.Cwd is { } serviceCwd) project.Service.Cwd = ResolvePath(serviceCwd, projectRoot, "service.cwd", errors) ?? serviceCwd;
                    if (project.Service?.Kind is { } kind && kind is not ("process" or "jupyter")) errors.Add("service.kind must be process or jupyter.");
                    CheckUrl(project.Service?.ReadyUrl, "service.readyUrl", errors, warnings);
                    CheckUrl(project.Service?.OpenUrl, "service.openUrl", errors, warnings);
                    if (project.Tasks != null)
                    foreach (var (name, task) in project.Tasks)
                    {
                        if (string.IsNullOrWhiteSpace(name)) errors.Add("Task names cannot be empty.");
                        if (task.Cwd is { } cwd) task.Cwd = ResolvePath(cwd, projectRoot, $"task '{name}' cwd", errors) ?? cwd;
                        foreach (var dependency in task.DependsOn ?? new()) CheckTaskReference(dependency, project, $"task '{name}' dependency", errors);
                        if (task.UseTemplate != null) warnings.Add($"Task '{name}' uses a profile template; check that it exists after import.");
                        CheckUrl(task.Url, $"task '{name}' url", errors, warnings);
                    }
                    CheckLayout(project.Layout, project, projectRoot, errors);
                    CheckTaskCycles(project, errors);
                }
                foreach (var taskName in project.QuickTasks ?? new()) CheckTaskReference(taskName, project, "quickTasks", errors);
                if (project.PythonEnvironment != null || project.Service?.Python is { Length: > 0 })
                    errors.Add("Machine-specific Python paths belong in the profile after import, not in a shared manifest.");
            }
        }
        catch (Exception error) when (error is JsonException or IOException or UnauthorizedAccessException or ArgumentException or InvalidOperationException or FormatException or OverflowException)
        {
            errors.Add($"Could not read manifest: {error.Message}");
        }
        return new(fullPath, project, errors, warnings);
    }

    public static WorkspaceProject ImportIntoProfile(string profilePath, string manifestPath)
    {
        var config = JsonNode.Parse(File.ReadAllText(profilePath))?.AsObject()
            ?? throw new InvalidOperationException("The active profile is not a JSON object.");
        var projects = config["projects"] as JsonArray;
        if (config["projects"] != null && projects == null)
            throw new InvalidOperationException("The active profile's projects field must be an array.");
        var existingIds = projects?.Select(item => item?["id"]?.GetValue<string>() ?? "") ?? Enumerable.Empty<string>();
        var preview = Preview(manifestPath, existingIds);
        if (preview.Errors.Count > 0 || preview.Project == null)
            throw new InvalidOperationException(string.Join(Environment.NewLine, preview.Errors));
        if (projects == null) { projects = new JsonArray(); config["projects"] = projects; }
        preview.Project.ManifestSource = preview.ManifestPath;
        // An imported Jupyter workspace needs a machine-local interpreter path before
        // Setup / Fix can create its environment and the service can start from it.
        var defaults = new WorkspaceManifestOverrides();
        if (preview.Project.Service?.Kind == "jupyter")
            defaults.PythonEnvironment = Path.Combine(preview.Project.Root!, ".venv");
        var overrideErrors = new List<string>();
        ApplyOverrides(preview.Project, preview.ManifestPath, defaults, overrideErrors);
        if (overrideErrors.Count > 0) throw new InvalidOperationException(string.Join(Environment.NewLine, overrideErrors));
        projects.Add(JsonSerializer.SerializeToNode(preview.Project, new JsonSerializerOptions { PropertyNamingPolicy = JsonNamingPolicy.CamelCase }));
        var temp = profilePath + ".import-" + Guid.NewGuid().ToString("N") + ".tmp";
        try
        {
            File.WriteAllText(temp, config.ToJsonString(new JsonSerializerOptions { WriteIndented = true }) + Environment.NewLine);
            File.Move(temp, profilePath, true);
        }
        finally { if (File.Exists(temp)) File.Delete(temp); }
        return preview.Project;
    }

    public static ProjectManifestPreview PreviewRefresh(string profilePath, string projectId)
    {
        var (_, _, existing) = ReadManagedProject(profilePath, projectId);
        var preview = Preview(existing.ManifestSource!, Array.Empty<string>());
        var errors = new List<string>(preview.Errors);
        var candidate = preview.Project;
        if (candidate != null)
        {
            if (!candidate.Id.Equals(projectId, StringComparison.OrdinalIgnoreCase)) errors.Add($"Source project id changed from '{projectId}' to '{candidate.Id}'.");
            ApplyOverrides(candidate, existing.ManifestSource!, existing.ManifestOverrides ?? new(), errors);
        }
        return new(preview.ManifestPath, candidate, errors, preview.Warnings, "refresh", projectId,
            candidate == null || errors.Count > 0 ? new() : DescribeChanges(existing, candidate));
    }

    public static WorkspaceProject RefreshInProfile(string profilePath, string projectId)
    {
        var preview = PreviewRefresh(profilePath, projectId);
        if (preview.Errors.Count > 0 || preview.Project == null)
            throw new InvalidOperationException(string.Join(Environment.NewLine, preview.Errors));
        ReplaceManagedProject(profilePath, projectId, preview.Project);
        return preview.Project;
    }

    public static WorkspaceProject SaveOverrides(string profilePath, string projectId, WorkspaceManifestOverrides overrides)
    {
        var (_, _, existing) = ReadManagedProject(profilePath, projectId);
        var source = Preview(existing.ManifestSource!, Array.Empty<string>());
        var errors = new List<string>(source.Errors);
        var candidate = source.Project;
        if (candidate == null) throw new InvalidOperationException(string.Join(Environment.NewLine, errors));
        if (!candidate.Id.Equals(projectId, StringComparison.OrdinalIgnoreCase)) errors.Add($"Source project id changed from '{projectId}' to '{candidate.Id}'.");
        ApplyOverrides(candidate, existing.ManifestSource!, existing.ManifestOverrides ?? new(), errors);
        if (errors.Count == 0 && DescribeChanges(existing, candidate).Count > 0)
            errors.Add("Source manifest changed. Preview and apply Refresh before saving local settings.");
        if (errors.Count > 0) throw new InvalidOperationException(string.Join(Environment.NewLine, errors));
        // Build a fresh copy because applying the previous overrides changed the first candidate.
        candidate = Preview(existing.ManifestSource!, Array.Empty<string>()).Project!;
        ApplyOverrides(candidate, existing.ManifestSource!, overrides, errors);
        if (errors.Count > 0) throw new InvalidOperationException(string.Join(Environment.NewLine, errors));
        ReplaceManagedProject(profilePath, projectId, candidate);
        return candidate;
    }

    private static (JsonObject Config, JsonArray Projects, WorkspaceProject Existing) ReadManagedProject(string profilePath, string projectId)
    {
        var config = JsonNode.Parse(File.ReadAllText(profilePath))?.AsObject()
            ?? throw new InvalidOperationException("The active profile is not a JSON object.");
        var projects = config["projects"] as JsonArray
            ?? throw new InvalidOperationException("The active profile has no projects array.");
        var node = projects.FirstOrDefault(item => item?["id"]?.GetValue<string>()?.Equals(projectId, StringComparison.OrdinalIgnoreCase) == true)
            ?? throw new InvalidOperationException($"Project '{projectId}' was not found in this profile.");
        var existing = node.Deserialize<WorkspaceProject>(new JsonSerializerOptions { PropertyNameCaseInsensitive = true })
            ?? throw new InvalidOperationException("Project could not be read.");
        if (string.IsNullOrWhiteSpace(existing.ManifestSource)) throw new InvalidOperationException("This project was not imported from a manifest.");
        return (config, projects, existing);
    }

    private static void ReplaceManagedProject(string profilePath, string projectId, WorkspaceProject project)
    {
        var (config, projects, _) = ReadManagedProject(profilePath, projectId);
        var index = -1;
        for (var i = 0; i < projects.Count; i++)
            if (projects[i]?["id"]?.GetValue<string>()?.Equals(projectId, StringComparison.OrdinalIgnoreCase) == true) { index = i; break; }
        if (index < 0) throw new InvalidOperationException("Project disappeared before refresh.");
        projects[index] = JsonSerializer.SerializeToNode(project, new JsonSerializerOptions { PropertyNamingPolicy = JsonNamingPolicy.CamelCase });
        WriteProfile(profilePath, config);
    }

    private static void ApplyOverrides(WorkspaceProject candidate, string manifestPath, WorkspaceManifestOverrides overrides, List<string> errors)
    {
        var sourceRoot = candidate.Root ?? Path.GetDirectoryName(manifestPath)!;
        var root = NormalizeLocalPath(overrides.Root, "Project root", errors);
        var python = NormalizeLocalPath(overrides.PythonEnvironment, "Python environment", errors);
        var servicePython = NormalizeLocalPath(overrides.ServicePython, "Jupyter Python", errors);
        if (servicePython != null && candidate.Service?.Kind != "jupyter")
            errors.Add("Jupyter Python override requires a Jupyter service in the manifest.");
        var repositoryPython = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var pair in overrides.RepositoryPythonEnvironments ?? new())
        {
            if (candidate.Repositories?.Any(repo => repo.Id.Equals(pair.Key, StringComparison.OrdinalIgnoreCase)) != true)
                errors.Add($"Repository Python override references unknown id '{pair.Key}'.");
            var path = NormalizeLocalPath(pair.Value, $"Repository '{pair.Key}' Python environment", errors);
            if (path != null) repositoryPython[pair.Key] = path;
        }
        if (errors.Count > 0) return;
        candidate.ManifestSource = manifestPath;
        candidate.ManifestOverrides = new WorkspaceManifestOverrides
        {
            Root = root,
            PythonEnvironment = python,
            ServicePython = servicePython,
            RepositoryPythonEnvironments = repositoryPython.Count == 0 ? null : repositoryPython
        };
        if (root != null)
        {
            candidate.Root = root;
            foreach (var repo in candidate.Repositories ?? new()) repo.Path = RebasePath(sourceRoot, root, repo.Path);
            if (candidate.Service?.Cwd is { } serviceCwd) candidate.Service.Cwd = RebasePath(sourceRoot, root, serviceCwd);
            foreach (var task in candidate.Tasks?.Values ?? Enumerable.Empty<WorkspaceTask>())
                if (task.Cwd is { } cwd) task.Cwd = RebasePath(sourceRoot, root, cwd);
            if (candidate.Layout != null) RebaseLayout(candidate.Layout, sourceRoot, root);
        }
        candidate.PythonEnvironment = python;
        if (candidate.Service?.Kind == "jupyter") candidate.Service.Python = servicePython ?? (python == null ? "" : Path.Combine(python, "Scripts", "python.exe"));
        foreach (var repo in candidate.Repositories ?? new())
            repo.PythonEnvironment = repositoryPython.GetValueOrDefault(repo.Id) ?? python;
    }

    private static string? NormalizeLocalPath(string? value, string label, List<string> errors)
    {
        if (string.IsNullOrWhiteSpace(value)) return null;
        if (!Path.IsPathFullyQualified(value)) { errors.Add($"{label} must be an absolute path on this computer."); return null; }
        return Path.TrimEndingDirectorySeparator(Path.GetFullPath(value));
    }

    private static string RebasePath(string sourceRoot, string targetRoot, string value) =>
        Path.GetFullPath(Path.Combine(targetRoot, Path.GetRelativePath(sourceRoot, value)));

    private static void RebaseLayout(ProjectLayout layout, string sourceRoot, string targetRoot)
    {
        foreach (var item in layout.Items ?? new()) if (item.Cwd is { } cwd) item.Cwd = RebasePath(sourceRoot, targetRoot, cwd);
        foreach (var pane in layout.Panes ?? new()) RebaseLayout(pane, sourceRoot, targetRoot);
    }

    private static List<string> DescribeChanges(WorkspaceProject existing, WorkspaceProject candidate)
    {
        var changes = new List<string>();
        void AddIfChanged(string label, object? before, object? after)
        {
            if (JsonSerializer.Serialize(before) != JsonSerializer.Serialize(after)) changes.Add(label + " changed");
        }
        if (existing.Name != candidate.Name) changes.Add($"Name: {existing.Name} → {candidate.Name}");
        AddIfChanged("Root", existing.Root, candidate.Root);
        AddIfChanged("Pinned", existing.Pinned, candidate.Pinned);
        var oldRepos = (existing.Repositories ?? new()).GroupBy(repo => repo.Id, StringComparer.OrdinalIgnoreCase).ToDictionary(group => group.Key, group => group.First(), StringComparer.OrdinalIgnoreCase);
        var newRepos = (candidate.Repositories ?? new()).GroupBy(repo => repo.Id, StringComparer.OrdinalIgnoreCase).ToDictionary(group => group.Key, group => group.First(), StringComparer.OrdinalIgnoreCase);
        foreach (var id in newRepos.Keys.Except(oldRepos.Keys, StringComparer.OrdinalIgnoreCase)) changes.Add($"Repository '{id}' added");
        foreach (var id in oldRepos.Keys.Except(newRepos.Keys, StringComparer.OrdinalIgnoreCase)) changes.Add($"Repository '{id}' removed");
        foreach (var id in oldRepos.Keys.Intersect(newRepos.Keys, StringComparer.OrdinalIgnoreCase))
            if (JsonSerializer.Serialize(oldRepos[id]) != JsonSerializer.Serialize(newRepos[id])) changes.Add($"Repository '{id}' changed");
        var oldTasks = existing.Tasks ?? new();
        var newTasks = candidate.Tasks ?? new();
        foreach (var name in newTasks.Keys.Except(oldTasks.Keys)) changes.Add($"Task '{name}' added");
        foreach (var name in oldTasks.Keys.Except(newTasks.Keys)) changes.Add($"Task '{name}' removed");
        foreach (var name in oldTasks.Keys.Intersect(newTasks.Keys))
            if (JsonSerializer.Serialize(oldTasks[name]) != JsonSerializer.Serialize(newTasks[name])) changes.Add($"Task '{name}' changed");
        AddIfChanged("Quick tasks", existing.QuickTasks, candidate.QuickTasks);
        AddIfChanged("Service", existing.Service, candidate.Service);
        AddIfChanged("Layout", existing.Layout, candidate.Layout);
        AddIfChanged("Required tools", existing.RequiredTools, candidate.RequiredTools);
        AddIfChanged("Python requirements", new { existing.PythonModules, existing.PythonPackages }, new { candidate.PythonModules, candidate.PythonPackages });
        AddIfChanged("Variables", existing.Vars, candidate.Vars);
        AddIfChanged("Bootstrap", existing.Bootstrap, candidate.Bootstrap);
        return changes;
    }

    private static void WriteProfile(string profilePath, JsonObject config)
    {
        var temp = profilePath + ".import-" + Guid.NewGuid().ToString("N") + ".tmp";
        try
        {
            File.WriteAllText(temp, config.ToJsonString(new JsonSerializerOptions { WriteIndented = true }) + Environment.NewLine);
            File.Move(temp, profilePath, true);
        }
        finally { if (File.Exists(temp)) File.Delete(temp); }
    }

    private static string? ResolvePath(string value, string basePath, string label, List<string> errors)
    {
        if (string.IsNullOrWhiteSpace(value)) { errors.Add($"{label} is required."); return null; }
        if (Path.IsPathRooted(value) || value.Contains("${", StringComparison.Ordinal))
        { errors.Add($"{label} must be relative to the manifest or project folder."); return null; }
        var full = Path.GetFullPath(Path.Combine(basePath, value));
        var relative = Path.GetRelativePath(basePath, full);
        if (relative == ".." || relative.StartsWith(".." + Path.DirectorySeparatorChar, StringComparison.Ordinal) || Path.IsPathFullyQualified(relative))
        { errors.Add($"{label} must stay inside its parent folder."); return null; }
        return full;
    }

    private static void CheckTaskReference(string? name, WorkspaceProject project, string label, List<string> errors)
    {
        if (!string.IsNullOrWhiteSpace(name) && project.Tasks?.ContainsKey(name) != true)
            errors.Add($"{label} references missing task '{name}'.");
    }

    private static void ValidateRepositoryPath(string? value, string basePath, string label, List<string> errors)
    {
        if (value != null) _ = ResolvePath(value, basePath, label, errors);
    }

    private static void CheckLayout(ProjectLayout? layout, WorkspaceProject project, string projectRoot, List<string> errors)
    {
        if (layout == null) return;
        if (layout.Type != "tabs" && layout.Type != "split") errors.Add("layout.type must be tabs or split.");
        foreach (var item in layout.Items ?? new())
        {
            CheckTaskReference(item.TaskId, project, $"layout item '{item.Title}'", errors);
            if (item.Cwd is { } cwd) item.Cwd = ResolvePath(cwd, projectRoot, $"layout item '{item.Title}' cwd", errors) ?? cwd;
        }
        foreach (var pane in layout.Panes ?? new()) CheckLayout(pane, project, projectRoot, errors);
    }

    private static void CheckUrl(string? value, string label, List<string> errors, List<string> warnings)
    {
        if (string.IsNullOrWhiteSpace(value)) return;
        if (!Uri.TryCreate(value, UriKind.Absolute, out var uri) || (uri.Scheme != "http" && uri.Scheme != "https"))
        { errors.Add($"{label} must be an absolute HTTP or HTTPS URL."); return; }
        if (uri.UserInfo.Length > 0) errors.Add($"{label} must not contain credentials.");
        if (uri.Query.Length > 0 || uri.Fragment.Length > 0)
            warnings.Add($"{label} contains a query or fragment. Remove tokens and secrets before sharing this manifest.");
    }

    private static void CheckTaskCycles(WorkspaceProject project, List<string> errors)
    {
        if (project.Tasks == null) return;
        var visited = new HashSet<string>(StringComparer.Ordinal);
        var active = new HashSet<string>(StringComparer.Ordinal);
        void Visit(string name)
        {
            if (!project.Tasks.ContainsKey(name) || visited.Contains(name)) return;
            if (!active.Add(name)) { errors.Add($"Task dependency cycle includes '{name}'."); return; }
            foreach (var dependency in project.Tasks[name].DependsOn ?? new()) Visit(dependency);
            active.Remove(name);
            visited.Add(name);
        }
        foreach (var name in project.Tasks.Keys) Visit(name);
    }
}
