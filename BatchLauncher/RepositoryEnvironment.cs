using System.Text.Json;

namespace BatchLauncher;

public static class RepositoryEnvironment
{
    public static async Task<List<HealthCheck>> Inspect(string projectId, string repositoryId, string path,
        IEnumerable<string> requiredTools, string? pythonEnvironment = null, List<string>? pythonModules = null,
        IReadOnlyDictionary<string, string>? toolPaths = null)
    {
        var checks = new List<HealthCheck>();
        void Add(string name, string state, string detail) => checks.Add(new(name, state, detail, projectId, repositoryId));
        string? Tool(string name) => DashboardInspector.FindTool(toolPaths?.GetValueOrDefault(name) ?? name);
        var tools = new HashSet<string>(requiredTools, StringComparer.OrdinalIgnoreCase);
        if (!Directory.Exists(path)) { Add("Repository folder", "error", "Clone this repository before checking its dependencies."); return checks; }
        try
        {
            var manifestPath = Path.Combine(path, "package.json");
            if (File.Exists(manifestPath))
            {
                tools.Add("node");
                var manager = File.Exists(Path.Combine(path, "pnpm-lock.yaml")) ? "pnpm" : File.Exists(Path.Combine(path, "yarn.lock")) ? "yarn" : "npm";
                tools.Add(manager);
                using var manifest = JsonDocument.Parse(await File.ReadAllTextAsync(manifestPath));
                var missing = new List<string>();
                foreach (var section in new[] { "dependencies", "devDependencies" })
                    if (manifest.RootElement.TryGetProperty(section, out var dependencies))
                        foreach (var dependency in dependencies.EnumerateObject())
                        {
                            // Only package names can be mapped to a folder inside node_modules.
                            if (!System.Text.RegularExpressions.Regex.IsMatch(dependency.Name, @"^(@[a-zA-Z0-9._-]+/)?[a-zA-Z0-9._-]+$"))
                            { Add("Node manifest", "error", "Invalid dependency name: " + dependency.Name); continue; }
                            if (!File.Exists(Path.Combine(path, "node_modules", dependency.Name, "package.json"))) missing.Add(dependency.Name);
                        }
                var install = manager == "npm" ? (File.Exists(Path.Combine(path, "package-lock.json")) ? "npm ci" : "npm install") : manager + " install";
                Add("Node packages", missing.Count == 0 ? "ok" : "error", missing.Count == 0 ? "Declared dependencies and development dependencies are installed."
                    : $"{missing.Count} missing: {string.Join(", ", missing.Take(8))}. Run {install} in {path}.");
            }
            if (Directory.EnumerateFiles(path, "*.csproj").Any() || Directory.EnumerateFiles(path, "*.sln*").Any())
            {
                tools.Add("dotnet");
                if (Tool("dotnet") is { } dotnet)
                {
                    var sdks = await DashboardInspector.Run(dotnet, new[] { "--list-sdks" });
                    Add(".NET SDK", sdks.Code == 0 && !string.IsNullOrWhiteSpace(sdks.Output) ? "ok" : "error",
                        string.IsNullOrWhiteSpace(sdks.Output) ? "Install a .NET SDK to build this repository; a runtime alone is insufficient." : sdks.Output.Trim());
                }
            }
            var requirements = Path.Combine(path, "requirements.txt");
            var needsPython = pythonEnvironment != null || pythonModules?.Count > 0 || File.Exists(requirements);
            if (needsPython)
            {
                var environment = pythonEnvironment ?? Path.Combine(path, ".venv");
                var python = File.Exists(environment) ? environment : File.Exists(Path.Combine(environment, "python.exe"))
                    ? Path.Combine(environment, "python.exe") : Path.Combine(environment, "Scripts", "python.exe");
                if (!File.Exists(python)) Add("Python environment", "error", $"Missing {python}. Create the environment and install this repository's Python requirements.");
                else
                {
                    Add("Python environment", "ok", python);
                    var prefix = Path.GetDirectoryName(python)!;
                    if (Path.GetFileName(prefix).Equals("Scripts", StringComparison.OrdinalIgnoreCase))
                        prefix = Path.GetDirectoryName(prefix)!;
                    Dictionary<string, string>? nativeEnvironment = null;
                    if (Directory.Exists(Path.Combine(prefix, "conda-meta")))
                    {
                        // Conda's compiled packages require its DLL folders, as
                        // they do when this environment is activated in a shell.
                        nativeEnvironment = new()
                        {
                            ["CONDA_PREFIX"] = prefix,
                            ["PATH"] = string.Join(";", new[] { prefix, Path.Combine(prefix, "Library", "mingw-w64", "bin"),
                                Path.Combine(prefix, "Library", "usr", "bin"), Path.Combine(prefix, "Library", "bin"),
                                Path.Combine(prefix, "Scripts"), Environment.GetEnvironmentVariable("PATH") ?? "" })
                        };
                    }
                    var modules = JsonSerializer.Serialize(pythonModules ?? new());
                    var code = "import importlib,json,sys; [importlib.import_module(m) for m in json.loads(sys.argv[1])]; print('Configured modules import successfully.')";
                    var result = await DashboardInspector.Run(python, new[] { "-c", code, modules }, nativeEnvironment);
                    Add("Python modules", result.Code == 0 ? "ok" : "error", result.Code == 0 ? result.Output.Trim() : result.Error.Trim());
                    if (File.Exists(requirements))
                    {
                        const string requirementCheck = """
import sys, importlib.metadata as metadata
from pip._vendor.packaging.requirements import Requirement
missing, skipped = [], []
for raw in open(sys.argv[1], encoding='utf-8-sig'):
    line = raw.strip()
    if not line or line.startswith('#'): continue
    try:
        requirement = Requirement(line.split(' #')[0])
        if requirement.marker and not requirement.marker.evaluate(): continue
        try:
            version = metadata.version(requirement.name)
            if requirement.specifier and not requirement.specifier.contains(version, prereleases=True): missing.append(str(requirement))
        except metadata.PackageNotFoundError: missing.append(str(requirement))
    except Exception: skipped.append(line)
print('Missing or incompatible: ' + ', '.join(missing) if missing else 'Requirement versions checked.')
if skipped: print('Additional requirement entries need manual verification: ' + ', '.join(skipped))
sys.exit(1 if missing else 2 if skipped else 0)
""";
                        result = await DashboardInspector.Run(python, new[] { "-c", requirementCheck, requirements }, nativeEnvironment);
                        Add("Python requirements", result.Code == 0 ? "ok" : result.Code == 2 ? "warning" : "error",
                            (result.Output + result.Error).Trim() + (result.Code == 0 ? "" : $"\nInstall with: & '{python.Replace("'", "''")}' -m pip install -r requirements.txt (in {path})."));
                    }
                }
            }
            foreach (var tool in tools)
            {
                var resolved = Tool(tool);
                Add(tool, resolved == null ? "error" : "ok", resolved ?? $"Missing {tool}. Install it or update the configured executable path.");
            }
            if (checks.Count == 0) Add("Environment", "ok", "No additional dependencies are declared for this repository.");
        }
        catch (Exception error) { Add("Environment check", "error", error.Message); }
        return checks;
    }
}
