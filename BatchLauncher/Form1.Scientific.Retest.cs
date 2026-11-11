using System.Collections.Concurrent;
using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace BatchLauncher;

public partial class Form1
{
    private sealed class ScientificRetestExecution
    {
        public required string PlanId { get; init; }
        public CancellationTokenSource Cancellation { get; } = new();
        public string? CurrentProvider { get; set; }
    }

    private readonly ConcurrentDictionary<string, ScientificRetestExecution> _scientificRetests = new();
    private static string ScientificRetestRoot => Path.Combine(ScientificDataRoot, "retest-plans");
    private static string ScientificRetestHash(string path) => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();

    private static JsonObject ScientificRetestRead(string id)
    {
        if (!Regex.IsMatch(id, "^[0-9a-f]{32}$")) throw new InvalidOperationException("Invalid retest plan ID.");
        var path = Path.Combine(ScientificRetestRoot, id, "retest-plan.json");
        var seal = path + ".sha256";
        if (!File.Exists(path) || !File.Exists(seal) || new FileInfo(path).Length > 524288
            || ScientificRetestHash(path) != File.ReadAllText(seal).Trim())
            throw new InvalidDataException("Retest plan hash changed.");
        var plan = JsonNode.Parse(File.ReadAllText(path)) as JsonObject;
        if (plan?["schemaVersion"]?.GetValue<int>() != 1 || plan["kind"]?.GetValue<string>() != "scientific.retest-plan"
            || plan["suites"] is not JsonArray) throw new InvalidDataException("Invalid retest plan.");
        var graph = Path.Combine(ScientificSourceRoot, "schemas", "scientific-retest-graph.v1.json");
        if (plan["graphSha256"]?.GetValue<string>() != ScientificRetestHash(graph))
            throw new InvalidDataException("Retest graph changed; create a new plan.");
        return plan;
    }

    private static string ScientificRetestBase(string profileId)
    {
        var root = Path.Combine(ScientificDataRoot, "runs");
        if (Directory.Exists(root))
            foreach (var directory in new DirectoryInfo(root).EnumerateDirectories()
                .OrderByDescending(item => item.LastWriteTimeUtc))
            {
                try
                {
                    var resultPath = Path.Combine(directory.FullName, "results.json");
                    if (!File.Exists(resultPath)) continue;
                    var result = JsonNode.Parse(File.ReadAllText(resultPath));
                    if (result?["profileId"]?.GetValue<string>() != profileId) continue;
                    var hash = result["sourceSnapshotSha256"]?.GetValue<string>();
                    if (hash == null) continue;
                    var snapshot = ScientificSourceSnapshot.Verify(directory.FullName, hash);
                    var commit = snapshot["repositories"]?["devshell"]?["commit"]?.GetValue<string>();
                    if (commit != null && Regex.IsMatch(commit, "^[0-9a-f]{40}$")) return commit;
                }
                catch (Exception error) when (error is IOException or JsonException or InvalidDataException
                    or InvalidOperationException or UnauthorizedAccessException) { }
            }
        return "origin/main";
    }

    private static IReadOnlyList<string> ScientificRetestEnvironmentChanges(string profileId)
    {
        var changed = new List<string>();
        var root = Path.Combine(ScientificDataRoot, "runs");
        if (!Directory.Exists(root)) return changed;
        foreach (var (runtimeId, key) in new[] { ("cgal-win-conda", "cgal.packages"),
            ("vtk-win-conda", "vtk.packages"), ("gmsh-win-conda", "gmsh.packages") })
        {
            foreach (var directory in new DirectoryInfo(root).EnumerateDirectories()
                .OrderByDescending(item => item.LastWriteTimeUtc))
            {
                try
                {
                    var result = JsonNode.Parse(File.ReadAllText(Path.Combine(directory.FullName, "results.json")));
                    if (result?["profileId"]?.GetValue<string>() != profileId
                        || result["runtimeId"]?.GetValue<string>() != runtimeId
                        || result["runFingerprintSha256"]?.GetValue<string>() is not { } hash) continue;
                    ScientificRunFingerprint.Verify(directory.FullName, hash);
                    var drift = ScientificRunFingerprint.AssessEnvironmentDrift(directory.FullName,
                        AppContext.BaseDirectory, ScientificReportPath());
                    if (drift["state"]?.GetValue<string>() != "current") changed.Add(key);
                    break;
                }
                catch (Exception error) when (error is IOException or JsonException or InvalidDataException
                    or InvalidOperationException or UnauthorizedAccessException) { }
            }
        }
        return changed;
    }

    private JsonObject ScientificRetestPlan(string profileId, JsonElement request)
    {
        var baseRevision = request.TryGetProperty("base", out var baseline) && baseline.ValueKind == JsonValueKind.String
            ? baseline.GetString() ?? "" : ScientificRetestBase(profileId);
        if (baseRevision != "origin/main" && !Regex.IsMatch(baseRevision, "^[0-9a-f]{40}$"))
            throw new InvalidOperationException("Choose a saved 40-digit source commit or origin/main.");
        var python = Path.Combine(ScientificRuntimeRoot(), "devshell-cgal", "python.exe");
        if (!File.Exists(python)) python = ScientificExecutable("python.exe");
        var script = Path.Combine(ScientificSourceRoot, "tools", "scientific-broker", "retest.py");
        var start = new ProcessStartInfo(python) { WorkingDirectory = ScientificSourceRoot,
            UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true };
        foreach (var argument in new[] { script, "--base", baseRevision, "--output-root", ScientificRetestRoot,
            "--include-worktree" }) start.ArgumentList.Add(argument);
        foreach (var key in ScientificRetestEnvironmentChanges(profileId))
        { start.ArgumentList.Add("--environment-changed"); start.ArgumentList.Add(key); }
        if (request.TryGetProperty("changedEnvironment", out var environment) && environment.ValueKind == JsonValueKind.Array)
            foreach (var item in environment.EnumerateArray())
            {
                var value = item.GetString() ?? "";
                if (!Regex.IsMatch(value, "^[a-z][a-z0-9.-]{1,60}$")) throw new InvalidOperationException("Invalid environment key.");
                start.ArgumentList.Add("--environment-changed"); start.ArgumentList.Add(value);
            }
        using var process = Process.Start(start) ?? throw new IOException("Could not start the retest planner.");
        var output = process.StandardOutput.ReadToEndAsync();
        var error = process.StandardError.ReadToEndAsync();
        if (!process.WaitForExit(120000)) { process.Kill(entireProcessTree: true); throw new TimeoutException("Retest planning timed out."); }
        if (process.ExitCode != 0) throw new InvalidOperationException(error.GetAwaiter().GetResult());
        var summary = JsonNode.Parse(output.GetAwaiter().GetResult());
        var path = summary?["record"]?.GetValue<string>() ?? throw new InvalidDataException("No saved retest plan.");
        var id = Path.GetFileName(Path.GetDirectoryName(path)) ?? throw new InvalidDataException("No retest plan ID.");
        var plan = ScientificRetestRead(id);
        plan["planId"] = id;
        plan["baseline"] = baseRevision;
        plan["profileId"] = profileId;
        File.WriteAllText(path, plan.ToJsonString(), new UTF8Encoding(false));
        File.WriteAllText(path + ".sha256", ScientificRetestHash(path), new UTF8Encoding(false));
        return ScientificRetestRead(id);
    }

    private JsonObject ScientificRetestStatus(string profileId, string id)
    {
        var plan = ScientificRetestRead(id);
        if (plan["profileId"]?.GetValue<string>() != profileId)
            throw new InvalidOperationException("Retest plan belongs to another profile.");
        var state = Path.Combine(ScientificRetestRoot, id, "execution.json");
        plan["execution"] = File.Exists(state) ? JsonNode.Parse(File.ReadAllText(state)) : null;
        return plan;
    }

    private object ScientificRetestStart(string profileId, string id)
    {
        var plan = ScientificRetestRead(id);
        if (plan["profileId"]?.GetValue<string>() != profileId)
            throw new InvalidOperationException("Retest plan belongs to another profile.");
        if (_scientificRetests.TryGetValue(profileId, out var existing)
            && !existing.Cancellation.IsCancellationRequested)
            throw new InvalidOperationException("A retest plan is already running.");
        var execution = new ScientificRetestExecution { PlanId = id };
        _scientificRetests[profileId] = execution;
        _ = Task.Run(() => ScientificRetestRun(profileId, plan, execution));
        return ScientificRetestStatus(profileId, id);
    }

    private async Task ScientificRetestRun(string profileId, JsonObject plan, ScientificRetestExecution execution)
    {
        var id = execution.PlanId;
        var path = Path.Combine(ScientificRetestRoot, id, "execution.json");
        var outcomes = new JsonArray();
        var state = "running";
        void Save()
        {
            var record = new JsonObject { ["schemaVersion"] = 1, ["planId"] = id, ["state"] = state,
                ["updatedAtUtc"] = DateTimeOffset.UtcNow.ToString("O"), ["suites"] = outcomes.DeepClone() };
            var temporary = path + ".tmp";
            File.WriteAllText(temporary, record.ToJsonString(), new UTF8Encoding(false));
            File.Move(temporary, path, true);
            ScientificSend(new { type = "scientific.runtime.retest", profileId, planId = id, execution = record });
        }
        try
        {
            Save();
            foreach (var suite in plan["suites"]!.AsArray().OfType<JsonObject>())
            {
                if (execution.Cancellation.IsCancellationRequested) { state = "cancelled"; break; }
                var suiteId = suite["id"]!.GetValue<string>();
                var provider = suite["provider"]!.GetValue<string>();
                var action = suite["managedAction"]?.GetValue<string>();
                if (suite["runner"]?.GetValue<string>() != "managed" || action == null)
                {
                    outcomes.Add(new JsonObject { ["id"] = suiteId, ["state"] = "pending-external" });
                    Save(); continue;
                }
                if (action != "lab-probe" && action != "recipe" && action != "gmsh-volume-product-readiness"
                    && !Regex.IsMatch(action, "^l[5-9]-[a-z0-9-]+$"))
                    throw new InvalidDataException("Retest action is outside the managed allowlist.");
                if (action == "recipe" && suite["recipeId"]?.GetValue<string>() != "compile-link")
                    throw new InvalidDataException("Retest recipe is outside the managed allowlist.");
                ScientificProviderRegistry.RequireAction(provider, action);
                execution.CurrentProvider = provider;
                _scientificJobs.TryGetValue(profileId + ":" + provider, out var previous);
                var command = new JsonObject { ["profileId"] = profileId, ["runtimeId"] = provider,
                    ["requestId"] = Guid.NewGuid().ToString("N"), ["action"] = action };
                if (action == "recipe") command["recipeId"] = suite["recipeId"]?.DeepClone();
                await HandleScientificRuntimeAsync(JsonSerializer.SerializeToElement(command));
                if (!_scientificJobs.TryGetValue(profileId + ":" + provider, out var job) || job.Id == previous?.Id)
                    throw new InvalidOperationException("Managed retest did not start: " + suiteId);
                outcomes.Add(new JsonObject { ["id"] = suiteId, ["state"] = "running", ["runId"] = job.Id });
                Save();
                while (job.State == "running" && !execution.Cancellation.IsCancellationRequested)
                    await Task.Delay(300);
                if (execution.Cancellation.IsCancellationRequested) job.Cancellation.Cancel();
                while (job.State == "running") await Task.Delay(300);
                var outcome = outcomes.Last()!.AsObject();
                outcome["state"] = job.State;
                if (job.Result is { } result && result.TryGetProperty("qualificationSha256", out var qualification))
                    outcome["qualificationSha256"] = qualification.GetString();
                Save();
                if (job.State != "succeeded" || outcome["qualificationSha256"] == null)
                { state = execution.Cancellation.IsCancellationRequested ? "cancelled" : "failed"; break; }
            }
            if (state == "running") state = outcomes.Any(item => item?["state"]?.GetValue<string>() == "pending-external")
                ? "managed-complete-external-pending" : "passed";
        }
        catch (Exception error)
        {
            state = "failed";
            outcomes.Add(new JsonObject { ["state"] = "failed", ["reason"] = error.Message });
        }
        finally
        {
            execution.CurrentProvider = null;
            Save();
            _scientificRetests.TryRemove(profileId, out _);
        }
    }

    private object ScientificRetestStop(string profileId, string id)
    {
        if (!_scientificRetests.TryGetValue(profileId, out var execution) || execution.PlanId != id)
            throw new InvalidOperationException("Retest plan is not running.");
        execution.Cancellation.Cancel();
        if (execution.CurrentProvider != null && _scientificJobs.TryGetValue(profileId + ":" + execution.CurrentProvider, out var job))
            job.Cancellation.Cancel();
        return ScientificRetestStatus(profileId, id);
    }
}
