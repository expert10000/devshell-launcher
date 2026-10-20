using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace BatchLauncher;

public static class PortableWorkspace
{
    public static Dictionary<string, string> DiscoverTools(string root, Func<string, string?>? lookup = null)
    {
        lookup ??= DashboardInspector.FindTool;
        var tools = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        var programFiles = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles);
        var local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        foreach (var name in new[] { "git", "pwsh", "node", "npm", "python", "dotnet", "latexmk", "code", "winget", "yarn", "pnpm" })
        {
            var path = lookup(name);
            if (name == "python" && path?.Contains("WindowsApps", StringComparison.OrdinalIgnoreCase) == true) path = null;
            if (path == null)
            {
                var candidates = name switch
                {
                    "node" => new[] { Path.Combine(root, ".tools", "node24", "node_modules", "node", "bin", "node.exe"), Path.Combine(programFiles, "nodejs", "node.exe") },
                    "git" => new[] { Path.Combine(programFiles, "Git", "cmd", "git.exe") },
                    "pwsh" => new[] { Path.Combine(programFiles, "PowerShell", "7", "pwsh.exe") },
                    "dotnet" => new[] { Path.Combine(programFiles, "dotnet", "dotnet.exe") },
                    "python" => Directory.Exists(Path.Combine(local, "Programs", "Python")) ? Directory.EnumerateDirectories(Path.Combine(local, "Programs", "Python"), "Python*").OrderDescending().Select(directory => Path.Combine(directory, "python.exe")).ToArray() : Array.Empty<string>(),
                    "yarn" or "pnpm" => new[] { Path.Combine(root, ".tools", "package-managers", name + ".cmd"), Path.Combine(root, ".tools", "package-managers", "node_modules", ".bin", name + ".cmd") },
                    _ => Array.Empty<string>()
                };
                path = candidates.FirstOrDefault(File.Exists);
            }
            if (path != null) tools[name] = path;
        }
        var npmCandidates = new List<string>();
        if (tools.TryGetValue("node", out var node)) npmCandidates.Add(Path.Combine(Path.GetDirectoryName(node)!, "node_modules", "npm", "bin", "npm-cli.js"));
        if (tools.TryGetValue("npm", out var npm)) npmCandidates.Add(Path.Combine(Path.GetDirectoryName(npm)!, "node_modules", "npm", "bin", "npm-cli.js"));
        npmCandidates.Add(Path.Combine(root, ".tools", "node24", "node_modules", "npm", "bin", "npm-cli.js"));
        if (npmCandidates.FirstOrDefault(File.Exists) is { } npmCli) tools["npmCli"] = npmCli;
        return tools;
    }

    public static WorkspaceConfig Resolve(WorkspaceConfig source, string? rootOverride = null, Dictionary<string, string>? detectedTools = null)
    {
        if (source.Globals?.AutoDetectTools != true) return source;
        var root = ValidateRoot(rootOverride ?? source.Globals.WorkspaceRoot ?? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "masters"));
        var userProfile = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
        var node = JsonSerializer.SerializeToNode(source)!;
        void Replace(JsonNode? current)
        {
            if (current is JsonObject obj)
                foreach (var key in obj.Select(pair => pair.Key).ToList())
                {
                    if (obj[key] is JsonValue value && value.TryGetValue<string>(out var text)) obj[key] = text.Replace("${workspaceRoot}", root).Replace("${userProfile}", userProfile);
                    else Replace(obj[key]);
                }
            else if (current is JsonArray array)
                for (var i = 0; i < array.Count; i++)
                {
                    if (array[i] is JsonValue value && value.TryGetValue<string>(out var text)) array[i] = text.Replace("${workspaceRoot}", root).Replace("${userProfile}", userProfile);
                    else Replace(array[i]);
                }
        }
        Replace(node);
        var workspace = node.Deserialize<WorkspaceConfig>()!;
        var globals = workspace.Globals!;
        globals.WorkspaceRoot = root;
        globals.Tools = detectedTools ?? DiscoverTools(root);
        globals.Vars ??= new();
        globals.Vars["workspaceRoot"] = root;
        if (globals.Tools.TryGetValue("node", out var nodeExe)) { globals.Vars["nodeExe"] = nodeExe; globals.Vars["nodeDirectory"] = Path.GetDirectoryName(nodeExe)!; }
        if (globals.Tools.TryGetValue("npmCli", out var npmCli)) globals.Vars["npmCli"] = npmCli;
        if (globals.Tools.TryGetValue("npm", out var npm)) globals.Vars["npmDirectory"] = Path.GetDirectoryName(npm)!;
        if (globals.Tools.TryGetValue("python", out var python)) globals.Vars["basePython"] = python;
        // Resolve nested variables once, so terminal tasks and backend checks see identical paths.
        foreach (var key in globals.Vars.Keys.ToList()) globals.Vars[key] = Expand(globals.Vars[key], globals.Vars);
        foreach (var project in workspace.Projects ?? new())
        {
            var variables = new Dictionary<string, string>(globals.Vars);
            foreach (var pair in project.Vars ?? new()) variables[pair.Key] = pair.Value;
            if (project.Vars != null) foreach (var key in project.Vars.Keys.ToList()) project.Vars[key] = Expand(project.Vars[key], variables);
        }
        WorkspaceStore.DiscoverProjectRepositories(workspace);
        return workspace;
    }
    public static string ValidateRoot(string root)
    {
        root = root.Trim().Replace("${userProfile}", Environment.GetFolderPath(Environment.SpecialFolder.UserProfile));
        if (!Path.IsPathFullyQualified(root)) throw new ArgumentException("Choose an absolute workspace folder.");
        return Path.TrimEndingDirectorySeparator(Path.GetFullPath(root));
    }
    public static string Expand(string value, IReadOnlyDictionary<string, string> variables)
    {
        var visited = new HashSet<string>();
        for (var iteration = 0; iteration < 64 && visited.Add(value); iteration++)
        {
            var next = Regex.Replace(value, @"\$\{vars\.([^}]+)\}", match => variables.TryGetValue(match.Groups[1].Value, out var replacement) ? replacement : match.Value);
            if (next == value) return value;
            value = next;
        }
        throw new InvalidOperationException("Profile variables contain a cycle.");
    }
}
