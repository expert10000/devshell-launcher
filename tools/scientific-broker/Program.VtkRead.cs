using System.Text.Json.Nodes;
using BatchLauncher;

static partial class BrokerManifest
{
    static readonly string[] VtkReadConsumers = ["renderer/src/mesh/surfaceMesh.ts", "renderer/src/mesh/meshDocumentAdapter.ts",
        "renderer/src/mesh/meshResourceStore.ts", "packages/core/src/meshDocument.ts",
        "src/main/python/nativeCgalProtocol.ts", "renderer/src/workspace/MeshDocumentViewport.tsx"];
    static readonly string[] VtkReadSources = ["tools/scientific-mesh-worker.py", "tools/scientific_worker_contract.py",
        "tools/scientific_vtk_read_scope.py", "tools/scientific_vtk_read_qualification.py",
        "tools/scientific-artifact-roundtrip.py", "tools/scientific-vtk-interop.py",
        "tools/math3d-vtk-import-handoff.mjs", "tools/math3d-vtk-read-product.mjs",
        "tools/math3d-vtk-read-viewer.mjs", "tools/scientific-cgal-repair-m3dm-roundtrip.py",
        "BatchLauncher/Form1.Scientific.VtkRead.cs", "BatchLauncher/ScientificQualificationRecords.VtkRead.cs",
        "BatchLauncher/ScientificRunFingerprint.cs", "tools/runtime-lab/Program.cs",
        "tools/scientific-broker/Program.cs", "tools/scientific-broker/Program.VtkRead.cs",
        "tools/scientific-broker/broker.py", "tools/scientific-broker/vtk_read_adapter.py",
        "tools/scientific-broker/vtk_read_broker_smoke.py",
        "schemas/scientific-mesh-inspect-classes.v3.json", "tools/scientific-broker/inspect_classes.py",
        "tools/scientific-broker/generate_inspect_topology.py",
        "scientific/fixtures/inspect-topology/concave-uv-512.obj",
        "scientific/fixtures/inspect-topology/concave-ico-320-holdout.obj",
        "scientific/fixtures/inspect-topology/torus-grid-256.obj",
        "scientific/fixtures/inspect-topology/torus-grid-400-holdout.obj",
        "scientific/fixtures/inspect-topology/torus-flipped.obj",
        "scientific/fixtures/inspect-topology/torus-scrambled.obj",
        "scientific/fixtures/inspect-shared/tetra-holdout.obj",
        "scientific/fixtures/inspect-shared/octa-holdout.obj",
        "scientific/fixtures/inspect-shared/cube-holdout.obj"];

    static JsonObject VtkReadContract() => new() { ["id"] = "math3d.vtk-mesh-read-handoff", ["version"] = 1,
        ["inputFormat"] = "obj-ply-vtp", ["outputFormat"] = "vtp-and-obj", ["scopeVersion"] = 4,
        ["viewer"] = "MeshDocumentViewport" };

    static JsonObject? VtkReadFiles(string root, IEnumerable<string> names)
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

    static List<JsonObject> VtkReadRuns(string repo, string installed, string math3d, string profile)
    {
        var runs = ReadRuns(repo, installed, profile, "vtk-win-conda");
        var ids = CurrentIds(runs, "L0", "L1", "L2", "L3", "L4");
        AssessDependencies(runs, ids, l6: false, l7: false, l8: false, l9: false);
        ids.UnionWith(CurrentIds(runs, "L5"));
        AssessDependencies(runs, ids, l7: false, l8: false, l9: false);
        ids.UnionWith(CurrentIds(runs, "L6"));
        var importer = Path.Combine(math3d, "renderer", "src", "mesh", "surfaceMesh.ts");
        foreach (var run in runs)
            if (run["qualifications"] is JsonArray records)
            {
                ScientificQualificationRecords.AssessL5Dependencies(records, ids, includeL8: false, includeL9: false);
                ScientificQualificationRecords.AssessVtkReadConsumers(records,
                    File.Exists(importer) ? HashFile(importer) : null, null, includeProduct: false);
            }
        ids.UnionWith(CurrentIds(runs, "L7"));
        AssessDependencies(runs, ids, l9: false);
        ids.UnionWith(CurrentIds(runs, "L8"));
        var consumers = VtkReadFiles(math3d, VtkReadConsumers);
        foreach (var run in runs)
            if (run["qualifications"] is JsonArray records)
            {
                ScientificQualificationRecords.AssessL5Dependencies(records, ids);
                ScientificQualificationRecords.AssessVtkReadConsumers(records,
                    File.Exists(importer) ? HashFile(importer) : null,
                    consumers == null ? null : Digest(consumers));
            }
        return runs;
    }

    static JsonObject? ExportVtkRead(string repo, string installed, string math3d, string profile)
    {
        if (!ScientificCapabilityRegistry.IsDeclared("vtk-win-conda", "mesh.read")) return null;
        var consumers = VtkReadFiles(math3d, VtkReadConsumers);
        var sources = VtkReadFiles(repo, VtkReadSources);
        if (consumers == null || sources == null) return null;
        var runs = VtkReadRuns(repo, installed, math3d, profile);
        var ids = CurrentIds(runs, "L0", "L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "L9");
        var summary = ScientificQualificationRecords.Summarize("vtk-win-conda", runs);
        var fixturePath = Path.Combine(repo, "scientific", "fixtures", "vtk", "read", "manifest.v4.json");
        var fixtures = JsonNode.Parse(File.ReadAllText(fixturePath))?["cases"] as JsonArray;
        if (fixtures is not { Count: 15 }) return null;
        foreach (var current in summary["currentRecords"]!.AsArray().OfType<JsonObject>()
            .Where(item => item["level"]?.GetValue<string>() == "L9" && item["capabilityId"]?.GetValue<string>() == "mesh.read"
                && item["evidenceId"]?.GetValue<string>() == "l9.vtk-read")
            .OrderByDescending(item => item["finishedAtUtc"]?.GetValue<string>(), StringComparer.Ordinal))
        {
            var run = runs.Single(item => item["runId"]?.GetValue<string>() == current["runId"]?.GetValue<string>());
            var directory = run["directory"]!.GetValue<string>();
            var result = JsonNode.Parse(File.ReadAllText(Path.Combine(directory, "results.json")))!;
            var evidence = result["vtkReadQualificationEvidence"]!;
            var record = run["qualifications"]!.AsArray().OfType<JsonObject>()
                .Single(item => item["recordId"]?.GetValue<string>() == current["recordId"]?.GetValue<string>());
            var lower = record["lowerQualification"]?["records"] as JsonArray;
            if (lower is not { Count: 9 } || lower.Where((item, index) =>
                item?["level"]?.GetValue<string>() != "L" + index
                || item?["recordId"]?.GetValue<string>() is not { } id || !ids.Contains(id)).Any()
                || record["consumerSourceSha256"]?.GetValue<string>() != Digest(consumers)) continue;
            var report = Path.GetFullPath(Path.Combine(directory, evidence["reportPath"]!.GetValue<string>()));
            var l9 = JsonNode.Parse(File.ReadAllText(report))!;
            var l8 = JsonNode.Parse(File.ReadAllText(l9["l8Path"]!.GetValue<string>()))!;
            var l7 = JsonNode.Parse(File.ReadAllText(l8["l7Path"]!.GetValue<string>()))!;
            var l6 = JsonNode.Parse(File.ReadAllText(l7["l6Path"]!.GetValue<string>()))!;
            var replay = JsonNode.Parse(File.ReadAllText(l6["replayPath"]!.GetValue<string>()))!;
            var outputs = replay["cases"]!.AsArray().OfType<JsonObject>()
                .ToDictionary(item => item["caseId"]!.GetValue<string>(), item => item["outputSha256"]?.GetValue<string>());
            var objOutputs = l7["cases"]!.AsArray().OfType<JsonObject>()
                .ToDictionary(item => item["caseId"]!.GetValue<string>(), item => item["objSha256"]!.GetValue<string>());
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
                    ["outputSha256"] = output, ["objSha256"] = objOutputs.GetValueOrDefault(caseId),
                    ["expected"] = fixture["expected"]?.DeepClone(), ["errorContains"] = fixture["errorContains"]?.DeepClone(),
                    ["inputExtension"] = Path.GetExtension(input).ToLowerInvariant() });
            }
            if (!valid || references.Count != 15) continue;
            var fingerprint = JsonNode.Parse(File.ReadAllText(Path.Combine(directory, "fingerprint.json")))!;
            var support = new JsonArray(lower.Select(item => item!.DeepClone()).ToArray());
            support.Add(new JsonObject { ["level"] = "L9", ["capabilityId"] = "mesh.read",
                ["runId"] = current["runId"]?.DeepClone(), ["recordId"] = current["recordId"]?.DeepClone() });
            var contract = VtkReadContract();
            return new JsonObject { ["runtimeId"] = "vtk-win-conda", ["capabilityId"] = "mesh.read", ["level"] = "L9",
                ["scope"] = "nine accepted VTK 9.6.1 mesh reads and three malformed-input rejections",
                ["sourceRunId"] = current["runId"]?.DeepClone(), ["recordId"] = current["recordId"]?.DeepClone(),
                ["runFingerprintSha256"] = run["fingerprintSha256"]?.DeepClone(),
                ["suiteRevisionSha256"] = record["suiteRevisionSha256"]?.DeepClone(),
                ["qualificationSha256"] = run["qualificationSha256"]?.DeepClone(),
                ["workerContractSha256"] = fingerprint["components"]?["contract"]?["workerContractModule"]?["sha256"]?.DeepClone(),
                ["runtimeManifestSha256"] = fingerprint["components"]?["contract"]?["runtimeManifest"]?["sha256"]?.DeepClone(),
                ["adapterSha256"] = HashFile(Path.Combine(repo, "tools", "scientific-broker", "vtk_read_adapter.py")),
                ["workerBinarySha256"] = HashFile(Path.Combine(repo, "tools", "scientific-mesh-worker.py")),
                ["pythonSha256"] = fingerprint["components"]?["environment"]?["pythonExecutable"]?["sha256"]?.DeepClone(),
                ["packageRecordsSha256"] = fingerprint["components"]?["environment"]?["condaPackageRecords"]?["sha256"]?.DeepClone(),
                ["productContract"] = contract, ["productContractSha256"] = Digest(contract),
                ["consumerSources"] = consumers, ["consumerSourceSha256"] = Digest(consumers),
                ["vtkReadSources"] = sources, ["vtkReadSourcesSha256"] = Digest(sources),
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
