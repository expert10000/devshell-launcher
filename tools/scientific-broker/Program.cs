using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using BatchLauncher;

static partial class BrokerManifest
{
    static string Hash(byte[] bytes) => Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
    static string HashFile(string path) => Hash(File.ReadAllBytes(path));
    static string Digest(JsonNode? node) => Hash(Encoding.UTF8.GetBytes(node?.ToJsonString() ?? "null"));
    static JsonObject? ProductSourceFiles(string root)
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
        return files;
    }
    static string? ProductSources(string root) => ProductSourceFiles(root) is { } files ? Digest(files) : null;
    static JsonObject? VolumeSourceFiles(string root)
    {
        var files = new JsonObject();
        foreach (var name in new[] { "scientific/volume-consumer.v1.json", "packages/core/src/tetrahedralMeshDocument.ts",
            "renderer/src/volume/tetrahedralMeshDocumentAdapter.ts", "renderer/src/volume/TetrahedralMeshViewport.tsx",
            "renderer/src/workspace/MeshDocumentViewport.tsx", "renderer/src/components/SurfaceViewer.tsx" })
        {
            var path = Path.Combine(root, name.Replace('/', Path.DirectorySeparatorChar));
            if (!File.Exists(path)) return null;
            files[name] = HashFile(path);
        }
        return files;
    }
    static JsonObject VolumeContract() => new()
    {
        ["id"] = "math3d.tetrahedral-product-handoff", ["version"] = 1,
        ["documentFormat"] = "math3d.tetrahedral-mesh-document",
        ["resourceEncoding"] = "math3d.tetmesh-buffers.v1", ["viewer"] = "TetrahedralMeshViewport"
    };
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
    static List<JsonObject> ReadRuns(string repo, string installed, string profile, string runtime,
        List<JsonObject>? rejected = null)
    {
        var root = Path.Combine(repo, ".scientific", "runs");
        var runs = new List<JsonObject>();
        if (!Directory.Exists(root)) return runs;
        var report = Path.Combine(repo, ".scientific", "runtime-report.json");
        foreach (var directory in Directory.EnumerateDirectories(root))
        {
            if (!Regex.IsMatch(Path.GetFileName(directory), "^[0-9a-f]{32}$")) continue;
            string? recipeId = null;
            try
            {
                var path = Path.Combine(directory, "results.json");
                if (!File.Exists(path) || new FileInfo(path).Length > 1048576) continue;
                using var document = JsonDocument.Parse(File.ReadAllText(path));
                var result = document.RootElement;
                if (result.GetProperty("runtimeId").GetString() != runtime
                    || result.GetProperty("profileId").GetString() != profile) continue;
                recipeId = result.GetProperty("recipeId").GetString();
                var run = new JsonObject { ["runId"] = result.GetProperty("runId").GetString(),
                    ["runtimeId"] = runtime, ["recipeId"] = recipeId,
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
                or InvalidOperationException or UnauthorizedAccessException or KeyNotFoundException)
            {
                if (rejected != null && recipeId is "l9.gmsh-volume" or "l9.cgal-repair")
                    rejected.Add(new JsonObject { ["folderId"] = Path.GetFileName(directory),
                        ["reason"] = error.Message });
            }
        }
        return runs;
    }
    static JsonObject? ExportGmsh(string repo, string installed, string math3d, string profile)
    {
        var runs = ReadRuns(repo, installed, profile, "gmsh-win-conda");
        var ids = CurrentIds(runs, "L0", "L1", "L2", "L3", "L4");
        AssessDependencies(runs, ids, l6: false, l7: false, l8: false, l9: false);
        ids.UnionWith(CurrentIds(runs, "L5"));
        AssessDependencies(runs, ids, l7: false, l8: false, l9: false);
        ids.UnionWith(CurrentIds(runs, "L6"));
        var importerPath = Path.Combine(math3d, "renderer", "src", "mesh", "surfaceMesh.ts");
        var importer = File.Exists(importerPath) ? HashFile(importerPath) : null;
        var codecPath = Path.Combine(math3d, "src", "main", "python", "nativeCgalProtocol.ts");
        var codec = File.Exists(codecPath) ? HashFile(codecPath) : null;
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
                var volumeFiles = VolumeSourceFiles(math3d);
                ScientificQualificationRecords.AssessL9Consumer(records, ProductSources(math3d), Digest(contract), codec,
                    volumeFiles is null ? null : Digest(volumeFiles), Digest(VolumeContract()));
            }
        var summary = ScientificQualificationRecords.Summarize("gmsh-win-conda", runs);
        foreach (var current in summary["currentRecords"]!.AsArray().OfType<JsonObject>()
            .Where(item => item["level"]?.GetValue<string>() == "L9"
                && item["capabilityId"]?.GetValue<string>() == "mesh.generate")
            .OrderByDescending(item => item["finishedAtUtc"]?.GetValue<string>(), StringComparer.Ordinal))
        {
            if (!ScientificCapabilityRegistry.IsDeclared("gmsh-win-conda", "mesh.generate")) continue;
            var run = runs.Single(item => item["runId"]?.GetValue<string>() == current["runId"]?.GetValue<string>());
            var directory = run["directory"]!.GetValue<string>();
            var result = JsonNode.Parse(File.ReadAllText(Path.Combine(directory, "results.json")))!;
            var record = run["qualifications"]!.AsArray().OfType<JsonObject>()
                .Single(item => item["recordId"]?.GetValue<string>() == current["recordId"]?.GetValue<string>());
            var evidence = result["l9GmshEvidence"]!;
            var consumerFiles = ProductSourceFiles(math3d);
            if (evidence["productContractSha256"]?.GetValue<string>() != Digest(contract)
                || consumerFiles == null || Digest(consumerFiles) != record["consumerSourceSha256"]?.GetValue<string>()
                || codec == null || codec != record["consumerCodecSha256"]?.GetValue<string>()) continue;
            var msh = Path.Combine(directory, "positive", "l5-positive.msh");
            var obj = Path.Combine(directory, "handoff", "mesh.obj");
            if (!File.Exists(msh) || !File.Exists(obj)
                || HashFile(msh) != evidence["worker"]?["artifactSha256"]?.GetValue<string>()
                || HashFile(obj) != evidence["conversion"]?["outputObjSha256"]?.GetValue<string>()) continue;
            var fingerprint = JsonNode.Parse(File.ReadAllText(Path.Combine(directory, "fingerprint.json")))!;
            var lower = record["lowerQualification"]?["records"] as JsonArray;
            var currentIds = CurrentIds(runs, "L0", "L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "L9");
            if (lower is not { Count: 9 } || lower.Where((item, index) =>
                    item?["level"]?.GetValue<string>() != "L" + index
                    || item?["recordId"]?.GetValue<string>() is not { } id || !currentIds.Contains(id)).Any()) continue;
            var support = new JsonArray(lower.Select(item => item!.DeepClone()).ToArray());
            support.Add(new JsonObject { ["level"] = "L9", ["capabilityId"] = "mesh.generate",
                ["runId"] = current["runId"]?.DeepClone(), ["recordId"] = current["recordId"]?.DeepClone() });
            return new JsonObject {
                ["runtimeId"] = "gmsh-win-conda", ["capabilityId"] = "mesh.generate", ["level"] = "L9",
                ["scope"] = "fixed public 2D unit square", ["sourceRunId"] = current["runId"]?.DeepClone(),
                ["recordId"] = current["recordId"]?.DeepClone(),
                ["runFingerprintSha256"] = run["fingerprintSha256"]?.DeepClone(),
                ["suiteRevisionSha256"] = record["suiteRevisionSha256"]?.DeepClone(),
                ["qualificationSha256"] = run["qualificationSha256"]?.DeepClone(),
                ["workerContractSha256"] = fingerprint["components"]?["contract"]?["workerContractModule"]?["sha256"]?.DeepClone(),
                ["runtimeManifestSha256"] = fingerprint["components"]?["contract"]?["runtimeManifest"]?["sha256"]?.DeepClone(),
                ["adapterSha256"] = HashFile(Path.Combine(repo, "tools", "scientific-broker", "gmsh_adapter.py")),
                ["workerBinarySha256"] = HashFile(Path.Combine(repo, "tools", "scientific-gmsh-worker.py")),
                ["converterSha256"] = HashFile(Path.Combine(repo, "tools", "scientific-gmsh-handoff.py")),
                ["pythonSha256"] = fingerprint["components"]?["environment"]?["pythonExecutable"]?["sha256"]?.DeepClone(),
                ["packageRecordsSha256"] = fingerprint["components"]?["environment"]?["condaPackageRecords"]?["sha256"]?.DeepClone(),
                ["productContract"] = contract.DeepClone(), ["productContractSha256"] = Digest(contract),
                ["consumerSources"] = consumerFiles, ["consumerSourceSha256"] = Digest(consumerFiles),
                ["codecSourceSha256"] = codec,
                ["referenceInputSha256"] = evidence["worker"]?["inputSha256"]?.DeepClone(),
                ["referenceWorkerArtifactSha256"] = evidence["worker"]?["artifactSha256"]?.DeepClone(),
                ["referenceArtifactSha256"] = evidence["conversion"]?["outputObjSha256"]?.DeepClone(),
                ["sourceL8RunId"] = evidence["sourceL8RunId"]?.DeepClone(),
                ["sourceL8RecordId"] = evidence["sourceL8RecordId"]?.DeepClone(),
                ["supportingRecords"] = support
            };
        }
        return null;
    }
    static JsonObject? ExportGmshVolume(string repo, string installed, string math3d, string profile,
        JsonObject? audit = null)
    {
        var rejected = audit is null ? null : new List<JsonObject>();
        var runs = ReadRuns(repo, installed, profile, "gmsh-win-conda", rejected);
        var ids = CurrentIds(runs, "L0", "L1", "L2", "L3", "L4");
        AssessDependencies(runs, ids, l6: false, l7: false, l8: false, l9: false);
        ids.UnionWith(CurrentIds(runs, "L5"));
        AssessDependencies(runs, ids, l7: false, l8: false, l9: false);
        ids.UnionWith(CurrentIds(runs, "L6"));
        AssessDependencies(runs, ids, l8: false, l9: false);
        ids.UnionWith(CurrentIds(runs, "L7"));
        AssessDependencies(runs, ids, l9: false);
        ids.UnionWith(CurrentIds(runs, "L8"));
        var volumeFiles = VolumeSourceFiles(math3d);
        var volumeContract = VolumeContract();
        var surfaceContract = ProductContract();
        var codecPath = Path.Combine(math3d, "src", "main", "python", "nativeCgalProtocol.ts");
        var codec = File.Exists(codecPath) ? HashFile(codecPath) : null;
        foreach (var run in runs)
            if (run["qualifications"] is JsonArray records)
            {
                ScientificQualificationRecords.AssessL5Dependencies(records, ids);
                ScientificQualificationRecords.AssessL9Consumer(records, ProductSources(math3d),
                    Digest(surfaceContract), codec, volumeFiles is null ? null : Digest(volumeFiles),
                    Digest(volumeContract));
            }
        var summary = ScientificQualificationRecords.Summarize("gmsh-win-conda", runs);
        if (audit is not null)
        {
            audit["runtimeId"] = "gmsh-win-conda";
            audit["capabilityId"] = "mesh.generate3d";
            audit["profileId"] = profile;
            audit["verifiedRunCount"] = runs.Count;
            audit["consumerFilesAvailable"] = volumeFiles is not null;
            audit["capabilityDeclared"] = ScientificCapabilityRegistry.IsDeclared("gmsh-win-conda", "mesh.generate3d");
            audit["rejectedL9Runs"] = new JsonArray((rejected ?? []).Select(item => item.DeepClone()).ToArray());
            var candidates = new JsonArray();
            var byId = Records(runs).Where(item => item["recordId"]?.GetValue<string>() is not null)
                .GroupBy(item => item["recordId"]!.GetValue<string>(), StringComparer.Ordinal)
                .ToDictionary(group => group.Key, group => group.First(), StringComparer.Ordinal);
            foreach (var run in runs.OrderByDescending(item => item["finishedAtUtc"]?.GetValue<string>(), StringComparer.Ordinal)
                .Take(20))
                foreach (var record in run["qualifications"]?.AsArray().OfType<JsonObject>() ?? [])
                {
                    if (record["level"]?.GetValue<string>() != "L9"
                        || record["capabilityId"]?.GetValue<string>() != "mesh.generate3d") continue;
                    var support = new JsonArray();
                    foreach (var item in record["lowerQualification"]?["records"]?.AsArray() ?? [])
                    {
                        var id = item?["recordId"]?.GetValue<string>();
                        var supporting = id is not null && byId.TryGetValue(id, out var found) ? found : null;
                        support.Add(new JsonObject { ["level"] = item?["level"]?.DeepClone(),
                            ["recordId"] = id, ["status"] = supporting?["status"]?.DeepClone(),
                            ["reasons"] = supporting?["staleReasons"]?.DeepClone() });
                    }
                    candidates.Add(new JsonObject { ["runId"] = run["runId"]?.DeepClone(),
                        ["recordId"] = record["recordId"]?.DeepClone(),
                        ["status"] = record["status"]?.DeepClone(),
                        ["reasons"] = record["staleReasons"]?.DeepClone(), ["support"] = support });
                    if (candidates.Count >= 20) break;
                }
            audit["candidates"] = candidates;
            audit["eligible"] = false;
        }
        if (volumeFiles is null || !ScientificCapabilityRegistry.IsDeclared("gmsh-win-conda", "mesh.generate3d"))
        {
            if (audit is not null) audit["exportReason"] = volumeFiles is null
                ? "MATH3D tetrahedral consumer files are unavailable" : "Volume capability is not declared";
            return null;
        }
        foreach (var current in summary["currentRecords"]!.AsArray().OfType<JsonObject>()
            .Where(item => item["level"]?.GetValue<string>() == "L9"
                && item["capabilityId"]?.GetValue<string>() == "mesh.generate3d")
            .OrderByDescending(item => item["finishedAtUtc"]?.GetValue<string>(), StringComparer.Ordinal))
        {
            var run = runs.Single(item => item["runId"]?.GetValue<string>() == current["runId"]?.GetValue<string>());
            var directory = run["directory"]!.GetValue<string>();
            var result = JsonNode.Parse(File.ReadAllText(Path.Combine(directory, "results.json")))!;
            var record = run["qualifications"]!.AsArray().OfType<JsonObject>()
                .Single(item => item["recordId"]?.GetValue<string>() == current["recordId"]?.GetValue<string>());
            var evidence = result["l9GmshVolumeEvidence"];
            var msh = Path.Combine(directory, "volume", "positive-a", "cube.msh");
            var resource = Path.Combine(directory, "product", "volume.m3dt");
            if (evidence?["productContractSha256"]?.GetValue<string>() != Digest(volumeContract)
                || record["consumerSourceSha256"]?.GetValue<string>() != Digest(volumeFiles)
                || record["consumerContractSha256"]?.GetValue<string>() != Digest(volumeContract)
                || !File.Exists(msh) || !File.Exists(resource)
                || HashFile(msh) != evidence["sourceMshSha256"]?.GetValue<string>()
                || HashFile(resource) != evidence["artifactHashes"]?["volume.m3dt"]?.GetValue<string>()) continue;
            var lower = record["lowerQualification"]?["records"] as JsonArray;
            var currentIds = CurrentIds(runs, "L0", "L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "L9");
            if (lower is not { Count: 9 } || lower.Where((item, index) =>
                    item?["level"]?.GetValue<string>() != "L" + index
                    || item?["recordId"]?.GetValue<string>() is not { } id || !currentIds.Contains(id)).Any()) continue;
            var fingerprint = JsonNode.Parse(File.ReadAllText(Path.Combine(directory, "fingerprint.json")))!;
            var support = new JsonArray(lower.Select(item => item!.DeepClone()).ToArray());
            support.Add(new JsonObject { ["level"] = "L9", ["capabilityId"] = "mesh.generate3d",
                ["runId"] = current["runId"]?.DeepClone(), ["recordId"] = current["recordId"]?.DeepClone() });
            if (audit is not null) audit["eligible"] = true;
            return new JsonObject {
                ["runtimeId"] = "gmsh-win-conda", ["capabilityId"] = "mesh.generate3d", ["level"] = "L9",
                ["scope"] = "fixed public unit-cube tetrahedra", ["sourceRunId"] = current["runId"]?.DeepClone(),
                ["recordId"] = current["recordId"]?.DeepClone(),
                ["runFingerprintSha256"] = run["fingerprintSha256"]?.DeepClone(),
                ["suiteRevisionSha256"] = record["suiteRevisionSha256"]?.DeepClone(),
                ["qualificationSha256"] = run["qualificationSha256"]?.DeepClone(),
                ["workerContractSha256"] = fingerprint["components"]?["contract"]?["workerContractModule"]?["sha256"]?.DeepClone(),
                ["runtimeManifestSha256"] = fingerprint["components"]?["contract"]?["runtimeManifest"]?["sha256"]?.DeepClone(),
                ["adapterSha256"] = HashFile(Path.Combine(repo, "tools", "scientific-broker", "gmsh_volume_adapter.py")),
                ["brokerSha256"] = HashFile(Path.Combine(repo, "tools", "scientific-broker", "broker.py")),
                ["workerBinarySha256"] = HashFile(Path.Combine(repo, "tools", "scientific-gmsh-volume-worker.py")),
                ["exporterSha256"] = HashFile(Path.Combine(repo, "tools", "scientific-gmsh-tetmesh-export.py")),
                ["pythonSha256"] = fingerprint["components"]?["environment"]?["pythonExecutable"]?["sha256"]?.DeepClone(),
                ["packageRecordsSha256"] = fingerprint["components"]?["environment"]?["condaPackageRecords"]?["sha256"]?.DeepClone(),
                ["productContract"] = volumeContract.DeepClone(), ["productContractSha256"] = Digest(volumeContract),
                ["consumerSources"] = volumeFiles, ["consumerSourceSha256"] = Digest(volumeFiles),
                ["referenceInputSha256"] = result["inputArtifacts"]?[0]?["sha256"]?.DeepClone(),
                ["referenceWorkerArtifactSha256"] = evidence["sourceMshSha256"]?.DeepClone(),
                ["referenceArtifactSha256"] = evidence["artifactHashes"]?["volume.m3dt"]?.DeepClone(),
                ["sourceL8RunId"] = evidence["sourceL8RunId"]?.DeepClone(),
                ["sourceL8RecordId"] = evidence["sourceL8RecordId"]?.DeepClone(),
                ["supportingRecords"] = support
            };
        }
        if (audit is not null) audit["exportReason"] = summary["currentRecords"]!.AsArray().OfType<JsonObject>()
            .Any(item => item["level"]?.GetValue<string>() == "L9"
                && item["capabilityId"]?.GetValue<string>() == "mesh.generate3d")
            ? "Current L9 candidate failed product artifact or support checks"
            : "No current L9 volume qualification chain";
        return null;
    }
    static JsonObject Export(string repo, string installed, string math3d, string profile)
    {
        repo = Path.GetFullPath(repo);
        installed = Path.GetFullPath(installed);
        math3d = Path.GetFullPath(math3d);
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
            if (!ScientificCapabilityRegistry.IsDeclared("cgal-win-conda", "mesh.interop.vtk-math3d")) continue;
            var run = runs.Single(item => item["runId"]?.GetValue<string>() == current["runId"]?.GetValue<string>());
            var directory = run["directory"]!.GetValue<string>();
            var result = JsonNode.Parse(File.ReadAllText(Path.Combine(directory, "results.json")))!;
            var record = run["qualifications"]!.AsArray().OfType<JsonObject>()
                .Single(item => item["recordId"]?.GetValue<string>() == current["recordId"]?.GetValue<string>());
            var evidence = result["l9Evidence"]!;
            if (evidence["productContractSha256"]?.GetValue<string>() != Digest(contract)) continue;
            var consumerFiles = ProductSourceFiles(math3d);
            if (consumerFiles == null || Digest(consumerFiles) != record["consumerSourceSha256"]?.GetValue<string>()) continue;
            var output = Path.Combine(directory, "positive", "l5-positive.obj");
            if (!File.Exists(output) || HashFile(output) != evidence["worker"]?["artifactSha256"]?.GetValue<string>()) continue;
            var fingerprint = JsonNode.Parse(File.ReadAllText(Path.Combine(directory, "fingerprint.json")))!;
            var binaryHash = fingerprint["components"]?["worker"]?["executedFiles"]?.AsArray()
                .OfType<JsonObject>().FirstOrDefault(item => item["name"]?.GetValue<string>() == "devshell_cgal_worker.exe")?
                ["sha256"]?.GetValue<string>();
            if (binaryHash is not { Length: 64 }) continue;
            var lower = record["lowerQualification"]?["records"] as JsonArray;
            var currentIds = CurrentIds(runs, "L0", "L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "L9");
            if (lower is not { Count: 9 } || lower.Where((item, index) =>
                    item?["level"]?.GetValue<string>() != "L" + index
                    || item?["recordId"]?.GetValue<string>() is not { } id || !currentIds.Contains(id)).Any()) continue;
            var support = new JsonArray(lower.Select(item => item!.DeepClone()).ToArray());
            support.Add(new JsonObject { ["level"] = "L9", ["capabilityId"] = "mesh.interop.vtk-math3d",
                ["runId"] = current["runId"]?.DeepClone(), ["recordId"] = current["recordId"]?.DeepClone() });
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
                ["consumerSources"] = consumerFiles, ["consumerSourceSha256"] = Digest(consumerFiles),
                ["referenceInputSha256"] = evidence["worker"]?["inputSha256"]?.DeepClone(),
                ["referenceArtifactSha256"] = evidence["worker"]?["artifactSha256"]?.DeepClone(),
                ["sourceL8RunId"] = evidence["sourceL8RunId"]?.DeepClone(),
                ["sourceL8RecordId"] = evidence["sourceL8RecordId"]?.DeepClone(),
                ["supportingRecords"] = support
            });
        }
        var gmsh = ExportGmsh(repo, installed, math3d, profile);
        if (gmsh != null) certified.Add(gmsh);
        var gmshVolume = ExportGmshVolume(repo, installed, math3d, profile);
        if (gmshVolume != null) certified.Add(gmshVolume);
        var repair = ExportRepair(repo, installed, math3d, profile);
        if (repair != null) certified.Add(repair);
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
            || capabilities.Any(item => item?["runtimeId"]?.GetValue<string>() is not ("cgal-win-conda" or "gmsh-win-conda")
                || item?["capabilityId"]?.GetValue<string>() is not ("mesh.interop.vtk-math3d" or "mesh.generate" or "mesh.generate3d" or "mesh.repair")
                || (item?["runtimeId"]?.GetValue<string>() == "cgal-win-conda"
                    && item?["capabilityId"]?.GetValue<string>() is not ("mesh.interop.vtk-math3d" or "mesh.repair"))
                || !ScientificCapabilityRegistry.IsDeclared(item?["runtimeId"]?.GetValue<string>() ?? "",
                    item?["capabilityId"]?.GetValue<string>() ?? "")
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
            if (args.Length == 5 && args[0] == "audit-volume")
            {
                var audit = new JsonObject { ["schemaVersion"] = 1, ["kind"] = "scientific.gmsh-volume-export-audit" };
                ExportGmshVolume(Path.GetFullPath(args[1]), Path.GetFullPath(args[2]),
                    Path.GetFullPath(args[3]), args[4], audit);
                Console.WriteLine(audit.ToJsonString(new JsonSerializerOptions { WriteIndented = true }));
                return 0;
            }
            if (args.Length == 5 && args[0] == "audit-repair")
            {
                var audit = AuditRepair(Path.GetFullPath(args[1]), Path.GetFullPath(args[2]),
                    Path.GetFullPath(args[3]), args[4]);
                Console.WriteLine(audit.ToJsonString(new JsonSerializerOptions { WriteIndented = true }));
                return 0;
            }
            if (args.Length == 2 && args[0] == "verify") { Verify(args[1]); Console.WriteLine("Certified manifest verified."); return 0; }
            Console.Error.WriteLine("Usage: export <repo> <installed-root> <math3d-root> <profile> <manifest.json> | audit-volume|audit-repair <repo> <installed-root> <math3d-root> <profile> | verify <manifest.json>");
            return 2;
        }
        catch (Exception error) { Console.Error.WriteLine(error.Message); return 1; }
    }
}
