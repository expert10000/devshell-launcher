using System.Text.Json;

namespace BatchLauncher;

public sealed record EnvironmentSetupStep(string Name, string Kind, string Directory, string? Tool = null, List<string>? Arguments = null,
    string? Environment = null, string? Manager = null, string? ManagerVersion = null, int MinimumMajor = 0, string? Target = null, string? NodeRange = null);
public sealed record EnvironmentSetupPlan(string Root, Dictionary<string, string> Tools, List<EnvironmentSetupStep> Steps, List<string> Issues)
{
    public List<string> Targets { get; init; } = new();
}

public static class EnvironmentSetup
{
    public static readonly HashSet<string> InstallableTools = new(StringComparer.OrdinalIgnoreCase) { "node", "npm", "python", "dotnet", "git", "pwsh", "code" };
    public static string Within(string root, string relative)
    {
        var fullRoot = Path.TrimEndingDirectorySeparator(Path.GetFullPath(root));
        var full = Path.GetFullPath(Path.Combine(fullRoot, relative));
        if (!full.Equals(fullRoot, StringComparison.OrdinalIgnoreCase) && !full.StartsWith(fullRoot + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("Dependency paths must stay inside the repository: " + relative);
        return full;
    }
    public static EnvironmentSetupPlan Plan(WorkspaceRepository repo, string workspaceRoot, Dictionary<string, string> tools, string? basePython = null, IReadOnlyCollection<string>? targets = null)
    {
        var root = Path.GetFullPath(repo.Path);
        if (!Directory.Exists(root)) throw new InvalidOperationException("Clone the repository before setting up its environment.");
        var steps = new List<EnvironmentSetupStep>();
        var issues = new List<string>();
        var needed = new HashSet<string>(targets == null ? repo.RequiredTools ?? new() : new(), StringComparer.OrdinalIgnoreCase);
        var knownTargets = new HashSet<string>();
        bool Selected(string target) => targets == null || targets.Contains(target);
        var dependencies = new[] { "." }.Concat(repo.DependencyFolders ?? new()).Select(folder => Within(root, folder)).Distinct(StringComparer.OrdinalIgnoreCase);
        foreach (var directory in dependencies)
        {
            var relative = Path.GetRelativePath(root, directory);
            if (!Directory.Exists(directory)) { if (targets == null) issues.Add("Dependency folder is missing: " + directory); continue; }
            var manifest = Path.Combine(directory, "package.json");
            if (File.Exists(manifest))
            {
                var target = "node:" + relative; knownTargets.Add(target);
                if (Selected(target))
                {
                    needed.Add("node");
                    var manifestInfo = NodeDependencies.Read(directory);
                    var manager = manifestInfo.Manager; var version = manifestInfo.ManagerVersion;
                    var minimumMajor = 0;
                    var minimum = System.Text.RegularExpressions.Regex.Match(manifestInfo.NodeRange ?? "", @">=\s*(\d+)");
                    if (minimum.Success) minimumMajor = int.Parse(minimum.Groups[1].Value);
                    var arguments = manager == "npm" ? new List<string> { File.Exists(Path.Combine(directory, "package-lock.json")) ? "ci" : "install", "--no-audit", "--no-fund" }
                        : manager == "yarn" ? new List<string> { "install", version?.StartsWith("1.") == false ? "--immutable" : "--frozen-lockfile" }
                        : new List<string> { "install", "--frozen-lockfile" };
                    steps.Add(new("Install " + manager + " dependencies · " + relative, "node", directory, Arguments: arguments, Manager: manager, ManagerVersion: version, MinimumMajor: minimumMajor, Target: target, NodeRange: manifestInfo.NodeRange));
                }
            }
            var projects = Directory.EnumerateFiles(directory, "*.csproj").ToArray();
            var restoreFiles = projects.Length > 0 ? projects : Directory.EnumerateFiles(directory, "*.sln*").ToArray();
            foreach (var project in restoreFiles)
            {
                var target = "dotnet:" + relative; knownTargets.Add(target);
                if (!Selected(target)) continue;
                needed.Add("dotnet");
                steps.Add(new("Restore " + Path.GetFileName(project), "command", directory, "dotnet", new() { "restore", project, "--nologo" }, MinimumMajor: RepositoryEnvironment.DotnetMinimum(directory), Target: target));
            }
        }
        var requirements = repo.PythonRequirements != null ? Within(root, repo.PythonRequirements) : Path.Combine(root, "requirements.txt");
        if (Selected("python") && repo.PythonRequirements != null && !File.Exists(requirements)) issues.Add("Python requirements file is missing: " + requirements);
        if (repo.PythonEnvironment != null || repo.PythonPackages?.Count > 0 || File.Exists(requirements))
        {
            knownTargets.Add("python");
            if (Selected("python"))
            {
                needed.Add("python");
                var environment = Path.GetFullPath(repo.PythonEnvironment ?? Path.Combine(root, ".venv"));
                if (Path.GetFileName(environment).Equals("python.exe", StringComparison.OrdinalIgnoreCase))
                {
                    environment = Path.GetDirectoryName(environment)!;
                    if (Path.GetFileName(environment).Equals("Scripts", StringComparison.OrdinalIgnoreCase)) environment = Path.GetDirectoryName(environment)!;
                }
                if (File.Exists(environment)) throw new InvalidOperationException("Choose a Python environment folder, not a file.");
                if ((File.Exists(Path.Combine(environment, "python.exe")) || File.Exists(Path.Combine(environment, "Scripts", "python.exe")))
                    && !File.Exists(Path.Combine(environment, "pyvenv.cfg")) && !Directory.Exists(Path.Combine(environment, "conda-meta")))
                    throw new InvalidOperationException("Choose a dedicated virtual or Conda environment; repairing a base Python installation is not supported.");
                if (environment.Equals(root, StringComparison.OrdinalIgnoreCase) || environment.Equals(Path.GetFullPath(workspaceRoot), StringComparison.OrdinalIgnoreCase)
                    || environment == Path.GetPathRoot(environment)) throw new InvalidOperationException("Choose a dedicated Python environment folder.");
                steps.Add(new("Create or reuse Python environment", "python-create", root, Environment: environment, Target: "python"));
                var arguments = new List<string> { "-m", "pip", "install", "--disable-pip-version-check" };
                if (File.Exists(requirements)) { arguments.Add("-r"); arguments.Add(requirements); }
                foreach (var package in repo.PythonPackages ?? new())
                {
                    if (package.StartsWith('-')) throw new InvalidOperationException("Python package entries must be package requirements, not pip options.");
                    arguments.Add(package);
                }
                if (arguments.Count > 4) steps.Add(new("Install Python dependencies", "python-install", root, Arguments: arguments, Environment: environment, Target: "python"));
                if (repo.PythonModules?.Count > 0)
                    steps.Add(new("Verify Python imports", "python-install", root, Arguments: new() { "-c", "import importlib,json,sys; [importlib.import_module(m) for m in json.loads(sys.argv[1])]; print('Python modules ready')", JsonSerializer.Serialize(repo.PythonModules) }, Environment: environment, Target: "python"));
            }
        }
        var discovered = new Dictionary<string, string>(tools, StringComparer.OrdinalIgnoreCase);
        if (basePython != null && File.Exists(basePython)) discovered["python"] = basePython;
        foreach (var tool in repo.RequiredTools ?? new())
        {
            if (!InstallableTools.Contains(tool)) continue;
            knownTargets.Add("tool:" + tool);
            if (targets?.Contains("tool:" + tool) == true) needed.Add(tool);
        }
        foreach (var tool in needed) if (InstallableTools.Contains(tool)) knownTargets.Add("tool:" + tool);
        if (targets != null && targets.Any(target => !knownTargets.Contains(target))) throw new InvalidOperationException("This repair target is not declared by the repository.");
        foreach (var tool in needed)
        {
            if (discovered.ContainsKey(tool) || DashboardInspector.FindTool(tool) != null) continue;
            if (InstallableTools.Contains(tool)) steps.Insert(0, new("Install missing " + tool, "tool", root, tool, Target: "tool:" + tool));
            else issues.Add("Install or configure this tool manually: " + tool);
        }
        if (steps.Count == 0 && issues.Count == 0) steps.Add(new("Environment already prepared", "note", root));
        return new(workspaceRoot, discovered, steps, issues) { Targets = targets?.ToList() ?? steps.Where(step => step.Target != null).Select(step => step.Target!).Distinct().ToList() };
    }
    public static RepositoryCommand Command(string shell, string helper, EnvironmentSetupPlan plan, string workingDirectory)
    {
        if (plan.Issues.Count > 0) throw new InvalidOperationException(string.Join("\n", plan.Issues));
        if (!File.Exists(helper)) throw new FileNotFoundException("Environment setup helper is missing.", helper);
        string Quote(string value) => "'" + value.Replace("'", "''") + "'";
        var json = JsonSerializer.Serialize(plan, new JsonSerializerOptions { PropertyNamingPolicy = JsonNamingPolicy.CamelCase });
        return new(shell, "$ErrorActionPreference='Stop'; try { & " + Quote(helper) + " -PlanJson " + Quote(json) + "; exit 0 } catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 }", workingDirectory);
    }
}
