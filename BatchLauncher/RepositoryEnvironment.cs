using System.Text.Json;
using System.Text.RegularExpressions;
using System.Xml.Linq;

namespace BatchLauncher;

public static class RepositoryEnvironment
{
    public static async Task<List<HealthCheck>> InspectRepository(string projectId, string repositoryId, WorkspaceRepository repo,
        IReadOnlyDictionary<string, string>? toolPaths = null)
    {
        var checks = await Inspect(projectId, repositoryId, repo.Path, repo.RequiredTools ?? new(), repo.PythonEnvironment,
            repo.PythonModules, toolPaths, repo.PythonRequirements, repo.PythonPackages, repo.PythonOptionalModules);
        foreach (var folder in (repo.DependencyFolders ?? new()).Distinct(StringComparer.OrdinalIgnoreCase))
        {
            try
            {
                var path = EnvironmentSetup.Within(repo.Path, folder);
                if (Path.GetFullPath(path).Equals(Path.GetFullPath(repo.Path), StringComparison.OrdinalIgnoreCase)) continue;
                if (!Directory.Exists(path))
                {
                    checks.Add(new("Dependency folder · " + folder, "error", "Missing " + path, projectId, repositoryId,
                        Guidance: "Restore this folder from the repository or correct dependencyFolders in the profile."));
                    continue;
                }
                checks.AddRange((await Inspect(projectId, repositoryId, path, Array.Empty<string>(), toolPaths: toolPaths,
                    repositoryRoot: repo.Path, relativeDirectory: Path.GetRelativePath(repo.Path, path))).Select(check => check with { Name = folder + " · " + check.Name }));
            }
            catch (Exception error) { checks.Add(new("Dependency folder · " + folder, "error", error.Message, projectId, repositoryId,
                Guidance: "Configure a dependency folder inside this repository.")); }
        }
        return checks;
    }

    public static async Task<List<HealthCheck>> Inspect(string projectId, string repositoryId, string path,
        IEnumerable<string> requiredTools, string? pythonEnvironment = null, List<string>? pythonModules = null,
        IReadOnlyDictionary<string, string>? toolPaths = null, string? requirementsFile = null,
        List<string>? pythonPackages = null, List<string>? pythonOptionalModules = null, string? repositoryRoot = null, string relativeDirectory = ".")
    {
        var checks = new List<HealthCheck>();
        void Add(string name, string state, string detail, string? target = null, string? label = null, string? guidance = null, bool optional = false) =>
            checks.Add(new(name, state, detail, projectId, repositoryId, target, label, guidance, optional));
        string? Tool(string name) => DashboardInspector.FindTool(toolPaths?.GetValueOrDefault(name) ?? name);
        var tools = new HashSet<string>(requiredTools, StringComparer.OrdinalIgnoreCase);
        if (!Directory.Exists(path)) { Add("Repository folder", "error", "Missing " + path, "clone", "Clone repository", "Clone this repository before installing dependencies."); return checks; }
        var nodeTarget = "node:" + relativeDirectory;
        try
        {
            var manifestPath = Path.Combine(path, "package.json");
            if (File.Exists(manifestPath))
            {
                try
                {
                    var manifest = NodeDependencies.Read(path);
                    tools.Add("node");
                    var node = Tool("node");
                    var semver = NodeDependencies.Semver(toolPaths?.GetValueOrDefault("npmCli") ?? Tool("npm"), node);
                    if (node != null && manifest.NodeRange != null)
                    {
                        var version = await NodeDependencies.Version(node);
                        var found = version.Output.Trim().TrimStart('v');
                        var match = version.Code == 0 ? (await NodeDependencies.MatchVersions(node, semver, new() { (found, manifest.NodeRange) }))[0] : false;
                        Add("Node version", match == true ? "ok" : match == false ? "error" : "warning",
                            $"Installed {found}; required {manifest.NodeRange}." + (match == null ? " Version range could not be verified; install npm with its bundled version checker." : ""),
                            match == false ? nodeTarget : null, "Update Node.js");
                    }
                    var manager = NodeDependencies.ManagedTool(toolPaths?.GetValueOrDefault("workspaceRoot"), manifest.Manager, manifest.ManagerVersion) ?? Tool(manifest.Manager);
                    if (manager == null) Add("Package manager", "error", $"Missing {manifest.Manager}" + (manifest.ManagerVersion == null ? "." : " " + manifest.ManagerVersion + "."), nodeTarget, "Prepare " + manifest.Manager);
                    else if (manifest.ManagerVersion != null)
                    {
                        var version = await NodeDependencies.Version(manager, node);
                        var found = version.Output.Trim();
                        Add("Package manager", version.Code == 0 && found == manifest.ManagerVersion ? "ok" : "error",
                            $"{manifest.Manager}: installed {found}; required {manifest.ManagerVersion}.", nodeTarget, "Use declared " + manifest.Manager);
                    }
                    else Add("Package manager", "ok", manifest.Manager + " · " + manager);
                    var missing = new List<string>();
                    var installed = new List<(string Name, string Version, string Range)>();
                    foreach (var dependency in manifest.Packages)
                    {
                        var file = NodeDependencies.PackageFile(repositoryRoot ?? path, path, dependency.Key);
                        if (file == null) { missing.Add(dependency.Key); continue; }
                        using var json = JsonDocument.Parse(await File.ReadAllTextAsync(file));
                        if (json.RootElement.TryGetProperty("version", out var version)) installed.Add((dependency.Key, version.GetString() ?? "", dependency.Value));
                    }
                    var matches = await NodeDependencies.MatchVersions(node, semver, installed.Select(item => (item.Version, item.Range)).ToList());
                    var incompatible = installed.Where((_, index) => matches[index] == false).Select(item => item.Name + " " + item.Version + " (requires " + item.Range + ")").ToList();
                    var issues = new List<string>();
                    if (missing.Count > 0) issues.Add($"{missing.Count} missing: {string.Join(", ", missing.Take(10))}.");
                    if (incompatible.Count > 0) issues.Add("Incompatible: " + string.Join(", ", incompatible.Take(10)) + ".");
                    Add("Node packages", issues.Count == 0 ? "ok" : "error", issues.Count == 0
                        ? "Declared dependencies and development dependencies are installed." : string.Join("\n", issues), nodeTarget, "Install Node dependencies",
                        "Uses this folder's declared package manager and lockfile: " + path);
                    var unverified = installed.Where((_, index) => matches[index] == null).Select(item => item.Name).ToList();
                    if (unverified.Count > 0) Add("Node version verification", "warning", "Version ranges could not be verified for: " + string.Join(", ", unverified.Take(10)),
                        guidance: "Local, Git, and other non-registry dependencies need manual verification. Install npm if the version checker is unavailable.");
                }
                catch (Exception error) { Add("Node environment", "error", error.Message, guidance: "Correct the package manifest or configured executable path, then recheck."); }
            }
            if (Directory.EnumerateFiles(path, "*.csproj").Any() || Directory.EnumerateFiles(path, "*.sln*").Any())
            {
                tools.Add("dotnet");
                try
                {
                    var minimum = DotnetMinimum(path);
                    var dotnet = Tool("dotnet");
                    var sdks = dotnet == null ? (-1, "", "") : await DashboardInspector.Run(dotnet, new[] { "--list-sdks" });
                    var majors = Regex.Matches(sdks.Item2, @"(?m)^(\d+)\.").Select(match => int.Parse(match.Groups[1].Value));
                    var ready = sdks.Item1 == 0 && majors.Any(major => major >= minimum);
                    Add(".NET SDK", ready ? "ok" : "error", ready ? sdks.Item2.Trim() : $"A .NET SDK {minimum} or newer is required. A runtime alone cannot build this repository.",
                        "dotnet:" + relativeDirectory, "Install SDK / restore packages");
                    if (ready && dotnet != null)
                    {
                        var selected = await DashboardInspector.Run(dotnet, new[] { "--version" }, workingDirectory: path);
                        Add(".NET SDK selection", selected.Code == 0 ? "ok" : "error", selected.Code == 0 ? "Selected SDK " + selected.Output.Trim() : (selected.Output + selected.Error).Trim(),
                            guidance: selected.Code == 0 ? null : "Install the SDK selected by global.json or update that file's version/rollForward settings, then recheck.");
                    }
                    foreach (var project in Directory.EnumerateFiles(path, "*.csproj"))
                    {
                        var assets = Path.Combine(path, "obj", "project.assets.json");
                        var restored = File.Exists(assets);
                        var missing = new List<string>();
                        if (restored)
                        {
                            using var json = JsonDocument.Parse(await File.ReadAllTextAsync(assets));
                            if (json.RootElement.TryGetProperty("packageFolders", out var folders) && json.RootElement.TryGetProperty("libraries", out var libraries))
                                foreach (var package in libraries.EnumerateObject().Where(item => item.Value.GetProperty("type").GetString() == "package"))
                                {
                                    var relative = package.Value.GetProperty("path").GetString()!;
                                    if (!folders.EnumerateObject().Any(folder => Directory.Exists(Path.Combine(folder.Name, relative)))) missing.Add(package.Name);
                                }
                        }
                        Add(".NET packages · " + Path.GetFileName(project), restored && missing.Count == 0 ? "ok" : "error",
                            !restored ? "Restore has not produced project.assets.json." : missing.Count > 0 ? "Missing packages: " + string.Join(", ", missing.Take(10)) : "Restored NuGet packages are available.",
                            "dotnet:" + relativeDirectory, "Restore .NET packages");
                    }
                }
                catch (Exception error) { Add(".NET SDK", "error", error.Message, "dotnet:" + relativeDirectory, "Restore .NET environment"); }
            }
            var requirements = requirementsFile == null ? Path.Combine(path, "requirements.txt") : EnvironmentSetup.Within(path, requirementsFile);
            if (requirementsFile != null && !File.Exists(requirements)) Add("Python requirements file", "error", "Missing " + requirements,
                guidance: "Restore the requirements file or correct pythonRequirements in the profile.");
            var needsPython = pythonEnvironment != null || pythonModules?.Count > 0 || pythonPackages?.Count > 0 || File.Exists(requirements);
            if (needsPython)
            {
                var environment = pythonEnvironment ?? Path.Combine(path, ".venv");
                var python = File.Exists(environment) ? environment : File.Exists(Path.Combine(environment, "python.exe"))
                    ? Path.Combine(environment, "python.exe") : Path.Combine(environment, "Scripts", "python.exe");
                var canInstall = File.Exists(requirements) || pythonPackages?.Count > 0;
                if (!File.Exists(python)) Add("Python environment", "error", "Missing " + python, "python", "Create Python environment",
                    "Creates a dedicated environment and installs the declared Python dependencies.");
                else
                {
                    Add("Python environment", "ok", python);
                    try
                    {
                        var nativeEnvironment = PythonEnvironmentVariables(python);
                        const string importCheck = """
import importlib,json,sys
results=[]
for name in json.loads(sys.argv[1]):
    try:
        importlib.import_module(name)
        results.append({'name':name,'error':None})
    except Exception as error:
        results.append({'name':name,'error':type(error).__name__+': '+str(error)[:350]})
print(json.dumps(results))
""";
                        var required = pythonModules ?? new();
                        var optional = pythonOptionalModules ?? new();
                        var modules = required.Concat(optional).Distinct().ToList();
                        var result = await DashboardInspector.Run(python, new[] { "-c", importCheck, JsonSerializer.Serialize(modules) }, nativeEnvironment);
                        if (result.Code != 0) throw new InvalidOperationException("Python could not inspect modules: " + result.Error.Trim());
                        using var json = JsonDocument.Parse(result.Output);
                        var errors = json.RootElement.EnumerateArray().Where(item => item.GetProperty("error").ValueKind != JsonValueKind.Null)
                            .ToDictionary(item => item.GetProperty("name").GetString()!, item => item.GetProperty("error").GetString()!);
                        var missing = required.Where(errors.ContainsKey).ToList();
                        Add("Python modules", missing.Count == 0 ? "ok" : "error", missing.Count == 0 ? "Configured modules import successfully."
                            : string.Join("\n", missing.Select(module => module + " · " + errors[module])), canInstall ? "python" : null, "Install Python dependencies",
                            canInstall ? "Installs declared packages in this Python environment." : "Declare the installable packages in pythonPackages or pythonRequirements; module names alone are insufficient to choose packages.");
                        foreach (var module in optional)
                            Add("Optional Python module · " + module, errors.ContainsKey(module) ? "warning" : "ok", errors.GetValueOrDefault(module) ?? "Available",
                                guidance: "This enables additional native features. Follow the repository's native dependency instructions; it does not block the base environment.", optional: true);
                        if (File.Exists(requirements) || pythonPackages?.Count > 0)
                        {
                            result = await DashboardInspector.Run(python, new[] { "-c", RequirementCheck, File.Exists(requirements) ? requirements : "", JsonSerializer.Serialize(pythonPackages ?? new()), path }, nativeEnvironment);
                            Add("Python requirements", result.Code == 0 ? "ok" : result.Code == 2 ? "warning" : "error", (result.Output + result.Error).Trim(),
                                result.Code == 1 ? "python" : null, "Install Python dependencies",
                                result.Code == 2 ? "Review unsupported entries in the requirements file before treating this environment as fully verified." : "Checks installed package versions against declared requirements.");
                        }
                    }
                    catch (Exception error) { Add("Python inspection", "error", error.Message, canInstall ? "python" : null, "Repair Python dependencies"); }
                }
            }
            foreach (var tool in tools)
            {
                var resolved = Tool(tool);
                var target = tool == "node" && File.Exists(manifestPath) ? nodeTarget : EnvironmentSetup.InstallableTools.Contains(tool) ? "tool:" + tool : null;
                Add(tool, resolved == null ? "error" : "ok", resolved ?? "Missing " + tool, target, "Install " + tool,
                    resolved == null && target == null ? "Install this tool manually or update its configured path, then Detect tools and recheck." : null);
            }
            if (checks.Count == 0) Add("Environment", "ok", "No additional dependencies are declared for this repository.");
        }
        catch (Exception error) { Add("Environment check", "error", error.Message, guidance: "Correct the profile's dependency paths, then recheck."); }
        return checks;
    }

    public static int DotnetMinimum(string path)
    {
        var majors = Directory.EnumerateFiles(path, "*.csproj").SelectMany(file => XDocument.Load(file).Descendants()
            .Where(element => element.Name.LocalName is "TargetFramework" or "TargetFrameworks")
            .SelectMany(element => Regex.Matches(element.Value, @"\bnet(\d+)\.\d+").Select(match => int.Parse(match.Groups[1].Value))));
        return Math.Max(8, majors.DefaultIfEmpty(8).Max());
    }

    public static Dictionary<string, string>? PythonEnvironmentVariables(string python)
    {
        var prefix = Path.GetDirectoryName(python)!;
        if (Path.GetFileName(prefix).Equals("Scripts", StringComparison.OrdinalIgnoreCase)) prefix = Path.GetDirectoryName(prefix)!;
        if (!Directory.Exists(Path.Combine(prefix, "conda-meta"))) return null;
        return new() { ["CONDA_PREFIX"] = prefix, ["PATH"] = string.Join(";", new[] { prefix,
            Path.Combine(prefix, "Library", "mingw-w64", "bin"), Path.Combine(prefix, "Library", "usr", "bin"),
            Path.Combine(prefix, "Library", "bin"), Path.Combine(prefix, "Scripts"), Environment.GetEnvironmentVariable("PATH") ?? "" }) };
    }

    private const string RequirementCheck = """
import sys,json,pathlib,importlib.metadata as metadata
from pip._vendor.packaging.requirements import Requirement
missing,skipped,visited=[],[],set()
root=pathlib.Path(sys.argv[3]).resolve()
def verify(raw):
    line=raw.strip()
    if not line or line.startswith('#'): return
    try:
        requirement=Requirement(line.split(' #')[0])
        if requirement.url: skipped.append(line); return
        if requirement.marker and not requirement.marker.evaluate(): return
        try:
            version=metadata.version(requirement.name)
            if requirement.specifier and not requirement.specifier.contains(version,prereleases=True): missing.append(str(requirement)+' (installed '+version+')')
        except metadata.PackageNotFoundError: missing.append(str(requirement))
    except Exception: skipped.append(line)
def read(file):
    file=file.resolve()
    if file in visited: return
    visited.add(file)
    if not file.is_relative_to(root): skipped.append('Requirements outside workspace: '+str(file)); return
    if not file.is_file(): missing.append('Missing requirements file: '+str(file)); return
    for raw in file.read_text(encoding='utf-8-sig').splitlines():
        line=raw.strip()
        if line.startswith('-r ') or line.startswith('--requirement '): read(file.parent/line.split(maxsplit=1)[1].strip().strip('\"\''))
        else: verify(raw)
if sys.argv[1]: read(pathlib.Path(sys.argv[1]))
for entry in json.loads(sys.argv[2]): verify(entry)
print('Missing or incompatible: '+', '.join(missing) if missing else 'Declared requirement versions checked.')
if skipped: print('Manual verification: '+', '.join(skipped))
sys.exit(1 if missing else 2 if skipped else 0)
""";
}
