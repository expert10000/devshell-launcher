using System.Text.Json;
using System.Text.Json.Nodes;

namespace BatchLauncher;

public static partial class ScientificQualificationRecords
{
    private static readonly string[] RemeshAccepted = ["accepted", "affine-accepted", "cube-accepted", "octa-accepted"];
    private static readonly string[] RemeshCases = ["accepted", "volume-loss", "malformed-open", "affine-accepted",
        "affine-volume-loss", "cube-accepted", "cube-volume-loss", "octa-accepted", "octa-volume-loss",
        "inward-invalid", "nonmanifold-invalid", "degenerate-invalid"];
    private static readonly string[] RemeshProductFiles = ["remesh-mesh-document.json", "remesh-mesh-resource.bin",
        "remeshed.m3dm", "product.json", "viewer.png", "viewer.json"];
    private static readonly string[] RemeshConsumerSources = ["renderer/src/mesh/surfaceMesh.ts",
        "renderer/src/mesh/meshDocumentAdapter.ts", "renderer/src/mesh/meshResourceStore.ts",
        "packages/core/src/meshDocument.ts", "src/main/python/nativeCgalProtocol.ts",
        "renderer/src/workspace/MeshDocumentViewport.tsx"];

    private static string? RemeshFileHash(string path, long limit = 64 * 1024 * 1024)
        => File.Exists(path) && new FileInfo(path).Length is > 0 and <= 67108864
            && new FileInfo(path).Length <= limit ? ScientificArtifactFiles.Hash(path) : null;

    private static string? RemeshContained(string root, string path)
    {
        var full = Path.GetFullPath(path);
        var basePath = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        return full.StartsWith(basePath, StringComparison.OrdinalIgnoreCase) ? full : null;
    }

    private static bool RemeshLinkedFile(JsonNode? path, JsonNode? hash, long limit = 64 * 1024 * 1024)
        => path?.GetValue<string>() is { Length: > 0 } file
            && hash?.GetValue<string>() is { Length: 64 } expected
            && RemeshFileHash(file, limit) == expected;

    private static bool RemeshL5Cases(string root, JsonObject report, JsonObject manifest)
    {
        if (report["cases"] is not JsonArray cases || cases.Count != RemeshCases.Length
            || manifest["cases"] is not JsonArray fixtures || fixtures.Count != RemeshCases.Length
            || RemeshFileHash(report["workerPath"]?.GetValue<string>() ?? "") != report["workerSha256"]?.GetValue<string>())
            return false;
        for (var index = 0; index < cases.Count; index++)
        {
            if (cases[index] is not JsonObject entry || fixtures[index] is not JsonObject fixture
                || entry["caseId"]?.GetValue<string>() != RemeshCases[index]
                || fixture["caseId"]?.GetValue<string>() != RemeshCases[index]) return false;
            var folder = RemeshContained(root, entry["directory"]?.GetValue<string>() ?? "");
            if (folder == null || Path.GetDirectoryName(folder) != root
                || RemeshFileHash(Path.Combine(folder, "request.json"), 1048576) != entry["requestSha256"]?.GetValue<string>()
                || RemeshFileHash(Path.Combine(folder, "results.json"), 1048576) != entry["resultSha256"]?.GetValue<string>()) return false;
            var request = JsonNode.Parse(File.ReadAllText(Path.Combine(folder, "request.json")));
            var result = JsonNode.Parse(File.ReadAllText(Path.Combine(folder, "results.json")));
            var expected = fixture["expected"]?.GetValue<string>();
            var state = expected == "accepted" ? "succeeded" : "failed";
            var output = Path.Combine(folder, "remeshed.obj");
            if (entry["state"]?.GetValue<string>() != state || result?["state"]?.GetValue<string>() != state
                || result["runId"]?.GetValue<string>() != request?["runId"]?.GetValue<string>()
                || request["recipeId"]?.GetValue<string>() != "cgal.remesh"
                || request["parameters"]?["targetEdge"]?.GetValue<double>() != fixture["targetEdge"]?.GetValue<double>()
                || request["parameters"]?["iterations"]?.GetValue<int>() != fixture["iterations"]?.GetValue<int>()
                || RemeshFileHash(request["inputArtifacts"]?[0]?["path"]?.GetValue<string>() ?? "") != fixture["sha256"]?.GetValue<string>()
                || (expected == "accepted") != File.Exists(output)) return false;
            if (expected == "accepted")
            {
                if (RemeshFileHash(output) != entry["outputSha256"]?.GetValue<string>()
                    || result["validatedCapabilities"] is not JsonArray capabilities
                    || !capabilities.Any(value => value?.GetValue<string>() == "mesh.remesh")) return false;
            }
            else if (entry["outputSha256"] != null || result["artifacts"] is not JsonArray { Count: 0 }) return false;
            if (expected == "invalid-input")
            {
                if (entry["guardReportSha256"] != null || result["guardEvidence"] != null) return false;
                continue;
            }
            var guardRelative = result["guardEvidence"]?["path"]?.GetValue<string>() ?? "";
            var guardPath = RemeshContained(folder, Path.Combine(folder, guardRelative));
            if (guardPath == null || RemeshFileHash(guardPath, 1048576) != entry["guardReportSha256"]?.GetValue<string>()
                || result["guardEvidence"]?["sha256"]?.GetValue<string>() != entry["guardReportSha256"]?.GetValue<string>()) return false;
            var guard = JsonNode.Parse(File.ReadAllText(guardPath));
            var decision = guard?["measurements"]?["decision"];
            if (guard?["policySha256"]?.GetValue<string>() != report["policySha256"]?.GetValue<string>()
                || guard["sourceSha256"]?.GetValue<string>() != fixture["sha256"]?.GetValue<string>()
                || guard["state"]?.GetValue<string>() != expected
                || decision?["eligible"]?.GetValue<bool>() != (expected == "accepted")
                || RemeshFileHash(Path.Combine(Path.GetDirectoryName(guardPath)!, "candidate.obj")) != guard["candidateSha256"]?.GetValue<string>()
                || (expected == "accepted"
                    ? RemeshFileHash(Path.Combine(Path.GetDirectoryName(guardPath)!, "accepted.obj")) != entry["outputSha256"]?.GetValue<string>()
                    : File.Exists(Path.Combine(Path.GetDirectoryName(guardPath)!, "accepted.obj")))) return false;
            if (expected == "rejected" && decision["checks"]?["relativeVolume"]?.GetValue<bool>() != false) return false;
        }
        return true;
    }

    private static bool RemeshLaterReport(string level, string root, JsonObject report, JsonObject evidence)
    {
        var sourceHash = evidence["sourceReportSha256"]?.GetValue<string>();
        if (sourceHash is not { Length: 64 }) return false;
        if (level == "L6")
        {
            if (!RemeshLinkedFile(report["baselinePath"], report["baselineSha256"], 1048576)
                || !RemeshLinkedFile(report["reproductionPath"], report["reproductionSha256"], 1048576)
                || report["baselineSha256"]?.GetValue<string>() != sourceHash
                || report["comparison"]?.GetValue<string>() != "state-and-accepted-output-sha256") return false;
            var reproduction = JsonNode.Parse(File.ReadAllText(report["reproductionPath"]!.GetValue<string>())) as JsonObject;
            var baseline = JsonNode.Parse(File.ReadAllText(report["baselinePath"]!.GetValue<string>())) as JsonObject;
            var manifest = JsonNode.Parse(File.ReadAllText(Path.Combine(Path.GetDirectoryName(root)!, "fixture-manifest.json"))) as JsonObject;
            return reproduction != null && baseline != null && manifest != null
                && RemeshL5Cases(Path.GetDirectoryName(report["reproductionPath"]!.GetValue<string>())!, reproduction, manifest)
                && reproduction["cases"] is JsonArray fresh && baseline["cases"] is JsonArray prior
                && fresh.Count == prior.Count && fresh.Select(item => item?["state"]?.GetValue<string>() + ":" + item?["outputSha256"]?.GetValue<string>())
                    .SequenceEqual(prior.Select(item => item?["state"]?.GetValue<string>() + ":" + item?["outputSha256"]?.GetValue<string>()));
        }
        var link = level == "L7" ? "l6" : level == "L8" ? "l7" : "l8";
        if (!RemeshLinkedFile(report[link + "Path"], report[link + "Sha256"], 1048576)
            || report[link + "Sha256"]?.GetValue<string>() != sourceHash) return false;
        if (level == "L7")
        {
            if (report["cases"] is not JsonArray cases || cases.Count != RemeshAccepted.Length
                || report["math3dImporterSha256"]?.GetValue<string>() != evidence["consumerSourceSha256"]?.GetValue<string>()) return false;
            for (var index = 0; index < cases.Count; index++)
            {
                var item = cases[index];
                if (item?["caseId"]?.GetValue<string>() != RemeshAccepted[index]
                    || !RemeshLinkedFile(item["sourcePath"], item["outputSha256"])
                    || !RemeshLinkedFile(item["vtkPath"], item["vtkSha256"], 65536)
                    || !RemeshLinkedFile(item["math3dPath"], item["math3dSha256"], 65536)) return false;
                var vtk = JsonNode.Parse(File.ReadAllText(item["vtkPath"]!.GetValue<string>()));
                var math3d = JsonNode.Parse(File.ReadAllText(item["math3dPath"]!.GetValue<string>()));
                if (vtk?["inputObjSha256"]?.GetValue<string>() != item["outputSha256"]?.GetValue<string>()
                    || math3d?["inputObjSha256"]?.GetValue<string>() != item["outputSha256"]?.GetValue<string>()
                    || vtk["closed"]?.GetValue<bool>() != true || math3d["closed"]?.GetValue<bool>() != true
                    || vtk["boundaryEdges"]?.GetValue<int>() != 0 || math3d["boundaryEdges"]?.GetValue<int>() != 0) return false;
            }
            return true;
        }
        if (level == "L8")
        {
            if (report["repeatCount"]?.GetValue<int>() != 3 || report["memoryLimitBytes"]?.GetValue<long>() != 134217728
                || report["repeats"] is not JsonArray repeats || repeats.Count != 12) return false;
            foreach (var item in repeats)
                if (!RemeshLinkedFile(item?["path"], item?["sha256"], 65536)) return false;
            foreach (var (name, state) in new[] { ("cancel", "cancelled"), ("timeout", "timed-out"), ("memory", "limited") })
                if (report["probes"]?[name]?["state"]?.GetValue<string>() != state
                    || report["probes"]?[name]?["outputAbsent"]?.GetValue<bool>() != true
                    || File.Exists(Path.Combine(root, name + "-output.txt"))) return false;
            return report["probes"]?["memory"]?["peakRssBytes"]?.GetValue<long>() >= 134217728;
        }
        if (report["cases"] is not JsonArray products || products.Count != RemeshAccepted.Length) return false;
        for (var index = 0; index < products.Count; index++)
        {
            var item = products[index];
            var folder = RemeshContained(root, item?["productDirectory"]?.GetValue<string>() ?? "");
            if (item?["caseId"]?.GetValue<string>() != RemeshAccepted[index] || folder == null
                || Path.GetDirectoryName(folder) != root
                || !RemeshLinkedFile(item["sourcePath"], item["sourceSha256"])) return false;
            foreach (var name in RemeshProductFiles)
                if (RemeshFileHash(Path.Combine(folder, name)) != item["files"]?[name]?.GetValue<string>()) return false;
            var product = JsonNode.Parse(File.ReadAllText(Path.Combine(folder, "product.json")));
            var viewer = JsonNode.Parse(File.ReadAllText(Path.Combine(folder, "viewer.json")));
            if (product?["sourceObjSha256"]?.GetValue<string>() != item["sourceSha256"]?.GetValue<string>()
                || viewer?["screenshotSha256"]?.GetValue<string>() != item["files"]?["viewer.png"]?.GetValue<string>()
                || viewer["viewerState"]?.GetValue<string>() != "mounted"
                || viewer["blueMeshPixels"]?.GetValue<int>() < 1000) return false;
        }
        return true;
    }

    private static string? RemeshHash(string directory, JsonObject result, JsonObject components, string level)
    {
        try
        {
            var evidence = result["remeshQualificationEvidence"] as JsonObject;
            var suite = components["suite"]?["files"];
            if (result["recipeId"]?.GetValue<string>() != $"l{level[1]}.cgal-remesh"
                || result["state"]?.GetValue<string>() != "succeeded"
                || evidence?["suiteId"]?.GetValue<string>() != "cgal-remesh-guarded-v2"
                || evidence["level"]?.GetValue<string>() != level
                || evidence["capabilityId"]?.GetValue<string>() != "mesh.remesh"
                || evidence["policySha256"]?.GetValue<string>() != suite?["schemas/scientific-remesh-guard.v2.json"]?["sha256"]?.GetValue<string>()
                || result["validatedCapabilities"] is not JsonArray capabilities
                || !capabilities.Any(item => item?.GetValue<string>() == "mesh.remesh")
                || evidence["lowerQualification"]?["records"] is not JsonArray lower
                || lower.Count != int.Parse(level[1..])
                || !lower.Select((item, index) => item?["level"]?.GetValue<string>() == $"L{index}"
                    && item["recordId"]?.GetValue<string>() is { Length: 64 }).All(value => value)) return null;
            if (level != "L5" && (evidence["sourceRecordId"]?.GetValue<string>() != lower[lower.Count - 1]?["recordId"]?.GetValue<string>()
                || evidence["sourceRunId"]?.GetValue<string>() != lower[lower.Count - 1]?["runId"]?.GetValue<string>())) return null;
            var reportPath = RemeshContained(directory, Path.Combine(directory, evidence["reportPath"]!.GetValue<string>()));
            var evidencePath = Path.Combine(directory, "remesh-qualification-evidence.json");
            var fixturePath = Path.Combine(directory, "fixture-manifest.json");
            if (reportPath == null || RemeshFileHash(reportPath, 1048576) != evidence["reportSha256"]?.GetValue<string>()
                || RemeshFileHash(reportPath + ".sha256", 256) == null
                || File.ReadAllText(reportPath + ".sha256").Trim() != evidence["reportSha256"]?.GetValue<string>()
                || !File.Exists(evidencePath) || new FileInfo(evidencePath).Length > 65536
                || RemeshFileHash(fixturePath, 65536) != suite?["scientific/fixtures/cgal-remesh-qualification/manifest.json"]?["sha256"]?.GetValue<string>()
                || JsonNode.Parse(File.ReadAllText(evidencePath))?.ToJsonString() != evidence.ToJsonString()
                || result["artifacts"] is not JsonArray artifacts
                || !artifacts.Any(item => item?["path"]?.GetValue<string>() == "remesh-qualification-evidence.json"
                    && item["sha256"]?.GetValue<string>() == RemeshFileHash(evidencePath))
                || !artifacts.Any(item => item?["path"]?.GetValue<string>() == "fixture-manifest.json"
                    && item["sha256"]?.GetValue<string>() == RemeshFileHash(fixturePath))) return null;
            var report = JsonNode.Parse(File.ReadAllText(reportPath)) as JsonObject;
            var root = Path.GetDirectoryName(reportPath)!;
            if (report?["kind"]?.GetValue<string>() != "scientific.cgal-remesh-" + level
                || report["verdict"]?.GetValue<string>() != "passed"
                || report["policySha256"]?.GetValue<string>() != evidence["policySha256"]?.GetValue<string>()
                || report["manifestSha256"]?.GetValue<string>() != suite?["scientific/fixtures/cgal-remesh-qualification/manifest.json"]?["sha256"]?.GetValue<string>()
                || report["adapterSha256"]?.GetValue<string>() != suite?["tools/scientific-cgal-worker.py"]?["sha256"]?.GetValue<string>()
                || report["guardSha256"]?.GetValue<string>() != suite?["tools/scientific_cgal_remesh_guard.py"]?["sha256"]?.GetValue<string>()
                || report["qualificationSourceSha256"]?.GetValue<string>() != suite?["tools/scientific_cgal_remesh_qualification.py"]?["sha256"]?.GetValue<string>()) return null;
            var valid = level == "L5"
                ? JsonNode.Parse(File.ReadAllText(fixturePath)) is JsonObject manifest
                    && RemeshL5Cases(root, report, manifest)
                : RemeshLaterReport(level, root, report, evidence);
            return valid ? Digest(evidence.ToJsonString()) : null;
        }
        catch (Exception error) when (error is IOException or JsonException or ArgumentException or InvalidOperationException
            or NullReferenceException or KeyNotFoundException) { return null; }
    }

    public static void AssessRemeshL9Consumer(JsonArray records, string? currentSourcesSha256)
    {
        foreach (var record in records.OfType<JsonObject>().Where(item => item["evidenceId"]?.GetValue<string>() == "l9.cgal-remesh"))
        {
            if (record["consumerSourceSha256"]?.GetValue<string>() == currentSourcesSha256) continue;
            record["status"] = currentSourcesSha256 == null ? "unknown" : "stale";
            var reasons = record["staleReasons"] as JsonArray ?? new JsonArray();
            reasons.Add(currentSourcesSha256 == null ? "MATH3D remesh product sources unavailable" : "MATH3D remesh product sources changed");
            record["staleReasons"] = reasons;
        }
    }
}
