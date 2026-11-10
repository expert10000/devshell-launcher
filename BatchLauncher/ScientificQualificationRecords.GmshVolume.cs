using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace BatchLauncher;

public static partial class ScientificQualificationRecords
{
    private static string? GmshVolumeHash(string directory, JsonObject result, JsonObject components, string level)
    {
        var recipe = $"{level.ToLowerInvariant()}.gmsh-volume";
        if (result["runtimeId"]?.GetValue<string>() != "gmsh-win-conda"
            || result["recipeId"]?.GetValue<string>() != recipe
            || result["volumeEvidence"] is not JsonObject evidence
            || evidence["suiteId"]?.GetValue<string>() != "gmsh-volume-managed-v1"
            || evidence["capabilityId"]?.GetValue<string>() != "mesh.generate3d"
            || evidence["level"]?.GetValue<string>() != level
            || evidence["candidateFolder"]?.GetValue<string>() != "volume"
            || result["validatedCapabilities"] is not JsonArray capabilities
            || !capabilities.Any(item => item?.GetValue<string>() == "mesh.generate3d")
            || result["inputArtifacts"] is not JsonArray inputs || inputs.Count != 1
            || inputs[0]?["datasetId"]?.GetValue<string>() != "gmsh/fixed-cube.geo"
            || evidence["lowerQualification"]?["records"] is not JsonArray lower
            || lower.Count != (level == "L5" ? 5 : level == "L6" ? 6 : 7)
            || lower[3]?["capabilityId"]?.GetValue<string>() != "gmsh.volume3d.cube"
            || lower[3]?["level"]?.GetValue<string>() != "L3"
            || components["suite"]?["files"]?["tools/scientific-broker/gmsh_volume.py"]?["sha256"] is not JsonNode)
            return null;
        for (var index = 0; index < 5; index++)
            if (lower[index]?["level"]?.GetValue<string>() != "L" + index
                || lower[index]?["runId"]?.GetValue<string>() is not { Length: 32 }
                || lower[index]?["recordId"]?.GetValue<string>() is not { Length: 64 }) return null;
        var folder = Path.Combine(directory, "volume");
        var ticket = level == "L5" ? "DS-SCI-067" : level == "L6" ? "DS-SCI-068" : "DS-SCI-069";
        var recordPath = Path.Combine(folder, ticket + ".json");
        var suitePath = Path.Combine(directory, "suite.json");
        var artifact = Path.Combine(folder, "positive-a", "cube.msh");
        string? Hash(string path)
        {
            if (!File.Exists(path) || new FileInfo(path).Length is <= 0 or > 33554432) return null;
            return Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();
        }
        if (Hash(recordPath) != evidence["candidateRecordSha256"]?.GetValue<string>()
            || File.ReadAllText(recordPath + ".sha256").Trim() != evidence["candidateRecordSha256"]?.GetValue<string>()
            || Hash(suitePath) != evidence["suiteResultSha256"]?.GetValue<string>()
            || Hash(artifact) != evidence["artifactSha256"]?.GetValue<string>()
            || result["artifacts"] is not JsonArray artifacts
            || !artifacts.Any(item => item?["path"]?.GetValue<string>() == "volume/positive-a/cube.msh"
                && item?["sha256"]?.GetValue<string>() == evidence["artifactSha256"]?.GetValue<string>())
            || !artifacts.Any(item => item?["path"]?.GetValue<string>() == "volume/" + ticket + ".json"
                && item?["sha256"]?.GetValue<string>() == evidence["candidateRecordSha256"]?.GetValue<string>()))
            return null;
        var suite = JsonNode.Parse(File.ReadAllText(suitePath));
        var record = JsonNode.Parse(File.ReadAllText(recordPath));
        if (suite?["verdict"]?.GetValue<string>() != "passed"
            || !suite["records"]!.AsArray().Any(item => item?.GetValue<string>() == recordPath)
            || record?["ticket"]?.GetValue<string>() != ticket
            || record["suiteId"]?.GetValue<string>() != "scientific.gmsh.candidate-volume.v1"
            || record["releaseCertified"]?.GetValue<bool>() != false
            || record["volumePromotionAllowed"]?.GetValue<bool>() != false
            || record["sourceCommit"]?.GetValue<string>() != components["source"]?["gitHead"]?.GetValue<string>()
            || record["verdict"]?.GetValue<string>() != "passed"
            || (level != "L7" && record["artifactSha256"]?.GetValue<string>() != evidence["artifactSha256"]?.GetValue<string>()))
            return null;
        if (record["sources"] is not JsonObject sources || sources.Count is < 8 or > 40
            || record["files"] is not JsonObject files || files.Count < (level == "L5" ? 6 : 5)
            || files.Count > 40) return null;
        foreach (var (path, expected) in sources)
            if (expected?.GetValue<string>() != Hash(path)) return null;
        var root = Path.GetFullPath(folder) + Path.DirectorySeparatorChar;
        foreach (var (path, expected) in files)
            if (!Path.GetFullPath(path).StartsWith(root, StringComparison.OrdinalIgnoreCase)
                || expected?.GetValue<string>() != Hash(path)) return null;
        var positive = JsonNode.Parse(File.ReadAllText(Path.Combine(folder, "positive-a", "results.json")));
        var rejectedGeometry = JsonNode.Parse(File.ReadAllText(Path.Combine(folder, "reject-geometry", "results.json")));
        var rejectedParameter = JsonNode.Parse(File.ReadAllText(Path.Combine(folder, "reject-parameter", "results.json")));
        if (positive?["state"]?.GetValue<string>() != "succeeded"
            || positive["validatedCapabilities"]?[0]?.GetValue<string>() != "mesh.generate3d"
            || positive["artifacts"]?[0]?["sha256"]?.GetValue<string>() != evidence["artifactSha256"]?.GetValue<string>()
            || positive["inputArtifacts"]?[0]?["sha256"]?.GetValue<string>() != inputs[0]?["sha256"]?.GetValue<string>()
            || rejectedGeometry?["state"]?.GetValue<string>() != "failed"
            || rejectedParameter?["state"]?.GetValue<string>() != "failed"
            || rejectedGeometry["artifacts"]?.AsArray().Count != 0
            || rejectedParameter["artifacts"]?.AsArray().Count != 0
            || File.Exists(Path.Combine(folder, "reject-geometry", "cube.msh"))
            || File.Exists(Path.Combine(folder, "reject-parameter", "cube.msh"))) return null;
        if (level is "L6" or "L7")
        {
            var parent = Path.Combine(folder, level == "L6" ? "DS-SCI-067.json" : "DS-SCI-068.json");
            var second = JsonNode.Parse(File.ReadAllText(Path.Combine(folder, "positive-b", "results.json")));
            if (JsonNode.Parse(File.ReadAllText(Path.Combine(folder, "reload.json"))) is not JsonObject reload
                || evidence["baseline"] is not JsonObject baseline) return null;
            if (record["parentRecord"]?.GetValue<string>() != parent
                || record["parentSha256"]?.GetValue<string>() != Hash(parent)
                || second?["state"]?.GetValue<string>() != "succeeded"
                || second["artifacts"]?[0]?["sha256"]?.GetValue<string>() != evidence["artifactSha256"]?.GetValue<string>()
                || Hash(Path.Combine(folder, "positive-b", "cube.msh")) != evidence["artifactSha256"]?.GetValue<string>()
                || Hash(Path.Combine(folder, "reload.json")) != evidence["reloadSha256"]?.GetValue<string>()
                || reload.ToJsonString() != evidence["reload"]?.ToJsonString()
                || reload["sourceMshSha256"]?.GetValue<string>() != evidence["artifactSha256"]?.GetValue<string>()
                || reload["tetrahedra"]?.GetValue<int>() is not > 5
                || reload["boundaryEdges"]?.GetValue<int>() != 0
                || reload["nonManifoldEdges"]?.GetValue<int>() != 0
                || Math.Abs((reload["volume"]?.GetValue<double>() ?? double.NaN) - 1) > 1e-6
                || Math.Abs((reload["surfaceArea"]?.GetValue<double>() ?? double.NaN) - 6) > 1e-5
                || baseline["artifactSha256"]?.GetValue<string>() != evidence["artifactSha256"]?.GetValue<string>()
                || lower[level == "L6" ? 5 : 6]?["runId"]?.GetValue<string>() != baseline["runId"]?.GetValue<string>()
                || lower[level == "L6" ? 5 : 6]?["recordId"]?.GetValue<string>() != baseline["recordId"]?.GetValue<string>()
                || lower[level == "L6" ? 5 : 6]?["capabilityId"]?.GetValue<string>() != "mesh.generate3d"
                || lower[level == "L6" ? 5 : 6]?["level"]?.GetValue<string>() != (level == "L6" ? "L5" : "L6")) return null;
            var baselineFolder = baseline["folderId"]?.GetValue<string>();
            if (baselineFolder is not { Length: 32 } || !baselineFolder.All(Uri.IsHexDigit)) return null;
            var baselineDirectory = Path.Combine(Path.GetDirectoryName(directory)!, baselineFolder);
            var baselinePath = Path.Combine(baselineDirectory, "results.json");
            if (!File.Exists(baselinePath) || new FileInfo(baselinePath).Length > 1048576) return null;
            using var document = JsonDocument.Parse(File.ReadAllText(baselinePath));
            var baselineResult = document.RootElement;
            if (baselineResult.GetProperty("state").GetString() != "succeeded"
                || baselineResult.GetProperty("recipeId").GetString() != (level == "L6" ? "l5.gmsh-volume" : "l6.gmsh-volume")
                || baselineResult.GetProperty("runId").GetString() != baseline["runId"]?.GetValue<string>()
                || baselineResult.GetProperty("profileId").GetString() != result["profileId"]?.GetValue<string>()
                || !Verify(baselineDirectory, baselineResult).OfType<JsonObject>().Any(item =>
                    item["recordId"]?.GetValue<string>() == baseline["recordId"]?.GetValue<string>()
                    && item["capabilityId"]?.GetValue<string>() == "mesh.generate3d"
                    && item["level"]?.GetValue<string>() == (level == "L6" ? "L5" : "L6"))) return null;
        }
        else if (evidence["baseline"] != null || evidence["reloadSha256"] != null || evidence["reload"] != null) return null;
        if (level == "L7")
        {
            var boundaryPath = Path.Combine(folder, "boundary.obj");
            var boundaryHash = evidence["boundaryArtifactSha256"]?.GetValue<string>();
            var boundary = JsonNode.Parse(File.ReadAllText(Path.Combine(folder, "boundary.json")));
            var vtk = JsonNode.Parse(File.ReadAllText(Path.Combine(folder, "vtk.json")));
            var math3d = JsonNode.Parse(File.ReadAllText(Path.Combine(folder, "math3d.json")));
            var vtkReject = JsonNode.Parse(File.ReadAllText(Path.Combine(folder, "vtk-rejection.json")));
            var math3dReject = JsonNode.Parse(File.ReadAllText(Path.Combine(folder, "math3d-rejection.json")));
            if (Hash(boundaryPath) != boundaryHash || boundary?["outputObjSha256"]?.GetValue<string>() != boundaryHash
                || boundary?["sourceMshSha256"]?.GetValue<string>() != evidence["artifactSha256"]?.GetValue<string>()
                || record["boundaryObj"]?.GetValue<string>() != boundaryPath
                || record["reloadResult"]?.GetValue<string>() != Path.Combine(folder, "boundary.json")
                || vtk?.ToJsonString() != evidence["vtk"]?.ToJsonString()
                || math3d?.ToJsonString() != evidence["math3d"]?.ToJsonString()
                || vtkReject?["state"]?.GetValue<string>() != "rejected"
                || math3dReject?["state"]?.GetValue<string>() != "rejected"
                || vtk?["inputObjSha256"]?.GetValue<string>() != boundaryHash
                || math3d?["inputObjSha256"]?.GetValue<string>() != boundaryHash
                || math3d?["importerSourceSha256"]?.GetValue<string>() != Hash(record["math3dImporter"]?.GetValue<string>() ?? "")
                || vtk?["tetrahedra"] != null || math3d?["tetrahedra"] != null
                || vtk?["points"]?.GetValue<int>() != boundary?["boundaryPoints"]?.GetValue<int>()
                || math3d?["points"]?.GetValue<int>() != boundary?["boundaryPoints"]?.GetValue<int>()
                || vtk?["triangles"]?.GetValue<int>() != boundary?["boundaryTriangles"]?.GetValue<int>()
                || math3d?["triangles"]?.GetValue<int>() != boundary?["boundaryTriangles"]?.GetValue<int>()
                || Math.Abs((vtk?["signedVolume"]?.GetValue<double>() ?? double.NaN) - 1) > 1e-5
                || Math.Abs((math3d?["signedVolume"]?.GetValue<double>() ?? double.NaN) - 1) > 1e-5
                || result["artifacts"] is not JsonArray outputs
                || !outputs.Any(item => item?["path"]?.GetValue<string>() == "volume/boundary.obj"
                    && item?["sha256"]?.GetValue<string>() == boundaryHash)) return null;
        }
        return Digest(evidence.ToJsonString());
    }

    private static string? GmshVolumeL8Hash(string directory, JsonObject result, JsonObject components)
    {
        if (result["runtimeId"]?.GetValue<string>() != "gmsh-win-conda"
            || result["recipeId"]?.GetValue<string>() != "l8.gmsh-volume"
            || result["l8GmshVolumeEvidence"] is not JsonObject evidence
            || evidence["suiteId"]?.GetValue<string>() != "l8-gmsh-volume-v1"
            || evidence["capabilityId"]?.GetValue<string>() != "mesh.generate3d"
            || evidence["readerSha256"]?.GetValue<string>() != components["suite"]?["files"]?
                ["tools/scientific-gmsh-volume-vtk.py"]?["sha256"]?.GetValue<string>()
            || evidence["lowerQualification"]?["records"] is not JsonArray lower || lower.Count != 8
            || evidence["observations"] is not JsonObject observations
            || observations["repeatCount"]?.GetValue<int>() != 3
            || observations["repeatMemoryLimitBytes"]?.GetValue<long>() != 536870912
            || observations["memoryLimitBytes"]?.GetValue<long>() != 134217728
            || observations["repeats"] is not JsonArray repeats || repeats.Count != 3)
            return null;
        var folderId = evidence["sourceL7FolderId"]?.GetValue<string>();
        var runId = evidence["sourceL7RunId"]?.GetValue<string>();
        var recordId = evidence["sourceL7RecordId"]?.GetValue<string>();
        if (folderId is not { Length: 32 } || !folderId.All(Uri.IsHexDigit)
            || runId is not { Length: 32 } || !runId.All(Uri.IsHexDigit)
            || recordId is not { Length: 64 } || !recordId.All(Uri.IsHexDigit)
            || lower[7]?["runId"]?.GetValue<string>() != runId
            || lower[7]?["recordId"]?.GetValue<string>() != recordId
            || lower[7]?["capabilityId"]?.GetValue<string>() != "mesh.generate3d"
            || lower[7]?["level"]?.GetValue<string>() != "L7") return null;
        var sourceDirectory = Path.Combine(Path.GetDirectoryName(directory)!, folderId);
        var sourcePath = Path.Combine(sourceDirectory, "results.json");
        var objPath = Path.Combine(sourceDirectory, "volume", "boundary.obj");
        if (!File.Exists(sourcePath) || !File.Exists(objPath)
            || new FileInfo(sourcePath).Length > 1048576 || new FileInfo(objPath).Length > 33554432
            || Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(objPath))).ToLowerInvariant()
                != evidence["sourceArtifactSha256"]?.GetValue<string>()) return null;
        using var document = JsonDocument.Parse(File.ReadAllText(sourcePath));
        var source = document.RootElement;
        if (source.GetProperty("state").GetString() != "succeeded"
            || source.GetProperty("recipeId").GetString() != "l7.gmsh-volume"
            || source.GetProperty("runId").GetString() != runId
            || source.GetProperty("profileId").GetString() != result["profileId"]?.GetValue<string>()
            || !Verify(sourceDirectory, source).OfType<JsonObject>().Any(item =>
                item["recordId"]?.GetValue<string>() == recordId && item["level"]?.GetValue<string>() == "L7")) return null;
        var l7 = JsonNode.Parse(source.GetRawText())?["volumeEvidence"];
        if (l7?["boundaryArtifactSha256"]?.GetValue<string>() != evidence["sourceArtifactSha256"]?.GetValue<string>()
            || l7?["candidateRecordSha256"]?.GetValue<string>() != evidence["sourceConsumerContractSha256"]?.GetValue<string>()
            || l7?["lowerQualification"]?["records"] is not JsonArray prior || prior.Count != 7) return null;
        for (var index = 0; index < 7; index++)
            if (lower[index]?.ToJsonString() != prior[index]?.ToJsonString()) return null;
        var root = Path.Combine(directory, "resilience");
        var observationPath = Path.Combine(root, "observations.json");
        if (!File.Exists(observationPath) || new FileInfo(observationPath).Length > 262144
            || Digest(File.ReadAllText(observationPath)) != evidence["observationsSha256"]?.GetValue<string>()
            || JsonNode.Parse(File.ReadAllText(observationPath))?.ToJsonString() != observations.ToJsonString()
            || result["artifacts"] is not JsonArray outputs
            || !outputs.Any(item => item?["path"]?.GetValue<string>() == "resilience/observations.json"
                && item?["sha256"]?.GetValue<string>() == evidence["observationsSha256"]?.GetValue<string>())) return null;
        string? common = null;
        for (var index = 1; index <= 3; index++)
        {
            var name = $"repeat-{index}.json";
            var path = Path.Combine(root, name);
            var repeat = repeats[index - 1];
            var hash = repeat?["resultSha256"]?.GetValue<string>();
            var accepted = repeat?["result"];
            if (!File.Exists(path) || new FileInfo(path).Length > 65536
                || hash != Digest(File.ReadAllText(path))
                || repeat?["caseId"]?.GetValue<string>() != $"repeat-{index}"
                || accepted?.ToJsonString() != JsonNode.Parse(File.ReadAllText(path))?.ToJsonString()
                || accepted?["state"]?.GetValue<string>() != "accepted"
                || accepted["inputObjSha256"]?.GetValue<string>() != evidence["sourceArtifactSha256"]?.GetValue<string>()
                || accepted["points"]?.GetValue<int>() != 80
                || accepted["triangles"]?.GetValue<int>() != 156
                || accepted["boundaryEdges"]?.GetValue<int>() != 0
                || accepted["nonManifoldEdges"]?.GetValue<int>() != 0
                || Math.Abs((accepted["signedVolume"]?.GetValue<double>() ?? double.NaN) - 1) > 1e-5
                || Math.Abs((accepted["surfaceArea"]?.GetValue<double>() ?? double.NaN) - 6) > 1e-5
                || repeat["peakProcessMemoryBytes"]?.GetValue<long>() is not > 0 and <= 536870912
                || !outputs.Any(item => item?["path"]?.GetValue<string>() == "resilience/" + name
                    && item?["sha256"]?.GetValue<string>() == hash)
                || common != null && hash != common) return null;
            common = hash;
        }
        if (new[] { "cancelled-output.txt", "timeout-output.txt", "memory-output.txt" }
                .Any(name => File.Exists(Path.Combine(root, name)))
            || observations["cancellation"]?["state"]?.GetValue<string>() != "cancelled"
            || observations["cancellation"]?["outputAbsent"]?.GetValue<bool>() != true
            || observations["cancellation"]?["childStopped"]?.GetValue<bool>() != true
            || observations["timeout"]?["state"]?.GetValue<string>() != "timed-out"
            || observations["timeout"]?["limitSeconds"]?.GetValue<int>() != 1
            || observations["timeout"]?["outputAbsent"]?.GetValue<bool>() != true
            || observations["timeout"]?["childStopped"]?.GetValue<bool>() != true
            || observations["memory"]?["state"]?.GetValue<string>() != "limited"
            || observations["memory"]?["exitCode"]?.GetValue<int>() != 42
            || observations["memory"]?["outputAbsent"]?.GetValue<bool>() != true
            || observations["memory"]?["childStopped"]?.GetValue<bool>() != true
            || result["inputArtifacts"] is not JsonArray inputs || inputs.Count != 1
            || inputs[0]?["sourceRunId"]?.GetValue<string>() != runId
            || inputs[0]?["sha256"]?.GetValue<string>() != evidence["sourceArtifactSha256"]?.GetValue<string>()) return null;
        return Digest(evidence.ToJsonString());
    }

    private static string? GmshVolumeL9Hash(string directory, JsonObject result, JsonObject components)
    {
        if (result["runtimeId"]?.GetValue<string>() != "gmsh-win-conda"
            || result["recipeId"]?.GetValue<string>() != "l9.gmsh-volume"
            || result["l9GmshVolumeEvidence"] is not JsonObject evidence
            || evidence["suiteId"]?.GetValue<string>() != "l9-gmsh-volume-v1"
            || evidence["capabilityId"]?.GetValue<string>() != "mesh.generate3d"
            || result["validatedCapabilities"] is not JsonArray capabilities
            || !capabilities.Any(item => item?.GetValue<string>() == "mesh.generate3d")
            || evidence["productContract"] is not JsonObject contract
            || contract["id"]?.GetValue<string>() != "math3d.tetrahedral-product-handoff"
            || contract["version"]?.GetValue<int>() != 1
            || contract["documentFormat"]?.GetValue<string>() != "math3d.tetrahedral-mesh-document"
            || contract["resourceEncoding"]?.GetValue<string>() != "math3d.tetmesh-buffers.v1"
            || contract["viewer"]?.GetValue<string>() != "TetrahedralMeshViewport"
            || Digest(contract.ToJsonString()) != evidence["productContractSha256"]?.GetValue<string>()
            || evidence["lowerQualification"]?["records"] is not JsonArray lower || lower.Count != 9
            || evidence["brokerHandoff"] is not JsonObject handoff
            || evidence["artifactHashes"] is not JsonObject hashes
            || evidence["exporter"] is not JsonObject exporter
            || evidence["regression"] is not JsonObject regression
            || evidence["roundtrip"] is not JsonObject roundtrip
            || components["suite"]?["files"]?["tools/scientific-gmsh-tetmesh-export.py"]?["sha256"] is not JsonNode
            || components["suite"]?["files"]?["tools/math3d-gmsh-tetmesh-product.mjs"]?["sha256"] is not JsonNode
            || components["suite"]?["files"]?["tools/scientific-gmsh-tetmesh-roundtrip.py"]?["sha256"] is not JsonNode)
            return null;
        var l8Folder = evidence["sourceL8FolderId"]?.GetValue<string>();
        var l7Folder = evidence["sourceL7FolderId"]?.GetValue<string>();
        var l8RunId = evidence["sourceL8RunId"]?.GetValue<string>();
        var l8RecordId = evidence["sourceL8RecordId"]?.GetValue<string>();
        if (l8Folder is not { Length: 32 } || !l8Folder.All(Uri.IsHexDigit)
            || l7Folder is not { Length: 32 } || !l7Folder.All(Uri.IsHexDigit)
            || l8RunId is not { Length: 32 } || !l8RunId.All(Uri.IsHexDigit)
            || l8RecordId is not { Length: 64 } || !l8RecordId.All(Uri.IsHexDigit)
            || lower[8]?["runId"]?.GetValue<string>() != l8RunId
            || lower[8]?["recordId"]?.GetValue<string>() != l8RecordId
            || lower[8]?["capabilityId"]?.GetValue<string>() != "mesh.generate3d"
            || lower[8]?["level"]?.GetValue<string>() != "L8") return null;
        var runs = Path.GetDirectoryName(directory)!;
        var l8Directory = Path.Combine(runs, l8Folder);
        var l8Path = Path.Combine(l8Directory, "results.json");
        var l7Path = Path.Combine(runs, l7Folder, "results.json");
        if (!File.Exists(l8Path) || !File.Exists(l7Path)
            || new FileInfo(l8Path).Length > 1048576 || new FileInfo(l7Path).Length > 1048576) return null;
        using var l8Document = JsonDocument.Parse(File.ReadAllText(l8Path));
        var l8Result = l8Document.RootElement;
        if (l8Result.GetProperty("state").GetString() != "succeeded"
            || l8Result.GetProperty("recipeId").GetString() != "l8.gmsh-volume"
            || l8Result.GetProperty("runId").GetString() != l8RunId
            || l8Result.GetProperty("profileId").GetString() != result["profileId"]?.GetValue<string>()
            || !Verify(l8Directory, l8Result).OfType<JsonObject>().Any(item =>
                item["recordId"]?.GetValue<string>() == l8RecordId && item["level"]?.GetValue<string>() == "L8")) return null;
        var l8Evidence = JsonNode.Parse(l8Result.GetRawText())?["l8GmshVolumeEvidence"];
        var l7Result = JsonNode.Parse(File.ReadAllText(l7Path));
        if (l8Evidence?["sourceL7FolderId"]?.GetValue<string>() != l7Folder
            || l7Result?["runId"]?.GetValue<string>() != l8Evidence["sourceL7RunId"]?.GetValue<string>()
            || l7Result?["volumeEvidence"]?["artifactSha256"]?.GetValue<string>() != evidence["sourceMshSha256"]?.GetValue<string>()
            || l8Evidence["lowerQualification"]?["records"] is not JsonArray prior || prior.Count != 8) return null;
        for (var index = 0; index < 8; index++)
            if (lower[index]?.ToJsonString() != prior[index]?.ToJsonString()) return null;
        string? Hash(string path)
        {
            if (!File.Exists(path) || new FileInfo(path).Length is <= 0 or > 33554432) return null;
            return Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();
        }
        var msh = Path.Combine(directory, "volume", "positive-a", "cube.msh");
        var product = Path.Combine(directory, "product");
        var mshHash = evidence["sourceMshSha256"]?.GetValue<string>();
        if (Hash(msh) != mshHash || Hash(Path.Combine(runs, l7Folder, "volume", "positive-a", "cube.msh")) != mshHash
            || Hash(Path.Combine(directory, "volume", "DS-SCI-067.json")) != evidence["freshWorkerRecordSha256"]?.GetValue<string>()
            || JsonNode.Parse(File.ReadAllText(Path.Combine(directory, "suite.json")))?["verdict"]?.GetValue<string>() != "passed"
            || result["inputArtifacts"] is not JsonArray inputs || inputs.Count != 1
            || inputs[0]?["datasetId"]?.GetValue<string>() != "gmsh/fixed-cube.geo"
            || result["artifacts"] is not JsonArray outputs) return null;
        foreach (var name in new[] { "volume.m3dt", "exporter.json", "handoff.json", "tetra-document.json",
            "tetra-resource.m3dt", "viewer.png", "regression.json", "roundtrip.json" })
        {
            var hash = hashes[name]?.GetValue<string>();
            if (hash is not { Length: 64 } || Hash(Path.Combine(product, name)) != hash
                || !outputs.Any(item => item?["path"]?.GetValue<string>() == "product/" + name
                    && item?["sha256"]?.GetValue<string>() == hash)) return null;
        }
        if (!outputs.Any(item => item?["path"]?.GetValue<string>() == "volume/positive-a/cube.msh"
                && item?["sha256"]?.GetValue<string>() == mshHash)
            || JsonNode.Parse(File.ReadAllText(Path.Combine(product, "handoff.json")))?.ToJsonString() != handoff.ToJsonString()
            || JsonNode.Parse(File.ReadAllText(Path.Combine(product, "exporter.json")))?.ToJsonString() != exporter.ToJsonString()
            || JsonNode.Parse(File.ReadAllText(Path.Combine(product, "regression.json")))?.ToJsonString() != regression.ToJsonString()
            || JsonNode.Parse(File.ReadAllText(Path.Combine(product, "roundtrip.json")))?.ToJsonString() != roundtrip.ToJsonString()
            || handoff["contract"]?.ToJsonString() != contract.ToJsonString()
            || handoff["sourceL8RunId"]?.GetValue<string>() != l8RunId
            || handoff["sourceL8RecordId"]?.GetValue<string>() != l8RecordId
            || handoff["sourceMsh"]?["path"]?.GetValue<string>() != msh
            || handoff["sourceMsh"]?["sha256"]?.GetValue<string>() != mshHash
            || handoff["resource"]?["sha256"]?.GetValue<string>() != hashes["volume.m3dt"]?.GetValue<string>()
            || handoff["exporterReport"]?["sha256"]?.GetValue<string>() != hashes["exporter.json"]?.GetValue<string>()
            || exporter["sourceMshSha256"]?.GetValue<string>() != mshHash
            || exporter["resourceSha256"]?.GetValue<string>() != hashes["volume.m3dt"]?.GetValue<string>()
            || exporter["points"]?.GetValue<int>() != l7Result?["volumeEvidence"]?["reload"]?["points"]?.GetValue<int>()
            || exporter["tetrahedra"]?.GetValue<int>() != l7Result?["volumeEvidence"]?["reload"]?["tetrahedra"]?.GetValue<int>()
            || exporter["boundaryTriangles"]?.GetValue<int>() != l7Result?["volumeEvidence"]?["reload"]?["boundaryTriangles"]?.GetValue<int>()
            || exporter["exporterSha256"]?.GetValue<string>() != components["suite"]?["files"]?
                ["tools/scientific-gmsh-tetmesh-export.py"]?["sha256"]?.GetValue<string>()
            || regression["regression"]?.GetValue<string>() != "passed"
            || regression["viewerState"]?.GetValue<string>() != "mounted"
            || regression["viewer"]?.GetValue<string>() != "TetrahedralMeshViewport"
            || regression["blueMeshPixels"]?.GetValue<int>() is not > 1000
            || regression["tamperRejected"]?.GetValue<bool>() != true
            || regression["points"]?.GetValue<int>() != exporter["points"]?.GetValue<int>()
            || regression["tetrahedra"]?.GetValue<int>() != exporter["tetrahedra"]?.GetValue<int>()
            || regression["boundaryTriangles"]?.GetValue<int>() != exporter["boundaryTriangles"]?.GetValue<int>()
            || regression["sourceMshSha256"]?.GetValue<string>() != mshHash
            || regression["documentSha256"]?.GetValue<string>() != hashes["tetra-document.json"]?.GetValue<string>()
            || regression["resourceSha256"]?.GetValue<string>() != hashes["tetra-resource.m3dt"]?.GetValue<string>()
            || regression["viewerSha256"]?.GetValue<string>() != hashes["viewer.png"]?.GetValue<string>()
            || regression["contractSha256"]?.GetValue<string>() != evidence["productContractSha256"]?.GetValue<string>()
            || regression["consumerSources"] is not JsonObject sources
            || Digest(sources.ToJsonString()) != evidence["consumerSourcesSha256"]?.GetValue<string>()
            || regression["consumerSourcesSha256"]?.GetValue<string>() != evidence["consumerSourcesSha256"]?.GetValue<string>()
            || roundtrip["verdict"]?.GetValue<string>() != "passed"
            || roundtrip["format"]?.GetValue<string>() != "M3DT"
            || roundtrip["points"]?.GetValue<int>() != exporter["points"]?.GetValue<int>()
            || roundtrip["tetrahedra"]?.GetValue<int>() != exporter["tetrahedra"]?.GetValue<int>()
            || roundtrip["boundaryTriangles"]?.GetValue<int>() != exporter["boundaryTriangles"]?.GetValue<int>()
            || roundtrip["boundaryEdges"]?.GetValue<int>() != 0
            || roundtrip["nonManifoldEdges"]?.GetValue<int>() != 0
            || Math.Abs((roundtrip["volume"]?.GetValue<double>() ?? double.NaN) - 1) > 1e-6
            || roundtrip["sourceMshSha256"]?.GetValue<string>() != mshHash
            || roundtrip["documentSha256"]?.GetValue<string>() != hashes["tetra-document.json"]?.GetValue<string>()
            || roundtrip["resourceSha256"]?.GetValue<string>() != hashes["tetra-resource.m3dt"]?.GetValue<string>()
            || roundtrip["parserSourceSha256"]?.GetValue<string>() != components["suite"]?["files"]?
                ["tools/scientific-gmsh-tetmesh-roundtrip.py"]?["sha256"]?.GetValue<string>()) return null;
        return Digest(evidence.ToJsonString());
    }
}
