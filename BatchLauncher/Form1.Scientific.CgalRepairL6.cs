using System.Diagnostics;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace BatchLauncher;

public partial class Form1
{
    private object ScientificCgalRepairL6Start(string profileId, string runtimeId)
    {
        ScientificProviderRegistry.RequireAction(runtimeId, "l6-cgal-repair");
        var prefix = ScientificPrefix(runtimeId);
        var support = ScientificCurrentL5(profileId, runtimeId, "mesh.repair", "l5.cgal-repair");
        var baselineRunId = support["runId"]!.GetValue<string>();
        var (baselineDirectory, saved) = ScientificHistoryFind(profileId, baselineRunId);
        var baseline = JsonNode.Parse(saved.GetRawText()) as JsonObject
            ?? throw new InvalidDataException("Repair L5 reference result is invalid.");
        var baselineRecords = ScientificQualificationRecords.Verify(baselineDirectory, saved);
        if (baseline["recipeId"]?.GetValue<string>() != "l5.cgal-repair"
            || baseline["repairQualificationEvidence"] is not JsonObject baselineEvidence
            || !baselineRecords.OfType<JsonObject>().Any(item => item["recordId"]?.GetValue<string>() == support["recordId"]?.GetValue<string>()
                && item["capabilityId"]?.GetValue<string>() == "mesh.repair" && item["level"]?.GetValue<string>() == "L5"))
            throw new InvalidDataException("Current repair L5 reference does not match its saved run.");
        // The L5 run itself issues a fresh L0 inventory record. Keep its verified
        // pinned L0-L4 support instead of selecting a different, newer L0 record.
        var lower5 = baselineEvidence["lowerQualification"] as JsonObject;
        if (lower5?["records"] is not JsonArray { Count: 5 })
            throw new InvalidDataException("Repair L5 lower support is incomplete.");
        lower5 = (JsonObject)lower5.DeepClone();
        var lower = (JsonArray)lower5["records"]!.DeepClone();
        lower.Add(support.DeepClone());
        var declarationPath = Path.Combine(AppContext.BaseDirectory, "runtimes", runtimeId, "runtime.json");
        var declaration = JsonNode.Parse(File.ReadAllText(declarationPath))?["qualificationRecipes"]?.AsArray()
            .OfType<JsonObject>().SingleOrDefault(item => item["id"]?.GetValue<string>() == "l6.cgal-repair");
        if (declaration?["capability"]?.GetValue<string>() != "mesh.repair"
            || declaration["readinessLevel"]?.GetValue<string>() != "L6"
            || declaration["referenceRecipe"]?.GetValue<string>() != "l5.cgal-repair"
            || declaration["comparison"]?.GetValue<string>() != "sha256-exact")
            throw new InvalidOperationException("Repair L6 reproduction is not declared by this runtime.");
        var fixtureManifest = ScientificRepairFixtures.Manifest(ScientificSourceRoot);
        var inputs = RepairL5Cases.Select(test => (Test: test,
            Input: ScientificDatasetArtifact(ScientificRepairFixtures.Dataset(ScientificSourceRoot, ScientificDataRoot, test.Fixture)["id"]!.GetValue<string>())))
            .ToArray();
        if (!_scientificGate.Wait(0)) throw new InvalidOperationException("A Scientific recipe is already running.");
        try
        {
            var directory = Path.Combine(ScientificDataRoot, "runs", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(directory);
            var job = new ScientificJob { ProfileId = profileId, RuntimeId = runtimeId,
                RecipeId = "l6.cgal-repair", Directory = directory };
            var parameters = JsonSerializer.SerializeToElement(new { baselineRunId,
                baselineRecordId = support["recordId"]?.GetValue<string>(), comparison = "sha256-exact" }, ScientificJson);
            var uniqueInputs = inputs.Select(item => item.Input).DistinctBy(item => item["datasetId"]?.GetValue<string>()).ToArray();
            var outputs = new JsonArray(RepairL5Cases.Where(item => item.Positive)
                .Select(item => (JsonNode)new JsonObject { ["path"] = $"cases/{item.Id}/repaired.obj", ["mediaType"] = "model/obj" }).ToArray());
            outputs.Add(new JsonObject { ["path"] = "fixture-manifest.json", ["mediaType"] = "application/json" });
            outputs.Add(new JsonObject { ["path"] = "repair-l5-evidence.json", ["mediaType"] = "application/json" });
            ScientificWriteRequest(job, parameters, uniqueInputs[0], "repair-l6-evidence.json",
                new JsonArray(uniqueInputs.Skip(1).Select(item => (JsonNode)item.DeepClone()).ToArray()), outputs);
            _scientificJobs[profileId + ":" + runtimeId] = job;
            ScientificSend(new { type = "scientific.runtime.job", profileId, job = ScientificJobSnapshot(job) });
            _ = ScientificCgalRepairL6RunAsync(job, prefix, inputs, lower5, new JsonObject { ["records"] = lower },
                fixtureManifest, baselineDirectory, baseline, baselineEvidence, support);
            return ScientificJobSnapshot(job);
        }
        catch { _scientificGate.Release(); throw; }
    }

    private async Task ScientificCgalRepairL6RunAsync(ScientificJob job, string prefix,
        (RepairL5Case Test, JsonObject Input)[] inputs, JsonObject lower5, JsonObject lower6,
        JsonObject fixtureManifest, string baselineDirectory, JsonObject baseline,
        JsonObject baselineEvidence, JsonObject support)
    {
        var timer = Stopwatch.StartNew();
        try
        {
            File.Copy(Path.Combine(ScientificSourceRoot,
                ScientificRepairFixtures.ManifestPath.Replace('/', Path.DirectorySeparatorChar)),
                Path.Combine(job.Directory, "fixture-manifest.json"));
            var cases = new JsonArray();
            foreach (var (test, input) in inputs)
            {
                job.Cancellation.Token.ThrowIfCancellationRequested();
                job.Stage = test.Id;
                cases.Add(await ScientificCgalRepairL5CaseAsync(job, prefix, test, input));
            }
            var reference = baselineEvidence["cases"]!.AsArray();
            for (var i = 0; i < cases.Count; i++)
            {
                var expected = reference[i]; var actual = cases[i];
                if (actual?["caseId"]?.GetValue<string>() != expected?["caseId"]?.GetValue<string>()
                    || actual?["recipeId"]?.GetValue<string>() != expected?["recipeId"]?.GetValue<string>()
                    || actual?["inputSha256"]?.GetValue<string>() != expected?["inputSha256"]?.GetValue<string>()
                    || actual?["state"]?.GetValue<string>() != expected?["state"]?.GetValue<string>()
                    || actual?["artifactSha256"]?.GetValue<string>() != expected?["artifactSha256"]?.GetValue<string>()
                    || actual?["patchSha256"]?.GetValue<string>() != expected?["patchSha256"]?.GetValue<string>()
                    || actual?["outputAbsent"]?.ToJsonString() != expected?["outputAbsent"]?.ToJsonString())
                    throw new InvalidDataException("Repair output or rejection differs from the L5 reference.");
            }
            if (ScientificCurrentL5(job.ProfileId, job.RuntimeId, "mesh.repair", "l5.cgal-repair")["recordId"]?.GetValue<string>()
                    != support["recordId"]?.GetValue<string>())
                throw new InvalidOperationException("Pinned repair L0-L5 evidence is no longer current.");
            var candidateL5 = new JsonObject { ["suiteId"] = ScientificRepairFixtures.SuiteId,
                ["capabilityId"] = "mesh.repair", ["fixtureManifestSha256"] = ScientificHash(Path.Combine(ScientificSourceRoot,
                    ScientificRepairFixtures.ManifestPath.Replace('/', Path.DirectorySeparatorChar))),
                ["fixtureSuite"] = fixtureManifest["suiteId"]?.GetValue<string>(),
                ["lowerQualification"] = lower5.DeepClone(), ["cases"] = cases.DeepClone() };
            File.WriteAllText(Path.Combine(job.Directory, "repair-l5-evidence.json"), candidateL5.ToJsonString(), new UTF8Encoding(false));
            var evidence = new JsonObject { ["suiteId"] = "cgal-repair-reproduce-v1",
                ["capabilityId"] = "mesh.repair", ["comparison"] = "sha256-exact", ["verdict"] = "matched",
                ["baseline"] = new JsonObject { ["runId"] = baseline["runId"]?.GetValue<string>(),
                    ["folderId"] = Path.GetFileName(baselineDirectory),
                    ["recordId"] = support["recordId"]?.GetValue<string>(),
                    ["runFingerprintSha256"] = baseline["runFingerprintSha256"]?.GetValue<string>(),
                    ["casesSha256"] = ScientificL6Digest(reference) },
                ["candidateL5EvidenceSha256"] = ScientificL6Digest(candidateL5),
                ["lowerQualification"] = lower6.DeepClone(), ["cases"] = cases.DeepClone() };
            File.WriteAllText(Path.Combine(job.Directory, "repair-l6-evidence.json"), evidence.ToJsonString(), new UTF8Encoding(false));
            File.WriteAllText(Path.Combine(job.Directory, "results.json"), new JsonObject
            {
                ["repairQualificationEvidence"] = candidateL5.DeepClone(),
                ["repairReproductionEvidence"] = evidence,
                ["validatedCapabilities"] = new JsonArray("mesh.repair")
            }.ToJsonString(), new UTF8Encoding(false));
            job.State = "succeeded"; job.Stage = "completed";
        }
        catch (OperationCanceledException) { job.State = "cancelled"; job.Error = "Only this repair reproduction was stopped."; }
        catch (TimeoutException error) { job.State = "timed-out"; job.Error = error.Message; }
        catch (Exception error) { job.State = "failed"; job.Error = error.Message; }
        finally
        {
            job.DurationMs = timer.ElapsedMilliseconds;
            try { ScientificFinish(job); ScientificLog(job, $"\n[{job.State}] repair L6 reproduction / {job.DurationMs} ms {job.Error}\n"); }
            catch (Exception error) { Debug.WriteLine($"Repair L6 finalization failed: {error}"); }
            finally { ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) }); _scientificGate.Release(); }
        }
    }
}
