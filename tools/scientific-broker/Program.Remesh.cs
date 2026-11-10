using System.Text.Json.Nodes;
using BatchLauncher;

static partial class BrokerManifest
{
    static readonly string[] RemeshCases = ["accepted", "volume-loss", "affine-accepted", "affine-volume-loss",
        "cube-accepted", "cube-volume-loss", "octa-accepted", "octa-volume-loss"];
    static readonly string[] RemeshConsumers = ["renderer/src/mesh/surfaceMesh.ts", "renderer/src/mesh/meshDocumentAdapter.ts",
        "renderer/src/mesh/meshResourceStore.ts", "packages/core/src/meshDocument.ts",
        "src/main/python/nativeCgalProtocol.ts", "renderer/src/workspace/MeshDocumentViewport.tsx"];

    static JsonObject RemeshContract() => new() { ["id"] = "math3d.guarded-remesh-handoff", ["version"] = 1,
        ["inputFormat"] = "obj", ["outputFormat"] = "obj", ["policyVersion"] = 2,
        ["viewer"] = "MeshDocumentViewport" };

    static JsonObject? RemeshSourceFiles(string root)
    {
        var files = new JsonObject();
        foreach (var name in RemeshConsumers)
        {
            var path = Path.Combine(root, name.Replace('/', Path.DirectorySeparatorChar));
            if (!File.Exists(path)) return null;
            files[name] = HashFile(path);
        }
        return files;
    }

    static JsonObject? ExportRemesh(string repo, string installed, string math3d, string profile)
    {
        if (!ScientificCapabilityRegistry.IsDeclared("cgal-win-conda", "mesh.remesh")) return null;
        var files = RemeshSourceFiles(math3d);
        if (files == null) return null;
        var runs = RepairRuns(repo, installed, math3d, profile);
        var ids = CurrentIds(runs, "L0", "L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "L9");
        foreach (var run in runs)
            if (run["qualifications"] is JsonArray records)
                ScientificQualificationRecords.AssessRemeshL9Consumer(records, Digest(files));
        var summary = ScientificQualificationRecords.Summarize("cgal-win-conda", runs);
        var fixturesPath = Path.Combine(repo, "scientific", "fixtures", "cgal-remesh-qualification", "manifest.json");
        var fixtures = JsonNode.Parse(File.ReadAllText(fixturesPath))?["cases"] as JsonArray;
        if (fixtures is null) return null;
        foreach (var current in summary["currentRecords"]!.AsArray().OfType<JsonObject>()
            .Where(item => item["level"]?.GetValue<string>() == "L9" && item["capabilityId"]?.GetValue<string>() == "mesh.remesh")
            .OrderByDescending(item => item["finishedAtUtc"]?.GetValue<string>(), StringComparer.Ordinal))
        {
            var run = runs.Single(item => item["runId"]?.GetValue<string>() == current["runId"]?.GetValue<string>());
            var directory = run["directory"]!.GetValue<string>();
            var result = JsonNode.Parse(File.ReadAllText(Path.Combine(directory, "results.json")))!;
            var evidence = result["remeshQualificationEvidence"];
            var record = run["qualifications"]!.AsArray().OfType<JsonObject>()
                .Single(item => item["recordId"]?.GetValue<string>() == current["recordId"]?.GetValue<string>());
            var lower = record["lowerQualification"]?["records"] as JsonArray;
            if (lower is not { Count: 9 } || lower.Where((item, index) =>
                item?["level"]?.GetValue<string>() != "L" + index
                || item?["recordId"]?.GetValue<string>() is not { } id || !ids.Contains(id)).Any()
                || record["consumerSourceSha256"]?.GetValue<string>() != Digest(files)) continue;
            var reportPath = Path.GetFullPath(Path.Combine(directory, evidence!["reportPath"]!.GetValue<string>()));
            var l9 = JsonNode.Parse(File.ReadAllText(reportPath))!;
            var l8 = JsonNode.Parse(File.ReadAllText(l9["l8Path"]!.GetValue<string>()))!;
            var l7 = JsonNode.Parse(File.ReadAllText(l8["l7Path"]!.GetValue<string>()))!;
            var l6 = JsonNode.Parse(File.ReadAllText(l7["l6Path"]!.GetValue<string>()))!;
            var l5 = JsonNode.Parse(File.ReadAllText(l6["reproductionPath"]!.GetValue<string>()))!;
            var outputByCase = l5["cases"]!.AsArray().OfType<JsonObject>()
                .ToDictionary(item => item["caseId"]!.GetValue<string>(), item => item["outputSha256"]?.GetValue<string>());
            var references = new JsonArray();
            var valid = true;
            foreach (var id in RemeshCases)
            {
                var fixture = fixtures.OfType<JsonObject>().SingleOrDefault(item => item["caseId"]?.GetValue<string>() == id);
                if (fixture == null || !outputByCase.TryGetValue(id, out var output)
                    || fixture["expected"]?.GetValue<string>() == "accepted" != (output != null)
                    || !File.Exists(Path.Combine(repo, fixture["path"]!.GetValue<string>().Replace('/', Path.DirectorySeparatorChar)))
                    || HashFile(Path.Combine(repo, fixture["path"]!.GetValue<string>().Replace('/', Path.DirectorySeparatorChar))) != fixture["sha256"]?.GetValue<string>())
                { valid = false; break; }
                references.Add(new JsonObject { ["caseId"] = id, ["inputSha256"] = fixture["sha256"]?.DeepClone(),
                    ["outputSha256"] = output, ["expected"] = fixture["expected"]?.DeepClone(),
                    ["targetEdge"] = fixture["targetEdge"]?.DeepClone(), ["iterations"] = fixture["iterations"]?.DeepClone() });
            }
            if (!valid || references.Count != 8) continue;
            var fingerprint = JsonNode.Parse(File.ReadAllText(Path.Combine(directory, "fingerprint.json")))!;
            var worker = l5["workerPath"]?.GetValue<string>();
            if (worker == null || !File.Exists(worker) || HashFile(worker) != l5["workerSha256"]?.GetValue<string>()) continue;
            var support = new JsonArray(lower.Select(item => item!.DeepClone()).ToArray());
            support.Add(new JsonObject { ["level"] = "L9", ["capabilityId"] = "mesh.remesh",
                ["runId"] = current["runId"]?.DeepClone(), ["recordId"] = current["recordId"]?.DeepClone() });
            var contract = RemeshContract();
            return new JsonObject { ["runtimeId"] = "cgal-win-conda", ["capabilityId"] = "mesh.remesh", ["level"] = "L9",
                ["scope"] = "eight pinned guarded remesh cases across tetrahedron, cube and octahedron",
                ["sourceRunId"] = current["runId"]?.DeepClone(), ["recordId"] = current["recordId"]?.DeepClone(),
                ["runFingerprintSha256"] = run["fingerprintSha256"]?.DeepClone(),
                ["suiteRevisionSha256"] = record["suiteRevisionSha256"]?.DeepClone(),
                ["qualificationSha256"] = run["qualificationSha256"]?.DeepClone(),
                ["workerContractSha256"] = fingerprint["components"]?["contract"]?["workerContractModule"]?["sha256"]?.DeepClone(),
                ["runtimeManifestSha256"] = fingerprint["components"]?["contract"]?["runtimeManifest"]?["sha256"]?.DeepClone(),
                ["adapterSha256"] = HashFile(Path.Combine(repo, "tools", "scientific-cgal-worker.py")),
                ["workerBinarySha256"] = HashFile(worker),
                ["pythonSha256"] = fingerprint["components"]?["environment"]?["pythonExecutable"]?["sha256"]?.DeepClone(),
                ["packageRecordsSha256"] = fingerprint["components"]?["environment"]?["condaPackageRecords"]?["sha256"]?.DeepClone(),
                ["productContract"] = contract, ["productContractSha256"] = Digest(contract),
                ["consumerSources"] = files, ["consumerSourceSha256"] = Digest(files),
                ["policySha256"] = l9["policySha256"]?.DeepClone(),
                ["guardSourceSha256"] = HashFile(Path.Combine(repo, "tools", "scientific_cgal_remesh_guard.py")),
                ["fixtureManifestSha256"] = HashFile(fixturesPath), ["referenceCases"] = references,
                ["referenceInputSha256"] = references[0]?["inputSha256"]?.DeepClone(),
                ["referenceArtifactSha256"] = references[0]?["outputSha256"]?.DeepClone(),
                ["sourceL8RunId"] = evidence["sourceRunId"]?.DeepClone(),
                ["sourceL8RecordId"] = evidence["sourceRecordId"]?.DeepClone(),
                ["supportingRecords"] = support };
        }
        return null;
    }

    static JsonObject AuditRemesh(string repo, string installed, string math3d, string profile)
    {
        var rejected = new List<JsonObject>();
        var runs = ReadRuns(repo, installed, profile, "cgal-win-conda", rejected);
        var ids = CurrentIds(runs, "L0", "L1", "L2", "L3", "L4");
        AssessDependencies(runs, ids, l6: false, l7: false, l8: false, l9: false);
        ids.UnionWith(CurrentIds(runs, "L5"));
        AssessDependencies(runs, ids, l7: false, l8: false, l9: false);
        ids.UnionWith(CurrentIds(runs, "L6"));
        foreach (var run in runs)
            if (run["qualifications"] is JsonArray records)
                ScientificQualificationRecords.AssessL7Consumer(records,
                    File.Exists(Path.Combine(math3d, "renderer/src/mesh/surfaceMesh.ts"))
                        ? HashFile(Path.Combine(math3d, "renderer/src/mesh/surfaceMesh.ts")) : null);
        ids.UnionWith(CurrentIds(runs, "L7"));
        AssessDependencies(runs, ids, l9: false);
        ids.UnionWith(CurrentIds(runs, "L8"));
        foreach (var run in runs)
            if (run["qualifications"] is JsonArray records)
            {
                ScientificQualificationRecords.AssessL5Dependencies(records, ids);
                ScientificQualificationRecords.AssessRemeshL9Consumer(records,
                    RemeshSourceFiles(math3d) is { } files ? Digest(files) : null);
            }
        return new JsonObject { ["schemaVersion"] = 1, ["kind"] = "scientific.cgal-remesh-export-audit",
            ["runs"] = runs.Count, ["rejected"] = new JsonArray(rejected.Select(item => (JsonNode?)item).ToArray()),
            ["records"] = new JsonArray(Records(runs).Where(item => item["capabilityId"]?.GetValue<string>() == "mesh.remesh")
                .Select(item => (JsonNode?)item.DeepClone()).ToArray()) };
    }
}
