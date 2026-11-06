using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace BatchLauncher;

// Qualification records describe only named evidence that passed in this run.
// The file is written once; History derives current status without changing it.
public static partial class ScientificQualificationRecords
{
    private static string Digest(string value) => Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(value))).ToLowerInvariant();

    private static JsonObject? Manifest(string runtimeId, string sourceRoot, string installedRoot, string? expectedHash)
    {
        var installed = Path.Combine(installedRoot, "runtimes", runtimeId, "runtime.json");
        var path = File.Exists(installed) ? installed : Path.Combine(sourceRoot, "runtimes", runtimeId, "runtime.json");
        if (!File.Exists(path) || new FileInfo(path).Length > 1048576) return null;
        var actual = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();
        if (!string.Equals(actual, expectedHash, StringComparison.OrdinalIgnoreCase)) return null;
        return JsonNode.Parse(File.ReadAllText(path)) as JsonObject;
    }

    private static JsonObject Record(string runId, string runtimeId, string capabilityId, string level,
        string evidenceId, string fingerprintSha256, string suiteRevisionSha256, JsonObject contract,
        string? evidenceSha256 = null, JsonNode? lowerQualification = null, string? consumerSourceSha256 = null,
        string? consumerContractSha256 = null, string? consumerEnvironmentSha256 = null,
        string? consumerCodecSha256 = null)
    {
        var record = new JsonObject
        {
            ["schemaVersion"] = 1, ["runId"] = runId, ["runtimeId"] = runtimeId,
            ["capabilityId"] = capabilityId, ["level"] = level, ["evidenceId"] = evidenceId,
            ["runFingerprintSha256"] = fingerprintSha256, ["suiteRevisionSha256"] = suiteRevisionSha256,
            ["contract"] = contract.DeepClone()
        };
        if (evidenceSha256 != null) record["evidenceSha256"] = evidenceSha256;
        if (lowerQualification != null) record["lowerQualification"] = lowerQualification.DeepClone();
        if (consumerSourceSha256 != null) record["consumerSourceSha256"] = consumerSourceSha256;
        if (consumerContractSha256 != null) record["consumerContractSha256"] = consumerContractSha256;
        if (consumerEnvironmentSha256 != null) record["consumerEnvironmentSha256"] = consumerEnvironmentSha256;
        if (consumerCodecSha256 != null) record["consumerCodecSha256"] = consumerCodecSha256;
        record["recordId"] = Digest(record.ToJsonString());
        return record;
    }

    private static string[] Arguments(JsonNode? step) => step?["arguments"] is JsonArray values
        ? values.Select(item => item?.GetValue<string>() ?? "").ToArray() : Array.Empty<string>();

    private static bool HasArgument(string[] arguments, string option, string value)
    {
        for (var index = 0; index < arguments.Length - 1; index++)
            if (arguments[index] == option && string.Equals(arguments[index + 1], value, StringComparison.OrdinalIgnoreCase))
                return true;
        return false;
    }

    private static string? CompileLinkHash(string directory, string sourceRoot, string runtimeId,
        JsonObject result, JsonObject components)
    {
        if (runtimeId is not ("cgal-win-conda" or "vtk-win-conda" or "gmsh-win-conda")
            || result["steps"] is not JsonArray steps || steps.Count != 2
            || result["compileLink"] is not JsonObject buildEvidence
            || components["worker"]?["executedFiles"] is not JsonArray executed
            || components["environment"]?["toolchain"]?["cmake"]?["state"]?.GetValue<string>() != "recorded"
            || components["environment"]?["toolchain"]?["msvcCompiler"]?["state"]?.GetValue<string>() != "recorded"
            || string.IsNullOrWhiteSpace(result["versions"]?["msvc"]?.GetValue<string>())) return null;
        var kind = runtimeId.StartsWith("cgal", StringComparison.Ordinal) ? "cgal"
            : runtimeId.StartsWith("gmsh", StringComparison.Ordinal) ? "gmsh" : "vtk";
        var build = Path.Combine(directory, "build");
        var source = Path.Combine(sourceRoot, "scientific", "smoke", kind);
        var configure = steps[0]; var compile = steps[1];
        var configureArguments = Arguments(configure); var compileArguments = Arguments(compile);
        if (configure?["stage"]?.GetValue<string>() != "configure" || compile?["stage"]?.GetValue<string>() != "build"
            || configure["exitCode"]?.GetValue<int>() != 0 || compile["exitCode"]?.GetValue<int>() != 0
            || !HasArgument(configureArguments, "-S", source) || !HasArgument(configureArguments, "-B", build)
            || !HasArgument(compileArguments, "--build", build) || !HasArgument(compileArguments, "--config", "Release")) return null;
        var cmake = components["environment"]?["toolchain"]?["cmake"]?["sha256"]?.GetValue<string>();
        if (!string.Equals(configure["executable"]?.GetValue<string>(), compile["executable"]?.GetValue<string>(), StringComparison.OrdinalIgnoreCase)
            || !string.Equals(Path.GetFileName(configure["executable"]?.GetValue<string>()), "cmake.exe", StringComparison.OrdinalIgnoreCase)
            || !executed.Any(item => item?["role"]?.GetValue<string>() == "executable"
                && item?["name"]?.GetValue<string>() == "cmake.exe" && item?["sha256"]?.GetValue<string>() == cmake)) return null;
        var binaryName = "devshell_" + kind + "_smoke.exe";
        var hash = buildEvidence["sha256"]?.GetValue<string>();
        var binary = Path.Combine(build, "Release", binaryName);
        if (buildEvidence["binaryName"]?.GetValue<string>() != binaryName || hash?.Length != 64 || !File.Exists(binary)) return null;
        var actual = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(binary))).ToLowerInvariant();
        return string.Equals(actual, hash, StringComparison.OrdinalIgnoreCase)
            && executed.Any(item => item?["role"]?.GetValue<string>() == "linked-binary"
                && item?["name"]?.GetValue<string>() == binaryName
                && string.Equals(item?["sha256"]?.GetValue<string>(), hash, StringComparison.OrdinalIgnoreCase))
            ? hash : null;
    }

    private static string? L5Hash(string directory, string runtimeId, JsonObject result, JsonObject components)
    {
        var (capability, recipe, positiveId, negativeId, positiveName, negativeName, reason) = runtimeId switch
        {
            "cgal-win-conda" => ("mesh.validate", "cgal.validate", "math3d/basic/01_tetrahedron.obj", "math3d/problematic/18_degenerate_faces.obj", "l5-positive.obj", "l5-rejected.obj", "not a readable manifold polygon mesh"),
            "vtk-win-conda" => ("mesh.read", "mesh.inspect", "math3d/basic/01_tetrahedron.obj", "math3d/import/truncated-ascii.ply", "l5-positive.vtp", "l5-rejected.vtp", "surface is empty"),
            "gmsh-win-conda" => ("mesh.generate", "gmsh.mesh2d", "gmsh/fixed-square.geo", "gmsh/tampered-square.geo", "l5-positive.msh", "l5-rejected.msh", "Only the registered fixed square GEO fixture is accepted"),
            _ => ("", "", "", "", "", "", "")
        };
        if (capability.Length == 0 || result["recipeId"]?.GetValue<string>() != "l5.worker"
            || result["l5Evidence"] is not JsonObject evidence || evidence["suiteId"]?.GetValue<string>() != "l5-worker-v1"
            || evidence["capabilityId"]?.GetValue<string>() != capability
            || evidence["workerContractVersion"]?.GetValue<int>() != 1
            || evidence["workerContractSha256"]?.GetValue<string>() != components["contract"]?["workerContractModule"]?["sha256"]?.GetValue<string>()
            || evidence["fixtureManifestSha256"]?.GetValue<string>() is not { Length: 64 }
            || evidence["lowerQualification"]?["records"] is not JsonArray lower || lower.Count != 5
            || result["validatedCapabilities"] is not JsonArray validated || !validated.Any(item => item?.GetValue<string>() == capability)) return null;
        var required = new[] { "L0", "L1", "L2", "L3", "L4" };
        for (var i = 0; i < 5; i++)
            if (lower[i]?["level"]?.GetValue<string>() != required[i]
                || lower[i]?["runId"]?.GetValue<string>() is not { Length: 32 }
                || lower[i]?["recordId"]?.GetValue<string>() is not { Length: 64 }) return null;
        var cases = new[] { ("positive", positiveId, positiveName, "succeeded"),
            ("rejection", negativeId, negativeName, "failed") };
        foreach (var (folder, datasetId, outputName, state) in cases)
        {
            if (evidence[folder] is not JsonObject entry || entry["caseId"]?.GetValue<string>() != folder
                || entry["recipeId"]?.GetValue<string>() != recipe || entry["datasetId"]?.GetValue<string>() != datasetId
                || entry["state"]?.GetValue<string>() != state) return null;
            var childDirectory = Path.Combine(directory, folder);
            var requestPath = Path.Combine(childDirectory, "request.json");
            var resultPath = Path.Combine(childDirectory, "results.json");
            if (!File.Exists(requestPath) || !File.Exists(resultPath)
                || new FileInfo(requestPath).Length > 1048576 || new FileInfo(resultPath).Length > 1048576
                || Digest(File.ReadAllText(requestPath)) != entry["requestSha256"]?.GetValue<string>()
                || Digest(File.ReadAllText(resultPath)) != entry["resultSha256"]?.GetValue<string>()) return null;
            var childRequest = JsonNode.Parse(File.ReadAllText(requestPath));
            var childResult = JsonNode.Parse(File.ReadAllText(resultPath));
            if (childRequest?["recipeId"]?.GetValue<string>() != recipe
                || childRequest["runtimeId"]?.GetValue<string>() != runtimeId
                || childRequest["inputArtifacts"] is not JsonArray inputs || inputs.Count != 1
                || inputs[0]?["datasetId"]?.GetValue<string>() != datasetId
                || inputs[0]?["sha256"]?.GetValue<string>() != entry["inputSha256"]?.GetValue<string>()
                || childRequest["outputArtifacts"] is not JsonArray outputs || outputs.Count != 1
                || outputs[0]?["path"]?.GetValue<string>() != outputName
                || childResult?["state"]?.GetValue<string>() != state
                || result["inputArtifacts"] is not JsonArray parentInputs
                || !parentInputs.Any(item => item?["datasetId"]?.GetValue<string>() == datasetId
                    && item?["sha256"]?.GetValue<string>() == entry["inputSha256"]?.GetValue<string>())) return null;
            var outputPath = Path.Combine(childDirectory, outputName);
            if (folder == "positive")
            {
                var hash = entry["artifactSha256"]?.GetValue<string>();
                if (entry["artifactPath"]?.GetValue<string>() != folder + "/" + outputName
                    || hash is not { Length: 64 } || !File.Exists(outputPath)
                    || Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(outputPath))).ToLowerInvariant() != hash
                    || childResult["validatedCapabilities"] is not JsonArray childCapabilities
                    || !childCapabilities.Any(item => item?.GetValue<string>() == capability)
                    || result["artifacts"] is not JsonArray artifacts
                    || !artifacts.Any(item => item?["path"]?.GetValue<string>() == folder + "/" + outputName
                        && item?["sha256"]?.GetValue<string>() == hash)) return null;
            }
            else if (File.Exists(outputPath) || entry["outputAbsent"]?.GetValue<bool>() != true
                || entry["expectedReason"]?.GetValue<string>() != reason
                || !string.Join("; ", childResult["diagnostics"]?.AsArray().OfType<JsonObject>()
                    .Select(item => item["message"]?.GetValue<string>()) ?? Array.Empty<string?>())
                    .Contains(reason, StringComparison.OrdinalIgnoreCase)) return null;
        }
        return Digest(evidence.ToJsonString());
    }

    private static string? L6Hash(string directory, string runtimeId, JsonObject result, JsonObject components)
    {
        if (result["recipeId"]?.GetValue<string>() != "l6.reproduce"
            || result["l6Evidence"] is not JsonObject evidence
            || evidence["suiteId"]?.GetValue<string>() != "l6-reproduce-v1"
            || evidence["comparison"]?.GetValue<string>() != "sha256-exact"
            || evidence["verdict"]?.GetValue<string>() != "matched"
            || evidence["baseline"] is not JsonObject baseline
            || result["l5Evidence"] is not JsonObject candidate
            || evidence["capabilityId"]?.GetValue<string>() != candidate["capabilityId"]?.GetValue<string>()
            || evidence["positive"]?.ToJsonString() != candidate["positive"]?.ToJsonString()
            || evidence["rejection"]?.ToJsonString() != candidate["rejection"]?.ToJsonString()
            || evidence["roundTrip"] is not JsonObject roundTrip
            || evidence["roundTripResultSha256"]?.GetValue<string>() is not { Length: 64 } reloadHash
            || evidence["lowerQualification"]?["records"] is not JsonArray lower || lower.Count != 6
            || candidate["lowerQualification"]?["records"] is not JsonArray l5Lower || l5Lower.Count != 5)
            return null;
        var reloadPath = Path.Combine(directory, "reload", "results.json");
        if (!File.Exists(reloadPath) || new FileInfo(reloadPath).Length > 65536
            || Digest(File.ReadAllText(reloadPath)) != reloadHash
            || JsonNode.Parse(File.ReadAllText(reloadPath))?.ToJsonString() != roundTrip.ToJsonString()
            || !ValidRoundTrip(roundTrip, runtimeId, candidate["positive"]?["artifactSha256"]?.GetValue<string>(),
                components["suite"]?["files"]?[runtimeId == "gmsh-win-conda"
                    ? "tools/scientific-gmsh-roundtrip.py" : "tools/scientific-artifact-roundtrip.py"]?["sha256"]?.GetValue<string>())
            || result["artifacts"] is not JsonArray reloadArtifacts
            || !reloadArtifacts.Any(item => item?["path"]?.GetValue<string>() == "reload/results.json"
                && item?["sha256"]?.GetValue<string>() == reloadHash)) return null;
        for (var i = 0; i < 5; i++)
            if (lower[i]?.ToJsonString() != l5Lower[i]?.ToJsonString()) return null;
        var baselineRunId = baseline["runId"]?.GetValue<string>();
        var baselineFolderId = baseline["folderId"]?.GetValue<string>();
        var baselineRecordId = baseline["recordId"]?.GetValue<string>();
        if (baselineRunId is not { Length: 32 } || !baselineRunId.All(Uri.IsHexDigit)
            || baselineFolderId is not { Length: 32 } || !baselineFolderId.All(Uri.IsHexDigit)
            || baselineRecordId is not { Length: 64 } || !baselineRecordId.All(Uri.IsHexDigit)
            || lower[5]?["runId"]?.GetValue<string>() != baselineRunId
            || lower[5]?["recordId"]?.GetValue<string>() != baselineRecordId
            || lower[5]?["level"]?.GetValue<string>() != "L5") return null;
        var candidateAsL5 = (JsonObject)result.DeepClone();
        candidateAsL5["recipeId"] = "l5.worker";
        if (L5Hash(directory, runtimeId, candidateAsL5, components) == null) return null;
        var baselineDirectory = Path.Combine(Path.GetDirectoryName(directory)!, baselineFolderId);
        var baselinePath = Path.Combine(baselineDirectory, "results.json");
        var fingerprintPath = Path.Combine(baselineDirectory, "fingerprint.json");
        if (!File.Exists(baselinePath) || !File.Exists(fingerprintPath)
            || new FileInfo(baselinePath).Length > 1048576 || new FileInfo(fingerprintPath).Length > 1048576) return null;
        using var baselineDocument = JsonDocument.Parse(File.ReadAllText(baselinePath));
        var baselineResult = baselineDocument.RootElement;
        if (baselineResult.GetProperty("runId").GetString() != baselineRunId
            || baselineResult.GetProperty("runtimeId").GetString() != runtimeId
            || baselineResult.GetProperty("profileId").GetString() != result["profileId"]?.GetValue<string>()
            || baselineResult.GetProperty("recipeId").GetString() != "l5.worker"
            || baselineResult.GetProperty("state").GetString() != "succeeded"
            || baselineResult.GetProperty("runFingerprintSha256").GetString() != baseline["runFingerprintSha256"]?.GetValue<string>()) return null;
        ScientificRunFingerprint.Verify(baselineDirectory, baselineResult.GetProperty("runFingerprintSha256").GetString() ?? "");
        if (!Verify(baselineDirectory, baselineResult).OfType<JsonObject>().Any(item => item["recordId"]?.GetValue<string>() == baselineRecordId
            && item["level"]?.GetValue<string>() == "L5" && item["capabilityId"]?.GetValue<string>() == evidence["capabilityId"]?.GetValue<string>())) return null;
        var savedBaseline = JsonNode.Parse(baselineResult.GetRawText())?["l5Evidence"];
        var baselineFingerprint = JsonNode.Parse(File.ReadAllText(fingerprintPath));
        var baselineArtifact = baseline["artifactPath"]?.GetValue<string>();
        if (baselineArtifact is not ("positive/l5-positive.obj" or "positive/l5-positive.vtp" or "positive/l5-positive.msh")) return null;
        var baselineOutput = Path.Combine(baselineDirectory, baselineArtifact.Replace('/', Path.DirectorySeparatorChar));
        if (!File.Exists(baselineOutput)
            || baseline["artifactSha256"]?.GetValue<string>() != savedBaseline?["positive"]?["artifactSha256"]?.GetValue<string>()
            || baseline["artifactSha256"]?.GetValue<string>() != Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(baselineOutput))).ToLowerInvariant()
            || baseline["positiveInputSha256"]?.GetValue<string>() != savedBaseline?["positive"]?["inputSha256"]?.GetValue<string>()
            || baseline["rejectionInputSha256"]?.GetValue<string>() != savedBaseline?["rejection"]?["inputSha256"]?.GetValue<string>()
            || baseline["workerContractSha256"]?.GetValue<string>() != savedBaseline?["workerContractSha256"]?.GetValue<string>()
            || baseline["environmentSha256"]?.GetValue<string>() != Digest(baselineFingerprint?["components"]?["environment"]?.ToJsonString() ?? "null")
            || evidence["environmentSha256"]?.GetValue<string>() != Digest(components["environment"]?.ToJsonString() ?? "null")
            || baseline["environmentSha256"]?.GetValue<string>() != evidence["environmentSha256"]?.GetValue<string>()
            || baseline["artifactSha256"]?.GetValue<string>() != candidate["positive"]?["artifactSha256"]?.GetValue<string>()
            || baseline["artifactPath"]?.GetValue<string>() != candidate["positive"]?["artifactPath"]?.GetValue<string>()
            || baseline["positiveInputSha256"]?.GetValue<string>() != candidate["positive"]?["inputSha256"]?.GetValue<string>()
            || baseline["rejectionInputSha256"]?.GetValue<string>() != candidate["rejection"]?["inputSha256"]?.GetValue<string>()
            || baseline["workerContractSha256"]?.GetValue<string>() != candidate["workerContractSha256"]?.GetValue<string>()) return null;
        return Digest(evidence.ToJsonString());
    }

    public static bool ValidRoundTrip(JsonObject? reload, string runtimeId, string? artifactSha256, string? parserSha256)
    {
        var format = runtimeId == "cgal-win-conda" ? "obj" : runtimeId == "vtk-win-conda" ? "vtp"
            : runtimeId == "gmsh-win-conda" ? "msh" : null;
        if (format == "msh")
        {
            if (artifactSha256 is not { Length: 64 } || parserSha256 is not { Length: 64 }
                || reload?["parserVersion"]?.GetValue<int>() != 1 || reload["format"]?.GetValue<string>() != "msh"
                || reload["artifactSha256"]?.GetValue<string>() != artifactSha256
                || reload["parserSourceSha256"]?.GetValue<string>() != parserSha256
                || reload["points"]?.GetValue<int>() != 44 || reload["triangles"]?.GetValue<int>() != 66
                || reload["boundaryEdges"]?.GetValue<int>() != 20 || reload["nonManifoldEdges"]?.GetValue<int>() != 0
                || Math.Abs((reload["signedAreaXY"]?.GetValue<double>() ?? double.NaN) - 1) > 1e-9
                || reload["bounds"] is not JsonArray square || square.Count != 6) return false;
            var expected = new[] { 0d, 1d, 0d, 1d, 0d, 0d };
            return Enumerable.Range(0, 6).All(index =>
                Math.Abs((square[index]?.GetValue<double>() ?? double.NaN) - expected[index]) <= 1e-9);
        }
        if (format == null || artifactSha256 is not { Length: 64 } || parserSha256 is not { Length: 64 }
            || reload?["parserVersion"]?.GetValue<int>() != 1 || reload["format"]?.GetValue<string>() != format
            || reload["artifactSha256"]?.GetValue<string>() != artifactSha256
            || reload["parserSourceSha256"]?.GetValue<string>() != parserSha256
            || reload["points"]?.GetValue<int>() != 4 || reload["triangles"]?.GetValue<int>() != 4
            || reload["boundaryEdges"]?.GetValue<int>() != 0 || reload["nonManifoldEdges"]?.GetValue<int>() != 0
            || reload["closed"]?.GetValue<bool>() != true || reload["bounds"] is not JsonArray bounds || bounds.Count != 6)
            return false;
        for (var index = 0; index < 6; index++)
            if (!double.IsFinite(bounds[index]?.GetValue<double>() ?? double.NaN)
                || Math.Abs((bounds[index]?.GetValue<double>() ?? double.NaN) - (index % 2 == 0 ? -1 : 1)) > 1e-6)
                return false;
        return Math.Abs((reload["absoluteVolume"]?.GetValue<double>() ?? double.NaN) - 8.0 / 3.0) <= 1e-6;
    }

    public static bool ValidMath3DImport(JsonObject reload, JsonObject consumer)
    {
        if (consumer["consumer"]?.GetValue<string>() != "MATH3D desktop loadSurfaceMeshFromFile"
            || consumer["consumerVersion"]?.GetValue<int>() != 1 || consumer["format"]?.GetValue<string>() != "obj"
            || consumer["indicesInRange"]?.GetValue<bool>() != true
            || consumer["points"]?.GetValue<int>() != reload["points"]?.GetValue<int>()
            || consumer["triangles"]?.GetValue<int>() != reload["triangles"]?.GetValue<int>()
            || consumer["boundaryEdges"]?.GetValue<int>() != reload["boundaryEdges"]?.GetValue<int>()
            || consumer["nonManifoldEdges"]?.GetValue<int>() != reload["nonManifoldEdges"]?.GetValue<int>()
            || consumer["closed"]?.GetValue<bool>() != reload["closed"]?.GetValue<bool>()
            || consumer["bounds"] is not JsonArray bounds || reload["bounds"] is not JsonArray expected || bounds.Count != 6 || expected.Count != 6)
            return false;
        return Enumerable.Range(0, 6).All(index =>
        {
            var actual = bounds[index]?.GetValue<double>() ?? double.NaN;
            var reference = expected[index]?.GetValue<double>() ?? double.NaN;
            return double.IsFinite(actual) && double.IsFinite(reference) && Math.Abs(actual - reference) <= 1e-6;
        });
    }

    public static bool ValidInteropSemantics(JsonObject source, JsonObject vtk, JsonObject math3d,
        JsonObject rejection, string malformedSha256, string vtkReaderSha256, string importerSha256)
    {
        if (source["format"]?.GetValue<string>() != "obj"
            || source["points"]?.GetValue<int>() != 4 || source["triangles"]?.GetValue<int>() != 4
            || source["closed"]?.GetValue<bool>() != true
            || vtk["consumer"]?.GetValue<string>() != "VTK vtkOBJReader"
            || vtk["readerSourceSha256"]?.GetValue<string>() != vtkReaderSha256
            || vtk["inputObjSha256"]?.GetValue<string>() != source["artifactSha256"]?.GetValue<string>()
            || math3d["consumer"]?.GetValue<string>() != "MATH3D desktop loadSurfaceMeshFromFile"
            || math3d["importerSourceSha256"]?.GetValue<string>() != importerSha256
            || math3d["inputObjSha256"]?.GetValue<string>() != source["artifactSha256"]?.GetValue<string>()
            || rejection["state"]?.GetValue<string>() != "rejected"
            || rejection["inputObjSha256"]?.GetValue<string>() != malformedSha256
            || rejection["readerSourceSha256"]?.GetValue<string>() != vtkReaderSha256
            || rejection["reason"]?.GetValue<string>()?.Contains("invalid face indices", StringComparison.Ordinal) != true
            || source["bounds"] is not JsonArray expectedBounds || expectedBounds.Count != 6)
            return false;
        foreach (var consumer in new[] { vtk, math3d })
        {
            if (consumer["points"]?.GetValue<int>() != source["points"]?.GetValue<int>()
                || consumer["triangles"]?.GetValue<int>() != source["triangles"]?.GetValue<int>()
                || consumer["boundaryEdges"]?.GetValue<int>() != 0
                || consumer["nonManifoldEdges"]?.GetValue<int>() != 0
                || consumer["closed"]?.GetValue<bool>() != true
                || consumer["bounds"] is not JsonArray bounds || bounds.Count != 6) return false;
            for (var index = 0; index < 6; index++)
            {
                var expected = expectedBounds[index]?.GetValue<double>() ?? double.NaN;
                var actual = bounds[index]?.GetValue<double>() ?? double.NaN;
                if (!double.IsFinite(expected) || !double.IsFinite(actual) || Math.Abs(actual - expected) > 1e-6)
                    return false;
            }
            foreach (var metric in new[] { "signedVolume", "surfaceArea" })
            {
                var expected = source[metric]?.GetValue<double>() ?? double.NaN;
                var actual = consumer[metric]?.GetValue<double>() ?? double.NaN;
                if (!double.IsFinite(expected) || !double.IsFinite(actual) || expected <= 0
                    || Math.Abs(actual - expected) > 1e-6) return false;
            }
        }
        return true;
    }

    private static string? L7InteropHash(string directory, JsonObject result, JsonObject components)
    {
        if (result["recipeId"]?.GetValue<string>() != "l7.cgal-vtk-math3d"
            || result["runtimeId"]?.GetValue<string>() != "cgal-win-conda"
            || result["l7InteropEvidence"] is not JsonObject evidence
            || evidence["suiteId"]?.GetValue<string>() != "l7-cgal-vtk-math3d-v1"
            || evidence["capabilityId"]?.GetValue<string>() != "mesh.interop.vtk-math3d"
            || evidence["source"] is not JsonObject source
            || evidence["sourceReload"] is not JsonObject reload
            || evidence["vtkConsumer"] is not JsonObject vtk
            || evidence["math3dConsumer"] is not JsonObject math3d
            || evidence["rejection"] is not JsonObject rejection
            || evidence["consumerContract"] is not JsonObject contract
            || evidence["lowerQualification"]?["records"] is not JsonArray lower || lower.Count != 7
            || source["lowerQualification"]?["records"] is not JsonArray sourceLower || sourceLower.Count != 6)
            return null;
        for (var index = 0; index < 6; index++)
            if (lower[index]?.ToJsonString() != sourceLower[index]?.ToJsonString()) return null;
        var folder = source["folderId"]?.GetValue<string>();
        var runId = source["runId"]?.GetValue<string>();
        var recordId = source["recordId"]?.GetValue<string>();
        if (folder is not { Length: 32 } || !folder.All(Uri.IsHexDigit)
            || runId is not { Length: 32 } || !runId.All(Uri.IsHexDigit)
            || recordId is not { Length: 64 } || !recordId.All(Uri.IsHexDigit)
            || lower[6]?["runId"]?.GetValue<string>() != runId
            || lower[6]?["recordId"]?.GetValue<string>() != recordId
            || lower[6]?["level"]?.GetValue<string>() != "L6") return null;
        var sourceDirectory = Path.Combine(Path.GetDirectoryName(directory)!, folder);
        var sourcePath = Path.Combine(sourceDirectory, "results.json");
        if (!File.Exists(sourcePath) || new FileInfo(sourcePath).Length > 1048576) return null;
        using var sourceDocument = JsonDocument.Parse(File.ReadAllText(sourcePath));
        var sourceResult = sourceDocument.RootElement;
        if (sourceResult.GetProperty("runId").GetString() != runId
            || sourceResult.GetProperty("runtimeId").GetString() != "cgal-win-conda"
            || sourceResult.GetProperty("profileId").GetString() != result["profileId"]?.GetValue<string>()
            || sourceResult.GetProperty("recipeId").GetString() != "l6.reproduce"
            || sourceResult.GetProperty("state").GetString() != "succeeded"
            || sourceResult.GetProperty("runFingerprintSha256").GetString() != source["runFingerprintSha256"]?.GetValue<string>()
            || !Verify(sourceDirectory, sourceResult).OfType<JsonObject>().Any(item =>
                item["recordId"]?.GetValue<string>() == recordId && item["level"]?.GetValue<string>() == "L6")) return null;
        var artifact = Path.Combine(sourceDirectory, "positive", "l5-positive.obj");
        if (source["artifactPath"]?.GetValue<string>() != "positive/l5-positive.obj"
            || !File.Exists(artifact) || new FileInfo(artifact).Length > 33554432
            || Digest(File.ReadAllText(artifact)) != source["artifactSha256"]?.GetValue<string>()
            || JsonNode.Parse(sourceResult.GetRawText())?["l6Evidence"]?["roundTrip"]?.ToJsonString()
                != source["roundTrip"]?.ToJsonString()) return null;
        var handoff = Path.Combine(directory, "handoff");
        var files = new[] { ("source-reload.json", "sourceReload", "sourceReloadSha256"),
            ("vtk-consumed.json", "vtkConsumer", "vtkConsumerSha256"),
            ("math3d-consumed.json", "math3dConsumer", "math3dConsumerSha256"),
            ("rejection.json", "rejection", "rejectionSha256") };
        if (files.Any(item => !File.Exists(Path.Combine(handoff, item.Item1))
            || new FileInfo(Path.Combine(handoff, item.Item1)).Length > 65536
            || Digest(File.ReadAllText(Path.Combine(handoff, item.Item1))) != evidence[item.Item3]?.GetValue<string>()
            || JsonNode.Parse(File.ReadAllText(Path.Combine(handoff, item.Item1)))?.ToJsonString()
                != evidence[item.Item2]?.ToJsonString())) return null;
        var malformed = Path.Combine(handoff, "malformed.obj");
        if (!File.Exists(malformed) || new FileInfo(malformed).Length > 1024
            || Digest(File.ReadAllText(malformed)) != evidence["malformedSha256"]?.GetValue<string>()
            || File.ReadAllText(malformed) != "v 0 0 0\nf 1 2 3\n"
            || reload["artifactSha256"]?.GetValue<string>() != source["artifactSha256"]?.GetValue<string>()
            || reload["parserSourceSha256"]?.GetValue<string>() != contract["reloadParserSha256"]?.GetValue<string>()
            || contract["reloadParserSha256"]?.GetValue<string>() != components["suite"]?["files"]?["tools/scientific-artifact-roundtrip.py"]?["sha256"]?.GetValue<string>()
            || contract["vtkReaderSourceSha256"]?.GetValue<string>() != components["suite"]?["files"]?["tools/scientific-vtk-interop.py"]?["sha256"]?.GetValue<string>()
            || contract["math3dHarnessSha256"]?.GetValue<string>() != components["suite"]?["files"]?["tools/math3d-vtk-import-handoff.mjs"]?["sha256"]?.GetValue<string>()
            || contract["math3dImporterSourceSha256"]?.GetValue<string>() != math3d["importerSourceSha256"]?.GetValue<string>()
            || contract["schemaVersion"]?.GetValue<int>() != 1
            || contract["format"]?.GetValue<string>() != "obj"
            || contract["comparisonTolerance"]?.GetValue<double>() != 1e-6
            || contract["vtkVersion"]?.GetValue<string>() != vtk["vtkVersion"]?.GetValue<string>()
            || contract["vtkEnvironmentSha256"]?.GetValue<string>() is not { Length: 64 }
            || contract["vtkPythonSha256"]?.GetValue<string>() is not { Length: 64 }
            || evidence["consumerContractSha256"]?.GetValue<string>() != Digest(contract.ToJsonString())
            || !ValidInteropSemantics(reload, vtk, math3d, rejection,
                evidence["malformedSha256"]?.GetValue<string>() ?? "",
                contract["vtkReaderSourceSha256"]?.GetValue<string>() ?? "",
                contract["math3dImporterSourceSha256"]?.GetValue<string>() ?? "")
            || result["inputArtifacts"] is not JsonArray inputs || inputs.Count != 1
            || inputs[0]?["sha256"]?.GetValue<string>() != source["artifactSha256"]?.GetValue<string>()
            || inputs[0]?["sourceRunId"]?.GetValue<string>() != runId
            || result["artifacts"] is not JsonArray outputs
            || !files.All(item => outputs.Any(output => output?["path"]?.GetValue<string>() == "handoff/" + item.Item1
                && output?["sha256"]?.GetValue<string>() == evidence[item.Item3]?.GetValue<string>()))
            || !outputs.Any(output => output?["path"]?.GetValue<string>() == "handoff/malformed.obj"
                && output?["sha256"]?.GetValue<string>() == evidence["malformedSha256"]?.GetValue<string>())) return null;
        return Digest(evidence.ToJsonString());
    }

    private static string? L9Hash(string directory, JsonObject result, JsonObject components)
    {
        if (result["recipeId"]?.GetValue<string>() != "l9.math3d-product"
            || result["runtimeId"]?.GetValue<string>() != "cgal-win-conda"
            || result["l9Evidence"] is not JsonObject evidence
            || evidence["suiteId"]?.GetValue<string>() != "l9-math3d-product-v1"
            || evidence["capabilityId"]?.GetValue<string>() != "mesh.interop.vtk-math3d"
            || evidence["worker"] is not JsonObject worker
            || evidence["brokerHandoff"] is not JsonObject handoff
            || evidence["productContract"] is not JsonObject contract
            || evidence["regression"] is not JsonObject report
            || evidence["lowerQualification"]?["records"] is not JsonArray lower || lower.Count != 9
            || components["suite"]?["files"]?["tools/math3d-l9-product-handoff.mjs"]?["sha256"] is not JsonNode)
            return null;
        if (contract["id"]?.GetValue<string>() != "math3d.mesh-product-handoff"
            || contract["version"]?.GetValue<int>() != 1
            || contract["workerResultSchemaVersion"]?.GetValue<int>() != 1
            || contract["meshDocumentSchemaVersion"]?.GetValue<int>() != 1
            || contract["inputFormat"]?.GetValue<string>() != "obj"
            || contract["viewer"]?.GetValue<string>() != "MeshDocumentViewport"
            || evidence["productContractSha256"]?.GetValue<string>() != Digest(contract.ToJsonString())) return null;
        var folder = evidence["sourceL8FolderId"]?.GetValue<string>();
        var runId = evidence["sourceL8RunId"]?.GetValue<string>();
        var recordId = evidence["sourceL8RecordId"]?.GetValue<string>();
        if (folder is not { Length: 32 } || !folder.All(Uri.IsHexDigit)
            || runId is not { Length: 32 } || !runId.All(Uri.IsHexDigit)
            || recordId is not { Length: 64 } || !recordId.All(Uri.IsHexDigit)
            || lower[8]?["runId"]?.GetValue<string>() != runId
            || lower[8]?["recordId"]?.GetValue<string>() != recordId
            || lower[8]?["level"]?.GetValue<string>() != "L8") return null;
        var sourceDirectory = Path.Combine(Path.GetDirectoryName(directory)!, folder);
        var sourcePath = Path.Combine(sourceDirectory, "results.json");
        if (!File.Exists(sourcePath) || new FileInfo(sourcePath).Length > 1048576) return null;
        using var sourceDocument = JsonDocument.Parse(File.ReadAllText(sourcePath));
        var sourceResult = sourceDocument.RootElement;
        if (sourceResult.GetProperty("runId").GetString() != runId
            || sourceResult.GetProperty("profileId").GetString() != result["profileId"]?.GetValue<string>()
            || sourceResult.GetProperty("runtimeId").GetString() != "cgal-win-conda"
            || sourceResult.GetProperty("recipeId").GetString() != "l8.resilience"
            || sourceResult.GetProperty("state").GetString() != "succeeded"
            || !Verify(sourceDirectory, sourceResult).OfType<JsonObject>().Any(item =>
                item["recordId"]?.GetValue<string>() == recordId && item["level"]?.GetValue<string>() == "L8")) return null;
        var l8 = JsonNode.Parse(sourceResult.GetRawText())?["l8Evidence"];
        if (l8?["sourceL7ContractSha256"]?.GetValue<string>() != evidence["sourceL8ContractSha256"]?.GetValue<string>()
            || l8?["lowerQualification"]?["records"] is not JsonArray sourceLower || sourceLower.Count != 8)
            return null;
        for (var index = 0; index < 8; index++)
            if (lower[index]?.ToJsonString() != sourceLower[index]?.ToJsonString()) return null;
        var positive = Path.Combine(directory, "positive");
        var workerRequest = Path.Combine(positive, "request.json");
        var workerResult = Path.Combine(positive, "results.json");
        var artifact = Path.Combine(positive, "l5-positive.obj");
        if (!File.Exists(workerRequest) || !File.Exists(workerResult) || !File.Exists(artifact)
            || new FileInfo(workerRequest).Length > 1048576 || new FileInfo(workerResult).Length > 1048576
            || new FileInfo(artifact).Length > 33554432
            || Digest(File.ReadAllText(workerRequest)) != worker["requestSha256"]?.GetValue<string>()
            || Digest(File.ReadAllText(workerResult)) != worker["resultSha256"]?.GetValue<string>()
            || Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(artifact))).ToLowerInvariant()
                != worker["artifactSha256"]?.GetValue<string>()
            || worker["artifactSha256"]?.GetValue<string>() != l8["sourceArtifactSha256"]?.GetValue<string>()
            || worker["state"]?.GetValue<string>() != "succeeded"
            || worker["artifactPath"]?.GetValue<string>() != "positive/l5-positive.obj"
            || handoff["workerRequest"]?["sha256"]?.GetValue<string>() != worker["requestSha256"]?.GetValue<string>()
            || handoff["workerResult"]?["sha256"]?.GetValue<string>() != worker["resultSha256"]?.GetValue<string>()
            || handoff["artifact"]?["sha256"]?.GetValue<string>() != worker["artifactSha256"]?.GetValue<string>()
            || handoff["sourceL8RunId"]?.GetValue<string>() != runId
            || handoff["sourceL8RecordId"]?.GetValue<string>() != recordId
            || handoff["contract"]?.ToJsonString() != contract.ToJsonString()) return null;
        using var childDocument = JsonDocument.Parse(File.ReadAllText(workerResult));
        var child = childDocument.RootElement;
        if (child.GetProperty("state").GetString() != "succeeded"
            || !child.GetProperty("validatedCapabilities").EnumerateArray().Any(item => item.GetString() == "mesh.validate")
            || !child.GetProperty("artifacts").EnumerateArray().Any(item =>
                item.GetProperty("path").GetString() == "l5-positive.obj"
                && item.GetProperty("sha256").GetString() == worker["artifactSha256"]?.GetValue<string>())) return null;
        var handoffPath = Path.Combine(directory, "handoff", "handoff.json");
        if (!File.Exists(handoffPath) || new FileInfo(handoffPath).Length > 65536
            || Digest(File.ReadAllText(handoffPath)) != evidence["brokerHandoffSha256"]?.GetValue<string>()
            || JsonNode.Parse(File.ReadAllText(handoffPath))?.ToJsonString() != handoff.ToJsonString()) return null;
        var product = Path.Combine(directory, "product");
        var outputs = new[] { ("mesh-document.json", "documentSha256"), ("mesh-resource.bin", "resourceSha256"),
            ("viewer.png", "viewerSha256"), ("regression.json", "regressionSha256") };
        if (outputs.Any(item => !File.Exists(Path.Combine(product, item.Item1))
            || new FileInfo(Path.Combine(product, item.Item1)).Length is < 100 or > 8388608
            || Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(Path.Combine(product, item.Item1)))).ToLowerInvariant()
                != evidence[item.Item2]?.GetValue<string>())
            || result["artifacts"] is not JsonArray artifacts
            || !outputs.All(item => artifacts.Any(file => file?["path"]?.GetValue<string>() == "product/" + item.Item1
                && file?["sha256"]?.GetValue<string>() == evidence[item.Item2]?.GetValue<string>()))
            || !artifacts.Any(file => file?["path"]?.GetValue<string>() == "handoff/handoff.json"
                && file?["sha256"]?.GetValue<string>() == evidence["brokerHandoffSha256"]?.GetValue<string>())
            || !artifacts.Any(file => file?["path"]?.GetValue<string>() == "positive/l5-positive.obj"
                && file?["sha256"]?.GetValue<string>() == worker["artifactSha256"]?.GetValue<string>())) return null;
        var savedDocument = JsonNode.Parse(File.ReadAllText(Path.Combine(product, "mesh-document.json")));
        if (savedDocument?["format"]?.GetValue<string>() != "math3d.mesh-document"
            || savedDocument["schemaVersion"]?.GetValue<int>() != 1
            || savedDocument["source"]?["resource"]?["checksum"]?.GetValue<string>() != "sha256:" + evidence["resourceSha256"]?.GetValue<string>()
            || savedDocument["identity"]?["id"]?.GetValue<string>() != report["documentId"]?.GetValue<string>()
            || savedDocument["identity"]?["structuralHash"]?.GetValue<string>() != report["structuralHash"]?.GetValue<string>()
            || report["documentSha256"]?.GetValue<string>() != evidence["documentSha256"]?.GetValue<string>()
            || report["resourceSha256"]?.GetValue<string>() != evidence["resourceSha256"]?.GetValue<string>()
            || report["screenshotSha256"]?.GetValue<string>() != evidence["viewerSha256"]?.GetValue<string>()
            || report["sourceArtifactSha256"]?.GetValue<string>() != worker["artifactSha256"]?.GetValue<string>()
            || report["workerRequestSha256"]?.GetValue<string>() != worker["requestSha256"]?.GetValue<string>()
            || report["workerResultSha256"]?.GetValue<string>() != worker["resultSha256"]?.GetValue<string>()
            || report["contractVersion"]?.GetValue<int>() != 1
            || report["contractSha256"]?.GetValue<string>() != evidence["productContractSha256"]?.GetValue<string>()
            || report["sourceL8RunId"]?.GetValue<string>() != runId
            || report["sourceL8RecordId"]?.GetValue<string>() != recordId
            || report["points"]?.GetValue<int>() != 4 || report["triangles"]?.GetValue<int>() != 4
            || report["viewer"]?.GetValue<string>() != "MeshDocumentViewport"
            || report["viewerState"]?.GetValue<string>() != "mounted"
            || report["regression"]?.GetValue<string>() != "passed"
            || report["blueMeshPixels"]?.GetValue<int>() is not > 1000
            || report["canvasSize"]?["width"]?.GetValue<int>() is not > 100
            || report["canvasSize"]?["height"]?.GetValue<int>() is not > 100
            || report["consumerSources"] is not JsonObject sources
            || Digest(sources.ToJsonString()) != evidence["consumerSourcesSha256"]?.GetValue<string>()
            || JsonNode.Parse(File.ReadAllText(Path.Combine(product, "regression.json")))?.ToJsonString() != report.ToJsonString()
            || result["inputArtifacts"] is not JsonArray inputs || inputs.Count != 1
            || inputs[0]?["sha256"]?.GetValue<string>() != worker["inputSha256"]?.GetValue<string>()) return null;
        var expectedSources = new[] { "renderer/src/mesh/surfaceMesh.ts", "renderer/src/mesh/meshDocumentAdapter.ts",
            "renderer/src/mesh/meshResourceStore.ts", "renderer/src/workspace/MeshDocumentViewport.tsx",
            "renderer/src/components/SurfaceViewer.tsx", "packages/core/src/meshDocument.ts" };
        if (sources.Count != expectedSources.Length || expectedSources.Any(name => sources[name]?.GetValue<string>() is not { Length: 64 })) return null;
        var screenshot = File.ReadAllBytes(Path.Combine(product, "viewer.png"));
        if (screenshot.Length < 8 || !screenshot.AsSpan(0, 8).SequenceEqual(new byte[] { 137, 80, 78, 71, 13, 10, 26, 10 })) return null;
        return Digest(evidence.ToJsonString());
    }

    private static string? L8Hash(string directory, JsonObject result, JsonObject components)
    {
        if (result["recipeId"]?.GetValue<string>() != "l8.resilience"
            || result["runtimeId"]?.GetValue<string>() != "cgal-win-conda"
            || result["l8Evidence"] is not JsonObject evidence
            || evidence["suiteId"]?.GetValue<string>() != "l8-resilience-v1"
            || evidence["capabilityId"]?.GetValue<string>() != "mesh.interop.vtk-math3d"
            || evidence["lowerQualification"]?["records"] is not JsonArray lower || lower.Count != 8
            || evidence["observations"] is not JsonObject observations
            || observations["repeats"] is not JsonArray repeats || repeats.Count != 3
            || observations["repeatCount"]?.GetValue<int>() != 3
            || observations["repeatLimitSeconds"]?.GetValue<int>() != 60
            || observations["memoryLimitBytes"]?.GetValue<long>() != 134217728
            || evidence["vtkReaderSha256"]?.GetValue<string>() != components["suite"]?["files"]?["tools/scientific-vtk-interop.py"]?["sha256"]?.GetValue<string>()) return null;
        var folder = evidence["sourceL7FolderId"]?.GetValue<string>();
        var runId = evidence["sourceL7RunId"]?.GetValue<string>();
        var recordId = evidence["sourceL7RecordId"]?.GetValue<string>();
        if (folder is not { Length: 32 } || !folder.All(Uri.IsHexDigit)
            || runId is not { Length: 32 } || !runId.All(Uri.IsHexDigit)
            || recordId is not { Length: 64 } || !recordId.All(Uri.IsHexDigit)
            || lower[7]?["runId"]?.GetValue<string>() != runId
            || lower[7]?["recordId"]?.GetValue<string>() != recordId
            || lower[7]?["level"]?.GetValue<string>() != "L7") return null;
        var supportDirectory = Path.Combine(Path.GetDirectoryName(directory)!, folder);
        var supportPath = Path.Combine(supportDirectory, "results.json");
        if (!File.Exists(supportPath) || new FileInfo(supportPath).Length > 1048576) return null;
        using var supportDocument = JsonDocument.Parse(File.ReadAllText(supportPath));
        var supportResult = supportDocument.RootElement;
        if (supportResult.GetProperty("runId").GetString() != runId
            || supportResult.GetProperty("profileId").GetString() != result["profileId"]?.GetValue<string>()
            || supportResult.GetProperty("runtimeId").GetString() != "cgal-win-conda"
            || supportResult.GetProperty("recipeId").GetString() != "l7.cgal-vtk-math3d"
            || supportResult.GetProperty("state").GetString() != "succeeded"
            || !Verify(supportDirectory, supportResult).OfType<JsonObject>().Any(item =>
                item["recordId"]?.GetValue<string>() == recordId && item["level"]?.GetValue<string>() == "L7")) return null;
        var l7 = JsonNode.Parse(supportResult.GetRawText())?["l7InteropEvidence"];
        if (l7?["consumerContractSha256"]?.GetValue<string>() != evidence["sourceL7ContractSha256"]?.GetValue<string>()
            || l7?["source"]?["artifactSha256"]?.GetValue<string>() != evidence["sourceArtifactSha256"]?.GetValue<string>()
            || l7?["lowerQualification"]?["records"] is not JsonArray l7Lower || l7Lower.Count != 7) return null;
        for (var index = 0; index < 7; index++)
            if (lower[index]?.ToJsonString() != l7Lower[index]?.ToJsonString()) return null;
        var root = Path.Combine(directory, "resilience");
        var observationsPath = Path.Combine(root, "observations.json");
        if (!File.Exists(observationsPath) || new FileInfo(observationsPath).Length > 262144
            || Digest(File.ReadAllText(observationsPath)) != evidence["observationsSha256"]?.GetValue<string>()
            || JsonNode.Parse(File.ReadAllText(observationsPath))?.ToJsonString() != observations.ToJsonString()
            || result["artifacts"] is not JsonArray artifacts
            || !artifacts.Any(item => item?["path"]?.GetValue<string>() == "resilience/observations.json"
                && item?["sha256"]?.GetValue<string>() == evidence["observationsSha256"]?.GetValue<string>())) return null;
        string? commonHash = null;
        for (var index = 0; index < 3; index++)
        {
            var repeat = repeats[index];
            var name = $"repeat-{index + 1}.json";
            var path = Path.Combine(root, name);
            if (!File.Exists(path) || new FileInfo(path).Length > 65536
                || repeat?["caseId"]?.GetValue<string>() != $"repeat-{index + 1}"
                || Digest(File.ReadAllText(path)) != repeat?["resultSha256"]?.GetValue<string>()
                || JsonNode.Parse(File.ReadAllText(path))?.ToJsonString() != repeat?["result"]?.ToJsonString()
                || repeat?["durationMs"]?.GetValue<long>() is not > 0 and < 60000
                || repeat?["peakProcessMemoryBytes"]?.GetValue<long>() is not > 0 and <= 134217728
                || repeat?["result"]?["inputObjSha256"]?.GetValue<string>() != evidence["sourceArtifactSha256"]?.GetValue<string>()
                || repeat?["result"]?["readerSourceSha256"]?.GetValue<string>() != evidence["vtkReaderSha256"]?.GetValue<string>()
                || repeat?["result"]?["points"]?.GetValue<int>() != 4
                || repeat?["result"]?["triangles"]?.GetValue<int>() != 4
                || repeat?["result"]?["closed"]?.GetValue<bool>() != true
                || !artifacts.Any(item => item?["path"]?.GetValue<string>() == "resilience/" + name
                    && item?["sha256"]?.GetValue<string>() == repeat?["resultSha256"]?.GetValue<string>())) return null;
            var hash = repeat?["resultSha256"]?.GetValue<string>();
            if (commonHash != null && hash != commonHash) return null;
            commonHash = hash;
        }
        if (observations["cancellation"]?["state"]?.GetValue<string>() != "cancelled"
            || observations["cancellation"]?["outputAbsent"]?.GetValue<bool>() != true
            || observations["cancellation"]?["durationMs"]?.GetValue<long>() is not > 0 and < 5000
            || observations["timeout"]?["state"]?.GetValue<string>() != "timed-out"
            || observations["timeout"]?["limitSeconds"]?.GetValue<int>() != 1
            || observations["timeout"]?["outputAbsent"]?.GetValue<bool>() != true
            || observations["timeout"]?["durationMs"]?.GetValue<long>() is not > 0 and < 5000
            || observations["memory"]?["state"]?.GetValue<string>() != "limited"
            || observations["memory"]?["limitBytes"]?.GetValue<long>() != 134217728
            || observations["memory"]?["requestedBytes"]?.GetValue<long>() != 536870912
            || observations["memory"]?["exitCode"]?.GetValue<int>() != 42
            || observations["memory"]?["outputAbsent"]?.GetValue<bool>() != true
            || File.Exists(Path.Combine(root, "cancelled-output.txt"))
            || File.Exists(Path.Combine(root, "timeout-output.txt"))
            || File.Exists(Path.Combine(root, "memory-output.txt"))
            || result["inputArtifacts"] is not JsonArray inputs || inputs.Count != 1
            || inputs[0]?["sha256"]?.GetValue<string>() != evidence["sourceArtifactSha256"]?.GetValue<string>()) return null;
        return Digest(evidence.ToJsonString());
    }

    private static string? L7Hash(string directory, JsonObject result, JsonObject components)
    {
        if (result["recipeId"]?.GetValue<string>() != "l7.math3d-import"
            || result["runtimeId"]?.GetValue<string>() != "vtk-win-conda"
            || result["l7Evidence"] is not JsonObject evidence
            || evidence["suiteId"]?.GetValue<string>() != "l7-math3d-import-v1"
            || evidence["capabilityId"]?.GetValue<string>() != "mesh.interop.math3d"
            || evidence["source"] is not JsonObject source
            || evidence["conversion"] is not JsonObject conversion
            || evidence["consumer"] is not JsonObject consumer
            || evidence["lowerQualification"]?["records"] is not JsonArray lower || lower.Count != 7
            || source["lowerQualification"]?["records"] is not JsonArray sourceLower || sourceLower.Count != 6)
            return null;
        for (var index = 0; index < 6; index++)
            if (lower[index]?.ToJsonString() != sourceLower[index]?.ToJsonString()) return null;
        var folder = source["folderId"]?.GetValue<string>();
        var runId = source["runId"]?.GetValue<string>();
        var recordId = source["recordId"]?.GetValue<string>();
        if (folder is not { Length: 32 } || !folder.All(Uri.IsHexDigit)
            || runId is not { Length: 32 } || !runId.All(Uri.IsHexDigit)
            || recordId is not { Length: 64 } || !recordId.All(Uri.IsHexDigit)
            || lower[6]?["runId"]?.GetValue<string>() != runId
            || lower[6]?["recordId"]?.GetValue<string>() != recordId
            || lower[6]?["level"]?.GetValue<string>() != "L6") return null;
        var sourceDirectory = Path.Combine(Path.GetDirectoryName(directory)!, folder);
        var sourceResultPath = Path.Combine(sourceDirectory, "results.json");
        if (!File.Exists(sourceResultPath) || new FileInfo(sourceResultPath).Length > 1048576) return null;
        using var sourceDocument = JsonDocument.Parse(File.ReadAllText(sourceResultPath));
        var sourceResult = sourceDocument.RootElement;
        if (sourceResult.GetProperty("runId").GetString() != runId
            || sourceResult.GetProperty("runtimeId").GetString() != "vtk-win-conda"
            || sourceResult.GetProperty("profileId").GetString() != result["profileId"]?.GetValue<string>()
            || sourceResult.GetProperty("recipeId").GetString() != "l6.reproduce"
            || sourceResult.GetProperty("state").GetString() != "succeeded"
            || sourceResult.GetProperty("runFingerprintSha256").GetString() != source["runFingerprintSha256"]?.GetValue<string>()
            || !Verify(sourceDirectory, sourceResult).OfType<JsonObject>().Any(item => item["recordId"]?.GetValue<string>() == recordId
                && item["level"]?.GetValue<string>() == "L6")) return null;
        ScientificRunFingerprint.Verify(sourceDirectory, sourceResult.GetProperty("runFingerprintSha256").GetString() ?? "");
        var sourceEvidence = JsonNode.Parse(sourceResult.GetRawText())?["l6Evidence"];
        if (sourceEvidence?["positive"]?["artifactSha256"]?.GetValue<string>() != source["artifactSha256"]?.GetValue<string>()
            || sourceEvidence?["roundTrip"]?.ToJsonString() != source["roundTrip"]?.ToJsonString()
            || source["artifactPath"]?.GetValue<string>() != "positive/l5-positive.vtp") return null;
        var sourceArtifact = Path.Combine(sourceDirectory, "positive", "l5-positive.vtp");
        if (!File.Exists(sourceArtifact)
            || Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(sourceArtifact))).ToLowerInvariant() != source["artifactSha256"]?.GetValue<string>()) return null;
        var handoff = Path.Combine(directory, "handoff");
        var converted = Path.Combine(handoff, "vtk-math3d.obj");
        var reloadPath = Path.Combine(handoff, "reload.json");
        var consumedPath = Path.Combine(handoff, "consumed.json");
        if (!File.Exists(converted) || !File.Exists(reloadPath) || !File.Exists(consumedPath)
            || new FileInfo(converted).Length > 33554432 || new FileInfo(reloadPath).Length > 65536
            || new FileInfo(consumedPath).Length > 65536
            || evidence["objSha256"]?.GetValue<string>() != Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(converted))).ToLowerInvariant()
            || evidence["conversionSha256"]?.GetValue<string>() != Digest(File.ReadAllText(reloadPath))
            || evidence["consumerSha256"]?.GetValue<string>() != Digest(File.ReadAllText(consumedPath))
            || JsonNode.Parse(File.ReadAllText(reloadPath))?.ToJsonString() != conversion.ToJsonString()
            || JsonNode.Parse(File.ReadAllText(consumedPath))?.ToJsonString() != consumer.ToJsonString()
            || conversion["artifactSha256"]?.GetValue<string>() != source["artifactSha256"]?.GetValue<string>()
            || conversion["exportObjSha256"]?.GetValue<string>() != evidence["objSha256"]?.GetValue<string>()
            || conversion["parserSourceSha256"]?.GetValue<string>() != components["suite"]?["files"]?["tools/scientific-artifact-roundtrip.py"]?["sha256"]?.GetValue<string>()
            || consumer["inputObjSha256"]?.GetValue<string>() != evidence["objSha256"]?.GetValue<string>()
            || consumer["importerSourceSha256"]?.GetValue<string>() != evidence["importerSourceSha256"]?.GetValue<string>()
            || !ValidMath3DImport(conversion, consumer)
            || result["inputArtifacts"] is not JsonArray inputs || inputs.Count != 1
            || inputs[0]?["sha256"]?.GetValue<string>() != source["artifactSha256"]?.GetValue<string>()
            || inputs[0]?["sourceRunId"]?.GetValue<string>() != runId
            || result["artifacts"] is not JsonArray artifacts
            || !new[] { ("handoff/vtk-math3d.obj", "objSha256"), ("handoff/reload.json", "conversionSha256"),
                    ("handoff/consumed.json", "consumerSha256") }.All(item => artifacts.Any(artifact =>
                        artifact?["path"]?.GetValue<string>() == item.Item1
                        && artifact?["sha256"]?.GetValue<string>() == evidence[item.Item2]?.GetValue<string>()))) return null;
        return Digest(evidence.ToJsonString());
    }

    public static string? Save(string directory, JsonObject result, string sourceRoot, string installedRoot)
    {
        if (result["state"]?.GetValue<string>() != "succeeded") return null;
        var runId = result["runId"]?.GetValue<string>();
        var runtimeId = result["runtimeId"]?.GetValue<string>();
        var fingerprintSha256 = result["runFingerprintSha256"]?.GetValue<string>();
        if (runId == null || runtimeId == null || fingerprintSha256 == null) return null;
        ScientificRunFingerprint.Verify(directory, fingerprintSha256);
        var fingerprint = JsonNode.Parse(File.ReadAllText(Path.Combine(directory, "fingerprint.json")));
        var components = fingerprint?["components"] as JsonObject;
        var suiteRevision = components?["suite"]?["revisionSha256"]?.GetValue<string>();
        var contract = components?["contract"] as JsonObject;
        var manifestHash = contract?["runtimeManifest"]?["sha256"]?.GetValue<string>();
        if (suiteRevision?.Length != 64 || manifestHash?.Length != 64 || contract == null
            || contract["providerRegistryVersion"]?.GetValue<int>() != ScientificProviderRegistry.ContractVersion)
            return null;
        var manifest = Manifest(runtimeId, sourceRoot, installedRoot, manifestHash);
        if (manifest == null) return null;
        var environment = components?["environment"];
        var packagesRecorded = environment?["condaPackageRecords"]?["state"]?.GetValue<string>() == "recorded"
            || environment?["systemPackageRecords"]?["state"]?.GetValue<string>() == "recorded";
        if (!packagesRecorded || components?["worker"]?["executedFiles"] is not JsonArray workers || workers.Count == 0)
            return null;
        var records = new List<JsonObject>();
        void Add(string capability, string level, string evidence, string? evidenceHash = null, JsonNode? lower = null,
            string? consumerSourceSha256 = null, string? consumerContractSha256 = null,
            string? consumerEnvironmentSha256 = null, string? consumerCodecSha256 = null)
        {
            if (level is "L5" or "L6" or "L7" or "L8" or "L9"
                && !ScientificCapabilityRegistry.IsDeclared(runtimeId, capability)) return;
            if (records.Any(item => item["capabilityId"]?.GetValue<string>() == capability
                && item["level"]?.GetValue<string>() == level)) return;
            records.Add(Record(runId, runtimeId, capability, level, evidence, fingerprintSha256, suiteRevision,
                contract, evidenceHash, lower, consumerSourceSha256, consumerContractSha256,
                consumerEnvironmentSha256, consumerCodecSha256));
        }
        Add("runtime.inventory", "L0", "fingerprint.environment");
        var recipeId = result["recipeId"]?.GetValue<string>();
        if (recipeId == "lab.probe" && result["probeResults"] is JsonArray probeResults
            && manifest["probes"] is JsonArray declared)
        {
            var declarations = declared.OfType<JsonObject>().ToDictionary(item => item["id"]!.GetValue<string>(), StringComparer.Ordinal);
            var observations = probeResults.OfType<JsonObject>().ToArray();
            if (observations.Length == declarations.Count
                && observations.Select(item => item["id"]?.GetValue<string>()).Distinct(StringComparer.Ordinal).Count() == declarations.Count
                && observations.All(item => item["status"]?.GetValue<string>() == "passed"
                    && item["exitCode"]?.GetValue<int>() == 0
                    && declarations.ContainsKey(item["id"]?.GetValue<string>() ?? "")))
                foreach (var observation in observations)
                {
                    var id = observation["id"]!.GetValue<string>();
                    var declaration = declarations[id];
                    var level = declaration["readinessLevel"]?.GetValue<string>();
                    if (level is not ("L1" or "L2" or "L3") || observation["readinessLevel"]?.GetValue<string>() != level)
                        continue;
                    Add(declaration["capability"]?.GetValue<string>() ?? id, level, id);
                }
        }
        else if (runtimeId == "sage-wsl" && recipeId == "sage.version"
            && !string.IsNullOrWhiteSpace(result["versions"]?["sage"]?.GetValue<string>()))
            Add("runtime.executable", "L1", "sage.version");
        else if (runtimeId == "sage-wsl" && recipeId == "sage.factor-smoke"
            && result["validatedCapabilities"] is JsonArray capabilities
            && capabilities.Any(item => item?.GetValue<string>() == "math.symbolic")
            && result["evidence"]?["output"]?.GetValue<string>() == "verified: (x - 1) * (x + 1)")
        {
            Add("sage.python.binding", "L2", "sage.factor-smoke");
            Add("math.symbolic", "L3", "sage.factor-smoke");
        }
        else if (recipeId == "compile-link" && manifest["qualificationRecipes"] is JsonArray recipes)
        {
            var declaration = recipes.OfType<JsonObject>().FirstOrDefault(item => item["id"]?.GetValue<string>() == "compile-link"
                && item["readinessLevel"]?.GetValue<string>() == "L4");
            var expectedCapability = runtimeId == "cgal-win-conda" ? "cgal.cpp.compile-link"
                : runtimeId == "vtk-win-conda" ? "vtk.cpp.compile-link"
                : runtimeId == "gmsh-win-conda" ? "gmsh.cpp.compile-link" : null;
            var hash = CompileLinkHash(directory, sourceRoot, runtimeId, result, components!);
            if (declaration?["capability"]?.GetValue<string>() == expectedCapability && hash != null)
                Add(expectedCapability!, "L4", "compile-link", hash);
        }
        else if (recipeId == "l5.worker" && manifest["qualificationRecipes"] is JsonArray l5Recipes)
        {
            var declaration = l5Recipes.OfType<JsonObject>().FirstOrDefault(item => item["id"]?.GetValue<string>() == "l5.worker"
                && item["readinessLevel"]?.GetValue<string>() == "L5");
            var capability = runtimeId == "cgal-win-conda" ? "mesh.validate" : runtimeId == "vtk-win-conda" ? "mesh.read"
                : runtimeId == "gmsh-win-conda" ? "mesh.generate" : null;
            var hash = L5Hash(directory, runtimeId, result, components!);
            if (capability != null && declaration?["capability"]?.GetValue<string>() == capability && hash != null)
                Add(capability, "L5", "l5.worker", hash, result["l5Evidence"]?["lowerQualification"]);
        }
        else if (recipeId == "l5.gmsh-volume" && manifest["qualificationRecipes"] is JsonArray volumeL5Recipes)
        {
            var declaration = volumeL5Recipes.OfType<JsonObject>().FirstOrDefault(item =>
                item["id"]?.GetValue<string>() == "l5.gmsh-volume"
                && item["readinessLevel"]?.GetValue<string>() == "L5"
                && item["capability"]?.GetValue<string>() == "mesh.generate3d"
                && item["workerRecipe"]?.GetValue<string>() == "gmsh.volume3d.cube");
            var hash = GmshVolumeHash(directory, result, components!, "L5");
            if (declaration != null && hash != null)
                Add("mesh.generate3d", "L5", "l5.gmsh-volume", hash, result["volumeEvidence"]?["lowerQualification"]);
        }
        else if (recipeId == "l6.reproduce" && manifest["qualificationRecipes"] is JsonArray l6Recipes)
        {
            var declaration = l6Recipes.OfType<JsonObject>().FirstOrDefault(item => item["id"]?.GetValue<string>() == "l6.reproduce"
                && item["readinessLevel"]?.GetValue<string>() == "L6"
                && item["referenceRecipe"]?.GetValue<string>() == "l5.worker"
                && item["comparison"]?.GetValue<string>() == "sha256-exact");
            var capability = runtimeId == "cgal-win-conda" ? "mesh.validate" : runtimeId == "vtk-win-conda" ? "mesh.read"
                : runtimeId == "gmsh-win-conda" ? "mesh.generate" : null;
            var hash = L6Hash(directory, runtimeId, result, components!);
            if (capability != null && declaration?["capability"]?.GetValue<string>() == capability && hash != null)
                Add(capability, "L6", "l6.reproduce", hash, result["l6Evidence"]?["lowerQualification"]);
        }
        else if (recipeId == "l6.gmsh-volume" && manifest["qualificationRecipes"] is JsonArray volumeL6Recipes)
        {
            var declaration = volumeL6Recipes.OfType<JsonObject>().FirstOrDefault(item =>
                item["id"]?.GetValue<string>() == "l6.gmsh-volume"
                && item["readinessLevel"]?.GetValue<string>() == "L6"
                && item["capability"]?.GetValue<string>() == "mesh.generate3d"
                && item["referenceRecipe"]?.GetValue<string>() == "l5.gmsh-volume");
            var hash = GmshVolumeHash(directory, result, components!, "L6");
            if (declaration != null && hash != null)
                Add("mesh.generate3d", "L6", "l6.gmsh-volume", hash, result["volumeEvidence"]?["lowerQualification"]);
        }
        else if (recipeId == "l7.gmsh-volume" && manifest["qualificationRecipes"] is JsonArray volumeL7Recipes)
        {
            var declaration = volumeL7Recipes.OfType<JsonObject>().FirstOrDefault(item =>
                item["id"]?.GetValue<string>() == "l7.gmsh-volume"
                && item["readinessLevel"]?.GetValue<string>() == "L7"
                && item["capability"]?.GetValue<string>() == "mesh.generate3d"
                && item["referenceRecipe"]?.GetValue<string>() == "l6.gmsh-volume");
            var hash = GmshVolumeHash(directory, result, components!, "L7");
            if (declaration != null && hash != null)
                Add("mesh.generate3d", "L7", "l7.gmsh-volume", hash, result["volumeEvidence"]?["lowerQualification"]);
        }
        else if (recipeId == "l7.math3d-import" && manifest["qualificationRecipes"] is JsonArray l7Recipes)
        {
            var declaration = l7Recipes.OfType<JsonObject>().FirstOrDefault(item => item["id"]?.GetValue<string>() == "l7.math3d-import"
                && item["readinessLevel"]?.GetValue<string>() == "L7"
                && item["capability"]?.GetValue<string>() == "mesh.interop.math3d"
                && item["referenceRecipe"]?.GetValue<string>() == "l6.reproduce");
            var hash = L7Hash(directory, result, components!);
            if (declaration != null && hash != null)
                Add("mesh.interop.math3d", "L7", "l7.math3d-import", hash,
                    result["l7Evidence"]?["lowerQualification"], result["l7Evidence"]?["importerSourceSha256"]?.GetValue<string>());
        }
        else if (recipeId == "l7.gmsh-interop" && manifest["qualificationRecipes"] is JsonArray gmshInteropRecipes)
        {
            var declaration = gmshInteropRecipes.OfType<JsonObject>().FirstOrDefault(item =>
                item["id"]?.GetValue<string>() == "l7.gmsh-interop"
                && item["readinessLevel"]?.GetValue<string>() == "L7"
                && item["capability"]?.GetValue<string>() == "mesh.generate"
                && item["referenceRecipe"]?.GetValue<string>() == "l6.reproduce");
            var hash = GmshL7Hash(directory, result, components!);
            var evidence = result["l7GmshEvidence"];
            if (declaration != null && hash != null)
                Add("mesh.generate", "L7", "l7.gmsh-interop", hash, evidence?["lowerQualification"],
                    evidence?["consumerContract"]?["math3dImporterSha256"]?.GetValue<string>(),
                    evidence?["consumerContractSha256"]?.GetValue<string>(),
                    evidence?["consumerContract"]?["vtkEnvironmentSha256"]?.GetValue<string>());
        }
        else if (recipeId == "l7.cgal-vtk-math3d" && manifest["qualificationRecipes"] is JsonArray cgalInteropRecipes)
        {
            var declaration = cgalInteropRecipes.OfType<JsonObject>().FirstOrDefault(item =>
                item["id"]?.GetValue<string>() == "l7.cgal-vtk-math3d"
                && item["readinessLevel"]?.GetValue<string>() == "L7"
                && item["capability"]?.GetValue<string>() == "mesh.interop.vtk-math3d"
                && item["referenceRecipe"]?.GetValue<string>() == "l6.reproduce"
                && item["format"]?.GetValue<string>() == "obj");
            var hash = L7InteropHash(directory, result, components!);
            var evidence = result["l7InteropEvidence"];
            if (declaration != null && hash != null)
                Add("mesh.interop.vtk-math3d", "L7", "l7.cgal-vtk-math3d", hash,
                    evidence?["lowerQualification"], evidence?["consumerContract"]?["math3dImporterSourceSha256"]?.GetValue<string>(),
                    evidence?["consumerContractSha256"]?.GetValue<string>(),
                    evidence?["consumerContract"]?["vtkEnvironmentSha256"]?.GetValue<string>());
        }
        else if (recipeId == "l8.resilience" && manifest["qualificationRecipes"] is JsonArray resilienceRecipes)
        {
            var declaration = resilienceRecipes.OfType<JsonObject>().FirstOrDefault(item =>
                item["id"]?.GetValue<string>() == "l8.resilience"
                && item["readinessLevel"]?.GetValue<string>() == "L8"
                && item["capability"]?.GetValue<string>() == "mesh.interop.vtk-math3d"
                && item["referenceRecipe"]?.GetValue<string>() == "l7.cgal-vtk-math3d"
                && item["repeatCount"]?.GetValue<int>() == 3
                && item["memoryLimitBytes"]?.GetValue<long>() == 134217728);
            var hash = L8Hash(directory, result, components!);
            if (declaration != null && hash != null)
                Add("mesh.interop.vtk-math3d", "L8", "l8.resilience", hash,
                    result["l8Evidence"]?["lowerQualification"]);
        }
        else if (recipeId == "l8.gmsh-resilience" && manifest["qualificationRecipes"] is JsonArray gmshResilienceRecipes)
        {
            var declaration = gmshResilienceRecipes.OfType<JsonObject>().FirstOrDefault(item =>
                item["id"]?.GetValue<string>() == "l8.gmsh-resilience"
                && item["readinessLevel"]?.GetValue<string>() == "L8"
                && item["capability"]?.GetValue<string>() == "mesh.generate"
                && item["referenceRecipe"]?.GetValue<string>() == "l7.gmsh-interop"
                && item["repeatCount"]?.GetValue<int>() == 3
                && item["memoryLimitBytes"]?.GetValue<long>() == 134217728);
            var hash = GmshL8Hash(directory, result, components!);
            if (declaration != null && hash != null)
                Add("mesh.generate", "L8", "l8.gmsh-resilience", hash,
                    result["l8GmshEvidence"]?["lowerQualification"]);
        }
        else if (recipeId == "l8.gmsh-volume" && manifest["qualificationRecipes"] is JsonArray gmshVolumeResilienceRecipes)
        {
            var declaration = gmshVolumeResilienceRecipes.OfType<JsonObject>().FirstOrDefault(item =>
                item["id"]?.GetValue<string>() == "l8.gmsh-volume"
                && item["readinessLevel"]?.GetValue<string>() == "L8"
                && item["capability"]?.GetValue<string>() == "mesh.generate3d"
                && item["referenceRecipe"]?.GetValue<string>() == "l7.gmsh-volume"
                && item["repeatCount"]?.GetValue<int>() == 3
                && item["memoryLimitBytes"]?.GetValue<long>() == 134217728);
            var hash = GmshVolumeL8Hash(directory, result, components!);
            if (declaration != null && hash != null)
                Add("mesh.generate3d", "L8", "l8.gmsh-volume", hash,
                    result["l8GmshVolumeEvidence"]?["lowerQualification"]);
        }
        else if (recipeId == "l9.math3d-product" && manifest["qualificationRecipes"] is JsonArray productRecipes)
        {
            var declaration = productRecipes.OfType<JsonObject>().FirstOrDefault(item =>
                item["id"]?.GetValue<string>() == "l9.math3d-product"
                && item["readinessLevel"]?.GetValue<string>() == "L9"
                && item["capability"]?.GetValue<string>() == "mesh.interop.vtk-math3d"
                && item["referenceRecipe"]?.GetValue<string>() == "l8.resilience"
                && item["contractVersion"]?.GetValue<int>() == 1
                && item["viewer"]?.GetValue<string>() == "MeshDocumentViewport");
            var hash = L9Hash(directory, result, components!);
            var evidence = result["l9Evidence"];
            if (declaration != null && hash != null)
                Add("mesh.interop.vtk-math3d", "L9", "l9.math3d-product", hash,
                    evidence?["lowerQualification"], evidence?["consumerSourcesSha256"]?.GetValue<string>(),
                    evidence?["productContractSha256"]?.GetValue<string>());
        }
        else if (recipeId == "l9.gmsh-product" && manifest["qualificationRecipes"] is JsonArray gmshProductRecipes)
        {
            var declaration = gmshProductRecipes.OfType<JsonObject>().FirstOrDefault(item =>
                item["id"]?.GetValue<string>() == "l9.gmsh-product"
                && item["readinessLevel"]?.GetValue<string>() == "L9"
                && item["capability"]?.GetValue<string>() == "mesh.generate"
                && item["referenceRecipe"]?.GetValue<string>() == "l8.gmsh-resilience"
                && item["contractVersion"]?.GetValue<int>() == 1
                && item["viewer"]?.GetValue<string>() == "MeshDocumentViewport");
            var hash = GmshL9Hash(directory, result, components!);
            var evidence = result["l9GmshEvidence"];
            if (declaration != null && hash != null)
                Add("mesh.generate", "L9", "l9.gmsh-product", hash, evidence?["lowerQualification"],
                    evidence?["consumerSourcesSha256"]?.GetValue<string>(),
                    evidence?["productContractSha256"]?.GetValue<string>(), null,
                    evidence?["regression"]?["codecSourceSha256"]?.GetValue<string>());
        }
        var document = new JsonObject
        {
            ["schemaVersion"] = 1, ["runId"] = runId, ["runtimeId"] = runtimeId,
            ["runFingerprintSha256"] = fingerprintSha256,
            ["records"] = new JsonArray(records.Select(item => (JsonNode?)item).ToArray())
        };
        var text = document.ToJsonString();
        var target = Path.Combine(directory, "qualifications.json");
        var temporary = Path.Combine(directory, $".qualifications-{Guid.NewGuid():N}.tmp");
        try
        {
            File.WriteAllText(temporary, text, new UTF8Encoding(false));
            File.Move(temporary, target);
        }
        finally { if (File.Exists(temporary)) File.Delete(temporary); }
        return Digest(text);
    }

    public static JsonArray Verify(string directory, JsonElement result)
    {
        if (!result.TryGetProperty("qualificationSha256", out var expectedValue)
            || expectedValue.GetString() is not { Length: 64 } expected)
            throw new InvalidDataException("Qualification reference is missing.");
        var path = Path.Combine(directory, "qualifications.json");
        if (!File.Exists(path) || new FileInfo(path).Length > 262144)
            throw new InvalidDataException("Qualification record is missing or too large.");
        var text = File.ReadAllText(path);
        if (!string.Equals(Digest(text), expected, StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("Qualification record does not match saved evidence.");
        var document = JsonNode.Parse(text) as JsonObject;
        var records = document?["records"] as JsonArray;
        var runId = result.GetProperty("runId").GetString();
        var runtimeId = result.GetProperty("runtimeId").GetString();
        var fingerprintSha256 = result.GetProperty("runFingerprintSha256").GetString();
        if (document?["schemaVersion"]?.GetValue<int>() != 1 || records == null || records.Count == 0
            || document["runId"]?.GetValue<string>() != runId
            || document["runtimeId"]?.GetValue<string>() != runtimeId
            || document["runFingerprintSha256"]?.GetValue<string>() != fingerprintSha256
            || result.GetProperty("state").GetString() != "succeeded")
            throw new InvalidDataException("Qualification identity is invalid.");
        var fingerprint = JsonNode.Parse(File.ReadAllText(Path.Combine(directory, "fingerprint.json")));
        var suiteRevision = fingerprint?["components"]?["suite"]?["revisionSha256"]?.GetValue<string>();
        var contract = fingerprint?["components"]?["contract"] as JsonObject;
        var ids = new HashSet<string>(StringComparer.Ordinal);
        foreach (var item in records)
        {
            if (item is not JsonObject record) throw new InvalidDataException("Invalid qualification entry.");
            var copy = (JsonObject)record.DeepClone();
            var recordId = copy["recordId"]?.GetValue<string>();
            copy.Remove("recordId");
            if (recordId == null || !ids.Add(recordId) || Digest(copy.ToJsonString()) != recordId
                || record["schemaVersion"]?.GetValue<int>() != 1
                || record["runId"]?.GetValue<string>() != runId
                || record["runtimeId"]?.GetValue<string>() != runtimeId
                || record["runFingerprintSha256"]?.GetValue<string>() != fingerprintSha256
                || record["suiteRevisionSha256"]?.GetValue<string>() != suiteRevision
                || record["contract"]?.ToJsonString() != contract?.ToJsonString()
                || record["level"]?.GetValue<string>() is not ("L0" or "L1" or "L2" or "L3" or "L4" or "L5" or "L6" or "L7" or "L8" or "L9"))
                throw new InvalidDataException("Qualification entry does not match its run.");
            if (record["level"]?.GetValue<string>() == "L4")
            {
                var kind = runtimeId == "cgal-win-conda" ? "cgal" : runtimeId == "vtk-win-conda" ? "vtk"
                    : runtimeId == "gmsh-win-conda" ? "gmsh" : null;
                var binaryName = kind == null ? null : "devshell_" + kind + "_smoke.exe";
                var binary = binaryName == null ? null : Path.Combine(directory, "build", "Release", binaryName);
                if (binary == null || !File.Exists(binary)
                    || record["capabilityId"]?.GetValue<string>() != kind + ".cpp.compile-link"
                    || record["evidenceId"]?.GetValue<string>() != "compile-link"
                    || !string.Equals(record["evidenceSha256"]?.GetValue<string>(),
                        Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(binary))).ToLowerInvariant(), StringComparison.OrdinalIgnoreCase))
                    throw new InvalidDataException("Compiled qualification binary has changed.");
            }
            if (record["level"]?.GetValue<string>() == "L5")
            {
                var sourceResult = JsonNode.Parse(result.GetRawText()) as JsonObject;
                if (record["evidenceId"]?.GetValue<string>() == "l5.gmsh-volume")
                {
                    if (sourceResult == null
                        || record["capabilityId"]?.GetValue<string>() != "mesh.generate3d"
                        || record["lowerQualification"]?.ToJsonString() != sourceResult["volumeEvidence"]?["lowerQualification"]?.ToJsonString()
                        || record["evidenceSha256"]?.GetValue<string>() != GmshVolumeHash(directory, sourceResult,
                            fingerprint!["components"]!.AsObject(), "L5"))
                        throw new InvalidDataException("Gmsh volume L5 evidence changed.");
                    continue;
                }
                if (sourceResult == null || record["evidenceId"]?.GetValue<string>() != "l5.worker"
                    || record["lowerQualification"]?.ToJsonString() != sourceResult["l5Evidence"]?["lowerQualification"]?.ToJsonString()
                    || record["evidenceSha256"]?.GetValue<string>() != L5Hash(directory, runtimeId!, sourceResult,
                        fingerprint!["components"]!.AsObject()))
                    throw new InvalidDataException("L5 worker qualification evidence has changed.");
            }
            if (record["level"]?.GetValue<string>() == "L6")
            {
                var sourceResult = JsonNode.Parse(result.GetRawText()) as JsonObject;
                if (record["evidenceId"]?.GetValue<string>() == "l6.gmsh-volume")
                {
                    if (sourceResult == null
                        || record["capabilityId"]?.GetValue<string>() != "mesh.generate3d"
                        || record["lowerQualification"]?.ToJsonString() != sourceResult["volumeEvidence"]?["lowerQualification"]?.ToJsonString()
                        || record["evidenceSha256"]?.GetValue<string>() != GmshVolumeHash(directory, sourceResult,
                            fingerprint!["components"]!.AsObject(), "L6"))
                        throw new InvalidDataException("Gmsh volume L6 evidence changed.");
                    continue;
                }
                if (sourceResult == null || record["evidenceId"]?.GetValue<string>() != "l6.reproduce"
                    || record["lowerQualification"]?.ToJsonString() != sourceResult["l6Evidence"]?["lowerQualification"]?.ToJsonString()
                    || record["evidenceSha256"]?.GetValue<string>() != L6Hash(directory, runtimeId!, sourceResult,
                        fingerprint!["components"]!.AsObject()))
                    throw new InvalidDataException("L6 reproduction evidence has changed.");
            }
            if (record["level"]?.GetValue<string>() == "L7")
            {
                var sourceResult = JsonNode.Parse(result.GetRawText()) as JsonObject;
                if (sourceResult == null) throw new InvalidDataException("L7 evidence is unavailable.");
                if (record["evidenceId"]?.GetValue<string>() == "l7.gmsh-volume")
                {
                    if (record["capabilityId"]?.GetValue<string>() != "mesh.generate3d"
                        || record["lowerQualification"]?.ToJsonString() != sourceResult["volumeEvidence"]?["lowerQualification"]?.ToJsonString()
                        || record["evidenceSha256"]?.GetValue<string>() != GmshVolumeHash(directory, sourceResult,
                            fingerprint!["components"]!.AsObject(), "L7"))
                        throw new InvalidDataException("Gmsh volume L7 evidence changed.");
                    continue;
                }
                if (record["evidenceId"]?.GetValue<string>() == "l7.gmsh-interop")
                {
                    var evidence = sourceResult["l7GmshEvidence"];
                    if (record["lowerQualification"]?.ToJsonString() != evidence?["lowerQualification"]?.ToJsonString()
                        || record["consumerSourceSha256"]?.GetValue<string>() != evidence?["consumerContract"]?["math3dImporterSha256"]?.GetValue<string>()
                        || record["consumerContractSha256"]?.GetValue<string>() != evidence?["consumerContractSha256"]?.GetValue<string>()
                        || record["consumerEnvironmentSha256"]?.GetValue<string>() != evidence?["consumerContract"]?["vtkEnvironmentSha256"]?.GetValue<string>()
                        || record["evidenceSha256"]?.GetValue<string>() != GmshL7Hash(directory, sourceResult,
                            fingerprint!["components"]!.AsObject()))
                        throw new InvalidDataException("Gmsh L7 interoperability evidence has changed.");
                    continue;
                }
                if (record["evidenceId"]?.GetValue<string>() == "l7.cgal-vtk-math3d")
                {
                    var evidence = sourceResult["l7InteropEvidence"];
                    if (record["lowerQualification"]?.ToJsonString() != evidence?["lowerQualification"]?.ToJsonString()
                        || record["consumerSourceSha256"]?.GetValue<string>() != evidence?["consumerContract"]?["math3dImporterSourceSha256"]?.GetValue<string>()
                        || record["consumerContractSha256"]?.GetValue<string>() != evidence?["consumerContractSha256"]?.GetValue<string>()
                        || record["consumerEnvironmentSha256"]?.GetValue<string>() != evidence?["consumerContract"]?["vtkEnvironmentSha256"]?.GetValue<string>()
                        || record["evidenceSha256"]?.GetValue<string>() != L7InteropHash(directory, sourceResult,
                            fingerprint!["components"]!.AsObject()))
                        throw new InvalidDataException("L7 CGAL interoperability evidence has changed.");
                    continue;
                }
                if (record["evidenceId"]?.GetValue<string>() != "l7.math3d-import"
                    || record["lowerQualification"]?.ToJsonString() != sourceResult["l7Evidence"]?["lowerQualification"]?.ToJsonString()
                    || record["consumerSourceSha256"]?.GetValue<string>() != sourceResult["l7Evidence"]?["importerSourceSha256"]?.GetValue<string>()
                    || record["evidenceSha256"]?.GetValue<string>() != L7Hash(directory, sourceResult,
                        fingerprint!["components"]!.AsObject()))
                    throw new InvalidDataException("L7 MATH3D importer evidence has changed.");
            }
            if (record["level"]?.GetValue<string>() == "L8")
            {
                var sourceResult = JsonNode.Parse(result.GetRawText()) as JsonObject;
                if (record["evidenceId"]?.GetValue<string>() == "l8.gmsh-volume")
                {
                    if (sourceResult == null || record["capabilityId"]?.GetValue<string>() != "mesh.generate3d"
                        || record["lowerQualification"]?.ToJsonString() != sourceResult["l8GmshVolumeEvidence"]?["lowerQualification"]?.ToJsonString()
                        || record["evidenceSha256"]?.GetValue<string>() != GmshVolumeL8Hash(directory, sourceResult,
                            fingerprint!["components"]!.AsObject()))
                        throw new InvalidDataException("Gmsh volume L8 resilience evidence changed.");
                    continue;
                }
                if (record["evidenceId"]?.GetValue<string>() == "l8.gmsh-resilience")
                {
                    if (sourceResult == null
                        || record["lowerQualification"]?.ToJsonString() != sourceResult["l8GmshEvidence"]?["lowerQualification"]?.ToJsonString()
                        || record["evidenceSha256"]?.GetValue<string>() != GmshL8Hash(directory, sourceResult,
                            fingerprint!["components"]!.AsObject()))
                        throw new InvalidDataException("Gmsh L8 resilience evidence has changed.");
                    continue;
                }
                if (sourceResult == null || record["evidenceId"]?.GetValue<string>() != "l8.resilience"
                    || record["lowerQualification"]?.ToJsonString() != sourceResult["l8Evidence"]?["lowerQualification"]?.ToJsonString()
                    || record["evidenceSha256"]?.GetValue<string>() != L8Hash(directory, sourceResult,
                        fingerprint!["components"]!.AsObject()))
                    throw new InvalidDataException("L8 resilience evidence has changed.");
            }
            if (record["level"]?.GetValue<string>() == "L9")
            {
                var sourceResult = JsonNode.Parse(result.GetRawText()) as JsonObject;
                if (record["evidenceId"]?.GetValue<string>() == "l9.gmsh-product")
                {
                    var evidence = sourceResult?["l9GmshEvidence"];
                    if (sourceResult == null
                        || record["lowerQualification"]?.ToJsonString() != evidence?["lowerQualification"]?.ToJsonString()
                        || record["consumerSourceSha256"]?.GetValue<string>() != evidence?["consumerSourcesSha256"]?.GetValue<string>()
                        || record["consumerContractSha256"]?.GetValue<string>() != evidence?["productContractSha256"]?.GetValue<string>()
                        || record["consumerCodecSha256"]?.GetValue<string>() != evidence?["regression"]?["codecSourceSha256"]?.GetValue<string>()
                        || record["evidenceSha256"]?.GetValue<string>() != GmshL9Hash(directory, sourceResult,
                            fingerprint!["components"]!.AsObject()))
                        throw new InvalidDataException("Gmsh L9 product evidence has changed.");
                    continue;
                }
                if (sourceResult == null || record["evidenceId"]?.GetValue<string>() != "l9.math3d-product"
                    || record["lowerQualification"]?.ToJsonString() != sourceResult["l9Evidence"]?["lowerQualification"]?.ToJsonString()
                    || record["consumerSourceSha256"]?.GetValue<string>() != sourceResult["l9Evidence"]?["consumerSourcesSha256"]?.GetValue<string>()
                    || record["consumerContractSha256"]?.GetValue<string>() != sourceResult["l9Evidence"]?["productContractSha256"]?.GetValue<string>()
                    || record["evidenceSha256"]?.GetValue<string>() != L9Hash(directory, sourceResult,
                        fingerprint!["components"]!.AsObject()))
                    throw new InvalidDataException("L9 product integration evidence has changed.");
            }
        }
        return records;
    }

    public static JsonArray Assess(JsonArray records, JsonObject sourceDrift, JsonObject environmentDrift)
    {
        var source = sourceDrift["state"]?.GetValue<string>();
        var environment = environmentDrift["state"]?.GetValue<string>();
        var contractChanged = records.Any(item => item?["contract"]?["providerRegistryVersion"]?.GetValue<int>()
            != ScientificProviderRegistry.ContractVersion
            || item?["contract"]?["requestSchemaVersion"]?.GetValue<int>() != 1
            || item?["contract"]?["resultSchemaVersion"]?.GetValue<int>() != 1);
        var state = source == "stale" || environment == "stale" || contractChanged ? "stale"
            : source == "unknown" || environment == "unknown" ? "unknown" : "current";
        var reasons = new JsonArray();
        if (source != "current") reasons.Add("source " + source);
        if (environment != "current") reasons.Add("environment " + environment);
        if (contractChanged) reasons.Add("contract version changed");
        foreach (var reason in sourceDrift["reasons"]?.AsArray() ?? new JsonArray()) reasons.Add(reason?.DeepClone());
        foreach (var reason in environmentDrift["reasons"]?.AsArray() ?? new JsonArray()) reasons.Add(reason?.DeepClone());
        return new JsonArray(records.Select(item =>
        {
            var view = (JsonObject)item!.DeepClone();
            view["status"] = state;
            view["staleReasons"] = reasons.DeepClone();
            return (JsonNode?)view;
        }).ToArray());
    }

    public static void AssessL5Dependencies(JsonArray records, IReadOnlySet<string> currentLowerRecordIds, bool includeL6 = true, bool includeL7 = true, bool includeL8 = true, bool includeL9 = true)
    {
        foreach (var record in records.OfType<JsonObject>().Where(item => item["level"]?.GetValue<string>() == "L5"
            || includeL6 && item["level"]?.GetValue<string>() == "L6"
            || includeL7 && item["level"]?.GetValue<string>() == "L7"
            || includeL8 && item["level"]?.GetValue<string>() == "L8"
            || includeL9 && item["level"]?.GetValue<string>() == "L9"))
        {
            var level = record["level"]?.GetValue<string>();
            var lower = record["lowerQualification"]?["records"] as JsonArray;
            if (lower is { Count: > 0 } && lower.Count == (level == "L5" ? 5 : level == "L6" ? 6 : level == "L7" ? 7 : level == "L8" ? 8 : 9)
                && lower.All(item => item?["recordId"]?.GetValue<string>() is { } id
                && currentLowerRecordIds.Contains(id))) continue;
            record["status"] = "stale";
            var reasons = record["staleReasons"] as JsonArray ?? new JsonArray();
            var reason = level == "L5" ? "supporting L0-L4 qualification is no longer current"
                : level == "L6" ? "supporting L0-L5 qualification is no longer current"
                : level == "L7" ? "supporting L0-L6 qualification is no longer current"
                : level == "L8" ? "supporting L0-L7 qualification is no longer current"
                : "supporting L0-L8 qualification is no longer current";
            if (!reasons.Any(item => item?.GetValue<string>() == reason)) reasons.Add(reason);
            record["staleReasons"] = reasons;
        }
    }

    public static void AssessL7Consumer(JsonArray records, string? currentImporterSha256, string? currentVtkEnvironmentSha256 = null)
    {
        foreach (var record in records.OfType<JsonObject>().Where(item => item["level"]?.GetValue<string>() == "L7"))
        {
            if (record["consumerSourceSha256"]?.GetValue<string>() == currentImporterSha256) continue;
            record["status"] = currentImporterSha256 == null ? "unknown" : "stale";
            var reasons = record["staleReasons"] as JsonArray ?? new JsonArray();
            reasons.Add(currentImporterSha256 == null ? "MATH3D importer source is unavailable" : "MATH3D importer source changed");
            record["staleReasons"] = reasons;
        }
        foreach (var record in records.OfType<JsonObject>().Where(item => item["level"]?.GetValue<string>() == "L7"
            && item["evidenceId"]?.GetValue<string>() is "l7.cgal-vtk-math3d" or "l7.gmsh-interop"))
        {
            if (record["consumerEnvironmentSha256"]?.GetValue<string>() == currentVtkEnvironmentSha256) continue;
            record["status"] = currentVtkEnvironmentSha256 == null ? "unknown" : "stale";
            var reasons = record["staleReasons"] as JsonArray ?? new JsonArray();
            reasons.Add(currentVtkEnvironmentSha256 == null ? "VTK consumer environment is unavailable" : "VTK consumer environment changed");
            record["staleReasons"] = reasons;
        }
    }

    public static void AssessL9Consumer(JsonArray records, string? currentSourcesSha256, string? currentContractSha256,
        string? currentCodecSha256 = null)
    {
        foreach (var record in records.OfType<JsonObject>().Where(item => item["level"]?.GetValue<string>() == "L9"))
        {
            var reasons = record["staleReasons"] as JsonArray ?? new JsonArray();
            if (record["evidenceId"]?.GetValue<string>() == "l9.gmsh-product"
                && record["consumerCodecSha256"]?.GetValue<string>() != currentCodecSha256)
            {
                record["status"] = currentCodecSha256 == null ? "unknown" : "stale";
                reasons.Add(currentCodecSha256 == null ? "MATH3D M3DM codec is unavailable" : "MATH3D M3DM codec changed");
            }
            if (currentSourcesSha256 == null || currentContractSha256 == null)
            {
                if (record["status"]?.GetValue<string>() != "stale") record["status"] = "unknown";
                reasons.Add("MATH3D product consumer or contract is unavailable");
            }
            else
            {
                if (record["consumerSourceSha256"]?.GetValue<string>() != currentSourcesSha256)
                {
                    record["status"] = "stale";
                    reasons.Add("MATH3D product consumer source changed");
                }
                if (record["consumerContractSha256"]?.GetValue<string>() != currentContractSha256)
                {
                    record["status"] = "stale";
                    reasons.Add("MATH3D product handoff contract changed");
                }
            }
            record["staleReasons"] = reasons;
        }
    }

    public static JsonObject Summarize(string runtimeId, IEnumerable<JsonObject> runs)
    {
        var current = new Dictionary<string, List<(int Level, JsonObject Run)>>(StringComparer.Ordinal);
        var excludedFailed = 0;
        var excludedStale = 0;
        var excludedUnknown = 0;
        var currentRecords = new JsonArray();
        foreach (var run in runs)
        {
            if (run["runtimeId"]?.GetValue<string>() != runtimeId) continue;
            if (run["state"]?.GetValue<string>() != "succeeded") { excludedFailed++; continue; }
            if (run["qualifications"] is not JsonArray records) continue;
            foreach (var record in records.OfType<JsonObject>())
            {
                var status = record["status"]?.GetValue<string>();
                if (status == "stale") { excludedStale++; continue; }
                if (status != "current") { excludedUnknown++; continue; }
                var capability = record["capabilityId"]?.GetValue<string>();
                var level = record["level"]?.GetValue<string>();
                if (capability == null || level?.Length != 2 || level[0] != 'L' || !int.TryParse(level[1..], out var number))
                    continue;
                currentRecords.Add(new JsonObject { ["runId"] = run["runId"]?.GetValue<string>(),
                    ["recordId"] = record["recordId"]?.GetValue<string>(), ["capabilityId"] = capability,
                    ["level"] = level, ["finishedAtUtc"] = run["finishedAtUtc"]?.GetValue<string>() });
                if (!current.TryGetValue(capability, out var candidates))
                    current[capability] = candidates = new List<(int, JsonObject)>();
                candidates.Add((number, new JsonObject
                {
                    ["runId"] = run["runId"]?.GetValue<string>(),
                    ["recordId"] = record["recordId"]?.GetValue<string>(),
                    ["recipeId"] = run["recipeId"]?.GetValue<string>(),
                    ["finishedAtUtc"] = run["finishedAtUtc"]?.GetValue<string>()
                }));
            }
        }
        var capabilities = new JsonArray();
        foreach (var (capability, candidates) in current.OrderBy(item => item.Key, StringComparer.Ordinal))
        {
            var highest = candidates.Max(item => item.Level);
            capabilities.Add(new JsonObject
            {
                ["capabilityId"] = capability,
                ["highestLevel"] = "L" + highest,
                ["supportingRuns"] = new JsonArray(candidates.Where(item => item.Level == highest)
                    .OrderByDescending(item => item.Run["finishedAtUtc"]?.GetValue<string>(), StringComparer.Ordinal)
                    .Select(item => (JsonNode?)item.Run).ToArray())
            });
        }
        return new JsonObject { ["runtimeId"] = runtimeId, ["capabilities"] = capabilities,
            ["currentRecords"] = currentRecords,
            ["excludedFailedRuns"] = excludedFailed, ["excludedStaleRecords"] = excludedStale,
            ["excludedUnknownRecords"] = excludedUnknown };
    }
}
