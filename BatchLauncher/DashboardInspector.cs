using System.Diagnostics;
using System.Text.RegularExpressions;

namespace BatchLauncher;

public sealed record RepositoryStatus(string ProjectId, string Id, string Path, string? Branch,
    string? Upstream, int? Ahead, int? Behind, int Changed, List<string> Files, string? Error)
{
    public RepositoryCommit? LastCommit { get; init; }
    public List<RepositoryRemote> Remotes { get; init; } = new();
    public List<RepositoryWorktree> Worktrees { get; init; } = new();
    public List<string> MetadataErrors { get; init; } = new();
}
public sealed record RepositoryCommit(string Hash, string Subject, string Author, string Timestamp);
public sealed record RepositoryRemote(string Name, string Url, string Direction);
public sealed record RepositoryWorktree(string Path, string? Branch, string? Head, bool Detached, bool Locked, bool Prunable, bool Bare);
public sealed record HealthCheck(string Name, string State, string Detail, string? ProjectId = null, string? RepositoryId = null);

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

    public static async Task<(int Code, string Output, string Error)> Run(string executable, IEnumerable<string> arguments,
        IReadOnlyDictionary<string, string>? environment = null)
    {
        var start = new ProcessStartInfo(executable) { UseShellExecute = false, CreateNoWindow = true,
            RedirectStandardOutput = true, RedirectStandardError = true };
        foreach (var argument in arguments) start.ArgumentList.Add(argument);
        foreach (var pair in environment ?? new Dictionary<string, string>()) start.Environment[pair.Key] = pair.Value;
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
            var status = ParseStatus(projectId, id, path, result.Output);
            var errors = new List<string>();
            async Task<string?> ReadMetadata(string label, params string[] arguments)
            {
                try
                {
                    var metadata = await Run("git", prefix.Concat(arguments));
                    if (metadata.Code == 0) return metadata.Output;
                    errors.Add(label + " unavailable.");
                }
                catch (Exception) { errors.Add(label + " unavailable; refresh to retry."); }
                return null;
            }
            RepositoryCommit? commit = null;
            // An unborn branch has no HEAD; this is a valid repository, not a metadata failure.
            if (!result.Output.Contains("# branch.oid (initial)", StringComparison.Ordinal))
            {
                var last = await ReadMetadata("Last commit", "--no-pager", "log", "-1", "--no-show-signature", "--format=%H%x00%s%x00%an%x00%aI");
                var fields = last?.TrimEnd('\r', '\n').Split('\0', 4);
                if (fields is { Length: 4 }) commit = new(fields[0], fields[1], fields[2], fields[3]);
            }
            var remotes = await ReadMetadata("Remotes", "remote", "--verbose");
            var worktrees = await ReadMetadata("Worktrees", "worktree", "list", "--porcelain", "-z");
            return status with { LastCommit = commit, Remotes = ParseRemotes(remotes ?? ""), Worktrees = ParseWorktrees(worktrees ?? ""), MetadataErrors = errors };
        }
        catch (Exception error) { return new(projectId, id, path, null, null, null, null, 0, new(), error.Message); }
    }

    public static List<RepositoryRemote> ParseRemotes(string output)
    {
        var remotes = new List<RepositoryRemote>();
        foreach (var line in output.Split('\n', StringSplitOptions.RemoveEmptyEntries))
        {
            var match = Regex.Match(line.TrimEnd('\r'), @"^(\S+)\s+(.+)\s+\((fetch|push)\)$");
            if (!match.Success) continue;
            var url = match.Groups[2].Value;
            if (Uri.TryCreate(url, UriKind.Absolute, out var uri) && uri.Scheme is "http" or "https" or "ssh")
                url = new UriBuilder(uri) { UserName = "", Password = "", Query = "", Fragment = "" }.Uri.AbsoluteUri;
            else url = Regex.Replace(url, @"(?<=://)[^/@]+@", "[redacted]@");
            remotes.Add(new(match.Groups[1].Value, url, match.Groups[3].Value));
        }
        return remotes;
    }

    public static List<RepositoryWorktree> ParseWorktrees(string output)
    {
        var worktrees = new List<RepositoryWorktree>();
        string? path = null, branch = null, head = null;
        var detached = false; var locked = false; var prunable = false; var bare = false;
        void Finish() { if (path != null) worktrees.Add(new(path, branch, head, detached, locked, prunable, bare)); }
        foreach (var row in output.Split('\0', StringSplitOptions.RemoveEmptyEntries))
        {
            if (row.StartsWith("worktree ", StringComparison.Ordinal))
            {
                Finish(); path = row[9..]; branch = head = null;
                detached = locked = prunable = bare = false;
            }
            else if (row.StartsWith("HEAD ", StringComparison.Ordinal)) head = row[5..];
            else if (row.StartsWith("branch ", StringComparison.Ordinal)) branch = row[7..].Replace("refs/heads/", "", StringComparison.Ordinal);
            else if (row == "detached") detached = true;
            else if (row == "bare") bare = true;
            else if (row == "locked" || row.StartsWith("locked ", StringComparison.Ordinal)) locked = true;
            else if (row == "prunable" || row.StartsWith("prunable ", StringComparison.Ordinal)) prunable = true;
        }
        Finish();
        return worktrees;
    }
}
