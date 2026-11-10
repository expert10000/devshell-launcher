using System.Text.Json.Nodes;
using System.Text.Json;

namespace BatchLauncher;

public static partial class ScientificQualificationRecords
{
    // The older CGAL interoperability check deliberately fixes a four-point tetrahedron.
    // Repair outputs have different topology, so compare each consumer with its own
    // independently parsed OBJ and keep the malformed-input rejection in scope.
    public static bool ValidRepairInteropSemantics(JsonObject source, JsonObject vtk, JsonObject math3d,
        JsonObject rejection, string malformedSha256, string vtkReaderSha256, string importerSha256)
    {
        var points = source["points"]?.GetValue<int>() ?? 0;
        var triangles = source["triangles"]?.GetValue<int>() ?? 0;
        var hash = source["artifactSha256"]?.GetValue<string>();
        if (source["format"]?.GetValue<string>() != "obj" || points < 4 || triangles < 4
            || hash is not { Length: 64 } || source["closed"]?.GetValue<bool>() != true
            || source["boundaryEdges"]?.GetValue<int>() != 0
            || source["nonManifoldEdges"]?.GetValue<int>() != 0
            || source["bounds"] is not JsonArray bounds || bounds.Count != 6
            || rejection["state"]?.GetValue<string>() != "rejected"
            || rejection["inputObjSha256"]?.GetValue<string>() != malformedSha256
            || rejection["readerSourceSha256"]?.GetValue<string>() != vtkReaderSha256
            || rejection["reason"]?.GetValue<string>()?.Contains("invalid face indices", StringComparison.Ordinal) != true)
            return false;
        var sourceVolume = source["signedVolume"]?.GetValue<double>() ?? double.NaN;
        var sourceArea = source["surfaceArea"]?.GetValue<double>() ?? double.NaN;
        if (!double.IsFinite(sourceVolume) || sourceVolume <= 0
            || !double.IsFinite(sourceArea) || sourceArea <= 0) return false;
        foreach (var (consumer, name, sourceField, expectedSource) in new[] {
            (vtk, "VTK vtkOBJReader", "readerSourceSha256", vtkReaderSha256),
            (math3d, "MATH3D desktop loadSurfaceMeshFromFile", "importerSourceSha256", importerSha256) })
        {
            if (consumer["consumer"]?.GetValue<string>() != name
                || consumer[sourceField]?.GetValue<string>() != expectedSource
                || consumer["inputObjSha256"]?.GetValue<string>() != hash
                || consumer["points"]?.GetValue<int>() != points
                || consumer["triangles"]?.GetValue<int>() != triangles
                || consumer["boundaryEdges"]?.GetValue<int>() != 0
                || consumer["nonManifoldEdges"]?.GetValue<int>() != 0
                || consumer["closed"]?.GetValue<bool>() != true
                || consumer["bounds"] is not JsonArray comparedBounds || comparedBounds.Count != 6)
                return false;
            for (var i = 0; i < 6; i++)
            {
                var expected = bounds[i]?.GetValue<double>() ?? double.NaN;
                var actual = comparedBounds[i]?.GetValue<double>() ?? double.NaN;
                if (!double.IsFinite(expected) || !double.IsFinite(actual)
                    || Math.Abs(expected - actual) > 1e-6) return false;
            }
            foreach (var (field, expected) in new[] { ("signedVolume", sourceVolume), ("surfaceArea", sourceArea) })
            {
                var actual = consumer[field]?.GetValue<double>() ?? double.NaN;
                if (!double.IsFinite(actual) || Math.Abs(actual - expected) > 1e-6) return false;
            }
        }
        return true;
    }

    private static string? RepairL7Hash(string directory, JsonObject result, JsonObject components)
    {
        try
        {
            if (result["runtimeId"]?.GetValue<string>() != "cgal-win-conda"
                || result["recipeId"]?.GetValue<string>() != "l7.cgal-repair"
                || result["state"]?.GetValue<string>() != "succeeded"
                || result["repairInteropEvidence"] is not JsonObject evidence
                || evidence["suiteId"]?.GetValue<string>() != "cgal-repair-interop-v1"
                || evidence["capabilityId"]?.GetValue<string>() != "mesh.repair"
                || result["validatedCapabilities"] is not JsonArray validated
                || !validated.Any(item => item?.GetValue<string>() == "mesh.repair")
                || evidence["source"] is not JsonObject source
                || evidence["cases"] is not JsonArray cases || cases.Count != 4
                || evidence["consumerContract"] is not JsonObject contract
                || evidence["lowerQualification"]?["records"] is not JsonArray lower || lower.Count != 7
                || result["inputArtifacts"] is not JsonArray inputs || inputs.Count != 4
                || result["artifacts"] is not JsonArray artifacts) return null;
            for (var i = 0; i < 7; i++)
                if (lower[i]?["level"]?.GetValue<string>() != "L" + i
                    || lower[i]?["runId"]?.GetValue<string>() is not { Length: 32 }
                    || lower[i]?["recordId"]?.GetValue<string>() is not { Length: 64 }) return null;
            var folder = source["folderId"]?.GetValue<string>();
            var runId = source["runId"]?.GetValue<string>();
            var recordId = source["recordId"]?.GetValue<string>();
            if (folder is not { Length: 32 } || !folder.All(Uri.IsHexDigit)
                || runId is not { Length: 32 } || !runId.All(Uri.IsHexDigit)
                || recordId is not { Length: 64 } || !recordId.All(Uri.IsHexDigit)
                || lower[6]?["runId"]?.GetValue<string>() != runId
                || lower[6]?["recordId"]?.GetValue<string>() != recordId
                || lower[6]?["capabilityId"]?.GetValue<string>() != "mesh.repair") return null;
            var sourceDirectory = Path.Combine(Path.GetDirectoryName(directory)!, folder);
            var sourcePath = Path.Combine(sourceDirectory, "results.json");
            if (!File.Exists(sourcePath) || new FileInfo(sourcePath).Length > 1048576) return null;
            using var sourceDocument = JsonDocument.Parse(File.ReadAllText(sourcePath));
            var saved = sourceDocument.RootElement;
            if (saved.GetProperty("runId").GetString() != runId
                || saved.GetProperty("profileId").GetString() != result["profileId"]?.GetValue<string>()
                || saved.GetProperty("runtimeId").GetString() != "cgal-win-conda"
                || saved.GetProperty("recipeId").GetString() != "l6.cgal-repair"
                || saved.GetProperty("state").GetString() != "succeeded"
                || saved.GetProperty("runFingerprintSha256").GetString() != source["runFingerprintSha256"]?.GetValue<string>()
                || !Verify(sourceDirectory, saved).OfType<JsonObject>().Any(item =>
                    item["recordId"]?.GetValue<string>() == recordId
                    && item["capabilityId"]?.GetValue<string>() == "mesh.repair"
                    && item["level"]?.GetValue<string>() == "L6")) return null;
            var savedEvidence = JsonNode.Parse(saved.GetRawText())?["repairReproductionEvidence"];
            if (savedEvidence?["lowerQualification"]?["records"] is not JsonArray sourceLower || sourceLower.Count != 6
                || savedEvidence["cases"] is not JsonArray sourceCases || sourceCases.Count != 6) return null;
            for (var i = 0; i < 6; i++)
                if (lower[i]?.ToJsonString() != sourceLower[i]?.ToJsonString()) return null;
            var evidenceFile = Path.Combine(directory, "repair-l7-evidence.json");
            var malformed = Path.Combine(directory, "handoff", "malformed.obj");
            var rejectionFile = Path.Combine(directory, "handoff", "rejection.json");
            if (!File.Exists(evidenceFile) || new FileInfo(evidenceFile).Length > 262144
                || JsonNode.Parse(File.ReadAllText(evidenceFile))?.ToJsonString() != evidence.ToJsonString()
                || !Artifact("repair-l7-evidence.json", ScientificArtifactFiles.Hash(evidenceFile))
                || !File.Exists(malformed) || File.ReadAllText(malformed) != "v 0 0 0\nf 1 2 3\n"
                || ScientificArtifactFiles.Hash(malformed) != evidence["malformedSha256"]?.GetValue<string>()
                || !Artifact("handoff/malformed.obj", evidence["malformedSha256"]?.GetValue<string>())
                || !File.Exists(rejectionFile) || new FileInfo(rejectionFile).Length > 65536
                || ScientificArtifactFiles.Hash(rejectionFile) != evidence["rejectionSha256"]?.GetValue<string>()
                || !Artifact("handoff/rejection.json", evidence["rejectionSha256"]?.GetValue<string>())
                || JsonNode.Parse(File.ReadAllText(rejectionFile))?.ToJsonString() != evidence["rejection"]?.ToJsonString())
                return null;
            if (contract["schemaVersion"]?.GetValue<int>() != 1
                || contract["format"]?.GetValue<string>() != "obj"
                || contract["comparisonTolerance"]?.GetValue<double>() != 1e-6
                || contract["vtkReaderSourceSha256"]?.GetValue<string>() != components["suite"]?["files"]?["tools/scientific-vtk-interop.py"]?["sha256"]?.GetValue<string>()
                || contract["reloadParserSha256"]?.GetValue<string>() != components["suite"]?["files"]?["tools/scientific-artifact-roundtrip.py"]?["sha256"]?.GetValue<string>()
                || contract["math3dHarnessSha256"]?.GetValue<string>() != components["suite"]?["files"]?["tools/math3d-vtk-import-handoff.mjs"]?["sha256"]?.GetValue<string>()
                || contract["math3dImporterSourceSha256"]?.GetValue<string>() is not { Length: 64 }
                || contract["vtkPythonSha256"]?.GetValue<string>() is not { Length: 64 }
                || contract["vtkEnvironmentSha256"]?.GetValue<string>() is not { Length: 64 }
                || Digest(contract.ToJsonString()) != evidence["consumerContractSha256"]?.GetValue<string>()) return null;
            bool Artifact(string path, string? hash) => hash is { Length: 64 }
                && artifacts.Any(item => item?["path"]?.GetValue<string>() == path
                    && item?["sha256"]?.GetValue<string>() == hash);
            for (var i = 0; i < 4; i++)
            {
                if (cases[i] is not JsonObject entry) return null;
                var expected = RepairProofCases[i];
                var relative = $"cases/{expected.Id}/repaired.obj";
                var sourceCase = sourceCases[i];
                var hash = entry["artifactSha256"]?.GetValue<string>();
                var sourceArtifact = Path.Combine(sourceDirectory, "cases", expected.Id, "repaired.obj");
                if (entry["caseId"]?.GetValue<string>() != expected.Id
                    || entry["artifactPath"]?.GetValue<string>() != relative
                    || sourceCase?["caseId"]?.GetValue<string>() != expected.Id
                    || sourceCase["artifactSha256"]?.GetValue<string>() != hash
                    || hash is not { Length: 64 } || !File.Exists(sourceArtifact)
                    || ScientificArtifactFiles.Hash(sourceArtifact) != hash
                    || inputs[i]?["sha256"]?.GetValue<string>() != hash
                    || inputs[i]?["sourceRunId"]?.GetValue<string>() != runId) return null;
                foreach (var (file, field, digestField) in new[] {
                    ("source-reload.json", "sourceReload", "sourceReloadSha256"),
                    ("vtk-consumed.json", "vtkConsumer", "vtkConsumerSha256"),
                    ("math3d-consumed.json", "math3dConsumer", "math3dConsumerSha256") })
                {
                    var relativeFile = $"handoff/{expected.Id}/{file}";
                    var path = Path.Combine(directory, "handoff", expected.Id, file);
                    if (!File.Exists(path) || new FileInfo(path).Length > 65536
                        || ScientificArtifactFiles.Hash(path) != entry[digestField]?.GetValue<string>()
                        || JsonNode.Parse(File.ReadAllText(path))?.ToJsonString() != entry[field]?.ToJsonString()
                        || !Artifact(relativeFile, entry[digestField]?.GetValue<string>())) return null;
                }
                if (entry["sourceReload"] is not JsonObject reload
                    || entry["vtkConsumer"] is not JsonObject vtk
                    || entry["math3dConsumer"] is not JsonObject math3d
                    || evidence["rejection"] is not JsonObject rejection
                    || reload["artifactSha256"]?.GetValue<string>() != hash
                    || reload["parserSourceSha256"]?.GetValue<string>() != contract["reloadParserSha256"]?.GetValue<string>()
                    || !ValidRepairInteropSemantics(reload, vtk, math3d, rejection,
                        evidence["malformedSha256"]?.GetValue<string>() ?? "",
                        contract["vtkReaderSourceSha256"]?.GetValue<string>() ?? "",
                        contract["math3dImporterSourceSha256"]?.GetValue<string>() ?? "")) return null;
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
