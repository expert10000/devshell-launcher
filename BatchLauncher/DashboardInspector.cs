using System.Diagnostics;

namespace BatchLauncher;

public sealed record RepositoryStatus(string ProjectId, string Id, string Path, string? Branch,
    string? Upstream, int? Ahead, int? Behind, int Changed, List<string> Files, string? Error);
public sealed record HealthCheck(string Name, string State, string Detail);

public static class DashboardInspector
{
    public static string? FindTool(string tool)
    {
        if (System.IO.Path.IsPathRooted(tool)) return File.Exists(tool) ? tool : null;
        var extensions = new[] { "", ".exe", ".cmd", ".bat" };
        foreach (var directory in (Environment.GetEnvironmentVariable("PATH") ?? "").Split(';', StringSplitOptions.RemoveEmptyEntries))
            foreach (var extension in extensions)
            {
                var path = System.IO.Path.Combine(directory.Trim('"'), tool + extension);
                if (File.Exists(path)) return path;
            }
        return null;
    }

    public static async Task<(int Code, string Output, string Error)> Run(string executable, IEnumerable<string> arguments)
    {
        var start = new ProcessStartInfo(executable) { UseShellExecute = false, CreateNoWindow = true,
            RedirectStandardOutput = true, RedirectStandardError = true };
        foreach (var argument in arguments) start.ArgumentList.Add(argument);
        using var process = Process.Start(start) ?? throw new InvalidOperationException($"Cannot run {executable}");
        var output = process.StandardOutput.ReadToEndAsync();
        var error = process.StandardError.ReadToEndAsync();
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(25));
        try { await process.WaitForExitAsync(timeout.Token); }
        catch (OperationCanceledException) { process.Kill(true); throw new InvalidOperationException("Check timed out; retry when the repository is available."); }
        return (process.ExitCode, await output, await error);
    }

    public static RepositoryStatus ParseStatus(string projectId, string id, string path, string output)
    {
        string? branch = null, upstream = null;
        int? ahead = null, behind = null;
        var files = new List<string>();
        var records = output.Split('\0', StringSplitOptions.RemoveEmptyEntries);
        for (var i = 0; i < records.Length; i++)
        {
            var row = records[i];
            if (row.StartsWith("# branch.head ")) branch = row[14..];
            else if (row.StartsWith("# branch.upstream ")) upstream = row[18..];
            else if (row.StartsWith("# branch.ab "))
            {
                var counts = row[12..].Split(' ');
                ahead = int.Parse(counts[0].TrimStart('+'));
                behind = int.Parse(counts[1].TrimStart('-'));
            }
            else if (row.StartsWith("? ")) files.Add(row[2..]);
            else if (row.StartsWith("1 ")) files.Add(row.Split(' ', 9)[8]);
            else if (row.StartsWith("2 ")) { files.Add(row.Split(' ', 10)[9]); i++; }
            else if (row.StartsWith("u ")) files.Add(row.Split(' ', 11)[10]);
        }
        return new(projectId, id, path, branch, upstream, ahead, behind, files.Count, files.Take(30).ToList(), null);
    }

    public static async Task<RepositoryStatus> Inspect(string projectId, string id, string path)
    {
        try
        {
            path = System.IO.Path.GetFullPath(path);
            if (!Directory.Exists(path)) throw new InvalidOperationException("Repository folder is missing.");
            var prefix = new[] { "-c", "safe.directory=" + path.Replace('\\', '/'), "-C", path };
            var root = await Run("git", prefix.Concat(new[] { "rev-parse", "--show-toplevel" }));
            if (root.Code != 0) throw new InvalidOperationException(root.Error.Trim());
            if (!System.IO.Path.GetFullPath(root.Output.Trim()).TrimEnd('\\').Equals(path.TrimEnd('\\'), StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("Folder is inside a repository but is not its root.");
            var result = await Run("git", prefix.Concat(new[] { "--no-optional-locks", "status", "--porcelain=v2", "--branch", "-z", "--untracked-files=all" }));
            if (result.Code != 0) throw new InvalidOperationException(result.Error.Trim());
            return ParseStatus(projectId, id, path, result.Output);
        }
        catch (Exception error) { return new(projectId, id, path, null, null, null, null, 0, new(), error.Message); }
    }
}
