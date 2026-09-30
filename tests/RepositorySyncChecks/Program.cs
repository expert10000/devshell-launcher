using BatchLauncher;

static void Check(bool value, string message) { if (!value) throw new Exception(message); }
static async Task Git(string cwd, params string[] arguments)
{
    var result = await DashboardInspector.Run("git", new[] { "-C", cwd, "-c", "user.name=DevShell Test", "-c", "user.email=devshell-test@example.invalid" }.Concat(arguments));
    Check(result.Code == 0, result.Error);
}
var shell = args[0];
var helper = Path.GetFullPath(args[1]);
var root = Path.Combine(Path.GetTempPath(), "devshell-sync-test-" + Guid.NewGuid().ToString("N"));
Directory.CreateDirectory(root);
var remote = Path.Combine(root, "remote.git");
var source = Path.Combine(root, "source");
var target = Path.Combine(root, "cloned ' unicode ż");
await Git(root, "init", "--bare", "-b", "main", remote);
await Git(root, "init", "-b", "main", source);
await File.WriteAllTextAsync(Path.Combine(source, "file.txt"), "initial");
await Git(source, "add", "."); await Git(source, "commit", "-m", "initial");
await Git(source, "remote", "add", "origin", remote); await Git(source, "push", "-u", "origin", "main");
const string url = "https://devshell.invalid/repository.git";
string Quote(string value) => "'" + value.Replace("'", "''") + "'";
using var runner = new RepositoryRunner();
RepositoryCommand Command(string action, string path, string? configuredUrl = url)
{
    var command = RepositoryGitCommand.Create(shell, helper, path, configuredUrl, action, root);
    // Redirect this test HTTPS origin to an isolated bare repository. No network or global Git config is used.
    return command with { Script = "$env:GIT_CONFIG_COUNT='1'; $env:GIT_CONFIG_KEY_0=" + Quote("url." + remote.Replace('\\', '/') + ".insteadOf")
        + "; $env:GIT_CONFIG_VALUE_0=" + Quote(url) + ";\n" + command.Script };
}
async Task<RepositoryJobStatus> Run(string action, string path, string? configuredUrl = url)
{
    Check(runner.Start("git", null, Command(action, path, configuredUrl), root, action), "Git action could not start");
    return await runner.Completion("git").WaitAsync(TimeSpan.FromSeconds(30));
}
var job = await Run("clone", target);
Check(job.State == "succeeded" && File.Exists(Path.Combine(target, "file.txt")), "Clone failed: " + job.Log);
await File.WriteAllTextAsync(Path.Combine(source, "remote.txt"), "remote change");
await Git(source, "add", "."); await Git(source, "commit", "-m", "remote change"); await Git(source, "push");
await File.WriteAllTextAsync(Path.Combine(target, "local.txt"), "keep me");
job = await Run("fetch", target);
Check(job.State == "succeeded" && !File.Exists(Path.Combine(target, "remote.txt")), "Fetch changed working files or rejected a dirty tree: " + job.Log);
Check((await DashboardInspector.Inspect("p", "r", target)).Behind == 1, "Fetch did not refresh upstream counts");
job = await Run("pull", target);
Check(job.State == "failed" && job.Log.Contains("Local changes") && File.ReadAllText(Path.Combine(target, "local.txt")) == "keep me", "Dirty pull was not protected");
File.Delete(Path.Combine(target, "local.txt"));
job = await Run("pull", target);
Check(job.State == "succeeded" && File.Exists(Path.Combine(target, "remote.txt")), "Clean fast-forward failed: " + job.Log);
job = await Run("pull", target, "https://devshell.invalid/unexpected.git");
Check(job.State == "failed" && job.Log.Contains("Unexpected origin"), "Unexpected origin was not rejected");
await File.WriteAllTextAsync(Path.Combine(target, "diverged.txt"), "local"); await Git(target, "add", "."); await Git(target, "commit", "-m", "local diverged");
await File.WriteAllTextAsync(Path.Combine(source, "second.txt"), "remote"); await Git(source, "add", "."); await Git(source, "commit", "-m", "remote diverged"); await Git(source, "push");
job = await Run("pull", target);
Check(job.State == "failed" && !File.Exists(Path.Combine(target, "second.txt")), "Diverged pull was not refused");
await Git(target, "checkout", "--detach");
job = await Run("pull", target); Check(job.State == "failed" && job.Log.Contains("detached HEAD"), "Detached pull was not refused");
var occupied = Path.Combine(root, "occupied"); Directory.CreateDirectory(occupied); File.WriteAllText(Path.Combine(occupied, "keep.txt"), "safe");
job = await Run("clone", occupied);
Check(job.State == "failed" && File.ReadAllText(Path.Combine(occupied, "keep.txt")) == "safe", "Clone overwrote a nonempty folder");
job = await Run("clone", Path.Combine(root, "no-url"), null); Check(job.State == "failed" && job.Log.Contains("Configure a repository URL"), "Missing clone URL was not reported");

using var queue = new RepositoryUpdateQueue(runner);
async Task<RepositoryUpdateStatus> WaitQueue()
{
    for (var i = 0; i < 300; i++) { var status = queue.Snapshot().Single(); if (status.State != "running") return status; await Task.Delay(100); }
    throw new Exception("Queue did not finish");
}
queue.Start("profile", new() {
    new("q1", "Successful clone", () => Command("sync", Path.Combine(root, "queue-one"))),
    new("q2", "Protected folder", () => Command("sync", occupied)),
    new("q3", "Continue after failure", () => Command("sync", Path.Combine(root, "queue-three")))
}, root);
var batch = await WaitQueue();
Check(batch.State == "completed-with-errors" && batch.Completed == 3 && batch.Results.Select(result => result.State).SequenceEqual(new[] { "succeeded", "failed", "succeeded" }), "Queue did not preserve individual results and continue after failure");
queue.Start("profile", new() {
    new("slow", "Active job", () => new(shell, "Write-Output 'STARTED'; Start-Sleep 60", root)),
    new("pending", "Pending job", () => new(shell, "Write-Output 'MUST NOT RUN'", root))
}, root);
for (var i = 0; i < 100 && !runner.Snapshot().Any(item => item.Key == "slow" && item.Log.Contains("STARTED")); i++) await Task.Delay(100);
queue.Stop(); batch = await WaitQueue();
Check(batch.State == "stopped" && batch.Results[0].State == "stopped" && batch.Results[1].State == "skipped" && !runner.Snapshot().Any(item => item.Key == "pending"), "Stop did not cancel the active job and skip pending work");

var environmentPath = Path.Combine(root, "environment"); Directory.CreateDirectory(environmentPath);
File.WriteAllText(Path.Combine(environmentPath, "package.json"), "{\"dependencies\":{\"fake-package\":\"1.0.0\"},\"devDependencies\":{\"@scope/fake-dev\":\"1.0.0\"}}");
var checks = await RepositoryEnvironment.Inspect("p", "r", environmentPath, new[] { "missing-devshell-tool" }, Path.Combine(root, "missing-python"));
Check(checks.Any(check => check.Name == "Node packages" && check.State == "error" && check.Detail.Contains("2 missing")) && checks.Any(check => check.Name == "missing-devshell-tool" && check.State == "error") && checks.Any(check => check.Name == "Python environment" && check.State == "error"), "Missing environment dependencies were not detected");
Check(checks.All(check => check.ProjectId == "p" && check.RepositoryId == "r"), "Environment checks are not associated with their repository");
foreach (var name in new[] { "fake-package", "@scope/fake-dev" }) { var folder = Path.Combine(environmentPath, "node_modules", name); Directory.CreateDirectory(folder); File.WriteAllText(Path.Combine(folder, "package.json"), "{}"); }
checks = await RepositoryEnvironment.Inspect("p", "r", environmentPath, Array.Empty<string>());
Check(checks.Any(check => check.Name == "Node packages" && check.State == "ok"), "Installed Node packages were not recognized");
Console.WriteLine("PASS: Clone, dirty Fetch, safe fast-forward Pull, dirty/diverged/detached/origin/nonempty safeguards, Update All results/continuation/Stop, repository dependency checks");
