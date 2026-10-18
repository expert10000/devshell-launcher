using BatchLauncher;
using System.Text.Json;

static void Check(bool value, string message) { if (!value) throw new Exception(message); }
static void Reject(Action action, string message) { try { action(); } catch (Exception) { return; } throw new Exception(message); }
// A disposable runtime-only dotnet shim for SDK diagnostics; never installs software.
if (args.Length == 1 && args[0] == "--list-sdks") return;
var shell = args[0]; var python = args[1]; var node = args[2]; var helper = Path.GetFullPath(args[3]);
var root = Path.Combine(Path.GetTempPath(), "devshell-setup-test-" + Guid.NewGuid().ToString("N"));
Directory.CreateDirectory(root);
var newRoot = Path.Combine(root, "new root ' ż");
var tools = PortableWorkspace.DiscoverTools(root);
tools["pwsh"] = shell; tools["python"] = python; tools["node"] = node;

if (args.Length > 4)
{
    var sourceProfile = JsonSerializer.Deserialize<WorkspaceConfig>(File.ReadAllText(args[4]), new JsonSerializerOptions { PropertyNameCaseInsensitive = true })!;
    var workspace = PortableWorkspace.Resolve(sourceProfile, detectedTools: tools);
    Check(Path.IsPathFullyQualified(workspace.Globals!.WorkspaceRoot!), "Profile default root is invalid");
    if (args.Length > 5)
    {
        var project = workspace.Projects!.Single(item => item.Id == args[5]);
        var repository = args.Length > 6 ? project.Repositories!.Single(item => item.Id == args[6]) : new WorkspaceRepository { Path = project.Root!,
            PythonEnvironment = project.PythonEnvironment, PythonModules = project.PythonModules, PythonPackages = project.PythonPackages };
        var target = JsonSerializer.Deserialize<WorkspaceRepository>(JsonSerializer.Serialize(repository))!;
        var variables = new Dictionary<string, string>(workspace.Globals!.Vars!);
        foreach (var pair in project.Vars ?? new()) variables[pair.Key] = pair.Value;
        target.Path = PortableWorkspace.Expand(target.Path, variables);
        if (target.PythonEnvironment != null) target.PythonEnvironment = PortableWorkspace.Expand(target.PythonEnvironment, variables);
        tools["workspaceRoot"] = workspace.Globals.WorkspaceRoot!;
        if (args.Length > 7 && args[7] == "inspect")
        {
            var configuredChecks = await RepositoryEnvironment.InspectRepository(project.Id, target.Id, target, tools);
            foreach (var check in configuredChecks) Console.WriteLine($"{check.State}: {check.Name} · {check.Detail}");
            Check(configuredChecks.All(check => check.State != "error"), "Configured environment has blocking requirements");
            return;
        }
        var setup = EnvironmentSetup.Plan(target, workspace.Globals.WorkspaceRoot!, tools, python, args.Length > 7 ? args[7].Split(',') : null);
        Console.WriteLine(JsonSerializer.Serialize(setup, new JsonSerializerOptions { WriteIndented = true }));
        using var actualRunner = new RepositoryRunner();
        actualRunner.Start("actual", null, EnvironmentSetup.Command(shell, helper, setup, root), root, "setup", stepCount: setup.Steps.Count);
        var outcome = await actualRunner.Completion("actual").WaitAsync(TimeSpan.FromMinutes(10));
        Console.WriteLine(outcome.Log);
        Check(outcome.State == "succeeded", "Actual setup did not succeed");
        return;
    }
}

var source = new WorkspaceConfig { Globals = new() { AutoDetectTools = true, WorkspaceRoot = "D:\\masters", Vars = new() {
    ["repo"] = "${workspaceRoot}\\repo", ["env"] = "${workspaceRoot}\\.venvs\\repo", ["python"] = "${vars.env}\\Scripts\\python.exe", ["nodeDirectory"] = "${workspaceRoot}\\missing-node" } },
    Projects = new() { new() { Id = "p", Root = "${workspaceRoot}", Vars = new() { ["nested"] = "${vars.repo}\\nested" },
        Repositories = new() { new() { Id = "r", Path = "${workspaceRoot}\\repo" } } } } };
var before = JsonSerializer.Serialize(source);
var resolved = PortableWorkspace.Resolve(source, newRoot, tools);
Check(resolved.Globals!.WorkspaceRoot == newRoot && resolved.Projects![0].Repositories![0].Path == Path.Combine(newRoot, "repo")
    && resolved.Globals.Vars!["python"] == Path.Combine(newRoot, ".venvs", "repo", "Scripts", "python.exe") && resolved.Globals.Vars["nodeDirectory"] == Path.GetDirectoryName(node)
    && resolved.Projects[0].Vars!["nested"] == Path.Combine(newRoot, "repo", "nested"), "Portable path or tool resolution failed");
Check(JsonSerializer.Serialize(source) == before, "Resolution modified the shared profile");
var settings = new WorkspaceRootStore(Path.Combine(root, "device-settings.json"));
settings.Save("laptop", newRoot); settings.Save("portable", Path.Combine(root, "second"));
Check(settings.Get("laptop") == newRoot && settings.Get("portable") != newRoot, "Root choices are not independent per profile");
Reject(() => settings.Save("laptop", "relative-folder"), "Relative workspace root accepted");
Reject(() => PortableWorkspace.Expand("${vars.a}", new Dictionary<string, string> { ["a"] = "${vars.a}x" }), "Expanding variable cycle was not rejected");
Reject(() => EnvironmentSetup.Within(newRoot, "..\\escape"), "Dependency path escaped the repository");

var fixture = Path.Combine(root, "fixture ' ż"); Directory.CreateDirectory(fixture);
File.WriteAllText(Path.Combine(fixture, "package.json"), "{\"name\":\"devshell-offline-fixture\",\"version\":\"1.0.0\",\"private\":true}");
File.WriteAllText(Path.Combine(fixture, "package-lock.json"), "{\"name\":\"devshell-offline-fixture\",\"version\":\"1.0.0\",\"lockfileVersion\":3,\"packages\":{\"\":{\"name\":\"devshell-offline-fixture\",\"version\":\"1.0.0\"}}}");
File.WriteAllText(Path.Combine(fixture, "requirements.txt"), "# No external packages required by this isolated fixture.\n");
var environment = Path.Combine(root, ".venvs", "fixture ' ż");
var repo = new WorkspaceRepository { Path = fixture, PythonEnvironment = environment, PythonModules = new() { "json" } };
var plan = EnvironmentSetup.Plan(repo, root, tools, python);
Check(plan.Issues.Count == 0 && plan.Steps.Any(step => step.Kind == "node" && step.Arguments![0] == "ci") && plan.Steps.Any(step => step.Kind == "python-create"), "Setup plan does not respect lockfiles and isolated environments");
using var runner = new RepositoryRunner();
async Task<RepositoryJobStatus> Run(string key, EnvironmentSetupPlan setup)
{
    Check(runner.Start(key, null, EnvironmentSetup.Command(shell, helper, setup, root), root, "setup", stepCount: setup.Steps.Count), "Setup launch failed");
    return await runner.Completion(key).WaitAsync(TimeSpan.FromSeconds(90));
}
var job = await Run("success", plan);
Check(job.State == "succeeded" && job.CompletedSteps == plan.Steps.Count && File.Exists(Path.Combine(environment, "Scripts", "python.exe"))
    && File.ReadAllText(job.LogPath).Contains("[setup] SUCCEEDED"), "Setup execution/progress/logs failed: " + job.Log);
job = await Run("reuse", plan); Check(job.State == "succeeded", "Existing environment cannot be reused: " + job.Log);
// One repair must not reinstall unrelated Node/.NET dependencies or be blocked by an unrelated manual tool.
File.WriteAllText(Path.Combine(fixture, "package.json"), "{\"engines\":{\"node\":\">=999.0.0\"},\"packageManager\":\"npm@99.0.0\",\"dependencies\":{\"missing-package\":\"^2.0.0\"}}");
File.WriteAllText(Path.Combine(fixture, "Example.csproj"), "<Project Sdk=\"Microsoft.NET.Sdk\"><PropertyGroup><TargetFramework>net9.0</TargetFramework></PropertyGroup></Project>");
repo.RequiredTools = new() { "manual-devshell-tool" };
var scoped = EnvironmentSetup.Plan(repo, root, tools, python, new[] { "python" });
Check(scoped.Issues.Count == 0 && scoped.Steps.All(step => step.Target == "python") && scoped.Targets.SequenceEqual(new[] { "python" }), "Python repair included unrelated installs or manual tool issues");
job = await Run("python-only", scoped); Check(job.State == "succeeded" && !job.Log.Contains("npm") && !job.Log.Contains("dotnet"), "Targeted Python repair executed unrelated commands");
Reject(() => EnvironmentSetup.Plan(repo, root, tools, python, new[] { "node:../escape" }), "Undeclared repair target was accepted");
var checks = await RepositoryEnvironment.InspectRepository("p", "r", repo, tools);
Check(checks.Any(check => check.Name == "Node version" && check.State == "error" && check.FixTarget == "node:.")
    && checks.Any(check => check.Name == "Package manager" && check.State == "error" && check.FixTarget == "node:.")
    && checks.Any(check => check.Name == "manual-devshell-tool" && check.FixTarget == null && check.Guidance != null), "Version mismatch or manual guidance missing");
var dotnetTools = new Dictionary<string, string>(tools) { ["dotnet"] = System.Diagnostics.Process.GetCurrentProcess().MainModule!.FileName! };
checks = await RepositoryEnvironment.InspectRepository("p", "r", repo, dotnetTools);
Check(checks.Any(check => check.Name == ".NET SDK" && check.State == "error" && check.Detail.Contains("runtime alone") && check.FixTarget == "dotnet:."), "Runtime-only .NET was reported ready");
Check(checks.Any(check => check.Name.StartsWith(".NET packages") && check.State == "error" && check.FixTarget == "dotnet:."), "Missing NuGet restore was reported ready");
File.WriteAllText(Path.Combine(fixture, "global.json"), "{\"sdk\":{\"version\":\"0.0.999\",\"rollForward\":\"disable\"}}");
checks = await RepositoryEnvironment.InspectRepository("p", "r", repo, tools);
Check(checks.Any(check => check.Name == ".NET SDK selection" && check.State == "error" && check.FixTarget == null && check.Guidance!.Contains("global.json")), "Unavailable pinned SDK was missed or offered an unrelated automatic install");
File.Delete(Path.Combine(fixture, "global.json"));
var baseEnvironment = new WorkspaceRepository { Path = fixture, PythonEnvironment = python, PythonPackages = new() { "pip" } };
Reject(() => EnvironmentSetup.Plan(baseEnvironment, root, tools, python, new[] { "python" }), "Repair was allowed to modify the base Python installation");
scoped = EnvironmentSetup.Plan(repo, root, tools, python, new[] { "dotnet:." });
Check(scoped.Steps.Count == 1 && scoped.Steps[0].MinimumMajor == 9 && scoped.Steps[0].Tool == "dotnet", "SDK repair did not use the project's target framework");
File.WriteAllText(Path.Combine(fixture, "included.txt"), "pip>=99999\n");
File.WriteAllText(Path.Combine(fixture, "requirements.txt"), "-r included.txt\n");
checks = await RepositoryEnvironment.Inspect("p", "r", fixture, Array.Empty<string>(), environment,
    new() { "devshell_missing_one", "devshell_missing_two" }, tools, pythonOptionalModules: new() { "devshell_optional_native" });
Check(checks.Any(check => check.Name == "Python modules" && check.Detail.Contains("devshell_missing_one") && check.Detail.Contains("devshell_missing_two") && !check.Detail.Contains("Traceback"))
    && checks.Any(check => check.Name == "Python requirements" && check.State == "error" && check.Detail.Contains("pip>=99999"))
    && checks.Any(check => check.Optional && check.State == "warning" && check.FixTarget == null), "Python dependency details, recursive requirements, or optional warning classification failed");
File.WriteAllText(Path.Combine(fixture, "requirements.txt"), "# offline fixture\n");
var nested = Path.Combine(fixture, "renderer"); Directory.CreateDirectory(nested);
File.WriteAllText(Path.Combine(nested, "package.json"), "{\"dependencies\":{\"@scope/shared\":\"^1.0.0\"}}");
var shared = Path.Combine(fixture, "node_modules", "@scope", "shared"); Directory.CreateDirectory(shared);
File.WriteAllText(Path.Combine(shared, "package.json"), "{\"version\":\"1.5.0\"}");
checks = await RepositoryEnvironment.Inspect("p", "r", nested, Array.Empty<string>(), toolPaths: tools, repositoryRoot: fixture, relativeDirectory: "renderer");
Check(checks.Any(check => check.Name == "Node packages" && check.State == "ok"), "Hoisted dependencies were incorrectly reported missing");
File.WriteAllText(Path.Combine(shared, "package.json"), "{\"version\":\"2.0.0\"}");
checks = await RepositoryEnvironment.Inspect("p", "r", nested, Array.Empty<string>(), toolPaths: tools, repositoryRoot: fixture, relativeDirectory: "renderer");
Check(checks.Any(check => check.Name == "Node packages" && check.State == "error" && check.FixTarget == "node:renderer" && check.Detail.Contains("Incompatible")), "Installed dependency version mismatch was missed");
repo.DependencyFolders = new() { "renderer" };
scoped = EnvironmentSetup.Plan(repo, root, tools, python, new[] { "node:renderer" });
Check(scoped.Steps.Count == 1 && scoped.Steps[0].Directory == nested && scoped.Steps[0].Target == "node:renderer", "Nested Node repair included root or Python steps");
Console.WriteLine("PASS: targeted repairs, Node/manager/package versions, hoisted dependencies, runtime-only SDK, Python details and recursive requirements, optional/manual guidance");
// Windows package-manager shims are version-scoped; testing them does not download packages.
File.WriteAllText(Path.Combine(fixture, "package.json"), "{\"packageManager\":\"yarn@1.22.21\",\"engines\":{\"node\":\">=8.0.0\"}}");
var managerDirectory = Path.Combine(root, ".tools", "package-managers", "yarn-1.22.21"); Directory.CreateDirectory(managerDirectory);
File.WriteAllText(Path.Combine(managerDirectory, "yarn.cmd"), "@echo off\r\nif \"%~1\"==\"--version\" (\r\n echo 1.22.21\r\n exit /b 0\r\n)\r\necho PINNED MANAGER %*\r\nexit /b 0\r\n");
tools["workspaceRoot"] = root;
checks = await RepositoryEnvironment.InspectRepository("p", "r", repo, tools);
Check(checks.Any(check => check.Name == "Package manager" && check.State == "ok"), "Version-scoped package manager was not discovered");
scoped = EnvironmentSetup.Plan(repo, root, tools, python, new[] { "node:." });
job = await Run("pinned-manager", scoped);
Check(job.State == "succeeded" && job.Log.Contains("PINNED MANAGER install --frozen-lockfile") && !job.Log.Contains("--global"), "Pinned manager reuse or Windows shim execution failed: " + job.Log);
var sentinel = Path.Combine(root, "should-not-run.txt");
var failure = new EnvironmentSetupPlan(root, tools, new() {
    new("First step", "note", root),
    new("Failing step", "command", root, "pwsh", new() { "-NoProfile", "-Command", "exit 7" }),
    new("Must not run", "command", root, "pwsh", new() { "-NoProfile", "-Command", "Set-Content -LiteralPath '" + sentinel + "' -Value wrong" })
}, new());
job = await Run("failure", failure);
Check(job.State == "failed" && job.CompletedSteps == 1 && !File.Exists(sentinel), "A failed setup did not stop subsequent steps");
var stop = new EnvironmentSetupPlan(root, tools, new() {
    new("Long step", "command", root, "pwsh", new() { "-NoProfile", "-Command", "Write-Output 'STARTED'; Start-Sleep 60" }),
    new("Must not run", "note", root)
}, new());
runner.Start("stop", null, EnvironmentSetup.Command(shell, helper, stop, root), root, "setup", stepCount: stop.Steps.Count);
for (var i = 0; i < 100 && !runner.Snapshot().Any(item => item.Key == "stop" && item.Log.Contains("STARTED\r")); i++) await Task.Delay(100);
runner.Stop("stop"); job = await runner.Completion("stop").WaitAsync(TimeSpan.FromSeconds(10));
Check(job.State == "stopped" && job.CompletedSteps == 0 && !job.Log.Contains("STEP 2/2"), "Stop did not cancel setup and suppress remaining steps");
Console.WriteLine("PASS: portable roots, device-local persistence, detected tools, nested variables, path confinement, real offline npm/venv setup and reuse, failure gating, progress/logs, Stop");
