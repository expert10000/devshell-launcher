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

    private static IReadOnlyList<(DateTime At, string Commit, JsonObject Snapshot, string Directory, string RuntimeId)> ScientificRetestL9Snapshots(string profileId)
    {
        var capabilities = new HashSet<string>(StringComparer.Ordinal)
            { "mesh.orient", "mesh.remesh", "mesh.repair", "mesh.generate3d", "mesh.read" };
        var latest = new Dictionary<string, (DateTime At, string Commit, JsonObject Snapshot, string Directory, string RuntimeId)>(StringComparer.Ordinal);
        var root = Path.Combine(ScientificDataRoot, "runs");
        if (Directory.Exists(root))
            foreach (var directory in new DirectoryInfo(root).EnumerateDirectories()
                .OrderByDescending(item => item.LastWriteTimeUtc))
            {
                try
                {
                    var (savedDirectory, result) = ScientificHistoryReadDirectory(profileId, directory.Name);
                    if (!result.TryGetProperty("sourceSnapshotSha256", out var reference)
                        || !result.TryGetProperty("qualificationSha256", out _)) continue;
                    var hash = reference.GetString();
                    if (hash == null) continue;
                    var snapshot = ScientificSourceSnapshot.Verify(savedDirectory, hash);
                    var commit = snapshot["repositories"]?["devshell"]?["commit"]?.GetValue<string>();
                    if (commit == null || !Regex.IsMatch(commit, "^[0-9a-f]{40}$")) continue;
                    var records = JsonNode.Parse(File.ReadAllText(Path.Combine(savedDirectory, "qualifications.json")))?["records"]?.AsArray();
                    if (records == null) continue;
                    foreach (var record in records.OfType<JsonObject>())
                    {
                        var capability = record["capabilityId"]?.GetValue<string>();
                        if (capability != null && capabilities.Contains(capability)
                            && record["level"]?.GetValue<string>() == "L9" && !latest.ContainsKey(capability))
                            latest[capability] = (directory.LastWriteTimeUtc, commit, snapshot, savedDirectory,
                                result.GetProperty("runtimeId").GetString() ?? "");
                    }
                    if (latest.Count == capabilities.Count) break;
                }
                catch (Exception error) when (error is IOException or JsonException or InvalidDataException
                    or InvalidOperationException or UnauthorizedAccessException) { }
            }
        return latest.Values.ToArray();
    }

    private static string ScientificRetestBase(string profileId) =>
        ScientificRetestL9Snapshots(profileId).OrderBy(item => item.At).FirstOrDefault().Commit ?? "origin/main";

    private static IReadOnlyList<string> ScientificRetestEnvironmentChanges(string profileId)
    {
        var changed = new HashSet<string>(StringComparer.Ordinal);
        foreach (var (_, _, snapshot, directory, runtimeId) in ScientificRetestL9Snapshots(profileId))
        {
            var key = runtimeId.StartsWith("cgal", StringComparison.Ordinal) ? "cgal.packages"
                : runtimeId.StartsWith("vtk", StringComparison.Ordinal) ? "vtk.packages" : "gmsh.packages";
            try
            {
                var drift = ScientificRunFingerprint.AssessEnvironmentDrift(directory,
                    AppContext.BaseDirectory, ScientificReportPath());
                if (drift["state"]?.GetValue<string>() != "current") changed.Add(key);
            }
            catch (Exception error) when (error is IOException or JsonException or InvalidDataException
                or InvalidOperationException or UnauthorizedAccessException) { changed.Add(key); }
            var math3d = snapshot["repositories"]?["math3d"];
            var path = math3d?["worktree"]?.GetValue<string>();
            if (path == null) continue;
            var current = ScientificSourceSnapshot.Capture(path)["repositories"]?["devshell"];
            if (current?["snapshotId"]?.GetValue<string>() != math3d?["snapshotId"]?.GetValue<string>())
                changed.Add("math3d.consumer");
        }
        return changed.ToArray();
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

    private bool ScientificRetestCurrent(string profileId, string suiteId, ScientificJob job)
    {
        var level = Regex.Match(suiteId, @"\.l([5-9])$").Groups[1].Value;
        if (level.Length == 0) return true;
        var capability = suiteId.StartsWith("cgal.orient.", StringComparison.Ordinal) ? "mesh.orient"
            : suiteId.StartsWith("cgal.remesh.", StringComparison.Ordinal) ? "mesh.remesh"
            : suiteId.StartsWith("cgal.repair.", StringComparison.Ordinal) ? "mesh.repair"
            : suiteId.StartsWith("gmsh.volume.", StringComparison.Ordinal) ? "mesh.generate3d"
            : suiteId.StartsWith("gmsh.", StringComparison.Ordinal) ? "mesh.generate"
            : suiteId.StartsWith("vtk.", StringComparison.Ordinal) ? "mesh.read" : "mesh.validate";
        var summary = ScientificQualificationSummary(profileId, job.RuntimeId);
        return summary["currentRecords"]?.AsArray().OfType<JsonObject>().Any(item =>
            item["runId"]?.GetValue<string>() == job.Id
            && item["capabilityId"]?.GetValue<string>() == capability
            && item["level"]?.GetValue<string>() == "L" + level) == true;
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
                var readiness = action == "gmsh-volume-product-readiness" && job.Result is { } readinessResult
                    && readinessResult.TryGetProperty("volumeProductReadiness", out var readinessEvidence)
                    && readinessEvidence.TryGetProperty("status", out var readinessStatus)
                    && readinessStatus.GetString() == "ready-for-l9";
                var current = job.State == "succeeded" && (readiness || outcome["qualificationSha256"] != null
                    && ScientificRetestCurrent(profileId, suiteId, job));
                if (!current && job.State == "succeeded") outcome["state"] = "stale-or-unqualified";
                Save();
                if (!current)
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
