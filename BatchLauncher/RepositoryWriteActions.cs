using System.Security.Cryptography;
using System.Text;

namespace BatchLauncher;

internal sealed record RepositoryWritePreview(string Path, string Branch, string Head, string IndexHash,
    List<string> StagedFiles, int StagedCount, string? Remote = null, string? RemoteRef = null,
    string? RemoteHash = null, string? RemoteDisplay = null);

internal static class RepositoryWriteActions
{
    public static async Task<RepositoryWritePreview> Preview(string path, string action)
    {
        path = System.IO.Path.GetFullPath(path).TrimEnd('\\', '/');
        var prefix = new[] { "-c", "safe.directory=" + path.Replace('\\', '/'), "-C", path };
        async Task<string> Read(params string[] arguments)
        {
            var result = await DashboardInspector.Run("git", prefix.Concat(arguments));
            if (result.Code != 0) throw new InvalidOperationException("Cannot prepare repository action: " + result.Error.Trim());
            return result.Output.TrimEnd('\r', '\n');
        }
        var root = await Read("rev-parse", "--show-toplevel");
        if (!System.IO.Path.GetFullPath(root).TrimEnd('\\', '/').Equals(path, StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("The configured path is not the repository root.");
        var branch = await Read("symbolic-ref", "--quiet", "--short", "HEAD");
        foreach (var operation in new[] { "MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply" })
        {
            var marker = await Read("rev-parse", "--git-path", operation);
            if (!System.IO.Path.IsPathRooted(marker)) marker = System.IO.Path.Combine(path, marker);
            if (File.Exists(marker) || Directory.Exists(marker)) throw new InvalidOperationException("Finish the current merge/rebase/cherry-pick/revert before using this action.");
        }
        var headResult = await DashboardInspector.Run("git", prefix.Concat(new[] { "rev-parse", "--verify", "HEAD" }));
        var head = headResult.Code == 0 ? headResult.Output.Trim() : "(unborn)";
        if (action == "commit")
        {
            if (!string.IsNullOrEmpty(await Read("diff", "--name-only", "--diff-filter=U", "-z")))
                throw new InvalidOperationException("Resolve unmerged files before committing.");
            var files = (await Read("diff", "--cached", "--name-only", "-z")).Split('\0', StringSplitOptions.RemoveEmptyEntries);
            if (files.Length == 0) throw new InvalidOperationException("No staged changes. Stage the intended files in VS Code or a terminal first; DevShell never stages everything automatically.");
            var index = await Read("ls-files", "--stage", "-z");
            return new(path, branch, head, Hash(index), files.Take(200).ToList(), files.Length);
        }
        if (action != "push") throw new ArgumentException("Unknown repository write action.");
        if (head == "(unborn)") throw new InvalidOperationException("Create a commit before pushing.");
        var upstream = (await Read("for-each-ref", "--format=%(upstream:remotename)%00%(upstream:remoteref)", "refs/heads/" + branch)).Split('\0');
        if (upstream.Length != 2 || string.IsNullOrWhiteSpace(upstream[0]) || upstream[0] == "." || !upstream[1].StartsWith("refs/heads/", StringComparison.Ordinal))
            throw new InvalidOperationException("Configure a remote tracking branch before pushing. No upstream is created automatically.");
        var urls = (await Read("remote", "get-url", "--push", "--all", upstream[0])).Split('\n', StringSplitOptions.RemoveEmptyEntries).Select(url => url.TrimEnd('\r')).ToArray();
        if (urls.Length != 1) throw new InvalidOperationException("Push requires exactly one destination URL for this remote.");
        var display = DashboardInspector.ParseRemotes(upstream[0] + "\t" + urls[0] + " (push)\n").First().Url;
        return new(path, branch, head, "", new(), 0, upstream[0], upstream[1], Hash(urls[0]), display);
    }

    private static string Hash(string value) => Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(value)));

    public static RepositoryCommand CreateCommand(string shell, string helper, RepositoryWritePreview preview, string action, string? message)
    {
        if (!File.Exists(helper)) throw new FileNotFoundException("Repository write helper is missing.", helper);
        string Quote(string value) => "'" + value.Replace("'", "''") + "'";
        var script = "$ErrorActionPreference = 'Stop'\ntry { & " + Quote(helper) + " -Action " + Quote(action)
            + " -Destination " + Quote(preview.Path) + " -ExpectedBranch " + Quote(preview.Branch) + " -ExpectedHead " + Quote(preview.Head);
        if (action == "commit") script += " -ExpectedIndexHash " + Quote(preview.IndexHash) + " -Message " + Quote(message ?? "");
        else script += " -Remote " + Quote(preview.Remote!) + " -RemoteRef " + Quote(preview.RemoteRef!) + " -ExpectedRemoteHash " + Quote(preview.RemoteHash!);
        script += "; exit 0 } catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 }";
        return new(shell, script, preview.Path);
    }
}
