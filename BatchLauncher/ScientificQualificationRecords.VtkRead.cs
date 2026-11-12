using System.Text.Json;
using System.Text.Json.Nodes;

namespace BatchLauncher;

public static partial class ScientificQualificationRecords
{
    private static readonly string[] VtkReadCases = ["tetra", "cube", "octa", "affine", "sphere-128", "sphere-512", "sphere-2048",
        "tetra-holdout", "octa-holdout", "cube-holdout", "open", "disconnected",
        "empty", "truncated", "invalid"];
    private static readonly string[] VtkReadProductFiles = ["vtk-mesh-document.json", "vtk-mesh-resource.bin",
        "read.m3dm", "product.json", "viewer.png", "viewer.json"];

    private static bool VtkReadScopeCases(string scopePath, JsonObject scope, JsonObject fixture)
    {
        var folder = Path.GetDirectoryName(scopePath)!;
        if (scope["cases"] is not JsonArray cases || fixture["cases"] is not JsonArray fixtures
            || cases.Count != VtkReadCases.Length || fixtures.Count != VtkReadCases.Length) return false;
        for (var index = 0; index < cases.Count; index++)
        {
            var item = cases[index]; var expected = fixtures[index];
            var caseId = VtkReadCases[index];
            var directory = RemeshContained(folder, item?["directory"]?.GetValue<string>() ?? "");
            if (item?["caseId"]?.GetValue<string>() != caseId || expected?["caseId"]?.GetValue<string>() != caseId
                || directory == null || Path.GetDirectoryName(directory) != folder) return false;
            var requestPath = Path.Combine(directory, "request.json");
            var resultPath = Path.Combine(directory, "results.json");
            var output = Path.Combine(directory, "mesh.vtp");
            if (RemeshFileHash(requestPath, 65536) != item["requestSha256"]?.GetValue<string>()
                || RemeshFileHash(resultPath, 65536) != item["resultSha256"]?.GetValue<string>()) return false;
            var request = JsonNode.Parse(File.ReadAllText(requestPath));
            var result = JsonNode.Parse(File.ReadAllText(resultPath));
            var accepted = expected["expected"]?.GetValue<string>() == "accepted";
            if (request?["recipeId"]?.GetValue<string>() != "mesh.inspect"
                || request["runtimeId"]?.GetValue<string>() != "vtk-win-conda"
                || request["runId"]?.GetValue<string>() != result?["runId"]?.GetValue<string>()
                || request["inputArtifacts"]?[0]?["sha256"]?.GetValue<string>() != expected["sha256"]?.GetValue<string>()
                || RemeshFileHash(request["inputArtifacts"]?[0]?["path"]?.GetValue<string>() ?? "") != expected["sha256"]?.GetValue<string>()
                || result["versions"]?["vtk"]?.GetValue<string>() != fixture["vtkVersion"]?.GetValue<string>()
                || result["state"]?.GetValue<string>() != (accepted ? "succeeded" : "failed")
                || item["state"]?.GetValue<string>() != result["state"]?.GetValue<string>()
                || accepted != File.Exists(output)
                || item["outputSha256"]?.GetValue<string>() != (accepted ? RemeshFileHash(output) : null)) return false;
            if (accepted)
            {
                if (result["before"]?.ToJsonString() != expected["before"]?.ToJsonString()
                    || result["after"]?.ToJsonString() != expected["before"]?.ToJsonString()
                    || item["outputSha256"]?.GetValue<string>() != expected["outputSha256"]?.GetValue<string>()
                    || result["artifacts"]?[0]?["sha256"]?.GetValue<string>() != item["outputSha256"]?.GetValue<string>()
                    || result["validatedCapabilities"] is not JsonArray capabilities
                    || !capabilities.Any(value => value?.GetValue<string>() == "mesh.read")) return false;
            }
            else if (result["validatedCapabilities"] is not JsonArray { Count: 0 }
                || result["diagnostics"] is not JsonArray diagnostics
                || !diagnostics.OfType<JsonObject>().Any(value => value["message"]?.GetValue<string>()?
                    .Contains(expected["errorContains"]!.GetValue<string>(), StringComparison.Ordinal) == true)) return false;
        }
        return true;
    }

    private static bool VtkReadScope(string reportPath, JsonNode? pathNode, JsonNode? hashNode,
        JsonObject fixture, JsonObject components)
    {
        var path = RemeshContained(Path.GetDirectoryName(reportPath)!, pathNode?.GetValue<string>() ?? "");
        if (path == null || RemeshFileHash(path, 1048576) != hashNode?.GetValue<string>()) return false;
        var scope = JsonNode.Parse(File.ReadAllText(path)) as JsonObject;
        var files = components["suite"]?["files"];
        return scope?["kind"]?.GetValue<string>() == "scientific.vtk-mesh-read-scope"
            && scope["verdict"]?.GetValue<string>() == "passed"
            && scope["manifestSha256"]?.GetValue<string>() == files?["scientific/fixtures/vtk/read/manifest.v4.json"]?["sha256"]?.GetValue<string>()
            && scope["workerSourceSha256"]?.GetValue<string>() == files?["tools/scientific-mesh-worker.py"]?["sha256"]?.GetValue<string>()
            && scope["scopeSourceSha256"]?.GetValue<string>() == files?["tools/scientific_vtk_read_scope.py"]?["sha256"]?.GetValue<string>()
            && VtkReadScopeCases(path, scope, fixture);
    }

    private static string? VtkReadHash(string directory, JsonObject result, JsonObject components, string level)
    {
        try
        {
            var evidence = result["vtkReadQualificationEvidence"] as JsonObject;
            var suite = components["suite"]?["files"];
            var index = int.Parse(level[1..]);
            if (result["recipeId"]?.GetValue<string>() != $"l{index}.vtk-read"
                || result["state"]?.GetValue<string>() != "succeeded"
                || evidence?["suiteId"]?.GetValue<string>() != "vtk-mesh-read-v4"
                || evidence["level"]?.GetValue<string>() != level
                || evidence["capabilityId"]?.GetValue<string>() != "mesh.read"
                || evidence["manifestSha256"]?.GetValue<string>() != suite?["scientific/fixtures/vtk/read/manifest.v4.json"]?["sha256"]?.GetValue<string>()
                || result["validatedCapabilities"] is not JsonArray capabilities
                || !capabilities.Any(item => item?.GetValue<string>() == "mesh.read")
                || evidence["lowerQualification"]?["records"] is not JsonArray lower || lower.Count != index
                || !lower.Select((item, position) => item?["level"]?.GetValue<string>() == $"L{position}"
                    && item["recordId"]?.GetValue<string>() is { Length: 64 }).All(value => value)) return null;
            if (index > 5 && (evidence["sourceRecordId"]?.GetValue<string>() != lower[lower.Count - 1]?["recordId"]?.GetValue<string>()
                || evidence["sourceRunId"]?.GetValue<string>() != lower[lower.Count - 1]?["runId"]?.GetValue<string>())) return null;
            var reportPath = RemeshContained(directory, Path.Combine(directory, evidence["reportPath"]!.GetValue<string>()));
            var evidencePath = Path.Combine(directory, "vtk-read-qualification-evidence.json");
            var fixturePath = Path.Combine(directory, "fixture-manifest.json");
            if (reportPath == null || RemeshFileHash(reportPath, 1048576) != evidence["reportSha256"]?.GetValue<string>()
                || !File.Exists(reportPath + ".sha256") || File.ReadAllText(reportPath + ".sha256").Trim() != evidence["reportSha256"]?.GetValue<string>()
                || RemeshFileHash(fixturePath, 65536) != evidence["manifestSha256"]?.GetValue<string>()
                || JsonNode.Parse(File.ReadAllText(evidencePath))?.ToJsonString() != evidence.ToJsonString()
                || result["artifacts"] is not JsonArray artifacts
                || !artifacts.Any(item => item?["path"]?.GetValue<string>() == "vtk-read-qualification-evidence.json"
                    && item["sha256"]?.GetValue<string>() == RemeshFileHash(evidencePath))) return null;
            var report = JsonNode.Parse(File.ReadAllText(reportPath)) as JsonObject;
            if (report?["kind"]?.GetValue<string>() != "scientific.vtk-read-" + level
                || report["verdict"]?.GetValue<string>() != "passed"
                || report["capabilityId"]?.GetValue<string>() != "mesh.read"
                || report["manifestSha256"]?.GetValue<string>() != evidence["manifestSha256"]?.GetValue<string>()
                || report["workerSourceSha256"]?.GetValue<string>() != suite?["tools/scientific-mesh-worker.py"]?["sha256"]?.GetValue<string>()
                || report["contractSha256"]?.GetValue<string>() != suite?["tools/scientific_worker_contract.py"]?["sha256"]?.GetValue<string>()
                || report["scopeSourceSha256"]?.GetValue<string>() != suite?["tools/scientific_vtk_read_scope.py"]?["sha256"]?.GetValue<string>()
                || report["qualificationSourceSha256"]?.GetValue<string>() != suite?["tools/scientific_vtk_read_qualification.py"]?["sha256"]?.GetValue<string>()) return null;
            var fixture = JsonNode.Parse(File.ReadAllText(fixturePath)) as JsonObject;
            if (fixture == null) return null;
            bool valid;
            if (index == 5)
            {
                valid = VtkReadScope(reportPath, report["scopePath"], report["scopeSha256"], fixture, components)
                    && report["cases"]?.ToJsonString() == JsonNode.Parse(File.ReadAllText(report["scopePath"]!.GetValue<string>()))?["cases"]?.ToJsonString()
                    && RemeshFileHash(report["pythonPath"]?.GetValue<string>() ?? "") == report["pythonSha256"]?.GetValue<string>();
            }
            else
            {
                var prior = index == 6 ? "l5" : $"l{index - 1}";
                valid = RemeshLinkedFile(report[prior + "Path"], report[prior + "Sha256"], 1048576)
                    && report[prior + "Sha256"]?.GetValue<string>() == evidence["sourceReportSha256"]?.GetValue<string>();
                if (index == 6)
                {
                    valid &= VtkReadScope(reportPath, report["replayPath"], report["replaySha256"], fixture, components)
                        && report["comparison"]?.GetValue<string>() == "state-and-output-sha256";
                }
                else if (index == 7)
                {
                    valid &= report["math3dImporterSha256"]?.GetValue<string>() == evidence["consumerSourceSha256"]?.GetValue<string>()
                        && report["parserSha256"]?.GetValue<string>() == suite?["tools/scientific-artifact-roundtrip.py"]?["sha256"]?.GetValue<string>()
                        && report["vtkConsumerSha256"]?.GetValue<string>() == suite?["tools/scientific-vtk-interop.py"]?["sha256"]?.GetValue<string>()
                        && report["cases"] is JsonArray consumers && consumers.Count == 12;
                    if (valid) foreach (var item in report["cases"]!.AsArray())
                        foreach (var name in new[] { "obj", "reload", "vtk", "math3d" })
                            valid &= RemeshLinkedFile(item?[name + "Path"], item?[name + "Sha256"]);
                }
                else if (index == 8)
                {
                    valid &= report["repeatCount"]?.GetValue<int>() == 3
                        && report["memoryLimitBytes"]?.GetValue<long>() == 134217728
                        && report["repeats"] is JsonArray repeats && repeats.Count == 36;
                    if (valid) foreach (var item in report["repeats"]!.AsArray())
                        valid &= RemeshLinkedFile(item?["path"], item?["sha256"], 65536);
                    foreach (var (probe, state) in new[] { ("cancel", "cancelled"), ("timeout", "timed-out"), ("memory", "limited") })
                        valid &= report["probes"]?[probe]?["state"]?.GetValue<string>() == state
                            && report["probes"]?[probe]?["outputAbsent"]?.GetValue<bool>() == true;
                }
                else
                {
                    valid &= report["productSourceSha256"]?.GetValue<string>() == suite?["tools/math3d-vtk-read-product.mjs"]?["sha256"]?.GetValue<string>()
                        && report["viewerSourceSha256"]?.GetValue<string>() == suite?["tools/math3d-vtk-read-viewer.mjs"]?["sha256"]?.GetValue<string>()
                        && report["cases"] is JsonArray products && products.Count == 12
                        && evidence["consumerSourceSha256"]?.GetValue<string>() is { Length: 64 };
                    if (valid) foreach (var item in report["cases"]!.AsArray())
                    {
                        var product = RemeshContained(Path.GetDirectoryName(reportPath)!, item?["productDirectory"]?.GetValue<string>() ?? "");
                        valid &= product != null && RemeshLinkedFile(item?["sourcePath"], item?["sourceSha256"]);
                        if (product != null) foreach (var name in VtkReadProductFiles)
                            valid &= RemeshFileHash(Path.Combine(product, name)) == item?["files"]?[name]?.GetValue<string>();
                    }
                }
            }
            return valid ? Digest(evidence.ToJsonString()) : null;
        }
        catch (Exception error) when (error is IOException or JsonException or ArgumentException or InvalidOperationException
            or NullReferenceException or KeyNotFoundException) { return null; }
    }

    public static void AssessVtkReadConsumers(JsonArray records, string? importerHash, string? productSourcesHash,
        bool includeProduct = true)
    {
        foreach (var record in records.OfType<JsonObject>().Where(item => item["evidenceId"]?.GetValue<string>() is "l7.vtk-read" or "l9.vtk-read"))
        {
            var product = record["evidenceId"]?.GetValue<string>() == "l9.vtk-read";
            if (product && !includeProduct) continue;
            var current = product ? productSourcesHash : importerHash;
            if (record["consumerSourceSha256"]?.GetValue<string>() == current) continue;
            record["status"] = current == null ? "unknown" : "stale";
            var reasons = record["staleReasons"] as JsonArray ?? new JsonArray();
            reasons.Add(current == null ? "MATH3D VTK read consumer unavailable" : "MATH3D VTK read consumer changed");
            record["staleReasons"] = reasons;
        }
    }
}
