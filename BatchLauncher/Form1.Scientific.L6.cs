using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace BatchLauncher;

public partial class Form1
{
    private static string ScientificL6Digest(JsonNode? value) => Convert.ToHexString(
        SHA256.HashData(Encoding.UTF8.GetBytes(value?.ToJsonString() ?? "null"))).ToLowerInvariant();

    private JsonObject ScientificCurrentL5(string profileId, string runtimeId, string capability, string evidenceId = "l5.worker")
    {
        var summary = ScientificQualificationSummary(profileId, runtimeId);
        var support = summary["currentRecords"]?.AsArray().OfType<JsonObject>()
            .Where(item => item["capabilityId"]?.GetValue<string>() == capability
                && item["level"]?.GetValue<string>() == "L5"
                && item["evidenceId"]?.GetValue<string>() == evidenceId)
            .OrderByDescending(item => item["finishedAtUtc"]?.GetValue<string>(), StringComparer.Ordinal)
            .FirstOrDefault();
        if (support == null) throw new InvalidOperationException($"A current {evidenceId} qualification is required before L6.");
        return new JsonObject { ["runId"] = support["runId"]?.GetValue<string>(),
            ["recordId"] = support["recordId"]?.GetValue<string>(), ["capabilityId"] = capability, ["level"] = "L5" };
    }

    private static void ScientificCheckL6Declaration(string runtimeId, string capability,
        string recipeId = "l6.reproduce", string referenceRecipe = "l5.worker")
    {
        var path = Path.Combine(AppContext.BaseDirectory, "runtimes", runtimeId, "runtime.json");
        if (!File.Exists(path) || new FileInfo(path).Length > 65536)
            throw new InvalidOperationException("L6 runtime manifest is unavailable.");
        var declaration = (JsonNode.Parse(File.ReadAllText(path))?["qualificationRecipes"] as JsonArray)?
            .OfType<JsonObject>().FirstOrDefault(item => item["id"]?.GetValue<string>() == recipeId);
        if (declaration?["readinessLevel"]?.GetValue<string>() != "L6"
            || declaration["capability"]?.GetValue<string>() != capability
            || declaration["referenceRecipe"]?.GetValue<string>() != referenceRecipe
            || declaration["comparison"]?.GetValue<string>() != "sha256-exact")
            throw new InvalidOperationException("L6 reproduction contract does not match the registered manifest.");
    }

    private static JsonObject ScientificL6Baseline(string profileId, string runtimeId, JsonObject support,
        string referenceRecipe = "l5.worker")
    {
        var runId = support["runId"]?.GetValue<string>() ?? "";
        var (directory, result) = ScientificHistoryFind(profileId, runId);
        var source = JsonNode.Parse(result.GetRawText()) as JsonObject
            ?? throw new InvalidDataException("L5 reference result is invalid.");
        var evidence = source["l5Evidence"] as JsonObject
            ?? throw new InvalidDataException("L5 reference evidence is missing.");
        var records = ScientificQualificationRecords.Verify(directory, result);
        if (source["runtimeId"]?.GetValue<string>() != runtimeId
            || source["recipeId"]?.GetValue<string>() != referenceRecipe
            || source["state"]?.GetValue<string>() != "succeeded"
            || !records.OfType<JsonObject>().Any(item => item["recordId"]?.GetValue<string>() == support["recordId"]?.GetValue<string>()
                && item["level"]?.GetValue<string>() == "L5"
                && item["evidenceId"]?.GetValue<string>() == referenceRecipe))
            throw new InvalidDataException("L5 reference record does not match its run.");
        var fingerprint = JsonNode.Parse(File.ReadAllText(Path.Combine(directory, "fingerprint.json")));
        return new JsonObject { ["runId"] = runId, ["folderId"] = Path.GetFileName(directory),
            ["recordId"] = support["recordId"]?.GetValue<string>(),
            ["evidenceId"] = referenceRecipe,
            ["runFingerprintSha256"] = source["runFingerprintSha256"]?.GetValue<string>(),
            ["artifactPath"] = evidence["positive"]?["artifactPath"]?.GetValue<string>(),
            ["artifactSha256"] = evidence["positive"]?["artifactSha256"]?.GetValue<string>(),
            ["positiveInputSha256"] = evidence["positive"]?["inputSha256"]?.GetValue<string>(),
            ["rejectionInputSha256"] = evidence["rejection"]?["inputSha256"]?.GetValue<string>(),
            ["workerContractSha256"] = evidence["workerContractSha256"]?.GetValue<string>(),
            ["environmentSha256"] = ScientificL6Digest(fingerprint?["components"]?["environment"]) };
    }

    private object ScientificL6Start(string profileId, string runtimeId) => ScientificL6StartCore(profileId, runtimeId, false);

    private object ScientificL6OrientationStart(string profileId, string runtimeId) => ScientificL6StartCore(profileId, runtimeId, true);

    private object ScientificL6StartCore(string profileId, string runtimeId, bool orientation)
    {
        ScientificProviderRegistry.RequireAction(runtimeId, orientation ? "l6-cgal-orientation" : "l6-reproduce");
        if (orientation && runtimeId != "cgal-win-conda") throw new InvalidOperationException("CGAL is required for orientation reproduction.");
        var (capability, positive, rejection) = orientation
            ? ("mesh.repair", new ScientificL5Case("cgal.repair-orientation", "cgal/inward-tetra.obj", "l5-repaired.obj", null),
                new ScientificL5Case("cgal.repair-orientation", "cgal/open-square.obj", "l5-rejected.obj", "requires a closed mesh"))
            : ScientificL5Cases(runtimeId);
        var l5Recipe = orientation ? "l5.cgal-orientation" : "l5.worker";
        var l6Recipe = orientation ? "l6.cgal-orientation" : "l6.reproduce";
        ScientificCheckL5Declaration(runtimeId, capability, positive, rejection, l5Recipe);
        ScientificCheckL6Declaration(runtimeId, capability, l6Recipe, l5Recipe);
        var lower = ScientificCurrentLowerLevels(profileId, runtimeId);
        var support = ScientificCurrentL5(profileId, runtimeId, capability, l5Recipe);
        var baseline = ScientificL6Baseline(profileId, runtimeId, support, l5Recipe);
        var positiveInput = ScientificDatasetArtifact(positive.DatasetId);
        var rejectionInput = ScientificDatasetArtifact(rejection.DatasetId);
        var prefix = ScientificPrefix(runtimeId);
        if (!_scientificGate.Wait(0)) throw new InvalidOperationException("Another Scientific job is running; stop or wait for it.");
        try
        {
            var directory = Path.Combine(ScientificDataRoot, "runs", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(directory);
            var job = new ScientificJob { ProfileId = profileId, RuntimeId = runtimeId,
                RecipeId = l6Recipe, Directory = directory };
            var parameters = JsonSerializer.SerializeToElement(new { suiteId = orientation ? "l6-cgal-orientation-v1" : "l6-reproduce-v1",
                baselineRunId = baseline["runId"]?.GetValue<string>(), baselineRecordId = baseline["recordId"]?.GetValue<string>(),
                positiveCase = positive.DatasetId, rejectionCase = rejection.DatasetId }, ScientificJson);
            ScientificWriteRequest(job, parameters, positiveInput, additionalInputs: new JsonArray(rejectionInput.DeepClone()),
                additionalOutputs: new JsonArray(new JsonObject { ["path"] = "positive/" + positive.OutputName,
                    ["mediaType"] = ScientificMediaType(positive.OutputName) },
                    new JsonObject { ["path"] = "reload/results.json", ["mediaType"] = "application/json" }));
            _scientificJobs[profileId + ":" + runtimeId] = job;
            ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) });
            _ = ScientificL6RunAsync(job, prefix, capability, positive, rejection, positiveInput, rejectionInput, lower, support, baseline, orientation);
            return ScientificJobSnapshot(job);
        }
        catch { _scientificGate.Release(); throw; }
    }

    private async Task ScientificL6RunAsync(ScientificJob job, string prefix, string capability,
        ScientificL5Case positive, ScientificL5Case rejection, JsonObject positiveInput,
        JsonObject rejectionInput, JsonObject lower, JsonObject support, JsonObject baseline, bool orientation)
    {
        var timer = Stopwatch.StartNew();
        try
        {
            job.Stage = "positive";
            var passed = await ScientificL5CaseAsync(job, prefix, "positive", positive, positiveInput, capability);
            job.Stage = "rejection";
            var rejected = await ScientificL5CaseAsync(job, prefix, "rejection", rejection, rejectionInput, capability);
            job.Stage = "reload";
            var reloadDirectory = Path.Combine(job.Directory, "reload");
            Directory.CreateDirectory(reloadDirectory);
            var reloadResult = Path.Combine(reloadDirectory, "results.json");
            var reloadTool = job.RuntimeId == "gmsh-win-conda"
                ? "scientific-gmsh-roundtrip.py" : "scientific-artifact-roundtrip.py";
            await ScientificProcessAsync(job, prefix, Path.Combine(prefix, "python.exe"),
                [Path.Combine(ScientificSourceRoot, "tools", reloadTool),
                    "--input", Path.Combine(job.Directory, "positive", positive.OutputName),
                    "--result", reloadResult], reloadDirectory, 60);
            var reloaded = JsonNode.Parse(File.ReadAllText(reloadResult)) as JsonObject
                ?? throw new InvalidDataException("Independent artifact reload did not return a result.");
            var reloadHash = ScientificHash(reloadResult);
            var contract = job.FingerprintComponents?["contract"];
            var currentEnvironment = ScientificL6Digest(job.FingerprintComponents?["environment"]);
            var matched = passed["artifactSha256"]?.GetValue<string>() == baseline["artifactSha256"]?.GetValue<string>()
                && passed["artifactPath"]?.GetValue<string>() == baseline["artifactPath"]?.GetValue<string>()
                && passed["inputSha256"]?.GetValue<string>() == baseline["positiveInputSha256"]?.GetValue<string>()
                && rejected["inputSha256"]?.GetValue<string>() == baseline["rejectionInputSha256"]?.GetValue<string>()
                && contract?["workerContractModule"]?["sha256"]?.GetValue<string>() == baseline["workerContractSha256"]?.GetValue<string>()
                && currentEnvironment == baseline["environmentSha256"]?.GetValue<string>()
                && (orientation
                    ? ScientificQualificationRecords.ValidOrientationRoundTrip(reloaded,
                        passed["artifactSha256"]?.GetValue<string>(),
                        job.FingerprintComponents?["suite"]?["files"]?["tools/" + reloadTool]?["sha256"]?.GetValue<string>())
                    : ScientificQualificationRecords.ValidRoundTrip(reloaded, job.RuntimeId,
                        passed["artifactSha256"]?.GetValue<string>(),
                        job.FingerprintComponents?["suite"]?["files"]?["tools/" + reloadTool]?["sha256"]?.GetValue<string>()));
            var currentLower = ScientificCurrentLowerLevels(job.ProfileId, job.RuntimeId);
            var currentL5 = ScientificCurrentL5(job.ProfileId, job.RuntimeId, capability,
                orientation ? "l5.cgal-orientation" : "l5.worker");
            if (currentLower.ToJsonString() != lower.ToJsonString()
                || currentL5["recordId"]?.GetValue<string>() != support["recordId"]?.GetValue<string>())
                throw new InvalidOperationException("The pinned L0-L5 evidence is no longer current.");
            var lowerRecords = (JsonArray)lower["records"]!.DeepClone();
            lowerRecords.Add(support.DeepClone());
            var l5Evidence = new JsonObject { ["suiteId"] = orientation ? "l5-cgal-orientation-v1" : "l5-worker-v1", ["capabilityId"] = capability,
                ["workerContractVersion"] = contract?["requestSchemaVersion"]?.GetValue<int>(),
                ["workerContractSha256"] = contract?["workerContractModule"]?["sha256"]?.GetValue<string>(),
                ["fixtureManifestSha256"] = ScientificHash(orientation
                    ? Path.Combine(ScientificSourceRoot, "scientific", "fixtures", "cgal", "orientation", "manifest.v1.json")
                    : Path.Combine(ScientificDataRoot, "datasets", "manifest.json")),
                ["lowerQualification"] = lower.DeepClone(), ["positive"] = passed.DeepClone(), ["rejection"] = rejected.DeepClone() };
            var comparison = new JsonObject { ["suiteId"] = orientation ? "l6-cgal-orientation-v1" : "l6-reproduce-v1", ["capabilityId"] = capability,
                ["comparison"] = "sha256-exact", ["verdict"] = matched ? "matched" : "mismatch",
                ["baseline"] = baseline.DeepClone(), ["positive"] = passed.DeepClone(), ["rejection"] = rejected.DeepClone(),
                ["environmentSha256"] = currentEnvironment, ["roundTrip"] = reloaded.DeepClone(),
                ["roundTripResultSha256"] = reloadHash,
                ["lowerQualification"] = new JsonObject { ["records"] = lowerRecords } };
            File.WriteAllText(Path.Combine(job.Directory, "results.json"), new JsonObject
            {
                ["l5Evidence"] = l5Evidence, ["l6Evidence"] = comparison,
                ["validatedCapabilities"] = matched ? new JsonArray(capability) : new JsonArray()
            }.ToJsonString(), new UTF8Encoding(false));
            job.State = matched ? "succeeded" : "failed";
            job.Error = matched ? null : "The new worker artifact hash or fixed-case evidence differs from the L5 reference run.";
            job.Stage = "completed";
        }
        catch (OperationCanceledException) { job.State = "cancelled"; job.Error = "The owned L6 reproduction suite was stopped."; }
        catch (TimeoutException exception) { job.State = "timed-out"; job.Error = exception.Message; }
        catch (Exception exception) { job.State = "failed"; job.Error = exception.Message; }
        finally
        {
            job.DurationMs = timer.ElapsedMilliseconds;
            try { ScientificFinish(job); ScientificLog(job, $"\n[{job.State}] L6 reproduction suite / {job.DurationMs} ms {job.Error}\n"); }
            catch (Exception exception) { Debug.WriteLine($"L6 reproduction finalization failed: {exception}"); }
            finally { ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) }); _scientificGate.Release(); }
        }
    }
}
