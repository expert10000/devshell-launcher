using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace BatchLauncher;

// The desktop uses the broker's source_snapshot.py v1 field contract. Capture is
// read-only: neither the index nor the worktree is modified to make evidence.
public static class ScientificSourceSnapshot
{
    private static string Hash(byte[] bytes) => Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
    private static string Hash(string text) => Hash(Encoding.UTF8.GetBytes(text));

    private static byte[] Git(string root, params string[] arguments)
    {
        using var process = new Process { StartInfo = new ProcessStartInfo("git")
        {
            UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true,
            RedirectStandardError = true
        } };
        process.StartInfo.ArgumentList.Add("-C");
        process.StartInfo.ArgumentList.Add(root);
        foreach (var argument in arguments) process.StartInfo.ArgumentList.Add(argument);
        process.Start();
        using var output = new MemoryStream();
        var copy = process.StandardOutput.BaseStream.CopyToAsync(output);
        var error = process.StandardError.ReadToEndAsync();
        if (!process.WaitForExit(30000)) { process.Kill(entireProcessTree: true); throw new IOException("Git source capture timed out."); }
        copy.GetAwaiter().GetResult();
        if (process.ExitCode != 0) throw new IOException(error.GetAwaiter().GetResult());
        return output.ToArray();
    }

    private static string GitText(string root, params string[] arguments) => Encoding.UTF8.GetString(Git(root, arguments)).Trim();

    private static string Canonical(JsonNode? node)
    {
        if (node is JsonObject obj)
            return "{" + string.Join(",", obj.OrderBy(item => item.Key, StringComparer.Ordinal)
                .Select(item => JsonSerializer.Serialize(item.Key) + ":" + Canonical(item.Value))) + "}";
        if (node is JsonArray array) return "[" + string.Join(",", array.Select(Canonical)) + "]";
        return node?.ToJsonString() ?? "null";
    }

    private static JsonObject Repository(string path)
    {
        var root = Path.GetFullPath(GitText(path, "rev-parse", "--show-toplevel"));
        var gitDirectory = Path.GetFullPath(GitText(root, "rev-parse", "--absolute-git-dir"));
        string? branch;
        try { branch = GitText(root, "symbolic-ref", "--quiet", "--short", "HEAD"); }
        catch (IOException) { branch = null; }
        var patch = Git(root, "diff", "--binary", "HEAD", "--");
        var untracked = new JsonArray();
        foreach (var relative in Encoding.UTF8.GetString(Git(root, "ls-files", "--others", "--exclude-standard", "-z"))
            .Split('\0', StringSplitOptions.RemoveEmptyEntries))
        {
            var file = Path.Combine(root, relative);
            var info = new FileInfo(file);
            var link = info.LinkTarget;
            untracked.Add(new JsonObject { ["path"] = relative.Replace('\\', '/'),
                ["kind"] = link == null ? "file" : "symlink",
                ["sha256"] = link == null ? Hash(File.ReadAllBytes(file)) : Hash(link) });
        }
        var dirty = patch.Length > 0 || untracked.Count > 0;
        var identity = new JsonObject { ["trackedPatchSha256"] = patch.Length > 0 ? Hash(patch) : null,
            ["untracked"] = untracked.DeepClone() };
        var snapshot = new JsonObject { ["schemaVersion"] = 1, ["repository"] = root,
            ["gitDirectory"] = gitDirectory, ["worktree"] = root, ["branch"] = branch,
            ["commit"] = GitText(root, "rev-parse", "HEAD"), ["tree"] = GitText(root, "rev-parse", "HEAD^{tree}"),
            ["dirty"] = dirty, ["trackedPatchSha256"] = identity["trackedPatchSha256"]?.DeepClone(),
            ["untracked"] = untracked.DeepClone(),
            ["dirtyDigestSha256"] = dirty ? Hash(Canonical(identity)) : null };
        snapshot["snapshotId"] = Hash(Canonical(snapshot));
        return snapshot;
    }

    public static JsonObject Capture(string devshell, string? math3d = null)
    {
        var repositories = new JsonObject();
        foreach (var (name, path) in new[] { ("devshell", devshell), ("math3d", math3d) })
        {
            if (path == null) continue;
            try
            {
                var entry = Repository(path);
                entry["state"] = "captured";
                repositories[name] = entry;
            }
            catch (Exception error) when (error is IOException or UnauthorizedAccessException or InvalidOperationException
                or System.ComponentModel.Win32Exception)
            {
                repositories[name] = new JsonObject { ["state"] = "unavailable", ["requestedPath"] = path,
                    ["reason"] = error.Message[..Math.Min(300, error.Message.Length)] };
            }
        }
        return new JsonObject { ["schemaVersion"] = 1, ["repositories"] = repositories };
    }

    public static string Save(string directory, JsonObject captured)
    {
        var path = Path.Combine(directory, "source-snapshot.json");
        var text = captured.ToJsonString();
        var temporary = Path.Combine(directory, $".source-snapshot-{Guid.NewGuid():N}.tmp");
        try { File.WriteAllText(temporary, text, new UTF8Encoding(false)); File.Move(temporary, path); }
        finally { if (File.Exists(temporary)) File.Delete(temporary); }
        return Hash(text);
    }

    public static JsonObject Verify(string directory, string expected)
    {
        if (!Regex.IsMatch(expected, "^[0-9a-f]{64}$")) throw new InvalidDataException("Invalid source snapshot hash.");
        var path = Path.Combine(directory, "source-snapshot.json");
        if (!File.Exists(path) || new FileInfo(path).Length > 2_097_152)
            throw new InvalidDataException("Source snapshot is missing or too large.");
        var text = File.ReadAllText(path);
        if (Hash(text) != expected) throw new InvalidDataException("Source snapshot hash changed.");
        var snapshot = JsonNode.Parse(text) as JsonObject;
        if (snapshot?["schemaVersion"]?.GetValue<int>() != 1 || snapshot["repositories"] is not JsonObject repositories
            || repositories["devshell"]?["state"]?.GetValue<string>() != "captured")
            throw new InvalidDataException("Desktop source snapshot is unavailable.");
        foreach (var (_, value) in repositories)
        {
            if (value?["state"]?.GetValue<string>() != "captured")
                throw new InvalidDataException("A requested source snapshot is unavailable.");
            var copy = (JsonObject)value.DeepClone();
            copy.Remove("state");
            var id = copy["snapshotId"]?.GetValue<string>();
            copy.Remove("snapshotId");
            if (id == null || Hash(Canonical(copy)) != id)
                throw new InvalidDataException("Repository snapshot identity changed.");
        }
        return snapshot;
    }

    public static JsonObject Assess(JsonObject saved)
    {
        var reasons = new JsonArray();
        var repositories = saved["repositories"]!.AsObject();
        foreach (var (name, record) in repositories)
        {
            var path = record?["worktree"]?.GetValue<string>();
            if (path == null) { reasons.Add(name + " source is unavailable"); continue; }
            var current = Capture(path)["repositories"]?["devshell"];
            if (current?["state"]?.GetValue<string>() != "captured")
                reasons.Add(name + " source cannot be read");
            else if (current["snapshotId"]?.GetValue<string>() != record?["snapshotId"]?.GetValue<string>())
                reasons.Add(name + " Git source snapshot changed");
        }
        return new JsonObject { ["state"] = reasons.Count == 0 ? "current" : "stale", ["reasons"] = reasons };
    }
}
