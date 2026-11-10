using System.Diagnostics;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace BatchLauncher;

public partial class Form1
{
    private sealed record RepairL5Case(string Id, string Fixture, string Recipe, bool Positive,
        int Loops, int Edges, int Patches, string? RejectionReason);

    private static readonly RepairL5Case[] RepairL5Cases =
    [
        new("triangle", "triangle", "cgal.fill-one-hole", true, 1, 3, 1, null),
        new("square", "square", "cgal.fill-quad-hole", true, 1, 4, 2, null),
        new("two-squares", "two-squares", "cgal.fill-two-quad-holes", true, 2, 8, 4, null),
        new("pentagon", "pentagon", "cgal.fill-bounded-holes", true, 1, 5, 3, null),
        new("closed-rejection", "closed-rejection", "cgal.fill-bounded-holes", false, 0, 0, 0, "Bounded repair requires"),
        new("wrong-operation", "triangle", "cgal.fill-quad-hole", false, 1, 3, 0, "selected boundary-loop scope")
    ];

    private object ScientificCgalRepairL5Start(string profileId, string runtimeId)
    {
        ScientificProviderRegistry.RequireAction(runtimeId, "l5-cgal-repair");
        var prefix = ScientificPrefix(runtimeId);
        var lower = ScientificCurrentLowerLevels(profileId, runtimeId);
        var fixtureManifest = ScientificRepairFixtures.Manifest(ScientificSourceRoot);
        var declarationPath = Path.Combine(AppContext.BaseDirectory, "runtimes", runtimeId, "runtime.json");
        var declaration = JsonNode.Parse(File.ReadAllText(declarationPath))?["qualificationRecipes"]?.AsArray()
            .OfType<JsonObject>().SingleOrDefault(item => item["id"]?.GetValue<string>() == "l5.cgal-repair");
        if (declaration?["capability"]?.GetValue<string>() != "mesh.repair"
            || declaration["readinessLevel"]?.GetValue<string>() != "L5"
            || declaration["suiteId"]?.GetValue<string>() != ScientificRepairFixtures.SuiteId)
            throw new InvalidOperationException("Repair L5 suite is not declared by this runtime.");
        var inputs = RepairL5Cases.Select(test => (Test: test,
            Input: ScientificDatasetArtifact(ScientificRepairFixtures.Dataset(ScientificSourceRoot, ScientificDataRoot, test.Fixture)["id"]!.GetValue<string>())))
            .ToArray();
        if (!_scientificGate.Wait(0)) throw new InvalidOperationException("A Scientific recipe is already running.");
        try
        {
            var directory = Path.Combine(ScientificDataRoot, "runs", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(directory);
            var job = new ScientificJob { ProfileId = profileId, RuntimeId = runtimeId,
                RecipeId = "l5.cgal-repair", Directory = directory };
            var parameters = JsonSerializer.SerializeToElement(new { suiteId = ScientificRepairFixtures.SuiteId,
                lowerRecords = lower["records"]?.DeepClone() }, ScientificJson);
            var uniqueInputs = inputs.Select(item => item.Input).DistinctBy(item => item["datasetId"]?.GetValue<string>()).ToArray();
            var outputs = new JsonArray(RepairL5Cases.Where(item => item.Positive)
                .Select(item => (JsonNode)new JsonObject { ["path"] = $"cases/{item.Id}/repaired.obj", ["mediaType"] = "model/obj" }).ToArray());
            ScientificWriteRequest(job, parameters, uniqueInputs[0], "repair-l5-evidence.json",
                new JsonArray(uniqueInputs.Skip(1).Select(item => (JsonNode)item.DeepClone()).ToArray()), outputs);
            _scientificJobs[profileId + ":" + runtimeId] = job;
            ScientificSend(new { type = "scientific.runtime.job", profileId, job = ScientificJobSnapshot(job) });
            _ = ScientificCgalRepairL5RunAsync(job, prefix, inputs, lower, fixtureManifest);
            return ScientificJobSnapshot(job);
        }
        catch { _scientificGate.Release(); throw; }
    }

    private async Task<JsonObject> ScientificCgalRepairL5CaseAsync(ScientificJob suite, string prefix,
        RepairL5Case test, JsonObject input)
    {
        var directory = Path.Combine(suite.Directory, "cases", test.Id);
        Directory.CreateDirectory(directory);
        var child = new ScientificJob { ProfileId = suite.ProfileId, RuntimeId = suite.RuntimeId,
            RecipeId = test.Recipe, Directory = directory, Cancellation = suite.Cancellation };
        var output = "repaired.obj";
        var parameters = JsonSerializer.SerializeToElement(new { inputId = input["datasetId"]!.GetValue<string>(), outputName = output });
        ScientificWriteRequest(child, parameters, input, output);
        var rejected = false;
        try { await ScientificCgalExecuteAsync(child, prefix, suite); }
        catch (InvalidOperationException) when (!test.Positive) { rejected = true; }
        var resultPath = Path.Combine(directory, "results.json");
        if (!File.Exists(resultPath) || new FileInfo(resultPath).Length > 1048576)
            throw new InvalidDataException($"Repair case {test.Id} has no bounded worker result.");
        var result = JsonNode.Parse(File.ReadAllText(resultPath)) as JsonObject
            ?? throw new InvalidDataException($"Repair case {test.Id} result is invalid.");
        var record = new JsonObject { ["caseId"] = test.Id, ["recipeId"] = test.Recipe,
            ["datasetId"] = input["datasetId"]?.GetValue<string>(), ["inputSha256"] = input["sha256"]?.GetValue<string>(),
            ["requestSha256"] = ScientificHash(Path.Combine(directory, "request.json")),
            ["resultSha256"] = ScientificHash(resultPath), ["state"] = result["state"]?.GetValue<string>() };
        if (test.Positive)
        {
            var artifact = ScientificArtifactFiles.Describe(directory, output)
                ?? throw new InvalidDataException($"Repair case {test.Id} has no OBJ output.");
            if (result["state"]?.GetValue<string>() != "succeeded"
                || result["validatedCapabilities"] is not JsonArray capabilities
                || !capabilities.Any(item => item?.GetValue<string>() == "mesh.repair")
                || result["repairEvidence"]?["holesFilled"]?.GetValue<int>() != test.Loops
                || result["repairEvidence"]?["boundaryEdgesBefore"]?.GetValue<int>() != test.Edges
                || result["repairAudit"]?["addedFaces"]?.GetValue<int>() != test.Patches
                || result["repairAudit"]?["boundaryEdgesCovered"]?.GetValue<int>() != test.Edges
                || result["artifacts"] is not JsonArray artifacts
                || !artifacts.Any(item => item?["path"]?.GetValue<string>() == output
                    && item?["sha256"]?.GetValue<string>() == artifact["sha256"]?.GetValue<string>()))
                throw new InvalidDataException($"Repair case {test.Id} failed its geometry or audit contract.");
            record["artifactPath"] = $"cases/{test.Id}/{output}";
            record["artifactSha256"] = artifact["sha256"]?.GetValue<string>();
            record["patchSha256"] = result["repairAudit"]?["patchSha256"]?.GetValue<string>();
        }
        else
        {
            var diagnostic = string.Join("; ", result["diagnostics"]?.AsArray().OfType<JsonObject>()
                .Select(item => item["message"]?.GetValue<string>()) ?? Array.Empty<string?>());
            if (!rejected || result["state"]?.GetValue<string>() != "failed"
                || File.Exists(Path.Combine(directory, output))
                || !diagnostic.Contains(test.RejectionReason!, StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException($"Repair case {test.Id} did not reject without output.");
            record["outputAbsent"] = true;
            record["expectedReason"] = test.RejectionReason;
        }
        return record;
    }

    private async Task ScientificCgalRepairL5RunAsync(ScientificJob job, string prefix,
        (RepairL5Case Test, JsonObject Input)[] inputs, JsonObject lower, JsonObject fixtureManifest)
    {
        var timer = Stopwatch.StartNew();
        try
        {
            var cases = new JsonArray();
            foreach (var (test, input) in inputs)
            {
                job.Cancellation.Token.ThrowIfCancellationRequested();
                job.Stage = test.Id;
                cases.Add(await ScientificCgalRepairL5CaseAsync(job, prefix, test, input));
            }
            if (ScientificCurrentLowerLevels(job.ProfileId, job.RuntimeId).ToJsonString() != lower.ToJsonString())
                throw new InvalidOperationException("Pinned L0-L4 repair support is no longer current.");
            var evidence = new JsonObject { ["suiteId"] = ScientificRepairFixtures.SuiteId,
                ["capabilityId"] = "mesh.repair", ["fixtureManifestSha256"] = ScientificHash(Path.Combine(ScientificSourceRoot,
                    ScientificRepairFixtures.ManifestPath.Replace('/', Path.DirectorySeparatorChar))),
                ["fixtureSuite"] = fixtureManifest["suiteId"]?.GetValue<string>(),
                ["lowerQualification"] = lower.DeepClone(), ["cases"] = cases };
            File.WriteAllText(Path.Combine(job.Directory, "repair-l5-evidence.json"), evidence.ToJsonString(), new UTF8Encoding(false));
            File.WriteAllText(Path.Combine(job.Directory, "results.json"), new JsonObject
            {
                ["repairQualificationEvidence"] = evidence.DeepClone(),
                ["validatedCapabilities"] = new JsonArray("mesh.repair")
            }.ToJsonString(), new UTF8Encoding(false));
            job.State = "succeeded"; job.Stage = "completed";
        }
        catch (OperationCanceledException) { job.State = "cancelled"; job.Error = "Only this repair suite was stopped."; }
        catch (TimeoutException error) { job.State = "timed-out"; job.Error = error.Message; }
        catch (Exception error) { job.State = "failed"; job.Error = error.Message; }
        finally
        {
            job.DurationMs = timer.ElapsedMilliseconds;
            try { ScientificFinish(job); ScientificLog(job, $"\n[{job.State}] repair L5 suite / {job.DurationMs} ms {job.Error}\n"); }
            catch (Exception error) { Debug.WriteLine($"Repair L5 finalization failed: {error}"); }
            finally { ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) }); _scientificGate.Release(); }
        }
    }
}
