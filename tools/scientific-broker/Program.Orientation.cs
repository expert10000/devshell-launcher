using System.Text.Json.Nodes;
using BatchLauncher;

static partial class BrokerManifest
{
    static readonly string[] OrientationConsumers = ["renderer/src/mesh/surfaceMesh.ts", "renderer/src/mesh/meshDocumentAdapter.ts",
        "renderer/src/mesh/meshResourceStore.ts", "packages/core/src/meshDocument.ts",
        "src/main/python/nativeCgalProtocol.ts", "renderer/src/workspace/MeshDocumentViewport.tsx"];
    static readonly string[] OrientationSources = ["scientific/cgal-worker/orientation.cpp", "tools/scientific-cgal-worker.py",
        "tools/scientific_worker_contract.py", "tools/scientific_cgal_corpus.py", "tools/scientific_cgal_orientation_fixture.py",
        "tools/scientific_cgal_orientation_scope.py", "tools/scientific_cgal_orientation_qualification.py",
        "tools/scientific_cgal_orientation_l7.py", "tools/scientific_cgal_orientation_l8.py",
        "tools/scientific_cgal_orientation_l9.py", "tools/math3d-cgal-orientation-product.mjs",
        "tools/math3d-cgal-orientation-viewer.mjs", "tools/scientific-cgal-repair-m3dm-roundtrip.py",
        "BatchLauncher/Form1.Scientific.CgalOrientation.cs", "BatchLauncher/ScientificQualificationRecords.Orientation.cs",
        "BatchLauncher/ScientificRunFingerprint.cs", "tools/runtime-lab/Program.cs",
        "tools/scientific-broker/Program.cs", "tools/scientific-broker/Program.Repair.cs",
        "tools/scientific-broker/Program.Orientation.cs", "tools/scientific-broker/broker.py",
        "tools/scientific-broker/orientation_broker_smoke.py"];

    static JsonObject OrientationContract() => new() { ["id"] = "math3d.orientation-handoff", ["version"] = 1,
        ["inputFormat"] = "obj", ["outputFormat"] = "obj", ["scopeVersion"] = 2,
        ["viewer"] = "MeshDocumentViewport" };

    static JsonObject? OrientationFiles(string root, IEnumerable<string> names)
    {
        var files = new JsonObject();
        foreach (var name in names)
        {
            var path = Path.Combine(root, name.Replace('/', Path.DirectorySeparatorChar));
            if (!File.Exists(path)) return null;
            files[name] = HashFile(path);
        }
        return files;
    }

    static JsonObject? ExportOrientation(string repo, string installed, string math3d, string profile)
    {
        if (!ScientificCapabilityRegistry.IsDeclared("cgal-win-conda", "mesh.orient")) return null;
        var files = OrientationFiles(math3d, OrientationConsumers);
        var sources = OrientationFiles(repo, OrientationSources);
        if (files == null || sources == null) return null;
        var runs = RepairRuns(repo, installed, math3d, profile);
        foreach (var run in runs)
            if (run["qualifications"] is JsonArray records)
            {
                ScientificQualificationRecords.AssessOrientationL7Consumer(records,
                    files["renderer/src/mesh/surfaceMesh.ts"]?.GetValue<string>());
                ScientificQualificationRecords.AssessOrientationL9Consumer(records, Digest(files));
            }
        var ids = CurrentIds(runs, "L0", "L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "L9");
        var summary = ScientificQualificationRecords.Summarize("cgal-win-conda", runs);
        var fixturePath = Path.Combine(repo, "scientific", "fixtures", "cgal", "orientation", "manifest.v2.json");
        var fixtures = JsonNode.Parse(File.ReadAllText(fixturePath))?["cases"] as JsonArray;
        if (fixtures is not { Count: 12 }) return null;
        foreach (var current in summary["currentRecords"]!.AsArray().OfType<JsonObject>()
            .Where(item => item["level"]?.GetValue<string>() == "L9" && item["capabilityId"]?.GetValue<string>() == "mesh.orient")
            .OrderByDescending(item => item["finishedAtUtc"]?.GetValue<string>(), StringComparer.Ordinal))
        {
            var run = runs.Single(item => item["runId"]?.GetValue<string>() == current["runId"]?.GetValue<string>());
            var directory = run["directory"]!.GetValue<string>();
            var result = JsonNode.Parse(File.ReadAllText(Path.Combine(directory, "results.json")))!;
            var evidence = result["orientationQualificationEvidence"];
            var record = run["qualifications"]!.AsArray().OfType<JsonObject>()
                .Single(item => item["recordId"]?.GetValue<string>() == current["recordId"]?.GetValue<string>());
            var lower = record["lowerQualification"]?["records"] as JsonArray;
            if (lower is not { Count: 9 } || lower.Where((item, index) =>
                item?["level"]?.GetValue<string>() != "L" + index
                || item?["recordId"]?.GetValue<string>() is not { } id || !ids.Contains(id)).Any()
                || record["consumerSourceSha256"]?.GetValue<string>() != Digest(files)) continue;
            var report = Path.GetFullPath(Path.Combine(directory, evidence!["reportPath"]!.GetValue<string>()));
            var l9 = JsonNode.Parse(File.ReadAllText(report))!;
            var l8 = JsonNode.Parse(File.ReadAllText(l9["l8Path"]!.GetValue<string>()))!;
            var l7 = JsonNode.Parse(File.ReadAllText(l8["l7Path"]!.GetValue<string>()))!;
            var l6 = JsonNode.Parse(File.ReadAllText(l7["l6Path"]!.GetValue<string>()))!;
            var l5 = JsonNode.Parse(File.ReadAllText(l6["l5Path"]!.GetValue<string>()))!;
            var replay = JsonNode.Parse(File.ReadAllText(l6["replayPath"]!.GetValue<string>()))!;
            var outputs = replay["cases"]!.AsArray().OfType<JsonObject>()
                .ToDictionary(item => item["caseId"]!.GetValue<string>(), item => item["outputSha256"]?.GetValue<string>());
            var references = new JsonArray();
            var valid = true;
            foreach (var fixture in fixtures.OfType<JsonObject>())
            {
                var caseId = fixture["caseId"]!.GetValue<string>();
                var input = Path.Combine(repo, fixture["path"]!.GetValue<string>().Replace('/', Path.DirectorySeparatorChar));
                if (!outputs.TryGetValue(caseId, out var output)
                    || (fixture["expected"]?.GetValue<string>() == "accepted") != (output != null)
                    || !File.Exists(input) || HashFile(input) != fixture["sha256"]?.GetValue<string>())
                { valid = false; break; }
                references.Add(new JsonObject { ["caseId"] = caseId, ["inputSha256"] = fixture["sha256"]?.DeepClone(),
                    ["outputSha256"] = output, ["expected"] = fixture["expected"]?.DeepClone(),
                    ["orientation"] = fixture["orientation"]?.DeepClone(),
                    ["errorContains"] = fixture["errorContains"]?.DeepClone() });
            }
            if (!valid || references.Count != 12) continue;
            var fingerprint = JsonNode.Parse(File.ReadAllText(Path.Combine(directory, "fingerprint.json")))!;
            var worker = l5["workerPath"]?.GetValue<string>();
            if (worker == null || !File.Exists(worker) || HashFile(worker) != l5["workerSha256"]?.GetValue<string>()) continue;
            var support = new JsonArray(lower.Select(item => item!.DeepClone()).ToArray());
            support.Add(new JsonObject { ["level"] = "L9", ["capabilityId"] = "mesh.orient",
                ["runId"] = current["runId"]?.DeepClone(), ["recordId"] = current["recordId"]?.DeepClone() });
            var contract = OrientationContract();
            return new JsonObject { ["runtimeId"] = "cgal-win-conda", ["capabilityId"] = "mesh.orient", ["level"] = "L9",
                ["scope"] = "eight accepted and four rejected pinned closed-mesh orientation cases",
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
                ["orientationSources"] = sources, ["orientationSourcesSha256"] = Digest(sources),
                ["fixtureManifestSha256"] = HashFile(fixturePath), ["referenceCases"] = references,
                ["referenceInputSha256"] = references[0]?["inputSha256"]?.DeepClone(),
                ["referenceArtifactSha256"] = references[0]?["outputSha256"]?.DeepClone(),
                ["sourceL8RunId"] = evidence["sourceRunId"]?.DeepClone(),
                ["sourceL8RecordId"] = evidence["sourceRecordId"]?.DeepClone(),
                ["supportingRecords"] = support };
        }
        return null;
    }

    static JsonObject AuditOrientation(string repo, string installed, string math3d, string profile)
    {
        var rejected = new List<JsonObject>();
        var runs = RepairRuns(repo, installed, math3d, profile, rejected);
        var files = OrientationFiles(math3d, OrientationConsumers);
        foreach (var run in runs)
            if (run["qualifications"] is JsonArray records)
            {
                ScientificQualificationRecords.AssessOrientationL7Consumer(records,
                    files?["renderer/src/mesh/surfaceMesh.ts"]?.GetValue<string>());
                ScientificQualificationRecords.AssessOrientationL9Consumer(records,
                    files == null ? null : Digest(files));
            }
        return new JsonObject { ["schemaVersion"] = 1, ["kind"] = "scientific.cgal-orientation-export-audit",
            ["runs"] = runs.Count, ["rejected"] = new JsonArray(rejected.Select(item => (JsonNode?)item).ToArray()),
            ["records"] = new JsonArray(Records(runs).Where(item => item["capabilityId"]?.GetValue<string>() == "mesh.orient")
                .Select(item => (JsonNode?)item.DeepClone()).ToArray()) };
    }
}
