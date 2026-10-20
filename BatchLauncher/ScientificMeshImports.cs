using System.Security.Cryptography;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace BatchLauncher;

internal static class ScientificMeshImports
{
    internal const long MaxBytes = 32 * 1024 * 1024;
    internal static JsonObject Progress(string runId, string profileId, JsonArray records) => new()
    {
        ["schemaVersion"] = 1, ["runId"] = runId, ["profileId"] = profileId, ["runtimeId"] = "cgal-win-conda", ["recipeId"] = "datasets.import",
        ["state"] = "running", ["durationMs"] = 0, ["versions"] = new JsonObject(), ["validatedCapabilities"] = new JsonArray(),
        ["diagnostics"] = new JsonArray(), ["artifacts"] = new JsonArray(), ["imports"] = records.DeepClone()
    };
    internal static JsonObject ReadManifest(string dataRoot)
    {
        var file = ScientificArtifactFiles.ScopedFile(Path.Combine(dataRoot, "datasets"), "manifest.json");
        if (!File.Exists(file)) return new JsonObject { ["schemaVersion"] = 1, ["entries"] = new JsonArray() };
        if (new FileInfo(file).Length > 1048576) throw new InvalidOperationException("Dataset registry exceeds 1 MiB.");
        var manifest = JsonNode.Parse(File.ReadAllText(file)) as JsonObject;
        if (manifest?["entries"] is not JsonArray) throw new InvalidOperationException("Invalid dataset registry.");
        return manifest;
    }

    private static void Save(string dataRoot, JsonObject manifest)
    {
        var root = Path.Combine(dataRoot, "datasets");
        Directory.CreateDirectory(root);
        var file = ScientificArtifactFiles.ScopedFile(root, "manifest.json");
        var json = manifest.ToJsonString();
        if (System.Text.Encoding.UTF8.GetByteCount(json) > 1048576) throw new InvalidOperationException("Dataset registry would exceed 1 MiB.");
        var temporary = ScientificArtifactFiles.ScopedFile(root, "manifest-" + Guid.NewGuid().ToString("N") + ".tmp");
        File.WriteAllText(temporary, json);
        File.Move(temporary, file, true);
    }

    internal static JsonObject Import(string dataRoot, string source, CancellationToken cancellation = default)
    {
        cancellation.ThrowIfCancellationRequested();
        source = Path.GetFullPath(source);
        var extension = Path.GetExtension(source).ToLowerInvariant();
        if (!new[] { ".obj", ".stl", ".ply", ".off" }.Contains(extension)) throw new InvalidOperationException("Choose OBJ, STL, PLY, or OFF meshes.");
        if ((File.GetAttributes(source) & FileAttributes.ReparsePoint) != 0) throw new InvalidOperationException("Choose a regular mesh file, not a link.");
        using var input = new FileStream(source, FileMode.Open, FileAccess.Read, FileShare.Read);
        if (input.Length is <= 0 or > MaxBytes) throw new InvalidOperationException("Each mesh must contain between 1 byte and 32 MiB.");
        var hash = Convert.ToHexString(SHA256.HashData(input)).ToLowerInvariant();
        input.Position = 0;
        var stem = Regex.Replace(Path.GetFileNameWithoutExtension(source), "[^a-zA-Z0-9_-]", "_");
        stem = stem[..Math.Min(stem.Length, 64)];
        var id = $"imported/{hash}/mesh-{stem}{extension}";
        var root = Path.Combine(dataRoot, "datasets");
        var destination = ScientificArtifactFiles.ScopedFile(root, id);
        var manifest = ReadManifest(dataRoot);
        var entries = manifest["entries"]!.AsArray();
        if (File.Exists(destination))
        {
            if (new FileInfo(destination).Length != input.Length || ScientificArtifactFiles.Hash(destination) != hash)
                throw new InvalidOperationException("The registered copy was modified. Restore or remove that copy before importing the same mesh again.");
        }
        else
        {
            Directory.CreateDirectory(Path.GetDirectoryName(destination)!);
            var temporary = destination + "." + Guid.NewGuid().ToString("N") + ".tmp";
            try
            {
                using (var output = new FileStream(temporary, FileMode.CreateNew, FileAccess.Write, FileShare.None))
                {
                    var buffer = new byte[65536];
                    int read;
                    while ((read = input.Read(buffer)) > 0) { cancellation.ThrowIfCancellationRequested(); output.Write(buffer, 0, read); }
                }
                cancellation.ThrowIfCancellationRequested();
                File.Move(temporary, destination);
            }
            finally { if (File.Exists(temporary)) File.Delete(temporary); }
        }
        var existing = entries.OfType<JsonObject>().FirstOrDefault(item => item["id"]?.GetValue<string>() == id);
        if (existing != null) return (JsonObject)existing.DeepClone();
        var entry = new JsonObject { ["id"] = id, ["path"] = id, ["name"] = Path.GetFileName(source), ["category"] = "Imported",
            ["bytes"] = input.Length, ["sha256"] = hash, ["sourcePath"] = Path.GetFileName(source), ["sourceRoot"] = Path.GetDirectoryName(source),
            ["expectedProblem"] = false, ["validation"] = new JsonObject { ["state"] = "not-checked" } };
        entries.Add(entry.DeepClone());
        manifest["importedAt"] = DateTimeOffset.UtcNow.ToString("O");
        manifest["note"] = "Registered local mesh copies. Originals remain unchanged; validation results describe the copied bytes.";
        Save(dataRoot, manifest);
        return entry;
    }

    internal static void SaveValidation(string dataRoot, string id, string hash, JsonObject validation)
    {
        var manifest = ReadManifest(dataRoot);
        var entry = manifest["entries"]!.AsArray().OfType<JsonObject>().FirstOrDefault(item => item["id"]?.GetValue<string>() == id);
        if (entry == null || entry["sha256"]?.GetValue<string>() != hash) throw new InvalidOperationException("Imported mesh identity changed before validation was recorded.");
        entry["validation"] = validation.DeepClone();
        Save(dataRoot, manifest);
    }
}
