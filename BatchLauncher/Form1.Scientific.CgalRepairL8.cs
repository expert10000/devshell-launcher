using System.Diagnostics;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace BatchLauncher;

public partial class Form1
{
    private static void ScientificCheckRepairL8Declaration()
    {
        var path = Path.Combine(AppContext.BaseDirectory, "runtimes", "cgal-win-conda", "runtime.json");
        var declaration = (JsonNode.Parse(File.ReadAllText(path))?["qualificationRecipes"] as JsonArray)?
            .OfType<JsonObject>().SingleOrDefault(item => item["id"]?.GetValue<string>() == "l8.cgal-repair");
        if (declaration?["readinessLevel"]?.GetValue<string>() != "L8"
            || declaration["capability"]?.GetValue<string>() != "mesh.repair"
            || declaration["referenceRecipe"]?.GetValue<string>() != "l7.cgal-repair"
            || declaration["repeatCount"]?.GetValue<int>() != 3
            || declaration["memoryLimitBytes"]?.GetValue<long>() != 134217728)
            throw new InvalidOperationException("The repair L8 resilience suite is not declared.");
    }

    private object ScientificCgalRepairL8Start(string profileId, string runtimeId)
    {
        ScientificProviderRegistry.RequireAction(runtimeId, "l8-cgal-repair");
        ScientificCheckRepairL8Declaration();
        var support = ScientificCurrentRepairLevel(profileId, "L7");
        var (l7Directory, saved) = ScientificHistoryFind(profileId, support["runId"]!.GetValue<string>());
        var l7 = JsonNode.Parse(saved.GetRawText()) as JsonObject;
        var evidence = l7?["repairInteropEvidence"] as JsonObject;
        if (l7?["runtimeId"]?.GetValue<string>() != runtimeId
            || l7["recipeId"]?.GetValue<string>() != "l7.cgal-repair"
            || l7["state"]?.GetValue<string>() != "succeeded"
            || evidence?["cases"] is not JsonArray cases || cases.Count != 4
            || !ScientificQualificationRecords.Verify(l7Directory, saved).OfType<JsonObject>().Any(item =>
                item["recordId"]?.GetValue<string>() == support["recordId"]?.GetValue<string>()
                && item["capabilityId"]?.GetValue<string>() == "mesh.repair" && item["level"]?.GetValue<string>() == "L7"))
            throw new InvalidDataException("The repair L7 consumer record does not verify.");
        var l6RunId = evidence["source"]?["runId"]?.GetValue<string>() ?? "";
        var (l6Directory, l6Saved) = ScientificHistoryFind(profileId, l6RunId);
        var selected = RepairL5Cases.Where(item => item.Positive).Select((test, index) =>
        {
            var entry = cases[index] as JsonObject ?? throw new InvalidDataException("A repair L7 case is missing.");
            var relative = entry["artifactPath"]?.GetValue<string>() ?? "";
            if (entry["caseId"]?.GetValue<string>() != test.Id || relative != $"cases/{test.Id}/repaired.obj")
                throw new InvalidDataException("The repair L7 case order changed.");
            var path = ScientificArtifactFiles.ResolveRegistered(l6Directory, l6Saved, relative);
            var hash = ScientificHash(path);
            if (hash != entry["artifactSha256"]?.GetValue<string>())
                throw new InvalidDataException("A repair L7 source output changed.");
            return (test.Id, Path: path, Hash: hash, Bytes: new FileInfo(path).Length,
                Vtk: (JsonObject)entry["vtkConsumer"]!.DeepClone());
        }).ToArray();
        var vtkPrefix = ScientificPrefix("vtk-win-conda");
        var vtkPython = Path.Combine(vtkPrefix, "python.exe");
        if (!File.Exists(vtkPython)) throw new InvalidOperationException("The VTK Python environment is unavailable.");
        if (!_scientificGate.Wait(0)) throw new InvalidOperationException("A Scientific recipe is already running.");
        try
        {
            var directory = Path.Combine(ScientificDataRoot, "runs", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(directory);
            var job = new ScientificJob { ProfileId = profileId, RuntimeId = runtimeId,
                RecipeId = "l8.cgal-repair", Directory = directory };
            var inputs = selected.Select(item => new JsonObject { ["path"] = item.Path, ["mediaType"] = "model/obj",
                ["bytes"] = item.Bytes, ["sha256"] = item.Hash, ["sourceRunId"] = l6RunId }).ToArray();
            var outputs = new JsonArray();
            foreach (var item in selected)
                for (var repeat = 1; repeat <= 3; repeat++)
                    outputs.Add(new JsonObject { ["path"] = $"resilience/{item.Id}/repeat-{repeat}.json",
                        ["mediaType"] = "application/json" });
            outputs.Add(new JsonObject { ["path"] = "resilience/observations.json", ["mediaType"] = "application/json" });
            var parameters = JsonSerializer.SerializeToElement(new { suiteId = "cgal-repair-resilience-v1",
                sourceL7RunId = support["runId"]?.GetValue<string>(), sourceL7RecordId = support["recordId"]?.GetValue<string>(),
                repeatCount = 3, memoryLimitBytes = 134217728 }, ScientificJson);
            ScientificWriteRequest(job, parameters, inputs[0], "repair-l8-evidence.json",
                new JsonArray(inputs.Skip(1).Select(item => (JsonNode)item.DeepClone()).ToArray()), outputs);
            _scientificJobs[profileId + ":" + runtimeId] = job;
            ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) });
            _ = ScientificCgalRepairL8RunAsync(job, vtkPrefix, vtkPython, l7Directory, evidence, selected, support, l6RunId);
            return ScientificJobSnapshot(job);
        }
        catch { _scientificGate.Release(); throw; }
    }

    private async Task ScientificCgalRepairL8RunAsync(ScientificJob job, string vtkPrefix, string vtkPython,
        string l7Directory, JsonObject l7Evidence,
        (string Id, string Path, string Hash, long Bytes, JsonObject Vtk)[] selected,
        JsonObject support, string l6RunId)
    {
        var timer = Stopwatch.StartNew();
        try
        {
            const long limit = 134217728;
            var tool = Path.Combine(ScientificSourceRoot, "tools", "scientific-vtk-interop.py");
            var root = Path.Combine(job.Directory, "resilience");
            Directory.CreateDirectory(root);
            var repeats = new JsonArray();
            foreach (var item in selected)
            {
                var caseDirectory = Path.Combine(root, item.Id);
                Directory.CreateDirectory(caseDirectory);
                for (var index = 1; index <= 3; index++)
                {
                    job.Cancellation.Token.ThrowIfCancellationRequested();
                    job.Stage = $"{item.Id}/repeat-{index}";
                    var output = Path.Combine(caseDirectory, $"repeat-{index}.json");
                    long peak = 0;
                    var step = Stopwatch.StartNew();
                    await ScientificProcessAsync(job, vtkPrefix, vtkPython,
                        [tool, "--input", item.Path, "--result", output], caseDirectory, 60,
                        memoryLimitBytes: limit, peakMemory: value => peak = value);
                    var report = JsonNode.Parse(File.ReadAllText(output)) as JsonObject
                        ?? throw new InvalidDataException("The repeated VTK repair report is invalid.");
                    if (!ScientificQualificationRecords.ValidRepairRepeat(item.Vtk, report, item.Hash, ScientificHash(tool)))
                        throw new InvalidDataException($"Repair case {item.Id} changed during a repeat.");
                    repeats.Add(new JsonObject { ["caseId"] = item.Id, ["repeat"] = index,
                        ["inputSha256"] = item.Hash, ["resultSha256"] = ScientificHash(output),
                        ["durationMs"] = step.ElapsedMilliseconds, ["peakProcessMemoryBytes"] = peak,
                        ["result"] = report.DeepClone() });
                }
            }
            var childCode = "import pathlib,sys,time; print('started',flush=True); time.sleep(30); pathlib.Path(sys.argv[1]).write_text('unexpected')";
            var cancelledOutput = Path.Combine(root, "cancelled-output.txt");
            var cancelled = new ScientificJob { ProfileId = job.ProfileId, RuntimeId = job.RuntimeId,
                RecipeId = "l8.repair-cancel-case", Directory = root };
            job.Stage = "cancel-case";
            var cancelTimer = Stopwatch.StartNew();
            using (job.Cancellation.Token.Register(cancelled.Cancellation.Cancel))
            {
                var pending = ScientificProcessAsync(cancelled, vtkPrefix, vtkPython,
                    ["-c", childCode, cancelledOutput], root, 40, memoryLimitBytes: limit);
                await Task.Delay(500, job.Cancellation.Token);
                cancelled.Cancellation.Cancel();
                try { await pending; throw new InvalidDataException("Cancellation case unexpectedly completed."); }
                catch (OperationCanceledException) when (cancelled.Cancellation.IsCancellationRequested) { }
            }
            if (File.Exists(cancelledOutput)) throw new InvalidDataException("Cancelled child wrote output.");
            var cancellation = new JsonObject { ["state"] = "cancelled", ["durationMs"] = cancelTimer.ElapsedMilliseconds,
                ["outputAbsent"] = true };
            var timeoutOutput = Path.Combine(root, "timeout-output.txt");
            var timed = new ScientificJob { ProfileId = job.ProfileId, RuntimeId = job.RuntimeId,
                RecipeId = "l8.repair-timeout-case", Directory = root };
            job.Stage = "timeout-case";
            var timeoutTimer = Stopwatch.StartNew();
            using (job.Cancellation.Token.Register(timed.Cancellation.Cancel))
            {
                try
                {
                    await ScientificProcessAsync(timed, vtkPrefix, vtkPython,
                        ["-c", childCode, timeoutOutput], root, 1, memoryLimitBytes: limit);
                    throw new InvalidDataException("Timeout case unexpectedly completed.");
                }
                catch (TimeoutException) { }
            }
            if (File.Exists(timeoutOutput)) throw new InvalidDataException("Timed-out child wrote output.");
            var timeout = new JsonObject { ["state"] = "timed-out", ["durationMs"] = timeoutTimer.ElapsedMilliseconds,
                ["limitSeconds"] = 1, ["outputAbsent"] = true };
            const string allocation = "import pathlib,sys\nprint('memory probe',flush=True)\ntry: bytearray(512*1024*1024)\nexcept MemoryError: print('memory limit observed',flush=True); sys.exit(42)\npathlib.Path(sys.argv[1]).write_text('unexpected')\nsys.exit(0)";
            var memoryOutput = Path.Combine(root, "memory-output.txt");
            var capped = new ScientificJob { ProfileId = job.ProfileId, RuntimeId = job.RuntimeId,
                RecipeId = "l8.repair-memory-case", Directory = root };
            job.Stage = "memory-case";
            using (job.Cancellation.Token.Register(capped.Cancellation.Cancel))
            {
                try
                {
                    await ScientificProcessAsync(capped, vtkPrefix, vtkPython,
                        ["-c", allocation, memoryOutput], root, 15, memoryLimitBytes: limit);
                    throw new InvalidDataException("Memory cap case unexpectedly completed.");
                }
                catch (InvalidOperationException) when (capped.ExitCode == 42
                    && capped.Log.ToString().Contains("memory limit observed", StringComparison.Ordinal)) { }
            }
            if (File.Exists(memoryOutput)) throw new InvalidDataException("Memory-limited child wrote output.");
            if (ScientificCurrentRepairLevel(job.ProfileId, "L7")["recordId"]?.GetValue<string>()
                != support["recordId"]?.GetValue<string>())
                throw new InvalidOperationException("The pinned repair L7 record is no longer current.");
            var lower = (JsonArray)l7Evidence["lowerQualification"]!["records"]!.DeepClone();
            lower.Add(support.DeepClone());
            var observations = new JsonObject { ["repeatCount"] = 3, ["repeatLimitSeconds"] = 60,
                ["memoryLimitBytes"] = limit, ["repeats"] = repeats,
                ["cancellation"] = cancellation, ["timeout"] = timeout,
                ["memory"] = new JsonObject { ["state"] = "limited", ["limitBytes"] = limit,
                    ["requestedBytes"] = 536870912, ["exitCode"] = capped.ExitCode,
                    ["outputAbsent"] = true } };
            var observationsFile = Path.Combine(root, "observations.json");
            File.WriteAllText(observationsFile, observations.ToJsonString(), new UTF8Encoding(false));
            var evidence = new JsonObject { ["suiteId"] = "cgal-repair-resilience-v1",
                ["capabilityId"] = "mesh.repair", ["sourceL7RunId"] = support["runId"]?.GetValue<string>(),
                ["sourceL7FolderId"] = Path.GetFileName(l7Directory),
                ["sourceL7RecordId"] = support["recordId"]?.GetValue<string>(),
                ["sourceL7ContractSha256"] = l7Evidence["consumerContractSha256"]?.GetValue<string>(),
                ["sourceL6RunId"] = l6RunId, ["vtkReaderSha256"] = ScientificHash(tool),
                ["vtkPythonSha256"] = ScientificHash(vtkPython),
                ["observations"] = observations.DeepClone(), ["observationsSha256"] = ScientificHash(observationsFile),
                ["lowerQualification"] = new JsonObject { ["records"] = lower } };
            File.WriteAllText(Path.Combine(job.Directory, "repair-l8-evidence.json"), evidence.ToJsonString(), new UTF8Encoding(false));
            File.WriteAllText(Path.Combine(job.Directory, "results.json"), new JsonObject {
                ["repairResilienceEvidence"] = evidence, ["validatedCapabilities"] = new JsonArray("mesh.repair")
            }.ToJsonString(), new UTF8Encoding(false));
            job.State = "succeeded"; job.Stage = "completed";
        }
        catch (OperationCanceledException) { job.State = "cancelled"; job.Error = "Only this repair resilience job was stopped."; }
        catch (TimeoutException error) { job.State = "timed-out"; job.Error = error.Message; }
        catch (Exception error) { job.State = "failed"; job.Error = error.Message; }
        finally
        {
            job.DurationMs = timer.ElapsedMilliseconds;
            try { ScientificFinish(job); ScientificLog(job, $"\n[{job.State}] repair L8 resilience / {job.DurationMs} ms {job.Error}\n"); }
            catch (Exception error) { Debug.WriteLine($"Repair L8 finalization failed: {error}"); }
            finally { ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) }); _scientificGate.Release(); }
        }
    }
}
