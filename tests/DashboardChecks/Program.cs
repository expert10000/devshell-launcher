using BatchLauncher;
using System.Text.Json;

static void Check(bool condition, string message) { if (!condition) throw new Exception(message); }
static async Task Git(string path, params string[] arguments)
{
    var result = await DashboardInspector.Run("git", new[] { "-C", path, "-c", "user.name=DevShell Test", "-c", "user.email=devshell-test@example.invalid" }.Concat(arguments));
    if (result.Code != 0) throw new Exception(result.Error);
}

if (args.Length > 0)
{
    using var config = JsonDocument.Parse(File.ReadAllText(args[0]));
    foreach (var project in config.RootElement.GetProperty("projects").EnumerateArray())
    {
        if (!project.TryGetProperty("repositories", out var repos)) continue;
        foreach (var repo in repos.EnumerateArray())
        {
            var path = repo.GetProperty("path").GetString()!;
            foreach (var pair in project.GetProperty("vars").EnumerateObject()) path = path.Replace("${vars." + pair.Name + "}", pair.Value.GetString());
            var status = await DashboardInspector.Inspect(project.GetProperty("id").GetString()!, repo.GetProperty("id").GetString()!, path);
            Check(status.Error == null, status.Error ?? "Repository check");
            Console.WriteLine($"{repo.GetProperty("name").GetString()}: {status.Branch}, {status.Changed} changed, ahead {status.Ahead}, behind {status.Behind}");
        }
    }
    return;
}

var root = Path.Combine(Path.GetTempPath(), "devshell-git-test-" + Guid.NewGuid().ToString("N"));
Directory.CreateDirectory(root);
try
{
    var repo = Path.Combine(root, "repo"); Directory.CreateDirectory(repo);
    await Git(repo, "init", "-b", "main");
    File.WriteAllText(Path.Combine(repo, "file.txt"), "initial\n");
    await Git(repo, "add", "."); await Git(repo, "commit", "-m", "initial");
    var status = await DashboardInspector.Inspect("p", "r", repo);
    Check(status.Error == null && status.Branch == "main" && status.Changed == 0 && status.Upstream == null && status.Ahead == null, "Clean/no-upstream status");
    var remote = Path.Combine(root, "remote"); Directory.CreateDirectory(remote);
    await Git(remote, "init", "--bare", "-b", "main"); await Git(repo, "remote", "add", "origin", remote); await Git(repo, "push", "-u", "origin", "main");
    await Git(repo, "mv", "file.txt", "renamed name.txt");
    File.WriteAllText(Path.Combine(repo, "zażółć name.txt"), "untracked\n");
    status = await DashboardInspector.Inspect("p", "r", repo);
    Check(status.Error == null && status.Changed == 2 && status.Files.Contains("renamed name.txt") && status.Files.Contains("zażółć name.txt") && status.Ahead == 0 && status.Behind == 0, "Rename/untracked/Unicode parsing");
    await Git(repo, "commit", "-m", "rename");
    var other = Path.Combine(root, "other");
    await Git(root, "clone", remote, other);
    File.WriteAllText(Path.Combine(other, "remote.txt"), "remote\n");
    await Git(other, "add", "."); await Git(other, "commit", "-m", "remote change"); await Git(other, "push"); await Git(repo, "fetch");
    status = await DashboardInspector.Inspect("p", "r", repo);
    Check(status.Ahead == 1 && status.Behind == 1, "Diverged branch counts");
    await Git(repo, "checkout", "--detach");
    status = await DashboardInspector.Inspect("p", "r", repo);
    Check(status.Branch == "(detached)" && status.Upstream == null, "Detached HEAD");
    var nested = Path.Combine(repo, "nested"); Directory.CreateDirectory(nested);
    Check((await DashboardInspector.Inspect("p", "r", nested)).Error != null, "Reject nested folder masquerading as root");
    Check((await DashboardInspector.Inspect("p", "r", Path.Combine(root, "missing"))).Error != null, "Missing folder");
    Check(DashboardInspector.FindTool("devshell-tool-does-not-exist") == null, "Missing tool");
    Console.WriteLine("PASS: clean, no upstream, rename, Unicode, diverged branches, detached HEAD, invalid roots, missing tools");
}
finally
{
    var full = Path.GetFullPath(root);
    if (!full.StartsWith(Path.GetFullPath(Path.GetTempPath()), StringComparison.OrdinalIgnoreCase) || !Path.GetFileName(full).StartsWith("devshell-git-test-")) throw new Exception("Unexpected cleanup path");
    foreach (var file in Directory.EnumerateFiles(full, "*", SearchOption.AllDirectories)) File.SetAttributes(file, FileAttributes.Normal);
    Directory.Delete(full, true);
}
