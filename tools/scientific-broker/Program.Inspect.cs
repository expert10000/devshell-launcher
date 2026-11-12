using System.Text.Json.Nodes;
using BatchLauncher;

static partial class BrokerManifest
{
    static readonly string[] InspectConsumers = ["renderer/src/mesh/surfaceMesh.ts",
        "renderer/src/workspace/MeshDocumentViewport.tsx", "packages/core/src/meshDocument.ts"];
    static readonly string[] InspectSources = ["tools/scientific-cgal-worker.py",
        "tools/scientific_worker_contract.py", "tools/scientific_cgal_inspect_qualification.py",
        "scientific/fixtures/cgal-inspect/manifest.v3.json",
        "schemas/scientific-mesh-inspect.v2.json",
        "schemas/scientific-mesh-inspect-classes.v1.json", "tools/scientific-broker/inspect_classes.py",
        "scientific/fixtures/inspect-shared/tetra-holdout.obj",
        "scientific/fixtures/inspect-shared/octa-holdout.obj",
        "scientific/fixtures/inspect-shared/cube-holdout.obj",
        "scientific/fixtures/inspect-shared/sphere-128.obj",
        "scientific/fixtures/inspect-shared/sphere-512.obj",
        "scientific/fixtures/inspect-shared/sphere-2048.obj",
        "BatchLauncher/Form1.Scientific.CgalInspect.cs",
        "BatchLauncher/ScientificQualificationRecords.Inspect.cs",
        "BatchLauncher/ScientificRunFingerprint.cs", "tools/scientific-broker/Program.Inspect.cs",
        "tools/scientific-broker/broker.py"];

    static JsonObject InspectContract() => new() { ["id"] = "math3d.mesh-inspect-handoff",
        ["version"] = 1, ["inputFormat"] = "obj", ["outputFormat"] = "obj",
        ["scopeVersion"] = 3, ["viewer"] = "MeshDocumentViewport" };

    static JsonObject? InspectFiles(string root, IEnumerable<string> names)
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

    static JsonObject? ExportInspect(string repo, string installed, string math3d, string profile)
    {
        if (!ScientificCapabilityRegistry.IsDeclared("cgal-win-conda", "mesh.inspect")) return null;
        var consumers = InspectFiles(math3d, InspectConsumers);
        var sources = InspectFiles(repo, InspectSources);
        if (consumers == null || sources == null) return null;
        var runs = RepairRuns(repo, installed, math3d, profile);
        var importer = Path.Combine(math3d, "renderer", "src", "mesh", "surfaceMesh.ts");
        foreach (var run in runs)
            if (run["qualifications"] is JsonArray records)
                ScientificQualificationRecords.AssessInspectConsumers(records,
                    File.Exists(importer) ? HashFile(importer) : null, Digest(consumers));
        var ids = CurrentIds(runs, "L0", "L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "L9");
        var summary = ScientificQualificationRecords.Summarize("cgal-win-conda", runs);
        var fixturePath = Path.Combine(repo, "scientific", "fixtures", "cgal-inspect", "manifest.v3.json");
        var fixtures = JsonNode.Parse(File.ReadAllText(fixturePath))?["cases"] as JsonArray;
        if (fixtures is not { Count: 13 }) return null;
        foreach (var current in summary["currentRecords"]!.AsArray().OfType<JsonObject>()
            .Where(item => item["level"]?.GetValue<string>() == "L9"
                && item["capabilityId"]?.GetValue<string>() == "mesh.inspect"
                && item["evidenceId"]?.GetValue<string>() == "l9.cgal-inspect")
            .OrderByDescending(item => item["finishedAtUtc"]?.GetValue<string>(), StringComparer.Ordinal))
        {
            var run = runs.Single(item => item["runId"]?.GetValue<string>() == current["runId"]?.GetValue<string>());
            var directory = run["directory"]!.GetValue<string>();
            var result = JsonNode.Parse(File.ReadAllText(Path.Combine(directory, "results.json")))!;
            var evidence = result["inspectQualificationEvidence"]!;
            var record = run["qualifications"]!.AsArray().OfType<JsonObject>()
                .Single(item => item["recordId"]?.GetValue<string>() == current["recordId"]?.GetValue<string>());
            var lower = record["lowerQualification"]?["records"] as JsonArray;
            if (lower is not { Count: 9 } || lower.Where((item, index) =>
                item?["level"]?.GetValue<string>() != "L" + index
                || item?["recordId"]?.GetValue<string>() is not { } id || !ids.Contains(id)).Any()
                || record["consumerSourceSha256"]?.GetValue<string>() != Digest(consumers)) continue;
            var l9 = JsonNode.Parse(File.ReadAllText(Path.Combine(directory, evidence["reportPath"]!.GetValue<string>())))!;
            var l8 = JsonNode.Parse(File.ReadAllText(l9["l8Path"]!.GetValue<string>()))!;
            var l7 = JsonNode.Parse(File.ReadAllText(l8["l7Path"]!.GetValue<string>()))!;
            var l6 = JsonNode.Parse(File.ReadAllText(l7["l6Path"]!.GetValue<string>()))!;
            var l5 = JsonNode.Parse(File.ReadAllText(l6["l5Path"]!.GetValue<string>()))!;
            var outputs = l6["cases"]!.AsArray().OfType<JsonObject>()
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
                references.Add(new JsonObject { ["caseId"] = caseId,
                    ["inputSha256"] = fixture["sha256"]?.DeepClone(), ["outputSha256"] = output,
                    ["expected"] = fixture["expected"]?.DeepClone() });
            }
            var worker = l5["workerPath"]?.GetValue<string>();
            if (!valid || references.Count != 13 || worker == null || !File.Exists(worker)
                || HashFile(worker) != l5["workerSha256"]?.GetValue<string>()) continue;
            var fingerprint = JsonNode.Parse(File.ReadAllText(Path.Combine(directory, "fingerprint.json")))!;
            var support = new JsonArray(lower.Select(item => item!.DeepClone()).ToArray());
            support.Add(new JsonObject { ["level"] = "L9", ["capabilityId"] = "mesh.inspect",
                ["runId"] = current["runId"]?.DeepClone(), ["recordId"] = current["recordId"]?.DeepClone() });
            var contract = InspectContract();
            return new JsonObject { ["runtimeId"] = "cgal-win-conda", ["capabilityId"] = "mesh.inspect", ["level"] = "L9",
                ["scope"] = "ten pinned closed OBJ inspections including three independent holdouts and three no-output rejections",
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
                ["consumerSources"] = consumers, ["consumerSourceSha256"] = Digest(consumers),
                ["inspectSources"] = sources, ["inspectSourcesSha256"] = Digest(sources),
                ["fixtureManifestSha256"] = HashFile(fixturePath), ["referenceCases"] = references,
                ["referenceInputSha256"] = references[0]?["inputSha256"]?.DeepClone(),
                ["referenceArtifactSha256"] = references[0]?["outputSha256"]?.DeepClone(),
                ["sourceL8RunId"] = evidence["sourceRunId"]?.DeepClone(),
                ["sourceL8RecordId"] = evidence["sourceRecordId"]?.DeepClone(),
                ["supportingRecords"] = support };
        }
        return null;
    }
}
