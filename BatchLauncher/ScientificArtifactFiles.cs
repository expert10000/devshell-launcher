using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace BatchLauncher;

internal static class ScientificArtifactFiles
{
    internal static readonly string[] MeshExtensions = { ".obj", ".stl", ".ply", ".vtp", ".m3dm" };
    internal const long MaxArtifactBytes = 64 * 1024 * 1024;

    internal static string[] SmokeOutputs(string runtimeId, string recipeId) => (runtimeId, recipeId) switch
    {
        ("vtk-win-conda", "run") => new[] { "sphere.vtp" },
        ("vtk-win-conda", "test-all") => new[] { "sphere.vtp", "render/vtk-offscreen.png" },
        _ => Array.Empty<string>()
    };

    internal static string MediaType(string path) => Path.GetExtension(path).ToLowerInvariant() switch
    {
        ".obj" => "model/obj", ".stl" => "model/stl", ".ply" => "application/ply",
        ".vtp" => "application/vnd.vtk.vtp", ".off" => "application/off", ".png" => "image/png",
        ".m3dm" => "application/octet-stream", _ => "application/json"
    };

    internal static string Hash(string path)
    {
        using var stream = File.OpenRead(path);
        return Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
    }

    internal static string ScopedFile(string root, string relative)
    {
        if (string.IsNullOrWhiteSpace(relative) || Path.IsPathRooted(relative) || relative.Contains(':') || relative.Contains('\\')
            || relative.Split('/').Any(part => part is "" or "." or ".."))
            throw new InvalidOperationException("Expected a safe relative artifact path.");
        var path = Path.GetFullPath(Path.Combine(root, relative));
        if (!path.StartsWith(Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("Artifact escapes root.");
        for (FileSystemInfo? item = new FileInfo(path); item != null; item = item is FileInfo file ? file.Directory : ((DirectoryInfo)item).Parent)
        {
            if (item.Exists && (item.Attributes & FileAttributes.ReparsePoint) != 0)
                throw new InvalidOperationException("Symlink/junction artifacts are not allowed.");
            if (string.Equals(item.FullName, Path.GetFullPath(root), StringComparison.OrdinalIgnoreCase)) break;
        }
        return path;
    }

    internal static JsonObject? Describe(string directory, string relative)
    {
        var path = ScopedFile(directory, relative);
        if (!File.Exists(path) || new FileInfo(path).Length is <= 0 or > MaxArtifactBytes) return null;
        return new JsonObject { ["path"] = relative, ["mediaType"] = MediaType(path), ["bytes"] = new FileInfo(path).Length, ["sha256"] = Hash(path) };
    }

    // Old smoke results did not declare outputArtifacts. Recover only the two known files
    // when their worker evidence exists; never rewrite the saved result or scan arbitrary files.
    internal static JsonElement RecoverLegacySmoke(string directory, JsonElement result)
    {
        if (result.GetProperty("state").GetString() != "succeeded"
            || result.GetProperty("runtimeId").GetString() != "vtk-win-conda"
            || result.GetProperty("recipeId").GetString() is not ("run" or "test-all")
            || result.TryGetProperty("artifacts", out var existing) && existing.ValueKind == JsonValueKind.Array && existing.GetArrayLength() > 0)
            return result;
        var requestPath = ScopedFile(directory, "request.json");
        if (!File.Exists(requestPath) || new FileInfo(requestPath).Length > 1048576) return result;
        using var requestDocument = JsonDocument.Parse(File.ReadAllText(requestPath));
        var request = requestDocument.RootElement;
        if (!request.TryGetProperty("outputArtifacts", out var outputs) || outputs.ValueKind != JsonValueKind.Array || outputs.GetArrayLength() != 0
            || new[] { "runId", "profileId", "runtimeId", "recipeId" }.Any(key => request.GetProperty(key).GetString() != result.GetProperty(key).GetString()))
            return result;
        var recovered = new JsonArray();
        foreach (var relative in SmokeOutputs("vtk-win-conda", result.GetProperty("recipeId").GetString()!))
        {
            var evidence = relative == "sphere.vtp"
                ? result.TryGetProperty("artifact", out var mesh) && mesh.GetString() == "sphere.vtp"
                : result.TryGetProperty("rendering", out var render) && render.ValueKind == JsonValueKind.Object
                    && render.TryGetProperty("state", out var state) && state.GetString() == "succeeded"
                    && render.TryGetProperty("artifact", out var image) && image.GetString() == "vtk-offscreen.png";
            if (!evidence) continue;
            try
            {
                if (Describe(directory, relative) is not { } artifact) continue;
                artifact["recoveredFromLegacyRun"] = true;
                recovered.Add(artifact);
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or InvalidOperationException)
            {
                System.Diagnostics.Debug.WriteLine($"Legacy smoke artifact unavailable: {exception.Message}");
            }
        }
        if (recovered.Count == 0) return result;
        var updated = JsonNode.Parse(result.GetRawText())!;
        updated["artifacts"] = recovered;
        return JsonSerializer.SerializeToElement(updated);
    }

    internal static string ResolveRegistered(string directory, JsonElement result, string relative)
    {
        if (result.GetProperty("state").GetString() != "succeeded")
            throw new InvalidOperationException("Only successful runs have output artifacts.");
        if (!result.TryGetProperty("artifacts", out var artifacts) || artifacts.ValueKind != JsonValueKind.Array)
            throw new InvalidOperationException("Artifact is not registered in this run.");
        var artifact = artifacts.EnumerateArray().FirstOrDefault(item => item.GetProperty("path").GetString() == relative);
        if (artifact.ValueKind != JsonValueKind.Object) throw new InvalidOperationException("Artifact is not registered in this run.");
        var path = ScopedFile(directory, relative);
        if (!File.Exists(path)) throw new InvalidOperationException("Artifact is no longer available.");
        if (new FileInfo(path).Length is <= 0 or > MaxArtifactBytes) throw new InvalidOperationException("Artifact is empty or exceeds the 64 MiB limit.");
        if (artifact.TryGetProperty("sha256", out var expected) && !string.Equals(Hash(path), expected.GetString(), StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("Output artifact changed since it was recorded.");
        return path;
    }

    internal static WorkspaceImagePreview ImagePreview(string directory, JsonElement result, string relative)
    {
        var path = ResolveRegistered(directory, result, relative);
        if (!Path.GetExtension(path).Equals(".png", StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("Scientific image preview supports PNG artifacts only.");
        return WorkspaceFiles.ImagePreview(directory, relative);
    }
}
