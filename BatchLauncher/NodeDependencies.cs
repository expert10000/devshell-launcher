using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace BatchLauncher;

public sealed record NodeManifest(string Manager, string? ManagerVersion, string? NodeRange, Dictionary<string, string> Packages);

public static class NodeDependencies
{
    public static string? ManagedTool(string? workspaceRoot, string manager, string? version)
    {
        if (workspaceRoot == null) return null;
        var directory = Path.Combine(workspaceRoot, ".tools", "package-managers");
        if (version != null) directory = Path.Combine(directory, manager + "-" + version);
        var file = manager == "npm" ? Path.Combine(directory, "node_modules", "npm", "bin", "npm-cli.js") : Path.Combine(directory, manager + ".cmd");
        if (File.Exists(file)) return file;
        if (version == null && manager != "npm" && Directory.Exists(directory))
            return Directory.EnumerateDirectories(directory, manager + "-*").OrderDescending()
                .Select(path => Path.Combine(path, manager + ".cmd")).FirstOrDefault(File.Exists);
        return null;
    }
    public static NodeManifest Read(string directory)
    {
        using var json = JsonDocument.Parse(File.ReadAllText(Path.Combine(directory, "package.json")));
        var manager = File.Exists(Path.Combine(directory, "pnpm-lock.yaml")) ? "pnpm" : File.Exists(Path.Combine(directory, "yarn.lock")) ? "yarn" : "npm";
        string? version = null, nodeRange = null;
        if (json.RootElement.TryGetProperty("packageManager", out var declared))
        {
            var match = Regex.Match(declared.GetString() ?? "", @"^(npm|yarn|pnpm)@(\d+\.\d+\.\d+)(?:\+.*)?$");
            if (!match.Success) throw new InvalidOperationException("Unsupported packageManager declaration: " + declared.GetString());
            manager = match.Groups[1].Value; version = match.Groups[2].Value;
        }
        if (json.RootElement.TryGetProperty("engines", out var engines) && engines.TryGetProperty("node", out var range)) nodeRange = range.GetString();
        var packages = new Dictionary<string, string>();
        foreach (var section in new[] { "dependencies", "devDependencies" })
            if (json.RootElement.TryGetProperty(section, out var dependencies))
                foreach (var dependency in dependencies.EnumerateObject())
                {
                    if (!Regex.IsMatch(dependency.Name, @"^(@[a-zA-Z0-9._-]+/)?[a-zA-Z0-9._-]+$"))
                        throw new InvalidOperationException("Invalid dependency name: " + dependency.Name);
                    packages[dependency.Name] = dependency.Value.GetString() ?? "*";
                }
        return new(manager, version, nodeRange, packages);
    }

    // Dependency checks follow Node's ancestor lookup, bounded by this checkout.
    public static string? PackageFile(string root, string directory, string name)
    {
        root = Path.TrimEndingDirectorySeparator(Path.GetFullPath(root));
        for (var current = Path.GetFullPath(directory); ; current = Path.GetDirectoryName(current)!)
        {
            if (!current.Equals(root, StringComparison.OrdinalIgnoreCase) && !current.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)) return null;
            var file = Path.Combine(current, "node_modules", name, "package.json");
            if (File.Exists(file)) return file;
            if (current.Equals(root, StringComparison.OrdinalIgnoreCase)) return null;
        }
    }

    public static string? Semver(string? npmPath, string? nodePath)
    {
        var candidates = new List<string>();
        if (npmPath != null)
        {
            var directory = Path.GetDirectoryName(npmPath)!;
            if (Path.GetFileName(npmPath).Equals("npm-cli.js", StringComparison.OrdinalIgnoreCase)) directory = Path.GetDirectoryName(directory)!;
            candidates.Add(Path.Combine(directory, "node_modules", "semver"));
            candidates.Add(Path.Combine(directory, "node_modules", "npm", "node_modules", "semver"));
        }
        if (nodePath != null) candidates.Add(Path.Combine(Path.GetDirectoryName(nodePath)!, "node_modules", "npm", "node_modules", "semver"));
        return candidates.FirstOrDefault(path => File.Exists(Path.Combine(path, "package.json")));
    }

    public static async Task<List<bool?>> MatchVersions(string? node, string? semver, List<(string Version, string Range)> versions, CancellationToken cancellationToken = default)
    {
        if (node == null || semver == null) return versions.Select(_ => (bool?)null).ToList();
        const string code = "const s=require(process.argv[1]); const items=JSON.parse(process.argv[2]); console.log(JSON.stringify(items.map(i=>s.valid(i.version)&&s.validRange(i.range)?s.satisfies(i.version,i.range):null)));";
        var json = JsonSerializer.Serialize(versions.Select(item => new { version = item.Version, range = item.Range }));
        var result = await DashboardInspector.Run(node, new[] { "-e", code, semver, json }, cancellationToken: cancellationToken);
        if (result.Code != 0) throw new InvalidOperationException("Could not check Node dependency versions: " + result.Error.Trim());
        return JsonSerializer.Deserialize<List<bool?>>(result.Output.Trim())!;
    }

    public static Task<(int Code, string Output, string Error)> Version(string tool, string? node = null, CancellationToken cancellationToken = default)
    {
        if (tool.EndsWith(".js", StringComparison.OrdinalIgnoreCase) && node != null) return DashboardInspector.Run(node, new[] { tool, "--version" }, cancellationToken: cancellationToken);
        // Windows command shims need a shell; pass literal arguments through encoded PowerShell.
        if (tool.EndsWith(".cmd", StringComparison.OrdinalIgnoreCase) || tool.EndsWith(".bat", StringComparison.OrdinalIgnoreCase) || File.Exists(tool + ".cmd"))
        {
            var shell = DashboardInspector.FindTool("pwsh") ?? DashboardInspector.FindTool("powershell") ?? throw new InvalidOperationException("PowerShell is required to inspect this tool.");
            if (File.Exists(tool + ".cmd")) tool += ".cmd";
            var command = "& '" + tool.Replace("'", "''") + "' --version; exit $LASTEXITCODE";
            return DashboardInspector.Run(shell, new[] { "-NoProfile", "-EncodedCommand", Convert.ToBase64String(Encoding.Unicode.GetBytes(command)) }, cancellationToken: cancellationToken);
        }
        return DashboardInspector.Run(tool, new[] { "--version" }, cancellationToken: cancellationToken);
    }
}
