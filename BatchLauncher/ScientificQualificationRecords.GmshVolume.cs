using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace BatchLauncher;

public static partial class ScientificQualificationRecords
{
    private static string? GmshVolumeHash(string directory, JsonObject result, JsonObject components, string level)
    {
        var recipe = level == "L5" ? "l5.gmsh-volume" : "l6.gmsh-volume";
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
            || lower.Count != (level == "L5" ? 5 : 6)
            || lower[3]?["capabilityId"]?.GetValue<string>() != "gmsh.volume3d.cube"
            || lower[3]?["level"]?.GetValue<string>() != "L3"
            || components["suite"]?["files"]?["tools/scientific-broker/gmsh_volume.py"]?["sha256"] is not JsonNode)
            return null;
        for (var index = 0; index < 5; index++)
            if (lower[index]?["level"]?.GetValue<string>() != "L" + index
                || lower[index]?["runId"]?.GetValue<string>() is not { Length: 32 }
                || lower[index]?["recordId"]?.GetValue<string>() is not { Length: 64 }) return null;
        var folder = Path.Combine(directory, "volume");
        var ticket = level == "L5" ? "DS-SCI-067" : "DS-SCI-068";
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
            || record["artifactSha256"]?.GetValue<string>() != evidence["artifactSha256"]?.GetValue<string>())
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
        if (level == "L6")
        {
            var parent = Path.Combine(folder, "DS-SCI-067.json");
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
                || lower[5]?["runId"]?.GetValue<string>() != baseline["runId"]?.GetValue<string>()
                || lower[5]?["recordId"]?.GetValue<string>() != baseline["recordId"]?.GetValue<string>()
                || lower[5]?["capabilityId"]?.GetValue<string>() != "mesh.generate3d"
                || lower[5]?["level"]?.GetValue<string>() != "L5") return null;
            var baselineFolder = baseline["folderId"]?.GetValue<string>();
            if (baselineFolder is not { Length: 32 } || !baselineFolder.All(Uri.IsHexDigit)) return null;
            var baselineDirectory = Path.Combine(Path.GetDirectoryName(directory)!, baselineFolder);
            var baselinePath = Path.Combine(baselineDirectory, "results.json");
            if (!File.Exists(baselinePath) || new FileInfo(baselinePath).Length > 1048576) return null;
            using var document = JsonDocument.Parse(File.ReadAllText(baselinePath));
            var baselineResult = document.RootElement;
            if (baselineResult.GetProperty("state").GetString() != "succeeded"
                || baselineResult.GetProperty("recipeId").GetString() != "l5.gmsh-volume"
                || baselineResult.GetProperty("runId").GetString() != baseline["runId"]?.GetValue<string>()
                || baselineResult.GetProperty("profileId").GetString() != result["profileId"]?.GetValue<string>()
                || !Verify(baselineDirectory, baselineResult).OfType<JsonObject>().Any(item =>
                    item["recordId"]?.GetValue<string>() == baseline["recordId"]?.GetValue<string>()
                    && item["capabilityId"]?.GetValue<string>() == "mesh.generate3d"
                    && item["level"]?.GetValue<string>() == "L5")) return null;
        }
        else if (evidence["baseline"] != null || evidence["reloadSha256"] != null || evidence["reload"] != null) return null;
        return Digest(evidence.ToJsonString());
    }
}
