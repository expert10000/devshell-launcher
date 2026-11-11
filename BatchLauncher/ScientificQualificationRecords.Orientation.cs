using System.Text.Json;
using System.Text.Json.Nodes;

namespace BatchLauncher;

public static partial class ScientificQualificationRecords
{
    private static readonly string[] OrientationCases = ["tetra-inward", "tetra-outward", "cube-inward", "cube-outward",
        "octa-inward", "octa-outward", "affine-inward", "affine-outward", "open", "disconnected", "nonmanifold", "degenerate"];
    private static readonly string[] OrientationProductFiles = ["orientation-mesh-document.json", "orientation-mesh-resource.bin",
        "oriented.m3dm", "product.json", "viewer.png", "viewer.json"];

    private static bool OrientationScopeCases(string reportPath, JsonObject scope, JsonObject fixture)
    {
        var folder = Path.GetDirectoryName(reportPath)!;
        if (scope["cases"] is not JsonArray cases || fixture["cases"] is not JsonArray fixtures
            || cases.Count != OrientationCases.Length || fixtures.Count != OrientationCases.Length) return false;
        for (var index = 0; index < cases.Count; index++)
        {
            var item = cases[index]; var expected = fixtures[index];
            var caseId = OrientationCases[index];
            var directory = RemeshContained(folder, item?["directory"]?.GetValue<string>() ?? "");
            if (item?["caseId"]?.GetValue<string>() != caseId || expected?["caseId"]?.GetValue<string>() != caseId
                || directory == null || Path.GetDirectoryName(directory) != folder) return false;
            var requestPath = Path.Combine(directory, "request.json");
            var resultPath = Path.Combine(directory, "results.json");
            var output = Path.Combine(directory, "oriented.obj");
            if (RemeshFileHash(requestPath, 65536) != item["requestSha256"]?.GetValue<string>()
                || RemeshFileHash(resultPath, 65536) != item["resultSha256"]?.GetValue<string>()) return false;
            var request = JsonNode.Parse(File.ReadAllText(requestPath));
            var result = JsonNode.Parse(File.ReadAllText(resultPath));
            var accepted = expected["expected"]?.GetValue<string>() == "accepted";
            if (request?["recipeId"]?.GetValue<string>() != "cgal.repair-orientation"
                || request["runId"]?.GetValue<string>() != result?["runId"]?.GetValue<string>()
                || request["inputArtifacts"]?[0]?["sha256"]?.GetValue<string>() != expected["sha256"]?.GetValue<string>()
                || RemeshFileHash(request["inputArtifacts"]?[0]?["path"]?.GetValue<string>() ?? "") != expected["sha256"]?.GetValue<string>()
                || result["state"]?.GetValue<string>() != (accepted ? "succeeded" : "failed")
                || item["state"]?.GetValue<string>() != result["state"]?.GetValue<string>()
                || accepted != File.Exists(output)
                || item["outputSha256"]?.GetValue<string>() != (accepted ? RemeshFileHash(output) : null)) return false;
            if (accepted)
            {
                if (result["engineDetails"]?["beforeOrientation"]?.GetValue<string>() != expected["orientation"]?.GetValue<string>()
                    || result["engineDetails"]?["afterOrientation"]?.GetValue<string>() != "outward"
                    || result["validatedCapabilities"] is not JsonArray capabilities
                    || !capabilities.Any(value => value?.GetValue<string>() == "mesh.orient")) return false;
            }
            else if (result["validatedCapabilities"] is not JsonArray { Count: 0 }
                || result["engineDetails"]?["error"]?.GetValue<string>() is not { } message
                || !message.Contains(expected["errorContains"]!.GetValue<string>(), StringComparison.Ordinal)) return false;
        }
        return true;
    }

    private static string? OrientationHash(string directory, JsonObject result, JsonObject components, string level)
    {
        try
        {
            var evidence = result["orientationQualificationEvidence"] as JsonObject;
            var suite = components["suite"]?["files"];
            var index = int.Parse(level[1..]);
            if (result["recipeId"]?.GetValue<string>() != $"l{index}.cgal-orient"
                || result["state"]?.GetValue<string>() != "succeeded"
                || evidence?["suiteId"]?.GetValue<string>() != "cgal-orientation-v2"
                || evidence["level"]?.GetValue<string>() != level
                || evidence["capabilityId"]?.GetValue<string>() != "mesh.orient"
                || evidence["manifestSha256"]?.GetValue<string>() != suite?["scientific/fixtures/cgal/orientation/manifest.v2.json"]?["sha256"]?.GetValue<string>()
                || result["validatedCapabilities"] is not JsonArray capabilities
                || !capabilities.Any(item => item?.GetValue<string>() == "mesh.orient")
                || evidence["lowerQualification"]?["records"] is not JsonArray lower || lower.Count != index
                || !lower.Select((item, position) => item?["level"]?.GetValue<string>() == $"L{position}"
                    && item["recordId"]?.GetValue<string>() is { Length: 64 }).All(value => value)) return null;
            if (index > 5 && (evidence["sourceRecordId"]?.GetValue<string>() != lower[lower.Count - 1]?["recordId"]?.GetValue<string>()
                || evidence["sourceRunId"]?.GetValue<string>() != lower[lower.Count - 1]?["runId"]?.GetValue<string>())) return null;
            var reportPath = RemeshContained(directory, Path.Combine(directory, evidence["reportPath"]!.GetValue<string>()));
            var evidencePath = Path.Combine(directory, "orientation-qualification-evidence.json");
            var fixturePath = Path.Combine(directory, "fixture-manifest.json");
            if (reportPath == null || RemeshFileHash(reportPath, 1048576) != evidence["reportSha256"]?.GetValue<string>()
                || !File.Exists(reportPath + ".sha256") || File.ReadAllText(reportPath + ".sha256").Trim() != evidence["reportSha256"]?.GetValue<string>()
                || RemeshFileHash(fixturePath, 65536) != evidence["manifestSha256"]?.GetValue<string>()
                || JsonNode.Parse(File.ReadAllText(evidencePath))?.ToJsonString() != evidence.ToJsonString()
                || result["artifacts"] is not JsonArray artifacts
                || !artifacts.Any(item => item?["path"]?.GetValue<string>() == "orientation-qualification-evidence.json"
                    && item["sha256"]?.GetValue<string>() == RemeshFileHash(evidencePath))) return null;
            var report = JsonNode.Parse(File.ReadAllText(reportPath)) as JsonObject;
            if (report?["kind"]?.GetValue<string>() != "scientific.cgal-orientation-" + level
                || report["verdict"]?.GetValue<string>() != "passed"
                || report["capabilityId"]?.GetValue<string>() != "mesh.orient"
                || report["manifestSha256"]?.GetValue<string>() != evidence["manifestSha256"]?.GetValue<string>()
                || report["adapterSha256"]?.GetValue<string>() != suite?["tools/scientific-cgal-worker.py"]?["sha256"]?.GetValue<string>()
                || report["contractSha256"]?.GetValue<string>() != suite?["tools/scientific_worker_contract.py"]?["sha256"]?.GetValue<string>()
                || report["workerSourceSha256"]?.GetValue<string>() != suite?["scientific/cgal-worker/orientation.cpp"]?["sha256"]?.GetValue<string>()
                || report["scopeSourceSha256"]?.GetValue<string>() != suite?["tools/scientific_cgal_orientation_scope.py"]?["sha256"]?.GetValue<string>()
                || report["qualificationSourceSha256"]?.GetValue<string>() != suite?["tools/scientific_cgal_orientation_qualification.py"]?["sha256"]?.GetValue<string>()) return null;
            if (index >= 7 && report[$"l{index}SourceSha256"]?.GetValue<string>()
                != suite?[$"tools/scientific_cgal_orientation_l{index}.py"]?["sha256"]?.GetValue<string>()) return null;
            var fixture = JsonNode.Parse(File.ReadAllText(fixturePath)) as JsonObject;
            bool valid;
            if (index == 5)
            {
                var scopePath = RemeshContained(Path.GetDirectoryName(reportPath)!, report["scopePath"]!.GetValue<string>());
                valid = scopePath != null && RemeshFileHash(scopePath) == report["scopeSha256"]?.GetValue<string>()
                    && JsonNode.Parse(File.ReadAllText(scopePath)) is JsonObject scope && fixture != null
                    && OrientationScopeCases(scopePath, scope, fixture)
                    && report["cases"]?.ToJsonString() == scope["cases"]?.ToJsonString()
                    && RemeshFileHash(report["workerPath"]?.GetValue<string>() ?? "") == report["workerSha256"]?.GetValue<string>();
            }
            else
            {
                var link = index == 6 ? "l5" : $"l{index - 1}";
                valid = RemeshLinkedFile(report[link + "Path"], report[link + "Sha256"], 1048576)
                    && report[link + "Sha256"]?.GetValue<string>() == evidence["sourceReportSha256"]?.GetValue<string>();
                if (index == 6)
                {
                    var replayPath = report["replayPath"]?.GetValue<string>() ?? "";
                    valid = valid && RemeshLinkedFile(report["replayPath"], report["replaySha256"], 1048576)
                        && JsonNode.Parse(File.ReadAllText(replayPath)) is JsonObject replay && fixture != null
                        && OrientationScopeCases(replayPath, replay, fixture)
                        && report["comparison"]?.GetValue<string>() == "state-and-output-sha256";
                }
                else if (index == 7)
                {
                    valid = valid && report["cases"] is JsonArray consumers && consumers.Count == 8;
                    valid &= report["math3dImporterSha256"]?.GetValue<string>() == evidence["consumerSourceSha256"]?.GetValue<string>();
                    if (valid) foreach (var item in report["cases"]!.AsArray())
                        valid &= RemeshLinkedFile(item?["sourcePath"], item?["outputSha256"])
                            && RemeshLinkedFile(item?["vtkPath"], item?["vtkSha256"], 65536)
                            && RemeshLinkedFile(item?["math3dPath"], item?["math3dSha256"], 65536);
                }
                else if (index == 8)
                {
                    valid = valid && report["repeatCount"]?.GetValue<int>() == 3
                        && report["memoryLimitBytes"]?.GetValue<long>() == 134217728
                        && report["repeats"] is JsonArray repeats && repeats.Count == 24;
                    if (valid) foreach (var item in report["repeats"]!.AsArray())
                        valid &= RemeshLinkedFile(item?["path"], item?["sha256"], 65536);
                    foreach (var (probe, state) in new[] { ("cancel", "cancelled"), ("timeout", "timed-out"), ("memory", "limited") })
                        valid &= report["probes"]?[probe]?["state"]?.GetValue<string>() == state
                            && report["probes"]?[probe]?["outputAbsent"]?.GetValue<bool>() == true;
                }
                else
                {
                    valid = valid && report["cases"] is JsonArray products && products.Count == 8;
                    if (valid) foreach (var item in report["cases"]!.AsArray())
                    {
                        var product = RemeshContained(Path.GetDirectoryName(reportPath)!, item?["productDirectory"]?.GetValue<string>() ?? "");
                        valid &= product != null && RemeshLinkedFile(item?["sourcePath"], item?["sourceSha256"]);
                        if (product != null) foreach (var name in OrientationProductFiles)
                            valid &= RemeshFileHash(Path.Combine(product, name)) == item?["files"]?[name]?.GetValue<string>();
                    }
                }
            }
            return valid ? Digest(evidence.ToJsonString()) : null;
        }
        catch (Exception error) when (error is IOException or JsonException or ArgumentException or InvalidOperationException
            or NullReferenceException or KeyNotFoundException) { return null; }
    }

    public static void AssessOrientationL9Consumer(JsonArray records, string? currentSourcesSha256)
    {
        foreach (var record in records.OfType<JsonObject>().Where(item => item["evidenceId"]?.GetValue<string>() == "l9.cgal-orient"))
        {
            if (record["consumerSourceSha256"]?.GetValue<string>() == currentSourcesSha256) continue;
            record["status"] = currentSourcesSha256 == null ? "unknown" : "stale";
            var reasons = record["staleReasons"] as JsonArray ?? new JsonArray();
            reasons.Add(currentSourcesSha256 == null ? "MATH3D orientation product sources unavailable" : "MATH3D orientation product sources changed");
            record["staleReasons"] = reasons;
        }
    }

    public static void AssessOrientationL7Consumer(JsonArray records, string? currentImporterSha256)
    {
        foreach (var record in records.OfType<JsonObject>().Where(item => item["evidenceId"]?.GetValue<string>() == "l7.cgal-orient"))
        {
            if (record["consumerSourceSha256"]?.GetValue<string>() == currentImporterSha256) continue;
            record["status"] = currentImporterSha256 == null ? "unknown" : "stale";
            var reasons = record["staleReasons"] as JsonArray ?? new JsonArray();
            reasons.Add(currentImporterSha256 == null ? "MATH3D orientation importer unavailable" : "MATH3D orientation importer changed");
            record["staleReasons"] = reasons;
        }
    }
}
