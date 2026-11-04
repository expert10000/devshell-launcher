using System.Diagnostics;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace BatchLauncher;

public partial class Form1
{
    private sealed record ScientificL5Case(string RecipeId, string DatasetId, string OutputName, string? ExpectedReason);

    private static (string Capability, ScientificL5Case Positive, ScientificL5Case Rejection) ScientificL5Cases(string runtimeId) => runtimeId switch
    {
        "cgal-win-conda" => ("mesh.validate",
            new("cgal.validate", "math3d/basic/01_tetrahedron.obj", "l5-positive.obj", null),
            new("cgal.validate", "math3d/problematic/18_degenerate_faces.obj", "l5-rejected.obj", "not a readable manifold polygon mesh")),
        "vtk-win-conda" => ("mesh.read",
            new("mesh.inspect", "math3d/basic/01_tetrahedron.obj", "l5-positive.vtp", null),
            new("mesh.inspect", "math3d/import/truncated-ascii.ply", "l5-rejected.vtp", "surface is empty")),
        _ => throw new InvalidOperationException("L5 worker evidence is registered only for CGAL and VTK.")
    };

    private static JsonObject ScientificCurrentLowerLevels(string profileId, string runtimeId)
    {
        var summary = ScientificQualificationSummary(profileId, runtimeId);
        var kind = runtimeId == "cgal-win-conda" ? "cgal" : "vtk";
        var required = new[] { ("runtime.inventory", "L0"), ("python.version", "L1"),
            ($"{kind}.python.import", "L2"), (kind == "cgal" ? "geometry.point3" : "geometry.polydata", "L3"),
            ($"{kind}.cpp.compile-link", "L4") };
        var records = new JsonArray();
        foreach (var (capability, level) in required)
        {
            var entry = summary["capabilities"]?.AsArray().OfType<JsonObject>()
                .FirstOrDefault(item => item["capabilityId"]?.GetValue<string>() == capability
                    && item["highestLevel"]?.GetValue<string>() == level);
            var support = entry?["supportingRuns"]?.AsArray().OfType<JsonObject>().FirstOrDefault();
            if (support == null) throw new InvalidOperationException($"Current {level} evidence for {capability} is required before L5.");
            records.Add(new JsonObject { ["runId"] = support["runId"]?.GetValue<string>(),
                ["recordId"] = support["recordId"]?.GetValue<string>(), ["capabilityId"] = capability, ["level"] = level });
        }
        return new JsonObject { ["records"] = records };
    }

    private static void ScientificCheckL5Declaration(string runtimeId, string capability,
        ScientificL5Case positive, ScientificL5Case rejection)
    {
        var path = Path.Combine(AppContext.BaseDirectory, "runtimes", runtimeId, "runtime.json");
        if (!File.Exists(path) || new FileInfo(path).Length > 65536)
            throw new InvalidOperationException("L5 runtime manifest is unavailable.");
        var manifest = JsonNode.Parse(File.ReadAllText(path));
        var declaration = manifest?["qualificationRecipes"]?.AsArray().OfType<JsonObject>()
            .FirstOrDefault(item => item["id"]?.GetValue<string>() == "l5.worker");
        bool Matches(JsonNode? node, ScientificL5Case test) => node?["recipeId"]?.GetValue<string>() == test.RecipeId
            && node["datasetId"]?.GetValue<string>() == test.DatasetId
            && node["outputName"]?.GetValue<string>() == test.OutputName;
        if (declaration?["readinessLevel"]?.GetValue<string>() != "L5"
            || declaration["capability"]?.GetValue<string>() != capability
            || !Matches(declaration["positive"], positive) || !Matches(declaration["rejection"], rejection)
            || declaration["rejection"]?["expectedReason"]?.GetValue<string>() != rejection.ExpectedReason)
            throw new InvalidOperationException("L5 cases do not match the registered manifest.");
    }

    private object ScientificL5Start(string profileId, string runtimeId)
    {
        ScientificProviderRegistry.RequireAction(runtimeId, "l5-worker");
        var (capability, positive, rejection) = ScientificL5Cases(runtimeId);
        ScientificCheckL5Declaration(runtimeId, capability, positive, rejection);
        var lower = ScientificCurrentLowerLevels(profileId, runtimeId);
        var positiveInput = ScientificDatasetArtifact(positive.DatasetId);
        var rejectionInput = ScientificDatasetArtifact(rejection.DatasetId);
        var prefix = ScientificPrefix(runtimeId);
        if (!_scientificGate.Wait(0)) throw new InvalidOperationException("Another Scientific job is running; stop or wait for it.");
        try
        {
            var directory = Path.Combine(ScientificDataRoot, "runs", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(directory);
            var job = new ScientificJob { ProfileId = profileId, RuntimeId = runtimeId,
                RecipeId = "l5.worker", Directory = directory };
            var parameters = JsonSerializer.SerializeToElement(new { suiteId = "l5-worker-v1",
                positiveCase = positive.DatasetId, rejectionCase = rejection.DatasetId,
                lowerRecords = lower["records"]?.DeepClone() }, ScientificJson);
            ScientificWriteRequest(job, parameters, positiveInput, additionalInputs: new JsonArray(rejectionInput.DeepClone()),
                additionalOutputs: new JsonArray(new JsonObject { ["path"] = "positive/" + positive.OutputName,
                    ["mediaType"] = ScientificMediaType(positive.OutputName) }));
            _scientificJobs[profileId + ":" + runtimeId] = job;
            ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) });
            _ = ScientificL5RunAsync(job, prefix, capability, positive, rejection, positiveInput, rejectionInput, lower);
            return ScientificJobSnapshot(job);
        }
        catch { _scientificGate.Release(); throw; }
    }

    private async Task<JsonObject> ScientificL5CaseAsync(ScientificJob suite, string prefix,
        string folder, ScientificL5Case test, JsonObject input)
    {
        var directory = Path.Combine(suite.Directory, folder);
        Directory.CreateDirectory(directory);
        var child = new ScientificJob { ProfileId = suite.ProfileId, RuntimeId = suite.RuntimeId,
            RecipeId = test.RecipeId, Directory = directory, Cancellation = suite.Cancellation };
        ScientificWriteRequest(child, JsonSerializer.SerializeToElement(new { caseId = folder }, ScientificJson), input, test.OutputName);
        var rejected = false;
        try
        {
            if (suite.RuntimeId == "cgal-win-conda") await ScientificCgalExecuteAsync(child, prefix, suite);
            else await ScientificProcessAsync(suite, prefix, Path.Combine(prefix, "python.exe"),
                [Path.Combine(ScientificSourceRoot, "tools", "scientific-mesh-worker.py"), "--request",
                    Path.Combine(directory, "request.json")], directory, 120);
        }
        catch (InvalidOperationException) when (test.ExpectedReason != null) { rejected = true; }
        var resultPath = Path.Combine(directory, "results.json");
        if (!File.Exists(resultPath) || new FileInfo(resultPath).Length > 1048576)
            throw new InvalidDataException("L5 case has no bounded worker result.");
        var result = JsonNode.Parse(File.ReadAllText(resultPath)) as JsonObject
            ?? throw new InvalidDataException("L5 worker result is invalid.");
        var requestHash = ScientificHash(Path.Combine(directory, "request.json"));
        var resultHash = ScientificHash(resultPath);
        if (test.ExpectedReason == null)
        {
            var output = ScientificArtifactFiles.Describe(directory, test.OutputName)
                ?? throw new InvalidDataException("Positive L5 output artifact is missing.");
            if (result["state"]?.GetValue<string>() != "succeeded"
                || result["validatedCapabilities"] is not JsonArray capabilities
                || !capabilities.Any(item => item?.GetValue<string>() == (suite.RuntimeId == "cgal-win-conda" ? "mesh.validate" : "mesh.read"))
                || result["artifacts"] is not JsonArray artifacts
                || !artifacts.Any(item => item?["path"]?.GetValue<string>() == test.OutputName
                    && item?["sha256"]?.GetValue<string>() == output["sha256"]?.GetValue<string>()))
                throw new InvalidDataException("Positive L5 worker verdict or output hash did not match.");
            return new JsonObject { ["caseId"] = "positive", ["recipeId"] = test.RecipeId,
                ["datasetId"] = test.DatasetId, ["inputSha256"] = input["sha256"]?.GetValue<string>(),
                ["requestSha256"] = requestHash, ["resultSha256"] = resultHash,
                ["state"] = "succeeded", ["artifactPath"] = "positive/" + test.OutputName,
                ["artifactSha256"] = output["sha256"]?.GetValue<string>() };
        }
        var diagnostic = string.Join("; ", result["diagnostics"]?.AsArray().OfType<JsonObject>()
            .Select(item => item["message"]?.GetValue<string>()) ?? Array.Empty<string?>());
        if (!rejected || result["state"]?.GetValue<string>() != "failed"
            || File.Exists(Path.Combine(directory, test.OutputName))
            || !diagnostic.Contains(test.ExpectedReason, StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("Expected L5 rejection or output absence was not observed.");
        return new JsonObject { ["caseId"] = "rejection", ["recipeId"] = test.RecipeId,
            ["datasetId"] = test.DatasetId, ["inputSha256"] = input["sha256"]?.GetValue<string>(),
            ["requestSha256"] = requestHash, ["resultSha256"] = resultHash,
            ["state"] = "failed", ["expectedReason"] = test.ExpectedReason,
            ["outputAbsent"] = true };
    }

    private async Task ScientificL5RunAsync(ScientificJob job, string prefix, string capability,
        ScientificL5Case positive, ScientificL5Case rejection, JsonObject positiveInput,
        JsonObject rejectionInput, JsonObject lower)
    {
        var timer = Stopwatch.StartNew();
        try
        {
            job.Stage = "positive";
            var passed = await ScientificL5CaseAsync(job, prefix, "positive", positive, positiveInput);
            job.Stage = "rejection";
            var rejected = await ScientificL5CaseAsync(job, prefix, "rejection", rejection, rejectionInput);
            var currentLower = ScientificCurrentLowerLevels(job.ProfileId, job.RuntimeId);
            if (currentLower.ToJsonString() != lower.ToJsonString())
                throw new InvalidOperationException("The pinned L0-L4 evidence is no longer current.");
            var contract = job.FingerprintComponents?["contract"];
            var evidence = new JsonObject { ["suiteId"] = "l5-worker-v1", ["capabilityId"] = capability,
                ["workerContractVersion"] = contract?["requestSchemaVersion"]?.GetValue<int>(),
                ["workerContractSha256"] = contract?["workerContractModule"]?["sha256"]?.GetValue<string>(),
                ["fixtureManifestSha256"] = ScientificHash(Path.Combine(ScientificDataRoot, "datasets", "manifest.json")),
                ["lowerQualification"] = lower.DeepClone(), ["positive"] = passed,
                ["rejection"] = rejected };
            File.WriteAllText(Path.Combine(job.Directory, "results.json"), new JsonObject
            {
                ["l5Evidence"] = evidence, ["validatedCapabilities"] = new JsonArray(capability)
            }.ToJsonString(), new UTF8Encoding(false));
            job.State = "succeeded"; job.Stage = "completed";
        }
        catch (OperationCanceledException) { job.State = "cancelled"; job.Error = "The owned L5 worker suite was stopped."; }
        catch (TimeoutException exception) { job.State = "timed-out"; job.Error = exception.Message; }
        catch (Exception exception) { job.State = "failed"; job.Error = exception.Message; }
        finally
        {
            job.DurationMs = timer.ElapsedMilliseconds;
            try { ScientificFinish(job); ScientificLog(job, $"\n[{job.State}] L5 worker suite / {job.DurationMs} ms {job.Error}\n"); }
            catch (Exception exception) { Debug.WriteLine($"L5 worker finalization failed: {exception}"); }
            finally { ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) }); _scientificGate.Release(); }
        }
    }
}
