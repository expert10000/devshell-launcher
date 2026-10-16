using System.Diagnostics;
using System.Text.Json;
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
        return (Path.GetDirectoryName(path)!, result.Clone());
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
            catch (Exception exception) when (exception is IOException or JsonException or InvalidOperationException or UnauthorizedAccessException or KeyNotFoundException)
            {
                Debug.WriteLine($"Skipping invalid Scientific run: {exception.Message}");
            }
        }
        throw new InvalidOperationException("Run is unavailable in this profile.");
    }

    private static JsonElement ScientificHistoryResult(string profileId, string jobId) => ScientificHistoryFind(profileId, jobId).Result;

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
                    artifactCount = artifacts
                });
                if (entries.Count == 50) break;
            }
            catch (Exception exception) when (exception is IOException or JsonException or InvalidOperationException or UnauthorizedAccessException or KeyNotFoundException)
            {
                Debug.WriteLine($"Skipping invalid Scientific history entry: {exception.Message}");
            }
        }
        return entries;
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
        else if (action == "history-reveal-artifact")
        {
            var relative = request.GetProperty("artifactPath").GetString() ?? "";
            if (!result.TryGetProperty("artifacts", out var artifacts) || artifacts.ValueKind != JsonValueKind.Array
                || !artifacts.EnumerateArray().Any(item => item.GetProperty("path").GetString() == relative))
                throw new InvalidOperationException("Artifact is not registered in this run.");
            path = ScientificScopedFile(directory, relative);
            if (!File.Exists(path)) throw new InvalidOperationException("Artifact is no longer available.");
        }
        else path = directory;
        var start = new ProcessStartInfo(executable) { UseShellExecute = true };
        if (action == "history-reveal-artifact") start.ArgumentList.Add("/select,");
        start.ArgumentList.Add(path);
        Process.Start(start);
        return new { path };
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
