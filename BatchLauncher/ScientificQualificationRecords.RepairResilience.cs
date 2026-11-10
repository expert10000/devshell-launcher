using System.Text.Json;
using System.Text.Json.Nodes;

namespace BatchLauncher;

public static partial class ScientificQualificationRecords
{
    public static bool ValidRepairRepeat(JsonObject expected, JsonObject actual, string inputSha256, string readerSha256) =>
        inputSha256.Length == 64 && readerSha256.Length == 64
        && actual["consumer"]?.GetValue<string>() == "VTK vtkOBJReader"
        && actual["inputObjSha256"]?.GetValue<string>() == inputSha256
        && actual["readerSourceSha256"]?.GetValue<string>() == readerSha256
        && actual.ToJsonString() == expected.ToJsonString();

    private static string? RepairL8Hash(string directory, JsonObject result, JsonObject components)
    {
        try
        {
            if (result["runtimeId"]?.GetValue<string>() != "cgal-win-conda"
                || result["recipeId"]?.GetValue<string>() != "l8.cgal-repair"
                || result["state"]?.GetValue<string>() != "succeeded"
                || result["repairResilienceEvidence"] is not JsonObject evidence
                || evidence["suiteId"]?.GetValue<string>() != "cgal-repair-resilience-v1"
                || evidence["capabilityId"]?.GetValue<string>() != "mesh.repair"
                || evidence["lowerQualification"]?["records"] is not JsonArray lower || lower.Count != 8
                || evidence["observations"] is not JsonObject observations
                || observations["repeats"] is not JsonArray repeats || repeats.Count != 12
                || observations["repeatCount"]?.GetValue<int>() != 3
                || observations["repeatLimitSeconds"]?.GetValue<int>() != 60
                || observations["memoryLimitBytes"]?.GetValue<long>() != 134217728
                || result["inputArtifacts"] is not JsonArray inputs || inputs.Count != 4
                || result["artifacts"] is not JsonArray artifacts
                || result["validatedCapabilities"] is not JsonArray validated
                || !validated.Any(item => item?.GetValue<string>() == "mesh.repair")) return null;
            for (var i = 0; i < 8; i++)
                if (lower[i]?["level"]?.GetValue<string>() != "L" + i
                    || lower[i]?["runId"]?.GetValue<string>() is not { Length: 32 }
                    || lower[i]?["recordId"]?.GetValue<string>() is not { Length: 64 }) return null;
            var folder = evidence["sourceL7FolderId"]?.GetValue<string>();
            var runId = evidence["sourceL7RunId"]?.GetValue<string>();
            var recordId = evidence["sourceL7RecordId"]?.GetValue<string>();
            if (folder is not { Length: 32 } || !folder.All(Uri.IsHexDigit)
                || runId is not { Length: 32 } || !runId.All(Uri.IsHexDigit)
                || recordId is not { Length: 64 } || !recordId.All(Uri.IsHexDigit)
                || lower[7]?["runId"]?.GetValue<string>() != runId
                || lower[7]?["recordId"]?.GetValue<string>() != recordId
                || lower[7]?["capabilityId"]?.GetValue<string>() != "mesh.repair") return null;
            var sourceDirectory = Path.Combine(Path.GetDirectoryName(directory)!, folder);
            var sourcePath = Path.Combine(sourceDirectory, "results.json");
            if (!File.Exists(sourcePath) || new FileInfo(sourcePath).Length > 1048576) return null;
            using var sourceDocument = JsonDocument.Parse(File.ReadAllText(sourcePath));
            var saved = sourceDocument.RootElement;
            if (saved.GetProperty("runId").GetString() != runId
                || saved.GetProperty("profileId").GetString() != result["profileId"]?.GetValue<string>()
                || saved.GetProperty("runtimeId").GetString() != "cgal-win-conda"
                || saved.GetProperty("recipeId").GetString() != "l7.cgal-repair"
                || saved.GetProperty("state").GetString() != "succeeded"
                || !Verify(sourceDirectory, saved).OfType<JsonObject>().Any(item =>
                    item["recordId"]?.GetValue<string>() == recordId
                    && item["capabilityId"]?.GetValue<string>() == "mesh.repair"
                    && item["level"]?.GetValue<string>() == "L7")) return null;
            var l7 = JsonNode.Parse(saved.GetRawText())?["repairInteropEvidence"];
            if (l7?["cases"] is not JsonArray sourceCases || sourceCases.Count != 4
                || l7["lowerQualification"]?["records"] is not JsonArray sourceLower || sourceLower.Count != 7
                || l7["consumerContractSha256"]?.GetValue<string>() != evidence["sourceL7ContractSha256"]?.GetValue<string>()
                || l7["source"]?["runId"]?.GetValue<string>() != evidence["sourceL6RunId"]?.GetValue<string>()
                || evidence["vtkReaderSha256"]?.GetValue<string>() != components["suite"]?["files"]?["tools/scientific-vtk-interop.py"]?["sha256"]?.GetValue<string>()
                || evidence["vtkPythonSha256"]?.GetValue<string>() is not { Length: 64 }) return null;
            for (var i = 0; i < 7; i++)
                if (lower[i]?.ToJsonString() != sourceLower[i]?.ToJsonString()) return null;
            var evidenceFile = Path.Combine(directory, "repair-l8-evidence.json");
            var root = Path.Combine(directory, "resilience");
            var observationsFile = Path.Combine(root, "observations.json");
            if (!File.Exists(evidenceFile) || new FileInfo(evidenceFile).Length > 524288
                || JsonNode.Parse(File.ReadAllText(evidenceFile))?.ToJsonString() != evidence.ToJsonString()
                || !Artifact("repair-l8-evidence.json", ScientificArtifactFiles.Hash(evidenceFile))
                || !File.Exists(observationsFile) || new FileInfo(observationsFile).Length > 524288
                || ScientificArtifactFiles.Hash(observationsFile) != evidence["observationsSha256"]?.GetValue<string>()
                || JsonNode.Parse(File.ReadAllText(observationsFile))?.ToJsonString() != observations.ToJsonString()
                || !Artifact("resilience/observations.json", evidence["observationsSha256"]?.GetValue<string>())) return null;
            bool Artifact(string path, string? hash) => hash is { Length: 64 }
                && artifacts.Any(item => item?["path"]?.GetValue<string>() == path
                    && item?["sha256"]?.GetValue<string>() == hash);
            for (var caseIndex = 0; caseIndex < 4; caseIndex++)
            {
                var expected = RepairProofCases[caseIndex];
                var sourceCase = sourceCases[caseIndex];
                var hash = sourceCase?["artifactSha256"]?.GetValue<string>();
                if (sourceCase?["caseId"]?.GetValue<string>() != expected.Id
                    || hash is not { Length: 64 }
                    || inputs[caseIndex]?["sha256"]?.GetValue<string>() != hash
                    || inputs[caseIndex]?["sourceRunId"]?.GetValue<string>() != evidence["sourceL6RunId"]?.GetValue<string>())
                    return null;
                string? commonHash = null;
                for (var repeatIndex = 1; repeatIndex <= 3; repeatIndex++)
                {
                    var repeat = repeats[caseIndex * 3 + repeatIndex - 1];
                    var relative = $"resilience/{expected.Id}/repeat-{repeatIndex}.json";
                    var path = Path.Combine(root, expected.Id, $"repeat-{repeatIndex}.json");
                    var reportHash = repeat?["resultSha256"]?.GetValue<string>();
                    if (!File.Exists(path) || new FileInfo(path).Length > 65536
                        || repeat?["caseId"]?.GetValue<string>() != expected.Id
                        || repeat["repeat"]?.GetValue<int>() != repeatIndex
                        || repeat["inputSha256"]?.GetValue<string>() != hash
                        || ScientificArtifactFiles.Hash(path) != reportHash
                        || !Artifact(relative, reportHash)
                        || JsonNode.Parse(File.ReadAllText(path))?.ToJsonString() != repeat["result"]?.ToJsonString()
                        || repeat["result"] is not JsonObject report
                        || sourceCase["vtkConsumer"] is not JsonObject expectedReport
                        || !ValidRepairRepeat(expectedReport, report, hash,
                            evidence["vtkReaderSha256"]?.GetValue<string>() ?? "")
                        || repeat["durationMs"]?.GetValue<long>() is not > 0 and < 60000
                        || repeat["peakProcessMemoryBytes"]?.GetValue<long>() is not > 0 and <= 134217728)
                        return null;
                    if (commonHash != null && reportHash != commonHash) return null;
                    commonHash = reportHash;
                }
            }
            if (observations["cancellation"]?["state"]?.GetValue<string>() != "cancelled"
                || observations["cancellation"]?["outputAbsent"]?.GetValue<bool>() != true
                || observations["cancellation"]?["durationMs"]?.GetValue<long>() is not > 0 and < 5000
                || observations["timeout"]?["state"]?.GetValue<string>() != "timed-out"
                || observations["timeout"]?["outputAbsent"]?.GetValue<bool>() != true
                || observations["timeout"]?["limitSeconds"]?.GetValue<int>() != 1
                || observations["timeout"]?["durationMs"]?.GetValue<long>() is not > 0 and < 5000
                || observations["memory"]?["state"]?.GetValue<string>() != "limited"
                || observations["memory"]?["limitBytes"]?.GetValue<long>() != 134217728
                || observations["memory"]?["requestedBytes"]?.GetValue<long>() != 536870912
                || observations["memory"]?["exitCode"]?.GetValue<int>() != 42
                || observations["memory"]?["outputAbsent"]?.GetValue<bool>() != true
                || File.Exists(Path.Combine(root, "cancelled-output.txt"))
                || File.Exists(Path.Combine(root, "timeout-output.txt"))
                || File.Exists(Path.Combine(root, "memory-output.txt"))) return null;
            return Digest(evidence.ToJsonString());
        }
        catch (Exception error) when (error is IOException or InvalidOperationException or ArgumentException
            or JsonException or UnauthorizedAccessException or KeyNotFoundException)
        {
            return null;
        }
    }
}
