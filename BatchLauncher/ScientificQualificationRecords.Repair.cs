using System.Text.Json.Nodes;

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
}
