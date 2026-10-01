using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;

namespace BatchLauncher;

public sealed record RepositoryChangedFile(string Path, string? OriginalPath, string Index, string Worktree, bool Conflicted)
{
    public bool Staged => Index is not (" " or "?");
    public bool Unstaged => Worktree != " ";
}
public sealed record RepositoryChangesSnapshot(string Path, string Head, string Token, List<RepositoryChangedFile> Files, string? BlockedReason);
public sealed record RepositoryFileDiff(string Path, string Side, string Text, bool Truncated);

public static class RepositoryChanges
{
    private static string Fingerprint(string value) => Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(value)));

    private static async Task<(int Code, string Text, bool Truncated)> Git(string path, int limit, params string[] args)
    {
        var info = new ProcessStartInfo("git") { UseShellExecute = false, CreateNoWindow = true, WorkingDirectory = path,
            RedirectStandardOutput = true, RedirectStandardError = true, StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8 };
        foreach (var arg in new[] { "--no-pager", "--literal-pathspecs", "-c", "safe.directory=" + path.Replace('\\', '/'), "-C", path }.Concat(args)) info.ArgumentList.Add(arg);
        info.Environment["GIT_TERMINAL_PROMPT"] = "0";
        info.Environment["GIT_OPTIONAL_LOCKS"] = "0";
        using var process = Process.Start(info) ?? throw new InvalidOperationException("Git could not start.");
        async Task<(string Text, bool Truncated)> Read(StreamReader reader, int max)
        {
            var text = new StringBuilder(); var buffer = new char[8192]; var truncated = false; int count;
            while ((count = await reader.ReadAsync(buffer)) > 0)
            {
                var keep = Math.Min(count, max - text.Length);
                if (keep > 0) text.Append(buffer, 0, keep);
                if (keep < count) truncated = true;
            }
            return (text.ToString(), truncated);
        }
        var stdout = Read(process.StandardOutput, limit); var stderr = Read(process.StandardError, 24000);
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(30));
        try { await process.WaitForExitAsync(timeout.Token); }
        catch (OperationCanceledException) { try { process.Kill(true); } catch (InvalidOperationException) { } throw new TimeoutException("Git timed out. Refresh and retry."); }
        var output = await stdout; var error = await stderr;
        if (process.ExitCode != 0 && !(args.Contains("rev-parse") && args.Contains("--verify")))
            throw new InvalidOperationException("Git failed: " + error.Text.Trim());
        return (process.ExitCode, output.Text, output.Truncated);
    }

    public static List<RepositoryChangedFile> ParseStatus(string text)
    {
        var rows = text.Split('\0'); var result = new List<RepositoryChangedFile>();
        for (var i = 0; i < rows.Length; i++)
        {
            var row = rows[i]; if (row.Length < 4) continue;
            string? original = null;
            if (row[0] is 'R' or 'C' || row[1] is 'R' or 'C')
            {
                if (++i >= rows.Length || rows[i].Length == 0) throw new InvalidOperationException("Incomplete rename status. Refresh and retry.");
                original = rows[i];
            }
            var xy = row[..2];
            result.Add(new(row[3..], original, row[..1], row.Substring(1, 1), xy is "DD" or "AU" or "UD" or "UA" or "DU" or "AA" or "UU"));
        }
        return result;
    }

    public static async Task<RepositoryChangesSnapshot> Read(string path)
    {
        if (!System.IO.Path.IsPathFullyQualified(path)) throw new ArgumentException("An absolute repository path is required.");
        path = System.IO.Path.GetFullPath(path).TrimEnd('\\', '/');
        var root = (await Git(path, 24000, "rev-parse", "--show-toplevel")).Text.TrimEnd('\r', '\n');
        if (!System.IO.Path.GetFullPath(root).TrimEnd('\\', '/').Equals(path, StringComparison.OrdinalIgnoreCase)) throw new InvalidOperationException("The configured path is not the repository root.");
        var headResult = await Git(path, 24000, "rev-parse", "--verify", "HEAD");
        var head = headResult.Code == 0 ? headResult.Text.Trim() : "(unborn)";
        var status = await Git(path, 2000000, "status", "--porcelain=v1", "-z", "--untracked-files=all");
        var index = await Git(path, 8000000, "ls-files", "--stage", "-z");
        if (status.Truncated || index.Truncated) throw new InvalidOperationException("Repository is too large for this panel. Use a terminal or VS Code.");
        var files = ParseStatus(status.Text);
        if (files.Count > 2000) throw new InvalidOperationException("More than 2,000 changed files. Narrow the changes in VS Code first.");
        string? blocked = files.Any(file => file.Conflicted) ? "Resolve merge conflicts in VS Code or a terminal before staging or committing here." : null;
        foreach (var operation in new[] { "MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply" })
        {
            var marker = (await Git(path, 24000, "rev-parse", "--git-path", operation)).Text.TrimEnd('\r', '\n');
            if (!System.IO.Path.IsPathRooted(marker)) marker = System.IO.Path.Combine(path, marker);
            if (File.Exists(marker) || Directory.Exists(marker)) blocked = "Finish the current merge/rebase/cherry-pick/revert before staging here.";
        }
        return new(path, head, Fingerprint(head + "\0" + status.Text + "\0" + index.Text), files, blocked);
    }

    private static string SafeFile(string root, string path)
    {
        if (string.IsNullOrEmpty(path) || System.IO.Path.IsPathRooted(path) || path.Contains('\\') || path.Contains(':') ||
            path.Split('/').Any(part => part is "." or ".." || part.Equals(".git", StringComparison.OrdinalIgnoreCase)))
            throw new ArgumentException("Invalid repository-relative file path.");
        var full = System.IO.Path.GetFullPath(System.IO.Path.Combine(root, path));
        if (!full.StartsWith(root + System.IO.Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)) throw new ArgumentException("File must be inside this checkout.");
        return full;
    }

    public static async Task<RepositoryFileDiff> Diff(string path, RepositoryChangesSnapshot snapshot, string filePath, string side)
    {
        var file = snapshot.Files.FirstOrDefault(file => file.Path == filePath) ?? throw new InvalidOperationException("File changed. Refresh the panel.");
        var full = SafeFile(snapshot.Path, filePath);
        if (side is not ("staged" or "working")) throw new ArgumentException("Unknown diff side.");
        if (side == "working" && file.Index == "?")
        {
            for (var current = full; current != snapshot.Path; current = System.IO.Path.GetDirectoryName(current)!)
                if ((File.GetAttributes(current) & FileAttributes.ReparsePoint) != 0) throw new InvalidOperationException("Untracked link previews are not supported.");
            using var stream = new FileStream(full, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
            var bytes = new byte[Math.Min(stream.Length, 240001)]; var count = await stream.ReadAsync(bytes);
            if (bytes.AsSpan(0, count).Contains((byte)0)) return new(filePath, side, "Binary file (content is not shown).", false);
            return new(filePath, side, "Untracked file (not staged)\n\n" + Encoding.UTF8.GetString(bytes, 0, Math.Min(count, 240000)), stream.Length > 240000);
        }
        var arguments = new List<string> { "diff", "--no-ext-diff", "--no-textconv", "--color=never" };
        if (side == "staged") arguments.Add("--cached");
        arguments.Add("--"); arguments.Add(filePath);
        if (file.OriginalPath != null) { SafeFile(snapshot.Path, file.OriginalPath); arguments.Add(file.OriginalPath); }
        var result = await Git(snapshot.Path, 240000, arguments.ToArray());
        return new(filePath, side, result.Text.Length == 0 ? "No textual diff (the file may be unchanged, a submodule, or a mode-only change)." : result.Text, result.Truncated);
    }

    public static async Task<RepositoryChangesSnapshot> ChangeIndex(string path, RepositoryChangesSnapshot snapshot, string expectedToken, string action, string[] paths)
    {
        if (action is not ("stage" or "unstage")) throw new ArgumentException("Unknown index action.");
        if (snapshot.Token != expectedToken) throw new InvalidOperationException("Repository state changed. Refresh and review the selection before retrying.");
        if (snapshot.BlockedReason != null) throw new InvalidOperationException(snapshot.BlockedReason);
        if (paths.Length == 0 || paths.Length > 200) throw new ArgumentException("Select 1-200 files.");
        var selected = new List<string>();
        foreach (var value in paths.Distinct(StringComparer.Ordinal))
        {
            SafeFile(snapshot.Path, value);
            var file = snapshot.Files.FirstOrDefault(file => file.Path == value) ?? throw new InvalidOperationException("Selected file is no longer in the change list. Refresh.");
            if (action == "stage" ? !file.Unstaged : !file.Staged) throw new InvalidOperationException("Selected file has no changes on this side. Refresh.");
            selected.Add(value);
            if (file.OriginalPath != null && (action == "unstage" && file.Index == "R" || action == "stage" && file.Worktree == "R"))
            { SafeFile(snapshot.Path, file.OriginalPath); selected.Add(file.OriginalPath); }
        }
        var current = await Read(snapshot.Path);
        if (current.Token != expectedToken) throw new InvalidOperationException("The index or checkout changed. Refresh before staging.");
        if (current.BlockedReason != null) throw new InvalidOperationException(current.BlockedReason);
        var args = action == "stage" ? new List<string> { "add", "--all" }
            : snapshot.Head == "(unborn)" ? new List<string> { "update-index", "--force-remove" }
            : new List<string> { "restore", "--staged", "--source=HEAD" };
        args.Add("--"); args.AddRange(selected.Distinct(StringComparer.Ordinal));
        await Git(snapshot.Path, 24000, args.ToArray());
        return await Read(snapshot.Path);
    }
}
