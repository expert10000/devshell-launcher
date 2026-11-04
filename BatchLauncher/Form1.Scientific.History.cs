using System.Diagnostics;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace BatchLauncher;

public partial class Form1
{
    private static (string Directory, JsonElement Result) ScientificHistoryReadDirectory(string profileId, string folderName)
    {
        if (!Regex.IsMatch(folderName, "^[0-9a-f]{32}$")) throw new InvalidOperationException("Invalid run folder.");
        var root = Path.Combine(ScientificDataRoot, "runs");
        var path = ScientificScopedFile(root, folderName + "/results.json");
        if (!File.Exists(path) || new FileInfo(path).Length > 1048576)
            throw new InvalidOperationException("Run result is missing or too large.");
        using var document = JsonDocument.Parse(File.ReadAllText(path));
        var result = document.RootElement;
        if (result.ValueKind != JsonValueKind.Object
            || !result.TryGetProperty("runId", out var runId) || !Regex.IsMatch(runId.GetString() ?? "", "^[0-9a-f]{32}$")
            || !result.TryGetProperty("profileId", out var profile) || profile.GetString() != profileId)
            throw new InvalidOperationException("Run does not belong to this profile.");
        var directory = Path.GetDirectoryName(path)!;
        if (result.TryGetProperty("runFingerprintSha256", out var fingerprint))
            ScientificRunFingerprint.Verify(directory, fingerprint.GetString() ?? "");
        if (result.TryGetProperty("qualificationSha256", out _))
            ScientificQualificationRecords.Verify(directory, result);
        return (directory, ScientificArtifactFiles.RecoverLegacySmoke(directory, result.Clone()));
    }

    private static (string Directory, JsonElement Result) ScientificHistoryFind(string profileId, string jobId)
    {
        if (!Regex.IsMatch(jobId, "^[0-9a-f]{32}$")) throw new InvalidOperationException("Invalid run ID.");
        var root = Path.Combine(ScientificDataRoot, "runs");
        if (!Directory.Exists(root)) throw new InvalidOperationException("No saved runs are available.");
        foreach (var folder in new DirectoryInfo(root).EnumerateDirectories().Where(item => Regex.IsMatch(item.Name, "^[0-9a-f]{32}$")))
        {
            try
            {
                var record = ScientificHistoryReadDirectory(profileId, folder.Name);
                if (record.Result.GetProperty("runId").GetString() == jobId) return record;
            }
            catch (Exception exception) when (exception is IOException or InvalidDataException or JsonException or InvalidOperationException or UnauthorizedAccessException or KeyNotFoundException)
            {
                Debug.WriteLine($"Skipping invalid Scientific run: {exception.Message}");
            }
        }
        throw new InvalidOperationException("Run is unavailable in this profile.");
    }

    private static JsonElement ScientificHistoryResult(string profileId, string jobId)
    {
        var (directory, result) = ScientificHistoryFind(profileId, jobId);
        if (!result.TryGetProperty("runFingerprintSha256", out _)) return result;
        var view = JsonNode.Parse(result.GetRawText())!.AsObject();
        var sourceDrift = ScientificRunFingerprint.AssessSourceDrift(directory, ScientificSourceRoot, AppContext.BaseDirectory);
        view["sourceDrift"] = sourceDrift;
        var wsl = result.GetProperty("runtimeId").GetString() == "sage-wsl";
        var environmentDrift = ScientificRunFingerprint.AssessEnvironmentDrift(directory, AppContext.BaseDirectory,
            ScientificReportPath(), wsl ? Environment.GetEnvironmentVariable("MATH3D_WSL_DISTRO") ?? "Ubuntu" : null,
            wsl ? ScientificSageCurrentEvidence() : null);
        view["environmentDrift"] = environmentDrift;
        if (result.TryGetProperty("qualificationSha256", out _))
        {
            var assessed = ScientificQualificationRecords.Assess(
                ScientificQualificationRecords.Verify(directory, result), sourceDrift, environmentDrift);
            if (assessed.OfType<JsonObject>().Any(item => item["level"]?.GetValue<string>() is "L5" or "L6"))
            {
                var summary = ScientificQualificationSummary(profileId, result.GetProperty("runtimeId").GetString() ?? "");
                var current = summary["currentRecords"]?.AsArray().OfType<JsonObject>()
                    .Select(item => item["recordId"]?.GetValue<string>()).OfType<string>()
                    .ToHashSet(StringComparer.Ordinal) ?? new HashSet<string>(StringComparer.Ordinal);
                ScientificQualificationRecords.AssessL5Dependencies(assessed, current);
            }
            view["qualifications"] = assessed;
        }
        return JsonSerializer.SerializeToElement(view, ScientificJson);
    }

    private static object ScientificHistoryList(string profileId)
    {
        var root = Path.Combine(ScientificDataRoot, "runs");
        if (!Directory.Exists(root)) return Array.Empty<object>();
        var entries = new List<object>();
        foreach (var directory in new DirectoryInfo(root).EnumerateDirectories()
            .Where(item => Regex.IsMatch(item.Name, "^[0-9a-f]{32}$"))
            .OrderByDescending(item => item.LastWriteTimeUtc).Take(500))
        {
            try
            {
                var result = ScientificHistoryReadDirectory(profileId, directory.Name).Result;
                var artifacts = result.TryGetProperty("artifacts", out var files) && files.ValueKind == JsonValueKind.Array ? files.GetArrayLength() : 0;
                entries.Add(new
                {
                    jobId = result.GetProperty("runId").GetString(),
                    runtimeId = result.GetProperty("runtimeId").GetString(),
                    recipeId = result.GetProperty("recipeId").GetString(),
                    testCaseId = result.TryGetProperty("testCaseId", out var testCase) ? testCase.GetString() : null,
                    state = result.GetProperty("state").GetString(),
                    durationMs = result.GetProperty("durationMs").GetInt64(),
                    finishedAtUtc = File.GetLastWriteTimeUtc(Path.Combine(directory.FullName, "results.json")),
                    meshArtifactCount = files.ValueKind == JsonValueKind.Array ? files.EnumerateArray().Count(item => ScientificMeshExtensions.Contains(Path.GetExtension(item.GetProperty("path").GetString() ?? "").ToLowerInvariant())) : 0,
                    thumbnailPath = result.GetProperty("state").GetString() == "succeeded" && files.ValueKind == JsonValueKind.Array
                        ? files.EnumerateArray().Select(item => item.GetProperty("path").GetString()).FirstOrDefault(path => path != null && path.EndsWith(".png", StringComparison.OrdinalIgnoreCase)) : null,
                    artifactCount = artifacts
                });
            }
            catch (Exception exception) when (exception is IOException or InvalidDataException or JsonException or InvalidOperationException or UnauthorizedAccessException or KeyNotFoundException)
            {
                Debug.WriteLine($"Skipping invalid Scientific history entry: {exception.Message}");
            }
        }
        return entries;
    }

    private static JsonObject ScientificQualificationSummary(string profileId, string runtimeId)
    {
        ScientificProviderRegistry.Get(runtimeId);
        var root = Path.Combine(ScientificDataRoot, "runs");
        if (!Directory.Exists(root)) return ScientificQualificationRecords.Summarize(runtimeId, Array.Empty<JsonObject>());
        var wsl = runtimeId == "sage-wsl";
        var wslEvidence = wsl ? ScientificSageCurrentEvidence() : null;
        var runs = new List<JsonObject>();
        foreach (var folder in new DirectoryInfo(root).EnumerateDirectories()
            .Where(item => Regex.IsMatch(item.Name, "^[0-9a-f]{32}$"))
            .OrderByDescending(item => item.LastWriteTimeUtc))
        {
            try
            {
                var (directory, result) = ScientificHistoryReadDirectory(profileId, folder.Name);
                if (result.GetProperty("runtimeId").GetString() != runtimeId) continue;
                var run = new JsonObject { ["runId"] = result.GetProperty("runId").GetString(),
                    ["runtimeId"] = runtimeId, ["recipeId"] = result.GetProperty("recipeId").GetString(),
                    ["state"] = result.GetProperty("state").GetString(),
                    ["finishedAtUtc"] = File.GetLastWriteTimeUtc(Path.Combine(directory, "results.json")).ToString("O") };
                if (result.GetProperty("state").GetString() == "succeeded"
                    && result.TryGetProperty("qualificationSha256", out _))
                {
                    var source = ScientificRunFingerprint.AssessSourceDrift(directory, ScientificSourceRoot, AppContext.BaseDirectory);
                    var environment = ScientificRunFingerprint.AssessEnvironmentDrift(directory, AppContext.BaseDirectory,
                        ScientificReportPath(), wsl ? Environment.GetEnvironmentVariable("MATH3D_WSL_DISTRO") ?? "Ubuntu" : null,
                        wslEvidence);
                    run["qualifications"] = ScientificQualificationRecords.Assess(
                        ScientificQualificationRecords.Verify(directory, result), source, environment);
                }
                runs.Add(run);
            }
            catch (Exception exception) when (exception is IOException or InvalidDataException or JsonException
                or InvalidOperationException or UnauthorizedAccessException or KeyNotFoundException)
            {
                Debug.WriteLine($"Skipping invalid Scientific qualification run: {exception.Message}");
            }
        }
        var lowerIds = runs.SelectMany(run => run["qualifications"]?.AsArray().OfType<JsonObject>() ?? [])
            .Where(record => record["status"]?.GetValue<string>() == "current" && record["level"]?.GetValue<string>() is "L0" or "L1" or "L2" or "L3" or "L4")
            .Select(record => record["recordId"]?.GetValue<string>()).OfType<string>()
            .ToHashSet(StringComparer.Ordinal);
        foreach (var run in runs)
            if (run["qualifications"] is JsonArray records) ScientificQualificationRecords.AssessL5Dependencies(records, lowerIds, includeL6: false);
        lowerIds.UnionWith(runs.SelectMany(run => run["qualifications"]?.AsArray().OfType<JsonObject>() ?? [])
            .Where(record => record["status"]?.GetValue<string>() == "current" && record["level"]?.GetValue<string>() == "L5")
            .Select(record => record["recordId"]?.GetValue<string>()).OfType<string>());
        foreach (var run in runs)
            if (run["qualifications"] is JsonArray records) ScientificQualificationRecords.AssessL5Dependencies(records, lowerIds);
        return ScientificQualificationRecords.Summarize(runtimeId, runs);
    }

    private static object ScientificHistoryOpen(string profileId, JsonElement request, string action)
    {
        var jobId = request.GetProperty("jobId").GetString() ?? "";
        var (directory, result) = ScientificHistoryFind(profileId, jobId);
        var executable = "explorer.exe";
        string path;
        if (action == "history-open-log")
        {
            path = ScientificScopedFile(directory, "full.log");
            if (!File.Exists(path)) throw new InvalidOperationException("Full log is unavailable for this run.");
            executable = "notepad.exe";
        }
        else if (action is "history-reveal-artifact" or "history-open-artifact")
        {
            var relative = request.GetProperty("artifactPath").GetString() ?? "";
            path = ScientificArtifactFiles.ResolveRegistered(directory, result, relative);
            if (action == "history-open-artifact")
            {
                if (!ScientificMeshExtensions.Contains(Path.GetExtension(path).ToLowerInvariant()) && Path.GetExtension(path).ToLowerInvariant() != ".png")
                    throw new InvalidOperationException("Open supports registered mesh and PNG artifacts only.");
                Process.Start(new ProcessStartInfo(path) { UseShellExecute = true });
                return new { path };
            }
        }
        else path = directory;
        var start = new ProcessStartInfo(executable) { UseShellExecute = true };
        if (action == "history-reveal-artifact") start.ArgumentList.Add("/select,");
        start.ArgumentList.Add(path);
        Process.Start(start);
        return new { path };
    }

    private static object ScientificHistoryThumbnail(string profileId, JsonElement selection)
    {
        var jobId = selection.GetProperty("jobId").GetString() ?? "";
        var (directory, result) = ScientificHistoryFind(profileId, jobId);
        var relative = selection.GetProperty("artifactPath").GetString() ?? "";
        return new { jobId, artifactPath = relative, dataUrl = ScientificArtifactThumbnails.Create(directory, result, relative) };
    }

    private static object ScientificHistoryImagePreview(string profileId, JsonElement selection)
    {
        var jobId = selection.GetProperty("jobId").GetString() ?? "";
        var (directory, result) = ScientificHistoryFind(profileId, jobId);
        var relative = selection.GetProperty("artifactPath").GetString() ?? "";
        return new { jobId, artifactPath = relative, image = ScientificArtifactFiles.ImagePreview(directory, result, relative) };
    }

    private async Task<object> ScientificHistoryPreviewAsync(string profileId, JsonElement selection)
    {
        var jobId = selection.GetProperty("jobId").GetString() ?? "";
        var (directory, result) = ScientificHistoryFind(profileId, jobId);
        if (result.GetProperty("state").GetString() != "succeeded")
            throw new InvalidOperationException("Only successful runs have previewable output artifacts.");
        var requestPath = ScientificScopedFile(directory, "request.json");
        if (!File.Exists(requestPath) || new FileInfo(requestPath).Length > 1048576)
            throw new InvalidOperationException("The saved request is unavailable for this run.");
        using var document = JsonDocument.Parse(File.ReadAllText(requestPath));
        var definition = document.RootElement;
        if (definition.GetProperty("runId").GetString() != jobId
            || definition.GetProperty("profileId").GetString() != profileId
            || definition.GetProperty("runtimeId").GetString() != result.GetProperty("runtimeId").GetString()
            || definition.GetProperty("recipeId").GetString() != result.GetProperty("recipeId").GetString())
            throw new InvalidOperationException("Saved request and result do not match.");
        var job = new ScientificJob
        {
            Id = jobId, ProfileId = profileId, RuntimeId = result.GetProperty("runtimeId").GetString() ?? "",
            RecipeId = result.GetProperty("recipeId").GetString() ?? "", Directory = directory,
            State = "succeeded", Request = definition.Clone(), Result = result
        };
        return await ScientificPreviewAsync(job, selection);
    }
}
