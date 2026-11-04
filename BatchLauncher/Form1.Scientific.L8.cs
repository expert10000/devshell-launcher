using System.Diagnostics;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace BatchLauncher;

public partial class Form1
{
    private JsonObject ScientificCurrentL7Interop(string profileId)
    {
        var summary = ScientificQualificationSummary(profileId, "cgal-win-conda");
        var support = summary["currentRecords"]?.AsArray().OfType<JsonObject>()
            .Where(item => item["capabilityId"]?.GetValue<string>() == "mesh.interop.vtk-math3d"
                && item["level"]?.GetValue<string>() == "L7")
            .OrderByDescending(item => item["finishedAtUtc"]?.GetValue<string>(), StringComparer.Ordinal)
            .FirstOrDefault();
        if (support == null) throw new InvalidOperationException("A current CGAL → VTK → MATH3D L7 record is required for L8.");
        return new JsonObject { ["runId"] = support["runId"]?.GetValue<string>(),
            ["recordId"] = support["recordId"]?.GetValue<string>(),
            ["capabilityId"] = "mesh.interop.vtk-math3d", ["level"] = "L7" };
    }

    private static void ScientificCheckL8Declaration()
    {
        var path = Path.Combine(AppContext.BaseDirectory, "runtimes", "cgal-win-conda", "runtime.json");
        var declaration = (JsonNode.Parse(File.ReadAllText(path))?["qualificationRecipes"] as JsonArray)?
            .OfType<JsonObject>().FirstOrDefault(item => item["id"]?.GetValue<string>() == "l8.resilience");
        if (declaration?["readinessLevel"]?.GetValue<string>() != "L8"
            || declaration["capability"]?.GetValue<string>() != "mesh.interop.vtk-math3d"
            || declaration["referenceRecipe"]?.GetValue<string>() != "l7.cgal-vtk-math3d"
            || declaration["repeatCount"]?.GetValue<int>() != 3
            || declaration["memoryLimitBytes"]?.GetValue<long>() != 134217728)
            throw new InvalidOperationException("The L8 resilience suite is not registered in the CGAL manifest.");
    }

    private object ScientificL8Start(string profileId, string runtimeId)
    {
        ScientificProviderRegistry.RequireAction(runtimeId, "l8-resilience");
        ScientificCheckL8Declaration();
        var support = ScientificCurrentL7Interop(profileId);
        var (l7Directory, l7Result) = ScientificHistoryFind(profileId, support["runId"]!.GetValue<string>());
        var l7 = JsonNode.Parse(l7Result.GetRawText())?["l7InteropEvidence"] as JsonObject
            ?? throw new InvalidDataException("The L7 interoperability evidence is missing.");
        var cgalL6 = l7["lowerQualification"]?["records"]?[6] as JsonObject
            ?? throw new InvalidDataException("The L7 CGAL L6 reference is missing.");
        var source = ScientificL7Source(profileId, cgalL6, runtimeId);
        if (source["artifactSha256"]?.GetValue<string>() != l7["source"]?["artifactSha256"]?.GetValue<string>()
            || l7["consumerContractSha256"]?.GetValue<string>() is not { Length: 64 })
            throw new InvalidDataException("The L7 source or consumer contract changed.");
        var vtkPrefix = ScientificPrefix("vtk-win-conda");
        if (!_scientificGate.Wait(0)) throw new InvalidOperationException("Another Scientific job is running; stop or wait for it.");
        try
        {
            var directory = Path.Combine(ScientificDataRoot, "runs", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(directory);
            var job = new ScientificJob { ProfileId = profileId, RuntimeId = runtimeId,
                RecipeId = "l8.resilience", Directory = directory };
            var input = new JsonObject { ["path"] = source["absolutePath"]?.GetValue<string>(),
                ["mediaType"] = "model/obj", ["bytes"] = source["artifactBytes"]?.GetValue<long>(),
                ["sha256"] = source["artifactSha256"]?.GetValue<string>(),
                ["sourceRunId"] = source["runId"]?.GetValue<string>() };
            var parameters = JsonSerializer.SerializeToElement(new { suiteId = "l8-resilience-v1",
                sourceL7RunId = support["runId"]?.GetValue<string>(),
                sourceL7RecordId = support["recordId"]?.GetValue<string>(),
                repeatCount = 3, memoryLimitBytes = 134217728 }, ScientificJson);
            ScientificWriteRequest(job, parameters, input, additionalOutputs: new JsonArray(
                new JsonObject { ["path"] = "resilience/repeat-1.json", ["mediaType"] = "application/json" },
                new JsonObject { ["path"] = "resilience/repeat-2.json", ["mediaType"] = "application/json" },
                new JsonObject { ["path"] = "resilience/repeat-3.json", ["mediaType"] = "application/json" },
                new JsonObject { ["path"] = "resilience/observations.json", ["mediaType"] = "application/json" }));
            _scientificJobs[profileId + ":" + runtimeId] = job;
            ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) });
            _ = ScientificL8RunAsync(job, vtkPrefix, source, support, l7, l7Directory);
            return ScientificJobSnapshot(job);
        }
        catch { _scientificGate.Release(); throw; }
    }

    private async Task ScientificL8RunAsync(ScientificJob job, string vtkPrefix, JsonObject source,
        JsonObject support, JsonObject l7, string l7Directory)
    {
        var timer = Stopwatch.StartNew();
        try
        {
            const long memoryLimit = 134217728;
            var python = Path.Combine(vtkPrefix, "python.exe");
            var tool = Path.Combine(ScientificSourceRoot, "tools", "scientific-vtk-interop.py");
            var root = Path.Combine(job.Directory, "resilience");
            Directory.CreateDirectory(root);
            var artifact = source["absolutePath"]!.GetValue<string>();
            var repeats = new JsonArray();
            for (var index = 1; index <= 3; index++)
            {
                job.Stage = "repeat-" + index;
                var output = Path.Combine(root, $"repeat-{index}.json");
                long peak = 0;
                var step = Stopwatch.StartNew();
                await ScientificProcessAsync(job, vtkPrefix, python,
                    [tool, "--input", artifact, "--result", output], root, 60,
                    memoryLimitBytes: memoryLimit, peakMemory: value => peak = value);
                repeats.Add(new JsonObject { ["caseId"] = "repeat-" + index,
                    ["resultSha256"] = ScientificHash(output), ["durationMs"] = step.ElapsedMilliseconds,
                    ["peakProcessMemoryBytes"] = peak,
                    ["result"] = JsonNode.Parse(File.ReadAllText(output))?.DeepClone() });
            }
            if (repeats[0]?["resultSha256"]?.GetValue<string>() != repeats[1]?["resultSha256"]?.GetValue<string>()
                || repeats[0]?["resultSha256"]?.GetValue<string>() != repeats[2]?["resultSha256"]?.GetValue<string>())
                throw new InvalidDataException("Repeated VTK consumer results changed.");
            var childCode = "import pathlib,sys,time; print('started',flush=True); time.sleep(30); pathlib.Path(sys.argv[1]).write_text('unexpected')";
            var cancelledOutput = Path.Combine(root, "cancelled-output.txt");
            var cancelled = new ScientificJob { ProfileId = job.ProfileId, RuntimeId = job.RuntimeId,
                RecipeId = "l8.cancel-case", Directory = root };
            job.Stage = "cancel-case";
            var cancelledTimer = Stopwatch.StartNew();
            using (job.Cancellation.Token.Register(cancelled.Cancellation.Cancel))
            {
                var pending = ScientificProcessAsync(cancelled, vtkPrefix, python, ["-c", childCode, cancelledOutput], root, 40,
                    memoryLimitBytes: memoryLimit);
                await Task.Delay(500, job.Cancellation.Token);
                cancelled.Cancellation.Cancel();
                try { await pending; throw new InvalidDataException("The cancellation case unexpectedly completed."); }
                catch (OperationCanceledException) when (cancelled.Cancellation.IsCancellationRequested) { }
            }
            if (File.Exists(cancelledOutput)) throw new InvalidDataException("Cancelled child created output.");
            var cancellation = new JsonObject { ["state"] = "cancelled", ["durationMs"] = cancelledTimer.ElapsedMilliseconds,
                ["outputAbsent"] = true };
            var timed = new ScientificJob { ProfileId = job.ProfileId, RuntimeId = job.RuntimeId,
                RecipeId = "l8.timeout-case", Directory = root };
            job.Stage = "timeout-case";
            var timedTimer = Stopwatch.StartNew();
            var timedOutput = Path.Combine(root, "timeout-output.txt");
            using (job.Cancellation.Token.Register(timed.Cancellation.Cancel))
            {
                try
                {
                    await ScientificProcessAsync(timed, vtkPrefix, python, ["-c", childCode, timedOutput], root, 1,
                        memoryLimitBytes: memoryLimit);
                    throw new InvalidDataException("The timeout case unexpectedly completed.");
                }
                catch (TimeoutException) { }
            }
            if (File.Exists(timedOutput)) throw new InvalidDataException("Timed-out child created output.");
            var timeout = new JsonObject { ["state"] = "timed-out", ["durationMs"] = timedTimer.ElapsedMilliseconds,
                ["limitSeconds"] = 1, ["outputAbsent"] = true };
            var capped = new ScientificJob { ProfileId = job.ProfileId, RuntimeId = job.RuntimeId,
                RecipeId = "l8.memory-case", Directory = root };
            job.Stage = "memory-case";
            const string allocation = "import pathlib,sys\nprint('memory probe',flush=True)\ntry: bytearray(512*1024*1024)\nexcept MemoryError: print('memory limit observed',flush=True); sys.exit(42)\npathlib.Path(sys.argv[1]).write_text('unexpected')\nsys.exit(0)";
            var memoryOutput = Path.Combine(root, "memory-output.txt");
            using (job.Cancellation.Token.Register(capped.Cancellation.Cancel))
            {
                try
                {
                    await ScientificProcessAsync(capped, vtkPrefix, python, ["-c", allocation, memoryOutput], root, 15,
                        memoryLimitBytes: memoryLimit);
                    throw new InvalidDataException("The memory cap case unexpectedly completed.");
                }
                catch (InvalidOperationException) when (capped.ExitCode == 42
                    && capped.Log.ToString().Contains("memory limit observed", StringComparison.Ordinal)) { }
            }
            if (File.Exists(memoryOutput)) throw new InvalidDataException("Memory-limited child created output.");
            var memory = new JsonObject { ["state"] = "limited", ["limitBytes"] = memoryLimit,
                ["requestedBytes"] = 536870912, ["exitCode"] = capped.ExitCode,
                ["observedMarker"] = "memory limit observed", ["outputAbsent"] = true };
            var lower = (JsonArray)l7["lowerQualification"]!["records"]!.DeepClone();
            lower.Add(support.DeepClone());
            if (ScientificCurrentL7Interop(job.ProfileId)["recordId"]?.GetValue<string>() != support["recordId"]?.GetValue<string>())
                throw new InvalidOperationException("The L7 interoperability qualification is no longer current.");
            var observations = new JsonObject { ["repeatCount"] = 3, ["repeatLimitSeconds"] = 60,
                ["memoryLimitBytes"] = memoryLimit, ["repeats"] = repeats.DeepClone(),
                ["cancellation"] = cancellation, ["timeout"] = timeout, ["memory"] = memory };
            var observationsFile = Path.Combine(root, "observations.json");
            File.WriteAllText(observationsFile, observations.ToJsonString(), new UTF8Encoding(false));
            var evidence = new JsonObject { ["suiteId"] = "l8-resilience-v1",
                ["capabilityId"] = "mesh.interop.vtk-math3d", ["sourceL7RunId"] = support["runId"]?.GetValue<string>(),
                ["sourceL7FolderId"] = Path.GetFileName(l7Directory),
                ["sourceL7RecordId"] = support["recordId"]?.GetValue<string>(),
                ["sourceL7ContractSha256"] = l7["consumerContractSha256"]?.GetValue<string>(),
                ["sourceArtifactSha256"] = source["artifactSha256"]?.GetValue<string>(),
                ["vtkReaderSha256"] = ScientificHash(tool), ["vtkPythonSha256"] = ScientificHash(python),
                ["observations"] = observations.DeepClone(), ["observationsSha256"] = ScientificHash(observationsFile),
                ["lowerQualification"] = new JsonObject { ["records"] = lower } };
            File.WriteAllText(Path.Combine(job.Directory, "results.json"), new JsonObject
            {
                ["l8Evidence"] = evidence,
                ["validatedCapabilities"] = new JsonArray("mesh.interop.vtk-math3d")
            }.ToJsonString(), new UTF8Encoding(false));
            job.State = "succeeded"; job.Stage = "completed";
        }
        catch (OperationCanceledException) { job.State = "cancelled"; job.Error = "The owned L8 resilience run was stopped."; }
        catch (TimeoutException exception) { job.State = "timed-out"; job.Error = exception.Message; }
        catch (Exception exception) { job.State = "failed"; job.Error = exception.Message; }
        finally
        {
            job.DurationMs = timer.ElapsedMilliseconds;
            try { ScientificFinish(job); ScientificLog(job, $"\n[{job.State}] L8 resilience / {job.DurationMs} ms {job.Error}\n"); }
            catch (Exception exception) { Debug.WriteLine($"L8 resilience finalization failed: {exception}"); }
            finally { ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) }); _scientificGate.Release(); }
        }
    }
}
