using System.Text.Json;
using System.Text.Json.Nodes;

namespace BatchLauncher;

public static partial class ScientificQualificationRecords
{
    private static string? RepairL9Hash(string directory, JsonObject result, JsonObject components)
    {
        try
        {
            if (result["runtimeId"]?.GetValue<string>() != "cgal-win-conda"
                || result["recipeId"]?.GetValue<string>() != "l9.cgal-repair"
                || result["state"]?.GetValue<string>() != "succeeded"
                || result["repairProductEvidence"] is not JsonObject evidence
                || evidence["suiteId"]?.GetValue<string>() != ScientificRepairProductContract.Id
                || evidence["capabilityId"]?.GetValue<string>() != "mesh.repair"
                || evidence["cases"] is not JsonArray cases || cases.Count != 4
                || evidence["lowerQualification"]?["records"] is not JsonArray lower || lower.Count != 9
                || result["inputArtifacts"] is not JsonArray inputs || inputs.Count != 4
                || result["artifacts"] is not JsonArray artifacts
                || result["validatedCapabilities"] is not JsonArray validated
                || !validated.Any(item => item?.GetValue<string>() == "mesh.repair")) return null;
            bool Artifact(string name, string? hash) => hash is { Length: 64 }
                && artifacts.Any(item => item?["path"]?.GetValue<string>() == name
                    && item?["sha256"]?.GetValue<string>() == hash);
            var contractPath = Path.Combine(directory, "repair-product-contract.json");
            if (!File.Exists(contractPath) || new FileInfo(contractPath).Length > 65536
                || ScientificArtifactFiles.Hash(contractPath) != evidence["productContractFileSha256"]?.GetValue<string>()
                || !Artifact("repair-product-contract.json", evidence["productContractFileSha256"]?.GetValue<string>())) return null;
            var contract = JsonNode.Parse(File.ReadAllText(contractPath)) as JsonObject;
            if (contract == null || contract.ToJsonString() != evidence["productContract"]?.ToJsonString()
                || Digest(contract.ToJsonString()) != evidence["productContractSha256"]?.GetValue<string>()
                || evidence["productContractFileSha256"]?.GetValue<string>()
                    != components["suite"]?["files"]?[ScientificRepairProductContract.RelativePath]?["sha256"]?.GetValue<string>()) return null;
            ScientificRepairProductContract.Validate(contract);
            var sources = evidence["consumerSources"] as JsonObject;
            if (sources == null || sources.Count != ScientificRepairProductContract.ConsumerSources.Length
                || Digest(sources.ToJsonString()) != evidence["consumerSourcesSha256"]?.GetValue<string>()
                || ScientificRepairProductContract.ConsumerSources.Any(name => sources[name]?.GetValue<string>() is not { Length: 64 }))
                return null;
            for (var i = 0; i < 9; i++)
                if (lower[i]?["level"]?.GetValue<string>() != "L" + i
                    || lower[i]?["runId"]?.GetValue<string>() is not { Length: 32 }
                    || lower[i]?["recordId"]?.GetValue<string>() is not { Length: 64 }) return null;
            var folder = evidence["sourceL8FolderId"]?.GetValue<string>();
            var runId = evidence["sourceL8RunId"]?.GetValue<string>();
            var recordId = evidence["sourceL8RecordId"]?.GetValue<string>();
            if (folder is not { Length: 32 } || !folder.All(Uri.IsHexDigit)
                || runId is not { Length: 32 } || !runId.All(Uri.IsHexDigit)
                || recordId is not { Length: 64 } || !recordId.All(Uri.IsHexDigit)
                || lower[8]?["runId"]?.GetValue<string>() != runId
                || lower[8]?["recordId"]?.GetValue<string>() != recordId) return null;
            var sourceDirectory = Path.Combine(Path.GetDirectoryName(directory)!, folder);
            var sourcePath = Path.Combine(sourceDirectory, "results.json");
            if (!File.Exists(sourcePath) || new FileInfo(sourcePath).Length > 1048576) return null;
            using var sourceDocument = JsonDocument.Parse(File.ReadAllText(sourcePath));
            var saved = sourceDocument.RootElement;
            if (saved.GetProperty("runId").GetString() != runId
                || saved.GetProperty("profileId").GetString() != result["profileId"]?.GetValue<string>()
                || saved.GetProperty("runtimeId").GetString() != "cgal-win-conda"
                || saved.GetProperty("recipeId").GetString() != "l8.cgal-repair"
                || saved.GetProperty("state").GetString() != "succeeded"
                || !Verify(sourceDirectory, saved).OfType<JsonObject>().Any(item =>
                    item["recordId"]?.GetValue<string>() == recordId
                    && item["capabilityId"]?.GetValue<string>() == "mesh.repair"
                    && item["level"]?.GetValue<string>() == "L8")) return null;
            var l8 = JsonNode.Parse(saved.GetRawText())?["repairResilienceEvidence"];
            if (l8?["lowerQualification"]?["records"] is not JsonArray sourceLower || sourceLower.Count != 8)
                return null;
            for (var i = 0; i < 8; i++)
                if (lower[i]?.ToJsonString() != sourceLower[i]?.ToJsonString()) return null;
            var l7Folder = l8["sourceL7FolderId"]?.GetValue<string>();
            if (l7Folder is not { Length: 32 } || !l7Folder.All(Uri.IsHexDigit)) return null;
            var l7Path = Path.Combine(Path.GetDirectoryName(directory)!, l7Folder, "results.json");
            if (!File.Exists(l7Path) || new FileInfo(l7Path).Length > 1048576) return null;
            var l7Cases = JsonNode.Parse(File.ReadAllText(l7Path))?["repairInteropEvidence"]?["cases"] as JsonArray;
            if (l7Cases?.Count != 4) return null;
            var evidencePath = Path.Combine(directory, "repair-l9-evidence.json");
            if (!File.Exists(evidencePath) || new FileInfo(evidencePath).Length > 1048576
                || JsonNode.Parse(File.ReadAllText(evidencePath))?.ToJsonString() != evidence.ToJsonString()
                || !Artifact("repair-l9-evidence.json", ScientificArtifactFiles.Hash(evidencePath))) return null;
            var expectedCases = new[] { ("triangle", "cgal.fill-one-hole"), ("square", "cgal.fill-quad-hole"),
                ("two-squares", "cgal.fill-two-quad-holes"), ("pentagon", "cgal.fill-bounded-holes") };
            for (var i = 0; i < 4; i++)
            {
                var (id, recipe) = expectedCases[i];
                if (cases[i] is not JsonObject item || item["caseId"]?.GetValue<string>() != id
                    || item["recipeId"]?.GetValue<string>() != recipe
                    || item["inputSha256"]?.GetValue<string>() != inputs[i]?["sha256"]?.GetValue<string>()
                    || item["outputSha256"]?.GetValue<string>() != l7Cases[i]?["artifactSha256"]?.GetValue<string>()
                    || item["artifactHashes"] is not JsonObject hashes
                    || hashes.Count != ScientificRepairProductContract.Artifacts.Length) return null;
                var relative = "cases/" + id + "/";
                var caseDirectory = Path.Combine(directory, "cases", id);
                var output = Path.Combine(caseDirectory, "repaired.obj");
                var request = Path.Combine(caseDirectory, "request.json");
                var childResult = Path.Combine(caseDirectory, "results.json");
                if (!File.Exists(output) || !File.Exists(request) || !File.Exists(childResult)
                    || ScientificArtifactFiles.Hash(output) != item["outputSha256"]?.GetValue<string>()
                    || !Artifact(relative + "repaired.obj", item["outputSha256"]?.GetValue<string>())
                    || ScientificArtifactFiles.Hash(request) != item["requestSha256"]?.GetValue<string>()
                    || ScientificArtifactFiles.Hash(childResult) != item["resultSha256"]?.GetValue<string>()) return null;
                var child = JsonNode.Parse(File.ReadAllText(childResult));
                var childRequest = JsonNode.Parse(File.ReadAllText(request));
                var childRunId = child?["runId"]?.GetValue<string>();
                if (childRunId is not { Length: 32 }
                    || child?["state"]?.GetValue<string>() != "succeeded"
                    || child?["recipeId"]?.GetValue<string>() != recipe
                    || childRequest?["runId"]?.GetValue<string>() != childRunId
                    || child?["repairAudit"]?["patchSha256"]?.GetValue<string>() != item["repairAudit"]?.GetValue<string>()
                    || child?["artifacts"]?[0]?["sha256"]?.GetValue<string>() != item["outputSha256"]?.GetValue<string>()) return null;
                foreach (var name in ScientificRepairProductContract.Artifacts)
                {
                    var path = Path.Combine(caseDirectory, name.Replace('/', Path.DirectorySeparatorChar));
                    var hash = hashes[name]?.GetValue<string>();
                    if (hash is not { Length: 64 } || !File.Exists(path)
                        || new FileInfo(path).Length > 8388608
                        || ScientificArtifactFiles.Hash(path) != hash || !Artifact(relative + name, hash)) return null;
                }
                var handoff = item["handoff"] as JsonObject;
                var product = item["product"] as JsonObject;
                var roundtrip = item["roundtrip"] as JsonObject;
                var viewer = item["viewer"] as JsonObject;
                if (handoff == null || product == null || roundtrip == null || viewer == null
                    || JsonNode.Parse(File.ReadAllText(Path.Combine(caseDirectory, "handoff.json")))?.ToJsonString() != handoff.ToJsonString()
                    || JsonNode.Parse(File.ReadAllText(Path.Combine(caseDirectory, "product", "product.json")))?.ToJsonString() != product.ToJsonString()
                    || JsonNode.Parse(File.ReadAllText(Path.Combine(caseDirectory, "product", "roundtrip.json")))?.ToJsonString() != roundtrip.ToJsonString()
                    || JsonNode.Parse(File.ReadAllText(Path.Combine(caseDirectory, "product", "viewer.json")))?.ToJsonString() != viewer.ToJsonString()
                    || handoff["verdict"]?.GetValue<string>() != "passed"
                    || handoff["runId"]?.GetValue<string>() != childRunId
                    || handoff["requestSha256"]?.GetValue<string>() != item["requestSha256"]?.GetValue<string>()
                    || handoff["resultSha256"]?.GetValue<string>() != item["resultSha256"]?.GetValue<string>()
                    || handoff["outputSha256"]?.GetValue<string>() != item["outputSha256"]?.GetValue<string>()
                    || handoff["repairAudit"]?["patchSha256"]?.GetValue<string>() != item["repairAudit"]?.GetValue<string>()
                    || handoff["consumerResultSha256"]?.GetValue<string>() != hashes["math3d-consumed.json"]?.GetValue<string>()
                    || product["verdict"]?.GetValue<string>() != "passed"
                    || product["runId"]?.GetValue<string>() != childRunId
                    || product["sourceObjSha256"]?.GetValue<string>() != item["outputSha256"]?.GetValue<string>()
                    || product["sourceResultSha256"]?.GetValue<string>() != item["resultSha256"]?.GetValue<string>()
                    || product["handoffSha256"]?.GetValue<string>() != hashes["handoff.json"]?.GetValue<string>()
                    || product["documentSha256"]?.GetValue<string>() != hashes["product/repair-mesh-document.json"]?.GetValue<string>()
                    || product["resourceSha256"]?.GetValue<string>() != hashes["product/repair-mesh-resource.bin"]?.GetValue<string>()
                    || product["m3dmSha256"]?.GetValue<string>() != hashes["product/repaired.m3dm"]?.GetValue<string>()
                    || roundtrip["verdict"]?.GetValue<string>() != "passed"
                    || roundtrip["runId"]?.GetValue<string>() != childRunId
                    || roundtrip["sourceObjSha256"]?.GetValue<string>() != item["outputSha256"]?.GetValue<string>()
                    || roundtrip["m3dmSha256"]?.GetValue<string>() != product["m3dmSha256"]?.GetValue<string>()
                    || roundtrip["productSha256"]?.GetValue<string>() != hashes["product/product.json"]?.GetValue<string>()
                    || roundtrip["source"]?["points"]?.GetValue<int>() != roundtrip["reloaded"]?["points"]?.GetValue<int>()
                    || roundtrip["source"]?["triangles"]?.GetValue<int>() != roundtrip["reloaded"]?["triangles"]?.GetValue<int>()
                    || viewer["verdict"]?.GetValue<string>() != "passed"
                    || viewer["viewerState"]?.GetValue<string>() != "mounted"
                    || viewer["blueMeshPixels"]?.GetValue<int>() is not > 1000
                    || viewer["runId"]?.GetValue<string>() != childRunId
                    || viewer["m3dmSha256"]?.GetValue<string>() != product["m3dmSha256"]?.GetValue<string>()
                    || viewer["roundtripSha256"]?.GetValue<string>() != hashes["product/roundtrip.json"]?.GetValue<string>()
                    || viewer["screenshotSha256"]?.GetValue<string>() != hashes["product/viewer.png"]?.GetValue<string>()
                    || product["consumerSources"] is not JsonObject caseSources) return null;
                foreach (var name in ScientificRepairProductContract.ConsumerSources[..^1])
                    if (caseSources[name]?.GetValue<string>() != sources[name]?.GetValue<string>()) return null;
                if (viewer["viewerSourceSha256"]?.GetValue<string>()
                    != sources[ScientificRepairProductContract.ConsumerSources[^1]]?.GetValue<string>()) return null;
            }
            var negative = evidence["negative"] as JsonObject;
            var negativeDirectory = Path.Combine(directory, "negative");
            var tampered = Path.Combine(negativeDirectory, "repaired.m3dm");
            var original = Path.Combine(directory, "cases", "pentagon", "product", "repaired.m3dm");
            var rejection = Path.Combine(negativeDirectory, "rejection.json");
            if (negative?["state"]?.GetValue<string>() != "rejected"
                || negative["sourceCaseId"]?.GetValue<string>() != "pentagon"
                || negative["mutation"]?.GetValue<string>() != "last-byte-xor-1"
                || negative["outputAbsent"]?.GetValue<bool>() != true
                || negative["exitCode"]?.GetValue<int>() is not > 0
                || !File.Exists(tampered) || !File.Exists(original) || !File.Exists(rejection)
                || File.Exists(Path.Combine(negativeDirectory, "roundtrip.json"))
                || ScientificArtifactFiles.Hash(original) != negative["sourceM3dmSha256"]?.GetValue<string>()
                || ScientificArtifactFiles.Hash(tampered) != negative["tamperedM3dmSha256"]?.GetValue<string>()
                || ScientificArtifactFiles.Hash(rejection) != evidence["negativeSha256"]?.GetValue<string>()
                || !Artifact("negative/repaired.m3dm", negative["tamperedM3dmSha256"]?.GetValue<string>())
                || !Artifact("negative/rejection.json", evidence["negativeSha256"]?.GetValue<string>())
                || JsonNode.Parse(File.ReadAllText(rejection))?.ToJsonString() != negative.ToJsonString()) return null;
            var originalBytes = File.ReadAllBytes(original);
            var tamperedBytes = File.ReadAllBytes(tampered);
            if (originalBytes.Length < 33 || originalBytes.Length != tamperedBytes.Length
                || !originalBytes.AsSpan(..^1).SequenceEqual(tamperedBytes.AsSpan(..^1))
                || (originalBytes[^1] ^ tamperedBytes[^1]) != 1) return null;
            return Digest(evidence.ToJsonString());
        }
        catch (Exception error) when (error is IOException or InvalidOperationException or ArgumentException
            or JsonException or UnauthorizedAccessException or KeyNotFoundException)
        { return null; }
    }
}
