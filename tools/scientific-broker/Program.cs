using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using BatchLauncher;

static class BrokerManifest
{
    static string Hash(byte[] bytes) => Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
    static string HashFile(string path) => Hash(File.ReadAllBytes(path));
    static string Digest(JsonNode? node) => Hash(Encoding.UTF8.GetBytes(node?.ToJsonString() ?? "null"));
    static string? ProductSources(string root)
    {
        var files = new JsonObject();
        foreach (var name in new[] { "renderer/src/mesh/surfaceMesh.ts", "renderer/src/mesh/meshDocumentAdapter.ts",
            "renderer/src/mesh/meshResourceStore.ts", "renderer/src/workspace/MeshDocumentViewport.tsx",
            "renderer/src/components/SurfaceViewer.tsx", "packages/core/src/meshDocument.ts" })
        {
            var path = Path.Combine(root, name.Replace('/', Path.DirectorySeparatorChar));
            if (!File.Exists(path)) return null;
            files[name] = HashFile(path);
        }
        return Digest(files);
    }
    static JsonObject ProductContract() => new()
    {
        ["id"] = "math3d.mesh-product-handoff", ["version"] = 1,
        ["workerResultSchemaVersion"] = 1, ["meshDocumentSchemaVersion"] = 1,
        ["inputFormat"] = "obj", ["viewer"] = "MeshDocumentViewport"
    };
    static IEnumerable<JsonObject> Records(IEnumerable<JsonObject> runs) =>
        runs.SelectMany(run => run["qualifications"]?.AsArray().OfType<JsonObject>() ?? []);
    static HashSet<string> CurrentIds(IEnumerable<JsonObject> runs, params string[] levels) =>
        Records(runs).Where(record => record["status"]?.GetValue<string>() == "current"
            && levels.Contains(record["level"]?.GetValue<string>()))
            .Select(record => record["recordId"]?.GetValue<string>()).OfType<string>()
            .ToHashSet(StringComparer.Ordinal);
    static void AssessDependencies(List<JsonObject> runs, IReadOnlySet<string> ids,
        bool l6 = true, bool l7 = true, bool l8 = true, bool l9 = true)
    {
        foreach (var run in runs)
            if (run["qualifications"] is JsonArray records)
                ScientificQualificationRecords.AssessL5Dependencies(records, ids, l6, l7, l8, l9);
    }
    static List<JsonObject> ReadRuns(string repo, string installed, string profile, string runtime)
    {
        var root = Path.Combine(repo, ".scientific", "runs");
        var runs = new List<JsonObject>();
        if (!Directory.Exists(root)) return runs;
        var report = Path.Combine(repo, ".scientific", "runtime-report.json");
        foreach (var directory in Directory.EnumerateDirectories(root))
        {
            if (!Regex.IsMatch(Path.GetFileName(directory), "^[0-9a-f]{32}$")) continue;
            try
            {
                var path = Path.Combine(directory, "results.json");
                if (!File.Exists(path) || new FileInfo(path).Length > 1048576) continue;
                using var document = JsonDocument.Parse(File.ReadAllText(path));
                var result = document.RootElement;
                if (result.GetProperty("runtimeId").GetString() != runtime
                    || result.GetProperty("profileId").GetString() != profile) continue;
                var run = new JsonObject { ["runId"] = result.GetProperty("runId").GetString(),
                    ["runtimeId"] = runtime, ["recipeId"] = result.GetProperty("recipeId").GetString(),
                    ["state"] = result.GetProperty("state").GetString(),
                    ["finishedAtUtc"] = File.GetLastWriteTimeUtc(path).ToString("O"), ["directory"] = directory };
                if (run["state"]?.GetValue<string>() == "succeeded"
                    && result.TryGetProperty("qualificationSha256", out var qualificationHash))
                {
                    ScientificRunFingerprint.Verify(directory, result.GetProperty("runFingerprintSha256").GetString() ?? "");
                    var records = ScientificQualificationRecords.Verify(directory, result);
                    var source = ScientificRunFingerprint.AssessSourceDrift(directory, repo, installed);
                    var environment = ScientificRunFingerprint.AssessEnvironmentDrift(directory, installed, report);
                    run["qualifications"] = ScientificQualificationRecords.Assess(records, source, environment);
                    run["qualificationSha256"] = qualificationHash.GetString();
                    run["fingerprintSha256"] = result.GetProperty("runFingerprintSha256").GetString();
                }
                runs.Add(run);
            }
            catch (Exception error) when (error is IOException or JsonException or InvalidDataException
                or InvalidOperationException or UnauthorizedAccessException or KeyNotFoundException) { }
        }
        return runs;
    }
    static JsonObject Export(string repo, string installed, string math3d, string profile)
    {
        var runs = ReadRuns(repo, installed, profile, "cgal-win-conda");
        var ids = CurrentIds(runs, "L0", "L1", "L2", "L3", "L4");
        AssessDependencies(runs, ids, l6: false, l7: false, l8: false, l9: false);
        ids.UnionWith(CurrentIds(runs, "L5"));
        AssessDependencies(runs, ids, l7: false, l8: false, l9: false);
        ids.UnionWith(CurrentIds(runs, "L6"));
        string? importer = null;
        var importerPath = Path.Combine(math3d, "renderer", "src", "mesh", "surfaceMesh.ts");
        if (File.Exists(importerPath)) importer = HashFile(importerPath);
        string? vtkEnvironment = null;
        try
        {
            var captured = ScientificRunFingerprint.Capture("vtk-win-conda", profile, repo, installed,
                Path.Combine(repo, ".scientific", "runtime-report.json"));
            if (captured["environment"]?["condaPackageRecords"]?["state"]?.GetValue<string>() == "recorded")
                vtkEnvironment = Digest(captured["environment"]);
        }
        catch (Exception) { }
        foreach (var run in runs)
            if (run["qualifications"] is JsonArray records)
            {
                ScientificQualificationRecords.AssessL5Dependencies(records, ids, includeL8: false, includeL9: false);
                ScientificQualificationRecords.AssessL7Consumer(records, importer, vtkEnvironment);
            }
        ids.UnionWith(CurrentIds(runs, "L7"));
        AssessDependencies(runs, ids, l9: false);
        ids.UnionWith(CurrentIds(runs, "L8"));
        var contract = ProductContract();
        foreach (var run in runs)
            if (run["qualifications"] is JsonArray records)
            {
                ScientificQualificationRecords.AssessL5Dependencies(records, ids);
                ScientificQualificationRecords.AssessL9Consumer(records, ProductSources(math3d), Digest(contract));
            }
        var summary = ScientificQualificationRecords.Summarize("cgal-win-conda", runs);
        var certified = new JsonArray();
        foreach (var current in summary["currentRecords"]!.AsArray().OfType<JsonObject>()
            .Where(item => item["level"]?.GetValue<string>() == "L9"
                && item["capabilityId"]?.GetValue<string>() == "mesh.interop.vtk-math3d")
            .OrderByDescending(item => item["finishedAtUtc"]?.GetValue<string>(), StringComparer.Ordinal).Take(1))
        {
            var run = runs.Single(item => item["runId"]?.GetValue<string>() == current["runId"]?.GetValue<string>());
            var directory = run["directory"]!.GetValue<string>();
            var result = JsonNode.Parse(File.ReadAllText(Path.Combine(directory, "results.json")))!;
            var record = run["qualifications"]!.AsArray().OfType<JsonObject>()
                .Single(item => item["recordId"]?.GetValue<string>() == current["recordId"]?.GetValue<string>());
            var evidence = result["l9Evidence"]!;
            if (evidence["productContractSha256"]?.GetValue<string>() != Digest(contract)) continue;
            var output = Path.Combine(directory, "positive", "l5-positive.obj");
            if (!File.Exists(output) || HashFile(output) != evidence["worker"]?["artifactSha256"]?.GetValue<string>()) continue;
            var fingerprint = JsonNode.Parse(File.ReadAllText(Path.Combine(directory, "fingerprint.json")))!;
            var binaryHash = fingerprint["components"]?["worker"]?["executedFiles"]?.AsArray()
                .OfType<JsonObject>().FirstOrDefault(item => item["name"]?.GetValue<string>() == "devshell_cgal_worker.exe")?
                ["sha256"]?.GetValue<string>();
            if (binaryHash is not { Length: 64 }) continue;
            certified.Add(new JsonObject
            {
                ["runtimeId"] = "cgal-win-conda", ["capabilityId"] = "mesh.interop.vtk-math3d", ["level"] = "L9",
                ["sourceRunId"] = current["runId"]?.DeepClone(), ["recordId"] = current["recordId"]?.DeepClone(),
                ["runFingerprintSha256"] = run["fingerprintSha256"]?.DeepClone(),
                ["suiteRevisionSha256"] = record["suiteRevisionSha256"]?.DeepClone(),
                ["qualificationSha256"] = run["qualificationSha256"]?.DeepClone(),
                ["workerContractSha256"] = fingerprint["components"]?["contract"]?["workerContractModule"]?["sha256"]?.DeepClone(),
                ["runtimeManifestSha256"] = fingerprint["components"]?["contract"]?["runtimeManifest"]?["sha256"]?.DeepClone(),
                ["adapterSha256"] = HashFile(Path.Combine(repo, "tools", "scientific-cgal-worker.py")),
                ["workerBinarySha256"] = binaryHash,
                ["pythonSha256"] = fingerprint["components"]?["environment"]?["pythonExecutable"]?["sha256"]?.DeepClone(),
                ["packageRecordsSha256"] = fingerprint["components"]?["environment"]?["condaPackageRecords"]?["sha256"]?.DeepClone(),
                ["productContract"] = contract.DeepClone(), ["productContractSha256"] = Digest(contract),
                ["referenceInputSha256"] = evidence["worker"]?["inputSha256"]?.DeepClone(),
                ["referenceArtifactSha256"] = evidence["worker"]?["artifactSha256"]?.DeepClone(),
                ["sourceL8RunId"] = evidence["sourceL8RunId"]?.DeepClone(),
                ["sourceL8RecordId"] = evidence["sourceL8RecordId"]?.DeepClone()
            });
        }
        return new JsonObject { ["schemaVersion"] = 1, ["kind"] = "scientific.certified-capabilities",
            ["issuedAtUtc"] = DateTimeOffset.UtcNow.ToString("O"), ["profileId"] = profile,
            ["providerRegistryVersion"] = ScientificProviderRegistry.ContractVersion,
            ["certifiedCapabilities"] = certified };
    }
    static void Save(string path, JsonObject manifest)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(path))!);
        var bytes = Encoding.UTF8.GetBytes(manifest.ToJsonString());
        var temp = path + ".tmp";
        File.WriteAllBytes(temp, bytes);
        File.Move(temp, path, true);
        File.WriteAllText(path + ".sha256", Hash(bytes) + "\n", new UTF8Encoding(false));
    }
    static void Verify(string path)
    {
        var bytes = File.ReadAllBytes(path);
        if (!string.Equals(Hash(bytes), File.ReadAllText(path + ".sha256").Trim(), StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("Certified manifest hash mismatch.");
        var manifest = JsonNode.Parse(bytes) as JsonObject ?? throw new InvalidDataException("Invalid certified manifest.");
        if (manifest["schemaVersion"]?.GetValue<int>() != 1 || manifest["kind"]?.GetValue<string>() != "scientific.certified-capabilities"
            || manifest["certifiedCapabilities"] is not JsonArray capabilities
            || capabilities.Any(item => item?["runtimeId"]?.GetValue<string>() != "cgal-win-conda"
                || item?["capabilityId"]?.GetValue<string>() != "mesh.interop.vtk-math3d"
                || item?["level"]?.GetValue<string>() != "L9"))
            throw new InvalidDataException("Unsupported certified manifest content.");
    }
    static int Main(string[] args)
    {
        try
        {
            if (args.Length == 6 && args[0] == "export")
            {
                var manifest = Export(args[1], args[2], args[3], args[4]);
                Save(args[5], manifest);
                Verify(args[5]);
                Console.WriteLine($"Exported {manifest["certifiedCapabilities"]!.AsArray().Count} certified capabilities: {args[5]}");
                return 0;
            }
            if (args.Length == 2 && args[0] == "verify") { Verify(args[1]); Console.WriteLine("Certified manifest verified."); return 0; }
            Console.Error.WriteLine("Usage: export <repo> <installed-root> <math3d-root> <profile> <manifest.json> | verify <manifest.json>");
            return 2;
        }
        catch (Exception error) { Console.Error.WriteLine(error.Message); return 1; }
    }
}
