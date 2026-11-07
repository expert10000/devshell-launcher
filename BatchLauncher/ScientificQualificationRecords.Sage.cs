using System.Security.Cryptography;
using System.Text.Json.Nodes;

namespace BatchLauncher;

public static partial class ScientificQualificationRecords
{
    private static readonly (string Id, string Capability, string Operation, string Expected)[] SageExactCases =
    {
        ("rational-positive", "math.rational.add", "rational.add", "succeeded"),
        ("rational-rejection", "math.rational.add", "rational.add", "zero-denominator"),
        ("polynomial-positive", "math.polynomial.factor", "polynomial.factor", "succeeded"),
        ("polynomial-rejection", "math.polynomial.factor", "polynomial.factor", "invalid-exact-value"),
        ("matrix-positive", "math.matrix.solve", "matrix.solve", "succeeded"),
        ("matrix-rejection", "math.matrix.solve", "matrix.solve", "singular-matrix"),
        ("field-positive", "math.number-field.quadratic", "number-field.quadratic.inspect", "succeeded"),
        ("field-rejection", "math.number-field.quadratic", "number-field.quadratic.inspect", "non-squarefree-field"),
        ("prime-rejection", "math.number-field.quadratic", "number-field.quadratic.inspect", "invalid-prime")
    };

    private static string SageFileHash(string path) =>
        Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();

    private static bool SageExactPositive(string id, JsonNode? value)
    {
        if (value is not JsonObject) return false;
        if (id == "rational-positive")
            return value["sum"]?["numerator"]?.GetValue<string>() == "1"
                && value["sum"]?["denominator"]?.GetValue<string>() == "2";
        if (id == "polynomial-positive")
            return value["verified"]?.GetValue<bool>() == true
                && value["factors"] is JsonArray factors && factors.Count == 2;
        if (id == "matrix-positive")
            return value["verified"]?.GetValue<bool>() == true
                && value["solution"] is JsonArray solution && solution.Count == 2
                && solution[0]?["numerator"]?.GetValue<string>() == "2"
                && solution[1]?["numerator"]?.GetValue<string>() == "1"
                && solution.All(item => item?["denominator"]?.GetValue<string>() == "1");
        return id == "field-positive" && value["verified"]?.GetValue<bool>() == true
            && value["radicand"]?.GetValue<string>() == "2"
            && value["degree"]?.GetValue<int>() == 2
            && value["discriminant"]?.GetValue<string>() == "8"
            && value["galoisOrder"]?.GetValue<int>() == 2
            && value["splitting"] is JsonArray splitting && splitting.Count == 3
            && splitting[0]?["prime"]?.GetValue<string>() == "2"
            && splitting[1]?["prime"]?.GetValue<string>() == "3"
            && splitting[2]?["prime"]?.GetValue<string>() == "7"
            && splitting[0]?["factors"] is JsonArray ramified && ramified.Count == 1
            && splitting[1]?["factors"] is JsonArray inert && inert.Count == 1
            && splitting[2]?["factors"] is JsonArray split && split.Count == 2;
    }

    private static string? SageExactHash(string directory, JsonObject result, string capabilityId)
    {
        try
        {
            if (!SageExactCases.Any(item => item.Capability == capabilityId)
                || result["runtimeId"]?.GetValue<string>() != "sage-wsl"
                || result["recipeId"]?.GetValue<string>() != "sage.qualify-exact"
                || result["state"]?.GetValue<string>() != "succeeded"
                || result["sageExactEvidence"] is not JsonObject evidence
                || evidence["suiteId"]?.GetValue<string>() != "sage-exact-qualification-v1"
                || evidence["fixtureRevision"]?.GetValue<int>() != 1
                || evidence["verdict"]?.GetValue<string>() != "passed"
                || evidence["cases"] is not JsonArray cases || cases.Count != SageExactCases.Length
                || evidence["workerSha256"]?.GetValue<string>() is not { Length: 64 } workerHash
                || result["versions"]?["sage"]?.GetValue<string>() is not { Length: > 0 }
                || result["validatedCapabilities"] is not JsonArray capabilities
                || !SageExactCases.Select(item => item.Capability).Distinct(StringComparer.Ordinal)
                    .All(capability => capabilities.Any(item => item?.GetValue<string>() == capability))) return null;
            for (var index = 0; index < SageExactCases.Length; index++)
            {
                var (id, capability, operation, expected) = SageExactCases[index];
                if (cases[index] is not JsonObject entry) return null;
                if (entry["caseId"]?.GetValue<string>() != id
                    || entry["capabilityId"]?.GetValue<string>() != capability
                    || entry["operation"]?.GetValue<string>() != operation
                    || entry["expected"]?.GetValue<string>() != expected
                    || entry["state"]?.GetValue<string>() != (expected == "succeeded" ? "succeeded" : "failed")
                    || entry["workerSha256"]?.GetValue<string>() != workerHash
                    || entry["requestPath"]?.GetValue<string>() != $"cases/{id}/worker-request.json"
                    || entry["resultPath"]?.GetValue<string>() != $"cases/{id}/results.json") return null;
                var requestPath = Path.Combine(directory, "cases", id, "worker-request.json");
                var resultPath = Path.Combine(directory, "cases", id, "results.json");
                if (!File.Exists(requestPath) || !File.Exists(resultPath)
                    || new FileInfo(requestPath).Length > 65536 || new FileInfo(resultPath).Length > 262144
                    || SageFileHash(requestPath) != entry["requestSha256"]?.GetValue<string>()
                    || SageFileHash(resultPath) != entry["resultSha256"]?.GetValue<string>()) return null;
                if (JsonNode.Parse(File.ReadAllText(requestPath)) is not JsonObject request
                    || JsonNode.Parse(File.ReadAllText(resultPath)) is not JsonObject child) return null;
                if (request["runtimeId"]?.GetValue<string>() != "sage-wsl"
                    || request["recipeId"]?.GetValue<string>() != "sage.exact.v1"
                    || request["operation"]?.GetValue<string>() != operation
                    || child["runId"]?.GetValue<string>() != request["runId"]?.GetValue<string>()
                    || child["operation"]?.GetValue<string>() != operation
                    || child["state"]?.GetValue<string>() != entry["state"]?.GetValue<string>()
                    || child["provenance"]?["requestSha256"]?.GetValue<string>() != entry["requestSha256"]?.GetValue<string>()
                    || child["provenance"]?["workerSha256"]?.GetValue<string>() != workerHash
                    || child["artifacts"] is not JsonArray artifacts || artifacts.Count != 0) return null;
                if (expected == "succeeded")
                {
                    if (child["exitCode"]?.GetValue<int>() != 0 || !SageExactPositive(id, child["result"])) return null;
                }
                else if (child["result"] != null || child["exitCode"]?.GetValue<int>() != 2
                    || child["diagnostics"] is not JsonArray diagnostics || diagnostics.Count != 1
                    || diagnostics[0]?["code"]?.GetValue<string>() != expected) return null;
            }
            return Digest(evidence.ToJsonString() + "|" + capabilityId);
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException or InvalidOperationException
            or ArgumentException or System.Text.Json.JsonException)
        {
            return null;
        }
    }
}
