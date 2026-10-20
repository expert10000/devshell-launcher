using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace BatchLauncher;

internal static class ScientificMath3DPreparation
{
    internal static readonly string[] DatasetIds = { "math3d/basic/01_tetrahedron.obj", "math3d/basic/02_cube.obj" };
    internal static readonly string[] Outputs = new[] { "math3d-native-self-union.m3dm", "math3d-native-cube-self-union.m3dm" }
        .Concat(new[] { "overlapping", "touching", "disjoint", "contained" }.SelectMany(relation =>
            new[] { "union", "intersection", "difference" }.Select(operation => $"math3d-native-{relation}-cubes-{operation}.m3dm"))).ToArray();

    internal static string? FindBaseline(string dataRoot, string profileId, string prefix, JsonObject input)
    {
        var runs = Path.Combine(dataRoot, "runs");
        if (!Directory.Exists(runs)) return null;
        foreach (var folder in new DirectoryInfo(runs).EnumerateDirectories().OrderByDescending(item => item.LastWriteTimeUtc))
        {
            if (!Regex.IsMatch(folder.Name, "^[0-9a-f]{32}$")) continue;
            try
            {
                var file = ScientificArtifactFiles.ScopedFile(runs, folder.Name + "/results.json");
                if (!File.Exists(file) || new FileInfo(file).Length > 1048576) continue;
                using var document = JsonDocument.Parse(File.ReadAllText(file));
                var result = document.RootElement;
                if (result.GetProperty("profileId").GetString() != profileId || result.GetProperty("runtimeId").GetString() != "cgal-win-conda"
                    || result.GetProperty("recipeId").GetString() != "cgal.validate" || result.GetProperty("state").GetString() != "succeeded"
                    || result.GetProperty("diagnostics").GetArrayLength() != 0) continue;
                var configured = result.GetProperty("steps").EnumerateArray().Any(step => step.GetProperty("stage").GetString() == "configure"
                    && string.Equals(step.GetProperty("executable").GetString(), Path.Combine(prefix, "Library", "bin", "cmake.exe"), StringComparison.OrdinalIgnoreCase));
                var matches = result.GetProperty("inputArtifacts").EnumerateArray().Any(artifact =>
                    artifact.GetProperty("datasetId").GetString() == input["datasetId"]!.GetValue<string>()
                    && string.Equals(artifact.GetProperty("path").GetString(), input["path"]!.GetValue<string>(), StringComparison.OrdinalIgnoreCase)
                    && artifact.GetProperty("sha256").GetString() == input["sha256"]!.GetValue<string>());
                if (!configured || !matches) continue;
                var output = result.GetProperty("artifacts").EnumerateArray().FirstOrDefault(item => Path.GetExtension(item.GetProperty("path").GetString()) == ".obj");
                if (output.ValueKind != JsonValueKind.Object || !output.TryGetProperty("sha256", out var outputHash)
                    || outputHash.ValueKind != JsonValueKind.String || outputHash.GetString()?.Length != 64
                    || !output.TryGetProperty("bytes", out var outputBytes)) continue;
                var outputFile = ScientificArtifactFiles.ResolveRegistered(folder.FullName, result, output.GetProperty("path").GetString()!);
                if (new FileInfo(outputFile).Length != outputBytes.GetInt64()) continue;
                return result.GetProperty("runId").GetString();
            }
            catch (Exception exception) when (exception is IOException or JsonException or InvalidOperationException or UnauthorizedAccessException or KeyNotFoundException or ArgumentException)
            { System.Diagnostics.Debug.WriteLine($"Skipping unusable MATH3D baseline: {exception.Message}"); }
        }
        return null;
    }

    internal static void ImportFixture(string dataRoot, string math3dRoot, string datasetId)
    {
        if (!DatasetIds.Contains(datasetId)) throw new InvalidOperationException("Unknown integration fixture.");
        var relative = "tests/assets/meshes/basic/" + Path.GetFileName(datasetId);
        var source = ScientificArtifactFiles.ScopedFile(math3dRoot, relative);
        if (!File.Exists(source) || new FileInfo(source).Length is <= 0 or > 33554432)
            throw new InvalidOperationException("The MATH3D fixture is missing or too large: " + relative);
        var root = Path.Combine(dataRoot, "datasets");
        var target = ScientificArtifactFiles.ScopedFile(root, datasetId);
        var manifestPath = ScientificArtifactFiles.ScopedFile(root, "manifest.json");
        if (File.Exists(manifestPath) && new FileInfo(manifestPath).Length > 1048576) throw new InvalidOperationException("Dataset manifest is too large.");
        var manifest = File.Exists(manifestPath) ? JsonNode.Parse(File.ReadAllText(manifestPath)) as JsonObject
            ?? throw new InvalidOperationException("Invalid dataset manifest.") : new JsonObject { ["schemaVersion"] = 1, ["entries"] = new JsonArray() };
        var entries = manifest["entries"] as JsonArray ?? throw new InvalidOperationException("Invalid dataset entries.");
        Directory.CreateDirectory(Path.GetDirectoryName(target)!);
        File.Copy(source, target, true);
        foreach (var old in entries.Where(item => item?["id"]?.GetValue<string>() == datasetId).ToArray()) entries.Remove(old);
        entries.Add(new JsonObject { ["id"] = datasetId, ["name"] = Path.GetFileName(datasetId), ["category"] = "basic", ["path"] = datasetId,
            ["bytes"] = new FileInfo(target).Length, ["sha256"] = ScientificArtifactFiles.Hash(target), ["sourcePath"] = relative,
            ["sourceRoot"] = math3dRoot, ["expectedProblem"] = false });
        manifest["importedAt"] = DateTimeOffset.UtcNow.ToString("O");
        manifest["note"] = "Registered local copies; original MATH3D fixtures unchanged.";
        File.WriteAllText(manifestPath + ".tmp", manifest.ToJsonString());
        File.Move(manifestPath + ".tmp", manifestPath, true);
    }
}
