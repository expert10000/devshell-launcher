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

    private static string? GmshL9Hash(string directory, JsonObject result, JsonObject components)
    {
        if (result["recipeId"]?.GetValue<string>() != "l9.gmsh-product"
            || result["runtimeId"]?.GetValue<string>() != "gmsh-win-conda"
            || result["l9GmshEvidence"] is not JsonObject evidence
            || evidence["suiteId"]?.GetValue<string>() != "l9-gmsh-product-v1"
            || evidence["capabilityId"]?.GetValue<string>() != "mesh.generate"
            || evidence["worker"] is not JsonObject worker
            || evidence["conversion"] is not JsonObject conversion
            || evidence["brokerHandoff"] is not JsonObject handoff
            || evidence["productContract"] is not JsonObject contract
            || evidence["regression"] is not JsonObject report
            || evidence["roundtrip"] is not JsonObject roundtrip
            || evidence["lowerQualification"]?["records"] is not JsonArray lower || lower.Count != 9
            || contract["id"]?.GetValue<string>() != "math3d.mesh-product-handoff"
            || contract["version"]?.GetValue<int>() != 1
            || contract["workerResultSchemaVersion"]?.GetValue<int>() != 1
            || contract["meshDocumentSchemaVersion"]?.GetValue<int>() != 1
            || contract["inputFormat"]?.GetValue<string>() != "obj"
            || contract["viewer"]?.GetValue<string>() != "MeshDocumentViewport"
            || Digest(contract.ToJsonString()) != evidence["productContractSha256"]?.GetValue<string>()
            || components["suite"]?["files"]?["tools/math3d-l9-product-handoff.mjs"]?["sha256"] is not JsonNode
            || roundtrip["parserSourceSha256"]?.GetValue<string>() != components["suite"]?["files"]?
                ["tools/scientific-gmsh-m3dm-roundtrip.py"]?["sha256"]?.GetValue<string>()) return null;
        var folder = evidence["sourceL8FolderId"]?.GetValue<string>();
        var runId = evidence["sourceL8RunId"]?.GetValue<string>();
        var recordId = evidence["sourceL8RecordId"]?.GetValue<string>();
        if (folder is not { Length: 32 } || !folder.All(Uri.IsHexDigit)
            || runId is not { Length: 32 } || !runId.All(Uri.IsHexDigit)
            || recordId is not { Length: 64 } || !recordId.All(Uri.IsHexDigit)
            || lower[8]?["runId"]?.GetValue<string>() != runId
            || lower[8]?["recordId"]?.GetValue<string>() != recordId
            || lower[8]?["level"]?.GetValue<string>() != "L8") return null;
        var supportDirectory = Path.Combine(Path.GetDirectoryName(directory)!, folder);
        var supportPath = Path.Combine(supportDirectory, "results.json");
        if (!File.Exists(supportPath) || new FileInfo(supportPath).Length > 1048576) return null;
        using var document = JsonDocument.Parse(File.ReadAllText(supportPath));
        var support = document.RootElement;
        if (support.GetProperty("runId").GetString() != runId
            || support.GetProperty("profileId").GetString() != result["profileId"]?.GetValue<string>()
            || support.GetProperty("runtimeId").GetString() != "gmsh-win-conda"
            || support.GetProperty("recipeId").GetString() != "l8.gmsh-resilience"
            || support.GetProperty("state").GetString() != "succeeded"
            || !Verify(supportDirectory, support).OfType<JsonObject>().Any(item =>
                item["recordId"]?.GetValue<string>() == recordId && item["level"]?.GetValue<string>() == "L8")) return null;
        var l8 = JsonNode.Parse(support.GetRawText())?["l8GmshEvidence"];
        if (l8?["lowerQualification"]?["records"] is not JsonArray prior || prior.Count != 8
            || l8["sourceConsumerContractSha256"]?.GetValue<string>() != evidence["sourceL8ContractSha256"]?.GetValue<string>()) return null;
        for (var i = 0; i < 8; i++) if (lower[i]?.ToJsonString() != prior[i]?.ToJsonString()) return null;
        var l7Folder = evidence["sourceL7FolderId"]?.GetValue<string>();
        if (l7Folder is not { Length: 32 } || !l7Folder.All(Uri.IsHexDigit)) return null;
        var l7Path = Path.Combine(Path.GetDirectoryName(directory)!, l7Folder, "results.json");
        if (!File.Exists(l7Path) || new FileInfo(l7Path).Length > 1048576) return null;
        var l7 = JsonNode.Parse(File.ReadAllText(l7Path));
        if (l7?["runId"]?.GetValue<string>() != l8?["sourceL7RunId"]?.GetValue<string>()
            || l7?["l7GmshEvidence"]?["source"]?["artifactSha256"]?.GetValue<string>() != worker["artifactSha256"]?.GetValue<string>()
            || l7?["l7GmshEvidence"]?["artifactHashes"]?["mesh.obj"]?.GetValue<string>() != l8?["sourceArtifactSha256"]?.GetValue<string>()) return null;
        var positive = Path.Combine(directory, "positive");
        var requestPath = Path.Combine(positive, "request.json");
        var resultPath = Path.Combine(positive, "results.json");
        var mshPath = Path.Combine(positive, "l5-positive.msh");
        var handoffDirectory = Path.Combine(directory, "handoff");
        var objPath = Path.Combine(handoffDirectory, "mesh.obj");
        var conversionPath = Path.Combine(handoffDirectory, "conversion.json");
        var handoffPath = Path.Combine(handoffDirectory, "handoff.json");
        var productDirectory = Path.Combine(directory, "product");
        if (!new[] { requestPath, resultPath, mshPath, objPath, conversionPath, handoffPath }.All(File.Exists)
            || Digest(File.ReadAllText(requestPath)) != worker["requestSha256"]?.GetValue<string>()
            || Digest(File.ReadAllText(resultPath)) != worker["resultSha256"]?.GetValue<string>()
            || Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(mshPath))).ToLowerInvariant()
                != worker["artifactSha256"]?.GetValue<string>()
            || worker["state"]?.GetValue<string>() != "succeeded"
            || worker["artifactPath"]?.GetValue<string>() != "positive/l5-positive.msh"
            || conversion["sourceMshSha256"]?.GetValue<string>() != worker["artifactSha256"]?.GetValue<string>()
            || conversion["outputObjSha256"]?.GetValue<string>() != l8?["sourceArtifactSha256"]?.GetValue<string>()
            || Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(objPath))).ToLowerInvariant()
                != conversion["outputObjSha256"]?.GetValue<string>()
            || Digest(File.ReadAllText(conversionPath)) != evidence["conversionSha256"]?.GetValue<string>()
            || JsonNode.Parse(File.ReadAllText(conversionPath))?.ToJsonString() != conversion.ToJsonString()
            || Digest(File.ReadAllText(handoffPath)) != evidence["brokerHandoffSha256"]?.GetValue<string>()
            || JsonNode.Parse(File.ReadAllText(handoffPath))?.ToJsonString() != handoff.ToJsonString()
            || handoff["runtimeId"]?.GetValue<string>() != "gmsh-win-conda"
            || handoff["capabilityId"]?.GetValue<string>() != "mesh.generate"
            || handoff["sourceL8RunId"]?.GetValue<string>() != runId
            || handoff["sourceL8RecordId"]?.GetValue<string>() != recordId
            || handoff["contract"]?.ToJsonString() != contract.ToJsonString()
            || handoff["workerRequest"]?["sha256"]?.GetValue<string>() != worker["requestSha256"]?.GetValue<string>()
            || handoff["workerResult"]?["sha256"]?.GetValue<string>() != worker["resultSha256"]?.GetValue<string>()
            || handoff["workerArtifact"]?["sha256"]?.GetValue<string>() != worker["artifactSha256"]?.GetValue<string>()
            || handoff["artifact"]?["sha256"]?.GetValue<string>() != conversion["outputObjSha256"]?.GetValue<string>()) return null;
        using var childDocument = JsonDocument.Parse(File.ReadAllText(resultPath));
        var child = childDocument.RootElement;
        if (child.GetProperty("state").GetString() != "succeeded"
            || !child.GetProperty("validatedCapabilities").EnumerateArray().Any(item => item.GetString() == "mesh.generate")
            || !child.GetProperty("artifacts").EnumerateArray().Any(item =>
                item.GetProperty("path").GetString() == "l5-positive.msh"
                && item.GetProperty("sha256").GetString() == worker["artifactSha256"]?.GetValue<string>())) return null;
        var outputs = new[] { ("mesh-document.json", "documentSha256"), ("mesh-resource.bin", "resourceSha256"),
            ("viewer.png", "viewerSha256"), ("regression.json", "regressionSha256"),
            ("qualified-mesh.m3dm", "m3dmSha256"), ("roundtrip.json", "roundtripSha256") };
        if (result["artifacts"] is not JsonArray artifacts || outputs.Any(item =>
                !File.Exists(Path.Combine(productDirectory, item.Item1))
                || new FileInfo(Path.Combine(productDirectory, item.Item1)).Length is < 100 or > 8388608
                || Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(Path.Combine(productDirectory, item.Item1)))).ToLowerInvariant()
                    != evidence[item.Item2]?.GetValue<string>()
                || !artifacts.Any(file => file?["path"]?.GetValue<string>() == "product/" + item.Item1
                    && file?["sha256"]?.GetValue<string>() == evidence[item.Item2]?.GetValue<string>()))
            || !new[] { ("positive/l5-positive.msh", worker["artifactSha256"]?.GetValue<string>()),
                    ("handoff/mesh.obj", conversion["outputObjSha256"]?.GetValue<string>()),
                    ("handoff/conversion.json", evidence["conversionSha256"]?.GetValue<string>()),
                    ("handoff/handoff.json", evidence["brokerHandoffSha256"]?.GetValue<string>()) }
                .All(item => artifacts.Any(file => file?["path"]?.GetValue<string>() == item.Item1
                    && file?["sha256"]?.GetValue<string>() == item.Item2))) return null;
        var saved = JsonNode.Parse(File.ReadAllText(Path.Combine(productDirectory, "mesh-document.json")));
        if (saved?["format"]?.GetValue<string>() != "math3d.mesh-document"
            || saved["schemaVersion"]?.GetValue<int>() != 1
            || saved["source"]?["resource"]?["checksum"]?.GetValue<string>() != "sha256:" + evidence["resourceSha256"]?.GetValue<string>()
            || saved["identity"]?["id"]?.GetValue<string>() != report["documentId"]?.GetValue<string>()
            || report["documentSha256"]?.GetValue<string>() != evidence["documentSha256"]?.GetValue<string>()
            || report["resourceSha256"]?.GetValue<string>() != evidence["resourceSha256"]?.GetValue<string>()
            || report["screenshotSha256"]?.GetValue<string>() != evidence["viewerSha256"]?.GetValue<string>()
            || report["m3dmSha256"]?.GetValue<string>() != evidence["m3dmSha256"]?.GetValue<string>()
            || report["sourceArtifactSha256"]?.GetValue<string>() != conversion["outputObjSha256"]?.GetValue<string>()
            || report["workerArtifactSha256"]?.GetValue<string>() != worker["artifactSha256"]?.GetValue<string>()
            || report["contractSha256"]?.GetValue<string>() != evidence["productContractSha256"]?.GetValue<string>()
            || report["sourceL8RunId"]?.GetValue<string>() != runId
            || report["sourceL8RecordId"]?.GetValue<string>() != recordId
            || report["points"]?.GetValue<int>() != 44 || report["triangles"]?.GetValue<int>() != 66
            || report["viewer"]?.GetValue<string>() != "MeshDocumentViewport"
            || report["viewerState"]?.GetValue<string>() != "mounted"
            || report["regression"]?.GetValue<string>() != "passed"
            || report["blueMeshPixels"]?.GetValue<int>() is not > 1000
            || report["consumerSources"] is not JsonObject sources
            || Digest(sources.ToJsonString()) != evidence["consumerSourcesSha256"]?.GetValue<string>()
            || JsonNode.Parse(File.ReadAllText(Path.Combine(productDirectory, "regression.json")))?.ToJsonString() != report.ToJsonString()
            || JsonNode.Parse(File.ReadAllText(Path.Combine(productDirectory, "roundtrip.json")))?.ToJsonString() != roundtrip.ToJsonString()
            || roundtrip["schemaVersion"]?.GetValue<int>() != 1
            || roundtrip["format"]?.GetValue<string>() != "M3DM"
            || roundtrip["verdict"]?.GetValue<string>() != "passed"
            || roundtrip["geometry"]?.GetValue<string>() != "passed"
            || roundtrip["topology"]?.GetValue<string>() != "passed"
            || roundtrip["orientation"]?.GetValue<string>() != "passed"
            || roundtrip["scale"]?.GetValue<string>() != "passed"
            || roundtrip["sourceObjSha256"]?.GetValue<string>() != conversion["outputObjSha256"]?.GetValue<string>()
            || roundtrip["m3dmSha256"]?.GetValue<string>() != evidence["m3dmSha256"]?.GetValue<string>()
            || roundtrip["reloaded"]?["points"]?.GetValue<int>() != 44
            || roundtrip["reloaded"]?["triangles"]?.GetValue<int>() != 66
            || roundtrip["reloaded"]?["boundaryEdges"]?.GetValue<int>() != 20
            || Math.Abs((roundtrip["reloaded"]?["signedAreaXY"]?.GetValue<double>() ?? double.NaN) - 1) > 1e-6
            || result["inputArtifacts"] is not JsonArray inputs || inputs.Count != 1
            || inputs[0]?["sha256"]?.GetValue<string>() != worker["inputSha256"]?.GetValue<string>()) return null;
        var png = File.ReadAllBytes(Path.Combine(productDirectory, "viewer.png"));
        var m3dm = File.ReadAllBytes(Path.Combine(productDirectory, "qualified-mesh.m3dm"));
        return png.Length > 8 && png.AsSpan(0, 8).SequenceEqual(new byte[] { 137, 80, 78, 71, 13, 10, 26, 10 })
            && m3dm.Length > 32 && m3dm.AsSpan(0, 4).SequenceEqual("M3DM"u8)
            ? Digest(evidence.ToJsonString()) : null;
    }
}
