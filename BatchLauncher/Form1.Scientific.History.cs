using System.Diagnostics;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace BatchLauncher;

public partial class Form1
{
    private static JsonElement ScientificHistoryResult(string profileId, string jobId)
    {
        if (!Regex.IsMatch(jobId, "^[0-9a-f]{32}$")) throw new InvalidOperationException("Invalid run ID.");
        var root = Path.Combine(ScientificDataRoot, "runs");
        var path = ScientificScopedFile(root, jobId + "/results.json");
        if (!File.Exists(path) || new FileInfo(path).Length > 1048576)
            throw new InvalidOperationException("Run result is missing or too large.");
        using var document = JsonDocument.Parse(File.ReadAllText(path));
        var result = document.RootElement;
        if (result.ValueKind != JsonValueKind.Object
            || !result.TryGetProperty("runId", out var runId) || runId.GetString() != jobId
            || !result.TryGetProperty("profileId", out var profile) || profile.GetString() != profileId)
            throw new InvalidOperationException("Run does not belong to this profile.");
        return result.Clone();
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
                var result = ScientificHistoryResult(profileId, directory.Name);
                var artifacts = result.TryGetProperty("artifacts", out var files) && files.ValueKind == JsonValueKind.Array ? files.GetArrayLength() : 0;
                entries.Add(new
                {
                    jobId = directory.Name,
                    runtimeId = result.GetProperty("runtimeId").GetString(),
                    recipeId = result.GetProperty("recipeId").GetString(),
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
        var result = ScientificHistoryResult(profileId, jobId);
        var directory = Path.GetDirectoryName(ScientificScopedFile(Path.Combine(ScientificDataRoot, "runs"), jobId + "/results.json"))!;
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
}
