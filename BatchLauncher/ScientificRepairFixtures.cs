using System.Text.Json.Nodes;

namespace BatchLauncher;

internal static class ScientificRepairFixtures
{
    internal const string SuiteId = "cgal-repair-qualification-v1";
    internal const string ManifestPath = "scientific/fixtures/cgal-repair-qualification/manifest.json";

    internal static JsonObject Manifest(string sourceRoot)
    {
        var file = Path.Combine(sourceRoot, ManifestPath.Replace('/', Path.DirectorySeparatorChar));
        if (!File.Exists(file) || new FileInfo(file).Length > 65536)
            throw new InvalidDataException("Repair fixture manifest is unavailable.");
        var manifest = JsonNode.Parse(File.ReadAllText(file)) as JsonObject;
        var fixtures = manifest?["fixtures"] as JsonArray;
        if (manifest?["schemaVersion"]?.GetValue<int>() != 1
            || manifest["suiteId"]?.GetValue<string>() != SuiteId
            || manifest["license"]?.GetValue<string>() != "CC0-1.0"
            || fixtures?.Count != 5)
            throw new InvalidDataException("Repair fixture manifest changed.");
        var expected = new[] { "triangle", "square", "two-squares", "pentagon", "closed-rejection" };
        for (var index = 0; index < expected.Length; index++)
        {
            var item = fixtures[index] as JsonObject;
            var relative = item?["path"]?.GetValue<string>() ?? "";
            if (item?["caseId"]?.GetValue<string>() != expected[index]
                || !relative.StartsWith("scientific/fixtures/", StringComparison.Ordinal)
                || relative.Contains("..", StringComparison.Ordinal)
                || Path.GetExtension(relative) != ".obj"
                || item["sha256"]?.GetValue<string>() is not { Length: 64 })
                throw new InvalidDataException("Repair fixture declaration is invalid.");
            var source = ScientificArtifactFiles.ScopedFile(sourceRoot, relative);
            if (!File.Exists(source) || new FileInfo(source).Length is <= 0 or > ScientificMeshImports.MaxBytes
                || ScientificArtifactFiles.Hash(source) != item["sha256"]?.GetValue<string>())
                throw new InvalidDataException("Repair fixture bytes changed: " + expected[index]);
        }
        return manifest;
    }

    internal static JsonObject Load(string sourceRoot, string dataRoot, CancellationToken cancellation = default)
    {
        var manifest = Manifest(sourceRoot);
        foreach (var item in manifest["fixtures"]!.AsArray().OfType<JsonObject>())
        {
            cancellation.ThrowIfCancellationRequested();
            var source = ScientificArtifactFiles.ScopedFile(sourceRoot, item["path"]!.GetValue<string>());
            var imported = ScientificMeshImports.Import(dataRoot, source, cancellation);
            if (imported["sha256"]?.GetValue<string>() != item["sha256"]?.GetValue<string>())
                throw new InvalidDataException("Registered repair copy differs from the authored fixture.");
        }
        return ScientificMeshImports.ReadManifest(dataRoot);
    }

    internal static JsonObject Dataset(string sourceRoot, string dataRoot, string caseId)
    {
        var manifest = Manifest(sourceRoot);
        var item = manifest["fixtures"]!.AsArray().OfType<JsonObject>()
            .SingleOrDefault(value => value["caseId"]?.GetValue<string>() == caseId)
            ?? throw new InvalidOperationException("Repair qualification case is not registered.");
        var hash = item["sha256"]!.GetValue<string>();
        var stem = Path.GetFileNameWithoutExtension(item["path"]!.GetValue<string>());
        var id = $"imported/{hash}/mesh-{stem}.obj";
        var registry = ScientificMeshImports.ReadManifest(dataRoot);
        var entry = registry["entries"]!.AsArray().OfType<JsonObject>()
            .FirstOrDefault(value => value["id"]?.GetValue<string>() == id
                && value["sha256"]?.GetValue<string>() == hash)
            ?? throw new InvalidOperationException("Load the authored repair fixtures first.");
        return (JsonObject)entry.DeepClone();
    }
}
