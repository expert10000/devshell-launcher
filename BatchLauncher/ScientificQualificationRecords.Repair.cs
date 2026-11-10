using System.Text.Json.Nodes;
using System.Text.Json;

namespace BatchLauncher;

public static partial class ScientificQualificationRecords
{
    private sealed record RepairProofCase(string Id, string Fixture, string Recipe, bool Positive,
        int Loops, int Edges, int Patches, string? Reason);

    private static readonly RepairProofCase[] RepairProofCases =
    [
        new("triangle", "triangle", "cgal.fill-one-hole", true, 1, 3, 1, null),
        new("square", "square", "cgal.fill-quad-hole", true, 1, 4, 2, null),
        new("two-squares", "two-squares", "cgal.fill-two-quad-holes", true, 2, 8, 4, null),
        new("pentagon", "pentagon", "cgal.fill-bounded-holes", true, 1, 5, 3, null),
        new("closed-rejection", "closed-rejection", "cgal.fill-bounded-holes", false, 0, 0, 0, "Bounded repair requires"),
        new("wrong-operation", "triangle", "cgal.fill-quad-hole", false, 1, 3, 0, "selected boundary-loop scope")
    ];

    private static string? RepairL5Hash(string directory, JsonObject result, JsonObject components)
    {
        try
        {
            if (result["runtimeId"]?.GetValue<string>() != "cgal-win-conda"
                || result["recipeId"]?.GetValue<string>() != "l5.cgal-repair"
                || result["state"]?.GetValue<string>() != "succeeded"
                || result["repairQualificationEvidence"] is not JsonObject evidence
                || evidence["suiteId"]?.GetValue<string>() != ScientificRepairFixtures.SuiteId
                || evidence["fixtureSuite"]?.GetValue<string>() != ScientificRepairFixtures.SuiteId
                || evidence["capabilityId"]?.GetValue<string>() != "mesh.repair"
                || result["validatedCapabilities"] is not JsonArray validated
                || !validated.Any(item => item?.GetValue<string>() == "mesh.repair")
                || result["inputArtifacts"] is not JsonArray parentInputs || parentInputs.Count != 5
                || result["artifacts"] is not JsonArray parentArtifacts
                || evidence["cases"] is not JsonArray cases || cases.Count != RepairProofCases.Length
                || evidence["lowerQualification"]?["records"] is not JsonArray lower || lower.Count != 5)
                return null;
            for (var i = 0; i < 5; i++)
            {
                if (lower[i]?["level"]?.GetValue<string>() != "L" + i
                    || lower[i]?["runId"]?.GetValue<string>() is not { Length: 32 }
                    || lower[i]?["recordId"]?.GetValue<string>() is not { Length: 64 }) return null;
            }
            var manifestPath = Path.Combine(directory, "fixture-manifest.json");
            var evidencePath = Path.Combine(directory, "repair-l5-evidence.json");
            if (!File.Exists(manifestPath) || !File.Exists(evidencePath)
                || new FileInfo(manifestPath).Length > 65536 || new FileInfo(evidencePath).Length > 262144
                || ScientificArtifactFiles.Hash(manifestPath) != evidence["fixtureManifestSha256"]?.GetValue<string>()
                || components["suite"]?["files"]?[ScientificRepairFixtures.ManifestPath]?["sha256"]?.GetValue<string>()
                    != evidence["fixtureManifestSha256"]?.GetValue<string>()
                || JsonNode.Parse(File.ReadAllText(evidencePath))?.ToJsonString() != evidence.ToJsonString()
                || !parentArtifacts.Any(item => item?["path"]?.GetValue<string>() == "fixture-manifest.json"
                    && item?["sha256"]?.GetValue<string>() == ScientificArtifactFiles.Hash(manifestPath))
                || !parentArtifacts.Any(item => item?["path"]?.GetValue<string>() == "repair-l5-evidence.json"
                    && item?["sha256"]?.GetValue<string>() == ScientificArtifactFiles.Hash(evidencePath))) return null;
            var manifest = JsonNode.Parse(File.ReadAllText(manifestPath));
            var fixtures = manifest?["fixtures"]?.AsArray().OfType<JsonObject>()
                .ToDictionary(item => item["caseId"]!.GetValue<string>(), StringComparer.Ordinal);
            if (manifest?["suiteId"]?.GetValue<string>() != ScientificRepairFixtures.SuiteId
                || fixtures?.Count != 5 || manifest["license"]?.GetValue<string>() != "CC0-1.0") return null;
            for (var i = 0; i < RepairProofCases.Length; i++)
            {
                var expected = RepairProofCases[i];
                if (cases[i] is not JsonObject entry || !fixtures.TryGetValue(expected.Fixture, out var fixture)
                    || entry["caseId"]?.GetValue<string>() != expected.Id
                    || entry["recipeId"]?.GetValue<string>() != expected.Recipe
                    || entry["inputSha256"]?.GetValue<string>() != fixture["sha256"]?.GetValue<string>()
                    || entry["requestSha256"]?.GetValue<string>() is not { Length: 64 }
                    || entry["resultSha256"]?.GetValue<string>() is not { Length: 64 }) return null;
                var inputHash = entry["inputSha256"]?.GetValue<string>();
                var datasetId = entry["datasetId"]?.GetValue<string>();
                if (!parentInputs.Any(item => item?["datasetId"]?.GetValue<string>() == datasetId
                    && item?["sha256"]?.GetValue<string>() == inputHash)) return null;
                var child = Path.Combine(directory, "cases", expected.Id);
                var requestPath = Path.Combine(child, "request.json");
                var resultPath = Path.Combine(child, "results.json");
                if (!File.Exists(requestPath) || !File.Exists(resultPath)
                    || new FileInfo(requestPath).Length > 65536 || new FileInfo(resultPath).Length > 1048576
                    || ScientificArtifactFiles.Hash(requestPath) != entry["requestSha256"]?.GetValue<string>()
                    || ScientificArtifactFiles.Hash(resultPath) != entry["resultSha256"]?.GetValue<string>()) return null;
                var request = JsonNode.Parse(File.ReadAllText(requestPath));
                var childResult = JsonNode.Parse(File.ReadAllText(resultPath));
                if (request?["recipeId"]?.GetValue<string>() != expected.Recipe
                    || request["runtimeId"]?.GetValue<string>() != "cgal-win-conda"
                    || request["inputArtifacts"]?[0]?["datasetId"]?.GetValue<string>() != datasetId
                    || request["inputArtifacts"]?[0]?["sha256"]?.GetValue<string>() != inputHash
                    || request["outputArtifacts"]?[0]?["path"]?.GetValue<string>() != "repaired.obj"
                    || childResult?["recipeId"]?.GetValue<string>() != expected.Recipe
                    || childResult["runId"]?.GetValue<string>() != request["runId"]?.GetValue<string>()) return null;
                var output = Path.Combine(child, "repaired.obj");
                if (expected.Positive)
                {
                    var hash = entry["artifactSha256"]?.GetValue<string>();
                    if (entry["state"]?.GetValue<string>() != "succeeded" || hash is not { Length: 64 }
                        || entry["artifactPath"]?.GetValue<string>() != $"cases/{expected.Id}/repaired.obj"
                        || !File.Exists(output) || ScientificArtifactFiles.Hash(output) != hash
                        || childResult["state"]?.GetValue<string>() != "succeeded"
                        || childResult["validatedCapabilities"] is not JsonArray capabilities
                        || !capabilities.Any(item => item?.GetValue<string>() == "mesh.repair")
                        || childResult["repairEvidence"]?["holesFilled"]?.GetValue<int>() != expected.Loops
                        || childResult["repairEvidence"]?["boundaryEdgesBefore"]?.GetValue<int>() != expected.Edges
                        || childResult["repairAudit"]?["addedFaces"]?.GetValue<int>() != expected.Patches
                        || childResult["repairAudit"]?["boundaryEdgesCovered"]?.GetValue<int>() != expected.Edges
                        || childResult["repairAudit"]?["patchSha256"]?.GetValue<string>() != entry["patchSha256"]?.GetValue<string>()
                        || childResult["artifacts"] is not JsonArray artifacts
                        || !artifacts.Any(item => item?["path"]?.GetValue<string>() == "repaired.obj"
                            && item?["sha256"]?.GetValue<string>() == hash)
                        || !parentArtifacts.Any(item => item?["path"]?.GetValue<string>() == $"cases/{expected.Id}/repaired.obj"
                            && item?["sha256"]?.GetValue<string>() == hash)) return null;
                }
                else
                {
                    var diagnostic = string.Join("; ", childResult["diagnostics"]?.AsArray().OfType<JsonObject>()
                        .Select(item => item["message"]?.GetValue<string>()) ?? Array.Empty<string?>());
                    if (entry["state"]?.GetValue<string>() != "failed"
                        || childResult["state"]?.GetValue<string>() != "failed"
                        || childResult["validatedCapabilities"]?.AsArray().Count != 0
                        || entry["outputAbsent"]?.GetValue<bool>() != true
                        || entry["expectedReason"]?.GetValue<string>() != expected.Reason
                        || File.Exists(output) || !diagnostic.Contains(expected.Reason!, StringComparison.OrdinalIgnoreCase)) return null;
                }
            }
            return Digest(evidence.ToJsonString());
        }
        catch (Exception error) when (error is IOException or InvalidOperationException or ArgumentException
            or System.Text.Json.JsonException or UnauthorizedAccessException or KeyNotFoundException)
        {
            return null;
        }
    }

    private static string? RepairL6Hash(string directory, JsonObject result, JsonObject components)
    {
        try
        {
            if (result["runtimeId"]?.GetValue<string>() != "cgal-win-conda"
                || result["recipeId"]?.GetValue<string>() != "l6.cgal-repair"
                || result["state"]?.GetValue<string>() != "succeeded"
                || result["repairReproductionEvidence"] is not JsonObject evidence
                || result["repairQualificationEvidence"] is not JsonObject candidate
                || evidence["suiteId"]?.GetValue<string>() != "cgal-repair-reproduce-v1"
                || evidence["capabilityId"]?.GetValue<string>() != "mesh.repair"
                || evidence["comparison"]?.GetValue<string>() != "sha256-exact"
                || evidence["verdict"]?.GetValue<string>() != "matched"
                || evidence["cases"]?.ToJsonString() != candidate["cases"]?.ToJsonString()
                || evidence["lowerQualification"]?["records"] is not JsonArray lower || lower.Count != 6
                || candidate["lowerQualification"]?["records"] is not JsonArray candidateLower || candidateLower.Count != 5)
                return null;
            for (var i = 0; i < 5; i++)
                if (lower[i]?.ToJsonString() != candidateLower[i]?.ToJsonString()) return null;
            var candidateAsL5 = (JsonObject)result.DeepClone();
            candidateAsL5["recipeId"] = "l5.cgal-repair";
            var candidateHash = RepairL5Hash(directory, candidateAsL5, components);
            if (candidateHash == null || candidateHash != evidence["candidateL5EvidenceSha256"]?.GetValue<string>())
                return null;
            var evidencePath = Path.Combine(directory, "repair-l6-evidence.json");
            if (!File.Exists(evidencePath) || new FileInfo(evidencePath).Length > 262144
                || JsonNode.Parse(File.ReadAllText(evidencePath))?.ToJsonString() != evidence.ToJsonString()
                || result["artifacts"] is not JsonArray artifacts
                || !artifacts.Any(item => item?["path"]?.GetValue<string>() == "repair-l6-evidence.json"
                    && item?["sha256"]?.GetValue<string>() == ScientificArtifactFiles.Hash(evidencePath))) return null;
            if (evidence["baseline"] is not JsonObject baseline) return null;
            var folder = baseline["folderId"]?.GetValue<string>();
            var runId = baseline["runId"]?.GetValue<string>();
            var recordId = baseline["recordId"]?.GetValue<string>();
            if (folder is not { Length: 32 } || !folder.All(Uri.IsHexDigit)
                || runId is not { Length: 32 } || !runId.All(Uri.IsHexDigit)
                || recordId is not { Length: 64 } || !recordId.All(Uri.IsHexDigit)
                || lower[5]?["runId"]?.GetValue<string>() != runId
                || lower[5]?["recordId"]?.GetValue<string>() != recordId
                || lower[5]?["capabilityId"]?.GetValue<string>() != "mesh.repair"
                || lower[5]?["level"]?.GetValue<string>() != "L5") return null;
            var baselineDirectory = Path.Combine(Path.GetDirectoryName(directory)!, folder);
            var baselinePath = Path.Combine(baselineDirectory, "results.json");
            if (!File.Exists(baselinePath) || new FileInfo(baselinePath).Length > 1048576) return null;
            using var baselineDocument = JsonDocument.Parse(File.ReadAllText(baselinePath));
            var saved = baselineDocument.RootElement;
            if (saved.GetProperty("runId").GetString() != runId
                || saved.GetProperty("profileId").GetString() != result["profileId"]?.GetValue<string>()
                || saved.GetProperty("runtimeId").GetString() != "cgal-win-conda"
                || saved.GetProperty("recipeId").GetString() != "l5.cgal-repair"
                || saved.GetProperty("state").GetString() != "succeeded"
                || saved.GetProperty("runFingerprintSha256").GetString() != baseline["runFingerprintSha256"]?.GetValue<string>()
                || !Verify(baselineDirectory, saved).OfType<JsonObject>().Any(item =>
                    item["recordId"]?.GetValue<string>() == recordId
                    && item["capabilityId"]?.GetValue<string>() == "mesh.repair"
                    && item["level"]?.GetValue<string>() == "L5")) return null;
            var reference = JsonNode.Parse(saved.GetRawText())?["repairQualificationEvidence"];
            if (reference is not JsonObject
                || reference["fixtureManifestSha256"]?.GetValue<string>() != candidate["fixtureManifestSha256"]?.GetValue<string>()
                || reference["cases"] is not JsonArray baselineCases || baselineCases.Count != 6
                || evidence["cases"] is not JsonArray candidateCases || candidateCases.Count != 6
                || Digest(baselineCases.ToJsonString()) != baseline["casesSha256"]?.GetValue<string>()) return null;
            for (var i = 0; i < 6; i++)
            {
                var first = baselineCases[i]; var second = candidateCases[i];
                if (first?["caseId"]?.GetValue<string>() != second?["caseId"]?.GetValue<string>()
                    || first?["recipeId"]?.GetValue<string>() != second?["recipeId"]?.GetValue<string>()
                    || first?["inputSha256"]?.GetValue<string>() != second?["inputSha256"]?.GetValue<string>()
                    || first?["state"]?.GetValue<string>() != second?["state"]?.GetValue<string>()
                    || first?["artifactSha256"]?.GetValue<string>() != second?["artifactSha256"]?.GetValue<string>()
                    || first?["patchSha256"]?.GetValue<string>() != second?["patchSha256"]?.GetValue<string>()
                    || first?["outputAbsent"]?.ToJsonString() != second?["outputAbsent"]?.ToJsonString()) return null;
            }
            return Digest(evidence.ToJsonString());
        }
        catch (Exception error) when (error is IOException or InvalidOperationException or ArgumentException
            or JsonException or UnauthorizedAccessException or KeyNotFoundException)
        {
            return null;
        }
    }
}
