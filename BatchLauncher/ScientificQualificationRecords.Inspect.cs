using System.Text.Json;
using System.Text.Json.Nodes;

namespace BatchLauncher;

public static partial class ScientificQualificationRecords
{
    private static readonly string[] InspectCases = ["tetra", "octa", "cube", "affine", "sphere-128", "sphere-512", "sphere-2048", "open", "nonmanifold", "degenerate"];
    private static readonly string[] InspectProductFiles = ["vtk-mesh-document.json", "vtk-mesh-resource.bin",
        "read.m3dm", "product.json", "viewer.png", "viewer.json"];

    private static bool InspectCasesVerify(JsonObject report, JsonObject manifest)
    {
        if (report["cases"] is not JsonArray cases || cases.Count != InspectCases.Length
            || manifest["cases"] is not JsonArray fixtures || fixtures.Count != InspectCases.Length) return false;
        for (var index = 0; index < cases.Count; index++)
        {
            var item = cases[index]; var fixture = fixtures[index];
            var directory = item?["directory"]?.GetValue<string>() ?? "";
            if (item?["caseId"]?.GetValue<string>() != InspectCases[index]
                || fixture?["caseId"]?.GetValue<string>() != InspectCases[index]
                || !Directory.Exists(directory)) return false;
            var input = Path.Combine(directory, "dataset", "input.obj");
            if (RemeshFileHash(input) != fixture?["sha256"]?.GetValue<string>()
                || item["inputSha256"]?.GetValue<string>() != fixture?["sha256"]?.GetValue<string>()) return false;
            var output = Path.Combine(directory, "inspected.obj");
            if (InspectCases[index] == "open")
            {
                var rejected = Path.Combine(directory, "scope-rejection.json");
                if (item["state"]?.GetValue<string>() != "rejected" || File.Exists(output)
                    || RemeshFileHash(rejected) != item["rejectionSha256"]?.GetValue<string>()
                    || JsonNode.Parse(File.ReadAllText(rejected))?["reason"]?.GetValue<string>() != "boundary edges")
                    return false;
                continue;
            }
            var requestPath = Path.Combine(directory, "request.json");
            var resultPath = Path.Combine(directory, "results.json");
            if (RemeshFileHash(requestPath) != item["requestSha256"]?.GetValue<string>()
                || RemeshFileHash(resultPath) != item["resultSha256"]?.GetValue<string>()) return false;
            var request = JsonNode.Parse(File.ReadAllText(requestPath));
            var result = JsonNode.Parse(File.ReadAllText(resultPath));
            var accepted = fixture?["expected"]?.GetValue<string>() == "accepted";
            if (request?["operation"]?.GetValue<string>() != "mesh.inspect"
                || request["recipeId"]?.GetValue<string>() != "cgal.validate"
                || request["runId"]?.GetValue<string>() != result?["runId"]?.GetValue<string>()
                || result["operation"]?.GetValue<string>() != "mesh.inspect"
                || result["state"]?.GetValue<string>() != (accepted ? "succeeded" : "failed")
                || item["state"]?.GetValue<string>() != result["state"]?.GetValue<string>()
                || accepted != File.Exists(output)
                || item["outputSha256"]?.GetValue<string>() != (accepted ? RemeshFileHash(output) : null)
                || (result["artifacts"] is JsonArray artifacts && artifacts.Count > 0) != accepted) return false;
            if (accepted && (result["before"]?["points"]?.GetValue<int>() != fixture?["points"]?.GetValue<int>()
                || result["before"]?["triangles"]?.GetValue<int>() != fixture?["triangles"]?.GetValue<int>()
                || result["before"]?["boundaryEdges"]?.GetValue<int>() != 0
                || result["before"]?.ToJsonString() != result["after"]?.ToJsonString()
                || (fixture["outputSha256"] is JsonValue pinned
                    && pinned.GetValue<string>() != item["outputSha256"]?.GetValue<string>()))) return false;
        }
        return true;
    }

    private static string? InspectHash(string directory, JsonObject result, JsonObject components, string level)
    {
        try
        {
            var index = int.Parse(level[1..]);
            var evidence = result["inspectQualificationEvidence"] as JsonObject;
            var files = components["suite"]?["files"];
            const string manifestName = "scientific/fixtures/cgal-inspect/manifest.v3.json";
            if (result["recipeId"]?.GetValue<string>() != $"l{index}.cgal-inspect"
                || result["state"]?.GetValue<string>() != "succeeded"
                || evidence?["suiteId"]?.GetValue<string>() != "cgal-mesh-inspect-v3"
                || evidence["level"]?.GetValue<string>() != level
                || evidence["capabilityId"]?.GetValue<string>() != "mesh.inspect"
                || evidence["manifestSha256"]?.GetValue<string>() != files?[manifestName]?["sha256"]?.GetValue<string>()
                || result["validatedCapabilities"] is not JsonArray capabilities
                || !capabilities.Any(item => item?.GetValue<string>() == "mesh.inspect")
                || evidence["lowerQualification"]?["records"] is not JsonArray lower || lower.Count != index
                || !lower.Select((item, position) => item?["level"]?.GetValue<string>() == $"L{position}"
                    && item["recordId"]?.GetValue<string>() is { Length: 64 }).All(value => value)) return null;
            if (index > 5 && (evidence["sourceRecordId"]?.GetValue<string>() != lower[lower.Count - 1]?["recordId"]?.GetValue<string>()
                || evidence["sourceRunId"]?.GetValue<string>() != lower[lower.Count - 1]?["runId"]?.GetValue<string>())) return null;
            var reportPath = RemeshContained(directory, Path.Combine(directory, evidence["reportPath"]!.GetValue<string>()));
            var evidencePath = Path.Combine(directory, "cgal-inspect-qualification-evidence.json");
            var fixturePath = Path.Combine(directory, "fixture-manifest.json");
            if (reportPath == null || RemeshFileHash(reportPath) != evidence["reportSha256"]?.GetValue<string>()
                || !File.Exists(reportPath + ".sha256")
                || File.ReadAllText(reportPath + ".sha256").Trim() != evidence["reportSha256"]?.GetValue<string>()
                || RemeshFileHash(fixturePath) != evidence["manifestSha256"]?.GetValue<string>()
                || JsonNode.Parse(File.ReadAllText(evidencePath))?.ToJsonString() != evidence.ToJsonString()
                || result["artifacts"] is not JsonArray artifacts
                || !artifacts.Any(item => item?["path"]?.GetValue<string>() == "cgal-inspect-qualification-evidence.json"
                    && item["sha256"]?.GetValue<string>() == RemeshFileHash(evidencePath))) return null;
            var report = JsonNode.Parse(File.ReadAllText(reportPath)) as JsonObject;
            var manifest = JsonNode.Parse(File.ReadAllText(fixturePath)) as JsonObject;
            if (report?["kind"]?.GetValue<string>() != "scientific.cgal-inspect-" + level
                || report["verdict"]?.GetValue<string>() != "passed"
                || report["manifestSha256"]?.GetValue<string>() != evidence["manifestSha256"]?.GetValue<string>()
                || report["adapterSha256"]?.GetValue<string>() != files?["tools/scientific-cgal-worker.py"]?["sha256"]?.GetValue<string>()
                || report["contractSha256"]?.GetValue<string>() != files?["tools/scientific_worker_contract.py"]?["sha256"]?.GetValue<string>()
                || report["qualificationSourceSha256"]?.GetValue<string>() != files?["tools/scientific_cgal_inspect_qualification.py"]?["sha256"]?.GetValue<string>()
                || manifest == null) return null;
            bool valid;
            if (index == 5)
                valid = InspectCasesVerify(report, manifest)
                    && RemeshFileHash(report["workerPath"]?.GetValue<string>() ?? "") == report["workerSha256"]?.GetValue<string>();
            else
            {
                var prior = $"l{index - 1}";
                valid = RemeshLinkedFile(report[prior + "Path"], report[prior + "Sha256"])
                    && report[prior + "Sha256"]?.GetValue<string>() == evidence["sourceReportSha256"]?.GetValue<string>();
                if (index == 6)
                    valid &= InspectCasesVerify(report, manifest)
                        && report["comparison"]?.GetValue<string>() == "state-and-output-sha256";
                else if (index == 7)
                {
                    valid &= report["cases"] is JsonArray consumers && consumers.Count == 7
                        && report["importerSha256"]?.GetValue<string>() == evidence["consumerSourceSha256"]?.GetValue<string>();
                    if (valid) foreach (var item in report["cases"]!.AsArray())
                        foreach (var name in new[] { "source", "vtk", "math3d" })
                            valid &= RemeshLinkedFile(item?[name + "Path"], item?[name + "Sha256"]);
                }
                else if (index == 8)
                {
                    valid &= report["repeatCount"]?.GetValue<int>() == 3
                        && report["repeats"] is JsonArray repeats && repeats.Count == 21;
                    if (valid) foreach (var item in report["repeats"]!.AsArray())
                    {
                        var fixture = manifest["cases"]?.AsArray().OfType<JsonObject>()
                            .FirstOrDefault(value => value["caseId"]?.GetValue<string>() == item?["caseId"]?.GetValue<string>());
                        var repeatDirectory = item?["directory"]?.GetValue<string>() ?? "";
                        valid &= fixture != null && fixture["expected"]?.GetValue<string>() == "accepted"
                            && RemeshFileHash(Path.Combine(repeatDirectory, "dataset", "input.obj")) == fixture["sha256"]?.GetValue<string>()
                            && RemeshFileHash(Path.Combine(repeatDirectory, "request.json")) == item?["requestSha256"]?.GetValue<string>()
                            && RemeshFileHash(Path.Combine(repeatDirectory, "results.json")) == item?["resultSha256"]?.GetValue<string>()
                            && RemeshFileHash(Path.Combine(repeatDirectory, "inspected.obj")) == item?["outputSha256"]?.GetValue<string>();
                    }
                    foreach (var (name, state) in new[] { ("cancel", "cancelled"), ("timeout", "timed-out"), ("memory", "limited") })
                        valid &= report["probes"]?[name]?["state"]?.GetValue<string>() == state
                            && report["probes"]?[name]?["outputAbsent"]?.GetValue<bool>() == true;
                }
                else
                {
                    valid &= report["cases"] is JsonArray products && products.Count == 7
                        && evidence["consumerSourceSha256"]?.GetValue<string>() is { Length: 64 };
                    if (valid) foreach (var item in report["cases"]!.AsArray())
                    {
                        var product = item?["productDirectory"]?.GetValue<string>() ?? "";
                        valid &= RemeshFileHash(item?["sourcePath"]?.GetValue<string>() ?? "") == item?["sourceSha256"]?.GetValue<string>();
                        foreach (var name in InspectProductFiles)
                            valid &= RemeshFileHash(Path.Combine(product, name)) == item?["files"]?[name]?.GetValue<string>();
                    }
                }
            }
            return valid ? Digest(evidence.ToJsonString()) : null;
        }
        catch (Exception error) when (error is IOException or JsonException or ArgumentException or InvalidOperationException
            or NullReferenceException or KeyNotFoundException) { return null; }
    }

    public static void AssessInspectConsumers(JsonArray records, string? importerHash, string? productHash)
    {
        foreach (var record in records.OfType<JsonObject>().Where(item => item["evidenceId"]?.GetValue<string>() is "l7.cgal-inspect" or "l9.cgal-inspect"))
        {
            var current = record["evidenceId"]?.GetValue<string>() == "l7.cgal-inspect" ? importerHash : productHash;
            if (record["consumerSourceSha256"]?.GetValue<string>() == current) continue;
            record["status"] = current == null ? "unknown" : "stale";
            var reasons = record["staleReasons"] as JsonArray ?? new JsonArray();
            reasons.Add(current == null ? "MATH3D inspect consumer unavailable" : "MATH3D inspect consumer changed");
            record["staleReasons"] = reasons;
        }
    }
}
