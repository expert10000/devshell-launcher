using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace BatchLauncher;

public static partial class ScientificQualificationRecords
{
    private static readonly string[] GmshHandoffFiles = ["mesh.obj", "handoff.json", "vtk.json", "math3d.json",
        "malformed.obj", "vtk-rejection.json", "math3d-rejection.json"];

    public static bool ValidGmshInterop(JsonObject handoff, JsonObject vtk, JsonObject math3d,
        JsonObject vtkReject, JsonObject math3dReject, string? mshHash, string? objHash,
        string? malformedHash, string? importerHash)
    {
        if (mshHash is not { Length: 64 } || objHash is not { Length: 64 }
            || malformedHash is not { Length: 64 } || importerHash is not { Length: 64 }
            || handoff["sourceMshSha256"]?.GetValue<string>() != mshHash
            || handoff["outputObjSha256"]?.GetValue<string>() != objHash
            || vtk["state"]?.GetValue<string>() != "accepted"
            || math3d["state"]?.GetValue<string>() != "accepted"
            || vtk["inputObjSha256"]?.GetValue<string>() != objHash
            || math3d["inputObjSha256"]?.GetValue<string>() != objHash
            || math3d["importerSourceSha256"]?.GetValue<string>() != importerHash
            || vtkReject["state"]?.GetValue<string>() != "rejected"
            || math3dReject["state"]?.GetValue<string>() != "rejected"
            || vtkReject["inputObjSha256"]?.GetValue<string>() != malformedHash
            || math3dReject["inputObjSha256"]?.GetValue<string>() != malformedHash)
            return false;
        var expected = new[] { 0d, 1d, 0d, 1d, 0d, 0d };
        foreach (var report in new[] { handoff, vtk, math3d })
        {
            if (report["points"]?.GetValue<int>() != 44 || report["triangles"]?.GetValue<int>() != 66
                || report["boundaryEdges"]?.GetValue<int>() != 20 || report["nonManifoldEdges"]?.GetValue<int>() != 0
                || Math.Abs((report["signedAreaXY"]?.GetValue<double>() ?? double.NaN) - 1) > 1e-9
                || report["bounds"] is not JsonArray bounds || bounds.Count != 6
                || !Enumerable.Range(0, 6).All(index =>
                    Math.Abs((bounds[index]?.GetValue<double>() ?? double.NaN) - expected[index]) <= 1e-6))
                return false;
        }
        return true;
    }

    private static string? GmshL7Hash(string directory, JsonObject result, JsonObject components)
    {
        if (result["recipeId"]?.GetValue<string>() != "l7.gmsh-interop"
            || result["runtimeId"]?.GetValue<string>() != "gmsh-win-conda"
            || result["l7GmshEvidence"] is not JsonObject evidence
            || evidence["suiteId"]?.GetValue<string>() != "l7-gmsh-interop-v1"
            || evidence["capabilityId"]?.GetValue<string>() != "mesh.generate"
            || evidence["source"] is not JsonObject source
            || evidence["consumerContract"] is not JsonObject contract
            || evidence["artifactHashes"] is not JsonObject hashes
            || evidence["lowerQualification"]?["records"] is not JsonArray lower || lower.Count != 7
            || source["lowerQualification"]?["records"] is not JsonArray prior || prior.Count != 6
            || Digest(contract.ToJsonString()) != evidence["consumerContractSha256"]?.GetValue<string>()) return null;
        for (var i = 0; i < 6; i++) if (lower[i]?.ToJsonString() != prior[i]?.ToJsonString()) return null;
        var folderId = source["folderId"]?.GetValue<string>();
        var runId = source["runId"]?.GetValue<string>();
        var recordId = source["recordId"]?.GetValue<string>();
        if (folderId is not { Length: 32 } || !folderId.All(Uri.IsHexDigit)
            || runId is not { Length: 32 } || !runId.All(Uri.IsHexDigit)
            || recordId is not { Length: 64 } || !recordId.All(Uri.IsHexDigit)
            || lower[6]?["runId"]?.GetValue<string>() != runId
            || lower[6]?["recordId"]?.GetValue<string>() != recordId
            || lower[6]?["level"]?.GetValue<string>() != "L6"
            || source["artifactPath"]?.GetValue<string>() != "positive/l5-positive.msh") return null;
        var supportDirectory = Path.Combine(Path.GetDirectoryName(directory)!, folderId);
        var supportPath = Path.Combine(supportDirectory, "results.json");
        var sourceArtifact = Path.Combine(supportDirectory, "positive", "l5-positive.msh");
        if (!File.Exists(supportPath) || !File.Exists(sourceArtifact)
            || new FileInfo(supportPath).Length > 1048576 || new FileInfo(sourceArtifact).Length > 33554432
            || Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(sourceArtifact))).ToLowerInvariant()
                != source["artifactSha256"]?.GetValue<string>()) return null;
        using var document = JsonDocument.Parse(File.ReadAllText(supportPath));
        var support = document.RootElement;
        if (support.GetProperty("runId").GetString() != runId
            || support.GetProperty("profileId").GetString() != result["profileId"]?.GetValue<string>()
            || support.GetProperty("runtimeId").GetString() != "gmsh-win-conda"
            || support.GetProperty("recipeId").GetString() != "l6.reproduce"
            || support.GetProperty("state").GetString() != "succeeded"
            || support.GetProperty("runFingerprintSha256").GetString() != source["runFingerprintSha256"]?.GetValue<string>()
            || !Verify(supportDirectory, support).OfType<JsonObject>().Any(item =>
                item["recordId"]?.GetValue<string>() == recordId && item["level"]?.GetValue<string>() == "L6")) return null;
        var sourceEvidence = JsonNode.Parse(support.GetRawText())?["l6Evidence"];
        if (sourceEvidence?["positive"]?["artifactSha256"]?.GetValue<string>() != source["artifactSha256"]?.GetValue<string>()
            || sourceEvidence?["roundTrip"]?.ToJsonString() != source["roundTrip"]?.ToJsonString()) return null;
        foreach (var (file, key) in new[] {
            ("scientific-gmsh-handoff.py", "converterSha256"),
            ("scientific-gmsh-vtk-consumer.py", "vtkReaderSha256"),
            ("math3d-gmsh-import-handoff.mjs", "math3dHandoffSha256") })
            if (contract[key]?.GetValue<string>() != components["suite"]?["files"]?["tools/" + file]?["sha256"]?.GetValue<string>()) return null;
        if (contract["math3dImporterSha256"]?.GetValue<string>() is not { Length: 64 }
            || contract["vtkPythonSha256"]?.GetValue<string>() is not { Length: 64 }
            || contract["vtkEnvironmentSha256"]?.GetValue<string>() is not { Length: 64 }
            || result["inputArtifacts"] is not JsonArray inputs || inputs.Count != 1
            || inputs[0]?["sourceRunId"]?.GetValue<string>() != runId
            || inputs[0]?["sha256"]?.GetValue<string>() != source["artifactSha256"]?.GetValue<string>()
            || result["artifacts"] is not JsonArray outputs) return null;
        foreach (var name in GmshHandoffFiles)
        {
            var path = Path.Combine(directory, "handoff", name);
            var expected = hashes[name]?.GetValue<string>();
            if (!File.Exists(path) || new FileInfo(path).Length > 33554432
                || expected is not { Length: 64 }
                || Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant() != expected
                || !outputs.Any(item => item?["path"]?.GetValue<string>() == "handoff/" + name
                    && item?["sha256"]?.GetValue<string>() == expected)) return null;
            if (name.EndsWith(".json", StringComparison.Ordinal))
            {
                var key = name switch { "handoff.json" => "handoff", "vtk.json" => "vtk", "math3d.json" => "math3d",
                    "vtk-rejection.json" => "vtkRejection", _ => "math3dRejection" };
                if (JsonNode.Parse(File.ReadAllText(path))?.ToJsonString() != evidence[key]?.ToJsonString()) return null;
            }
        }
        return evidence["handoff"] is JsonObject handoff && evidence["vtk"] is JsonObject vtk
            && evidence["math3d"] is JsonObject math3d && evidence["vtkRejection"] is JsonObject vtkReject
            && evidence["math3dRejection"] is JsonObject math3dReject
            && ValidGmshInterop(handoff, vtk, math3d, vtkReject, math3dReject,
                source["artifactSha256"]?.GetValue<string>(), hashes["mesh.obj"]?.GetValue<string>(),
                hashes["malformed.obj"]?.GetValue<string>(), contract["math3dImporterSha256"]?.GetValue<string>())
            ? Digest(evidence.ToJsonString()) : null;
    }

    private static string? GmshL8Hash(string directory, JsonObject result, JsonObject components)
    {
        if (result["recipeId"]?.GetValue<string>() != "l8.gmsh-resilience"
            || result["runtimeId"]?.GetValue<string>() != "gmsh-win-conda"
            || result["l8GmshEvidence"] is not JsonObject evidence
            || evidence["suiteId"]?.GetValue<string>() != "l8-gmsh-resilience-v1"
            || evidence["capabilityId"]?.GetValue<string>() != "mesh.generate"
            || evidence["lowerQualification"]?["records"] is not JsonArray lower || lower.Count != 8
            || evidence["observations"] is not JsonObject observations
            || observations["repeats"] is not JsonArray repeats || repeats.Count != 3
            || observations["repeatCount"]?.GetValue<int>() != 3
            || observations["repeatLimitSeconds"]?.GetValue<int>() != 60
            || observations["repeatMemoryLimitBytes"]?.GetValue<long>() != 536870912
            || observations["memoryLimitBytes"]?.GetValue<long>() != 134217728
            || evidence["readerSha256"]?.GetValue<string>() != components["suite"]?["files"]?
                ["tools/scientific-gmsh-vtk-consumer.py"]?["sha256"]?.GetValue<string>()) return null;
        var folder = evidence["sourceL7FolderId"]?.GetValue<string>();
        var runId = evidence["sourceL7RunId"]?.GetValue<string>();
        var recordId = evidence["sourceL7RecordId"]?.GetValue<string>();
        if (folder is not { Length: 32 } || !folder.All(Uri.IsHexDigit)
            || runId is not { Length: 32 } || !runId.All(Uri.IsHexDigit)
            || recordId is not { Length: 64 } || !recordId.All(Uri.IsHexDigit)
            || lower[7]?["runId"]?.GetValue<string>() != runId
            || lower[7]?["recordId"]?.GetValue<string>() != recordId
            || lower[7]?["level"]?.GetValue<string>() != "L7") return null;
        var sourceDirectory = Path.Combine(Path.GetDirectoryName(directory)!, folder);
        var sourcePath = Path.Combine(sourceDirectory, "results.json");
        var objPath = Path.Combine(sourceDirectory, "handoff", "mesh.obj");
        if (!File.Exists(sourcePath) || !File.Exists(objPath)
            || new FileInfo(sourcePath).Length > 1048576 || new FileInfo(objPath).Length > 33554432
            || Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(objPath))).ToLowerInvariant()
                != evidence["sourceArtifactSha256"]?.GetValue<string>()) return null;
        using var sourceDocument = JsonDocument.Parse(File.ReadAllText(sourcePath));
        var sourceResult = sourceDocument.RootElement;
        if (sourceResult.GetProperty("runId").GetString() != runId
            || sourceResult.GetProperty("profileId").GetString() != result["profileId"]?.GetValue<string>()
            || sourceResult.GetProperty("runtimeId").GetString() != "gmsh-win-conda"
            || sourceResult.GetProperty("recipeId").GetString() != "l7.gmsh-interop"
            || sourceResult.GetProperty("state").GetString() != "succeeded"
            || !Verify(sourceDirectory, sourceResult).OfType<JsonObject>().Any(item =>
                item["recordId"]?.GetValue<string>() == recordId && item["level"]?.GetValue<string>() == "L7")) return null;
        var l7 = JsonNode.Parse(sourceResult.GetRawText())?["l7GmshEvidence"];
        if (l7?["artifactHashes"]?["mesh.obj"]?.GetValue<string>() != evidence["sourceArtifactSha256"]?.GetValue<string>()
            || l7?["consumerContractSha256"]?.GetValue<string>() != evidence["sourceConsumerContractSha256"]?.GetValue<string>()
            || l7?["lowerQualification"]?["records"] is not JsonArray prior || prior.Count != 7) return null;
        for (var i = 0; i < 7; i++) if (lower[i]?.ToJsonString() != prior[i]?.ToJsonString()) return null;
        var root = Path.Combine(directory, "resilience");
        var observationsPath = Path.Combine(root, "observations.json");
        if (!File.Exists(observationsPath) || new FileInfo(observationsPath).Length > 262144
            || Digest(File.ReadAllText(observationsPath)) != evidence["observationsSha256"]?.GetValue<string>()
            || JsonNode.Parse(File.ReadAllText(observationsPath))?.ToJsonString() != observations.ToJsonString()
            || result["artifacts"] is not JsonArray artifacts
            || !artifacts.Any(item => item?["path"]?.GetValue<string>() == "resilience/observations.json"
                && item?["sha256"]?.GetValue<string>() == evidence["observationsSha256"]?.GetValue<string>())) return null;
        string? common = null;
        for (var i = 0; i < 3; i++)
        {
            var repeat = repeats[i];
            var name = $"repeat-{i + 1}.json";
            var path = Path.Combine(root, name);
            var hash = repeat?["resultSha256"]?.GetValue<string>();
            if (!File.Exists(path) || new FileInfo(path).Length > 65536
                || repeat?["caseId"]?.GetValue<string>() != $"repeat-{i + 1}"
                || hash != Digest(File.ReadAllText(path))
                || repeat?["result"]?.ToJsonString() != JsonNode.Parse(File.ReadAllText(path))?.ToJsonString()
                || repeat?["durationMs"]?.GetValue<long>() is not > 0 and < 60000
                || repeat?["peakProcessMemoryBytes"]?.GetValue<long>() is not > 0 and <= 536870912
                || repeat?["result"]?["state"]?.GetValue<string>() != "accepted"
                || repeat?["result"]?["inputObjSha256"]?.GetValue<string>() != evidence["sourceArtifactSha256"]?.GetValue<string>()
                || repeat?["result"]?["points"]?.GetValue<int>() != 44
                || repeat?["result"]?["triangles"]?.GetValue<int>() != 66
                || repeat?["result"]?["boundaryEdges"]?.GetValue<int>() != 20
                || repeat?["result"]?["nonManifoldEdges"]?.GetValue<int>() != 0
                || Math.Abs((repeat?["result"]?["signedAreaXY"]?.GetValue<double>() ?? double.NaN) - 1) > 1e-9
                || !artifacts.Any(item => item?["path"]?.GetValue<string>() == "resilience/" + name
                    && item?["sha256"]?.GetValue<string>() == hash)) return null;
            if (common != null && hash != common) return null;
            common = hash;
        }
        foreach (var name in new[] { "cancelled-output.txt", "timeout-output.txt", "memory-output.txt" })
            if (File.Exists(Path.Combine(root, name))) return null;
        if (observations["cancellation"]?["state"]?.GetValue<string>() != "cancelled"
            || observations["cancellation"]?["outputAbsent"]?.GetValue<bool>() != true
            || observations["cancellation"]?["childStopped"]?.GetValue<bool>() != true
            || observations["cancellation"]?["durationMs"]?.GetValue<long>() is not > 0 and < 5000
            || observations["timeout"]?["state"]?.GetValue<string>() != "timed-out"
            || observations["timeout"]?["limitSeconds"]?.GetValue<int>() != 1
            || observations["timeout"]?["outputAbsent"]?.GetValue<bool>() != true
            || observations["timeout"]?["childStopped"]?.GetValue<bool>() != true
            || observations["memory"]?["state"]?.GetValue<string>() != "limited"
            || observations["memory"]?["limitBytes"]?.GetValue<long>() != 134217728
            || observations["memory"]?["requestedBytes"]?.GetValue<long>() != 536870912
            || observations["memory"]?["exitCode"]?.GetValue<int>() != 42
            || observations["memory"]?["outputAbsent"]?.GetValue<bool>() != true
            || observations["memory"]?["childStopped"]?.GetValue<bool>() != true
            || result["inputArtifacts"] is not JsonArray inputs || inputs.Count != 1
            || inputs[0]?["sourceRunId"]?.GetValue<string>() != runId
            || inputs[0]?["sha256"]?.GetValue<string>() != evidence["sourceArtifactSha256"]?.GetValue<string>()) return null;
        return Digest(evidence.ToJsonString());
    }
}
