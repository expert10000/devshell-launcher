using System.Diagnostics;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace BatchLauncher;

public partial class Form1
{
    private static void ScientificGmshDeclaration(string recipe, string level, string reference)
    {
        var path = Path.Combine(AppContext.BaseDirectory, "runtimes", "gmsh-win-conda", "runtime.json");
        var entry = (JsonNode.Parse(File.ReadAllText(path))?["qualificationRecipes"] as JsonArray)?
            .OfType<JsonObject>().FirstOrDefault(item => item["id"]?.GetValue<string>() == recipe);
        if (entry?["readinessLevel"]?.GetValue<string>() != level
            || entry["capability"]?.GetValue<string>() != "mesh.generate"
            || entry["referenceRecipe"]?.GetValue<string>() != reference)
            throw new InvalidOperationException($"The Gmsh {level} contract is not registered.");
    }

    private JsonObject ScientificGmshCurrentL7(string profileId)
    {
        var summary = ScientificQualificationSummary(profileId, "gmsh-win-conda");
        var support = summary["currentRecords"]?.AsArray().OfType<JsonObject>()
            .Where(item => item["capabilityId"]?.GetValue<string>() == "mesh.generate"
                && item["level"]?.GetValue<string>() == "L7")
            .OrderByDescending(item => item["finishedAtUtc"]?.GetValue<string>(), StringComparer.Ordinal)
            .FirstOrDefault() ?? throw new InvalidOperationException("A current Gmsh L7 interoperability record is required.");
        return new JsonObject { ["runId"] = support["runId"]?.GetValue<string>(),
            ["recordId"] = support["recordId"]?.GetValue<string>(),
            ["capabilityId"] = "mesh.generate", ["level"] = "L7" };
    }

    private object ScientificGmshL7Start(string profileId, string runtimeId)
    {
        ScientificProviderRegistry.RequireAction(runtimeId, "l7-gmsh-interop");
        ScientificGmshDeclaration("l7.gmsh-interop", "L7", "l6.reproduce");
        var support = ScientificCurrentL6(profileId, runtimeId);
        var source = ScientificL7Source(profileId, support, runtimeId);
        var checkout = ScientificL7Checkout();
        var importer = Path.Combine(checkout, "renderer", "src", "mesh", "surfaceMesh.ts");
        if (!File.Exists(importer) || !Directory.Exists(Path.Combine(checkout, "renderer", "node_modules", "vite")))
            throw new InvalidOperationException("MATH3D importer dependencies are required for Gmsh L7.");
        var prefix = ScientificPrefix(runtimeId);
        var vtkPrefix = ScientificPrefix("vtk-win-conda");
        if (!_scientificGate.Wait(0)) throw new InvalidOperationException("Another Scientific job is running.");
        try
        {
            var directory = Path.Combine(ScientificDataRoot, "runs", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(directory);
            var job = new ScientificJob { ProfileId = profileId, RuntimeId = runtimeId,
                RecipeId = "l7.gmsh-interop", Directory = directory };
            var input = new JsonObject { ["path"] = source["absolutePath"]?.GetValue<string>(),
                ["mediaType"] = "model/vnd.gmsh.msh", ["bytes"] = source["artifactBytes"]?.GetValue<long>(),
                ["sha256"] = source["artifactSha256"]?.GetValue<string>(),
                ["sourceRunId"] = source["runId"]?.GetValue<string>() };
            var parameters = JsonSerializer.SerializeToElement(new { suiteId = "l7-gmsh-interop-v1",
                sourceRunId = support["runId"]?.GetValue<string>(), sourceRecordId = support["recordId"]?.GetValue<string>() }, ScientificJson);
            var outputs = new JsonArray();
            foreach (var name in new[] { "mesh.obj", "handoff.json", "vtk.json", "math3d.json",
                "malformed.obj", "vtk-rejection.json", "math3d-rejection.json" })
                outputs.Add(new JsonObject { ["path"] = "handoff/" + name,
                    ["mediaType"] = name.EndsWith(".obj", StringComparison.Ordinal) ? "model/obj" : "application/json" });
            ScientificWriteRequest(job, parameters, input, additionalOutputs: outputs);
            _scientificJobs[profileId + ":" + runtimeId] = job;
            ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) });
            _ = ScientificGmshL7RunAsync(job, prefix, vtkPrefix, checkout, source, support);
            return ScientificJobSnapshot(job);
        }
        catch { _scientificGate.Release(); throw; }
    }

    private async Task ScientificGmshL7RunAsync(ScientificJob job, string prefix, string vtkPrefix,
        string checkout, JsonObject source, JsonObject support)
    {
        var timer = Stopwatch.StartNew();
        try
        {
            var folder = Path.Combine(job.Directory, "handoff");
            Directory.CreateDirectory(folder);
            string At(string name) => Path.Combine(folder, name);
            var tools = Path.Combine(ScientificSourceRoot, "tools");
            var artifact = source["absolutePath"]!.GetValue<string>();
            job.Stage = "convert";
            await ScientificProcessAsync(job, prefix, Path.Combine(prefix, "python.exe"),
                [Path.Combine(tools, "scientific-gmsh-handoff.py"), "--input", artifact,
                    "--output", At("mesh.obj"), "--result", At("handoff.json")], folder, 60);
            job.Stage = "vtk-consumer";
            await ScientificProcessAsync(job, vtkPrefix, Path.Combine(vtkPrefix, "python.exe"),
                [Path.Combine(tools, "scientific-gmsh-vtk-consumer.py"), "--input", At("mesh.obj"),
                    "--result", At("vtk.json")], folder, 60);
            job.Stage = "math3d-consumer";
            await ScientificProcessAsync(job, prefix, Math3DNode,
                [Path.Combine(tools, "math3d-gmsh-import-handoff.mjs"), "--checkout", checkout,
                    "--input", At("mesh.obj"), "--result", At("math3d.json")], folder, 120);
            File.WriteAllText(At("malformed.obj"), "v 0 0 0\nv 1 0 0\nf 1 2 99\n", new UTF8Encoding(false));
            job.Stage = "reject-vtk";
            await ScientificProcessAsync(job, vtkPrefix, Path.Combine(vtkPrefix, "python.exe"),
                [Path.Combine(tools, "scientific-gmsh-vtk-consumer.py"), "--input", At("malformed.obj"),
                    "--result", At("vtk-rejection.json"), "--expect-reject"], folder, 60);
            job.Stage = "reject-math3d";
            await ScientificProcessAsync(job, prefix, Math3DNode,
                [Path.Combine(tools, "math3d-gmsh-import-handoff.mjs"), "--checkout", checkout,
                    "--input", At("malformed.obj"), "--result", At("math3d-rejection.json"), "--expect-reject"], folder, 120);
            JsonObject Read(string name) => JsonNode.Parse(File.ReadAllText(At(name)))?.AsObject()
                ?? throw new InvalidDataException("Gmsh consumer result is missing.");
            var handoff = Read("handoff.json"); var vtk = Read("vtk.json"); var math3d = Read("math3d.json");
            var vtkReject = Read("vtk-rejection.json"); var math3dReject = Read("math3d-rejection.json");
            var contracts = new JsonObject {
                ["converterSha256"] = ScientificHash(Path.Combine(tools, "scientific-gmsh-handoff.py")),
                ["vtkReaderSha256"] = ScientificHash(Path.Combine(tools, "scientific-gmsh-vtk-consumer.py")),
                ["math3dHandoffSha256"] = ScientificHash(Path.Combine(tools, "math3d-gmsh-import-handoff.mjs")),
                ["math3dImporterSha256"] = ScientificHash(Path.Combine(checkout, "renderer", "src", "mesh", "surfaceMesh.ts")),
                ["vtkPythonSha256"] = ScientificHash(Path.Combine(vtkPrefix, "python.exe")),
                ["vtkEnvironmentSha256"] = ScientificCurrentVtkConsumerEnvironment(job.ProfileId) };
            var reference = (JsonObject)source.DeepClone(); reference.Remove("absolutePath");
            var lower = (JsonArray)source["lowerQualification"]!["records"]!.DeepClone(); lower.Add(support.DeepClone());
            var hashes = new JsonObject();
            foreach (var name in new[] { "mesh.obj", "handoff.json", "vtk.json", "math3d.json",
                "malformed.obj", "vtk-rejection.json", "math3d-rejection.json" }) hashes[name] = ScientificHash(At(name));
            if (!ScientificQualificationRecords.ValidGmshInterop(handoff, vtk, math3d, vtkReject, math3dReject,
                    source["artifactSha256"]?.GetValue<string>(), hashes["mesh.obj"]?.GetValue<string>(),
                    hashes["malformed.obj"]?.GetValue<string>(), contracts["math3dImporterSha256"]?.GetValue<string>())
                || ScientificCurrentL6(job.ProfileId, job.RuntimeId)["recordId"]?.GetValue<string>() != support["recordId"]?.GetValue<string>())
                throw new InvalidDataException("The Gmsh L7 consumer handoff or supporting L6 record changed.");
            var evidence = new JsonObject { ["suiteId"] = "l7-gmsh-interop-v1", ["capabilityId"] = "mesh.generate",
                ["source"] = reference, ["handoff"] = handoff.DeepClone(), ["vtk"] = vtk.DeepClone(),
                ["math3d"] = math3d.DeepClone(), ["vtkRejection"] = vtkReject.DeepClone(),
                ["math3dRejection"] = math3dReject.DeepClone(), ["artifactHashes"] = hashes,
                ["consumerContract"] = contracts, ["consumerContractSha256"] = ScientificL6Digest(contracts),
                ["lowerQualification"] = new JsonObject { ["records"] = lower } };
            File.WriteAllText(Path.Combine(job.Directory, "results.json"), new JsonObject {
                ["l7GmshEvidence"] = evidence, ["validatedCapabilities"] = new JsonArray("mesh.generate")
            }.ToJsonString(), new UTF8Encoding(false));
            job.State = "succeeded"; job.Stage = "completed";
        }
        catch (OperationCanceledException) { job.State = "cancelled"; job.Error = "The owned Gmsh L7 run was stopped."; }
        catch (TimeoutException exception) { job.State = "timed-out"; job.Error = exception.Message; }
        catch (Exception exception) { job.State = "failed"; job.Error = exception.Message; }
        finally
        {
            job.DurationMs = timer.ElapsedMilliseconds;
            try { ScientificFinish(job); ScientificLog(job, $"\n[{job.State}] Gmsh L7 / {job.DurationMs} ms {job.Error}\n"); }
            catch (Exception exception) { Debug.WriteLine($"Gmsh L7 finalization failed: {exception}"); }
            finally { ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) }); _scientificGate.Release(); }
        }
    }

    private object ScientificGmshL8Start(string profileId, string runtimeId)
    {
        ScientificProviderRegistry.RequireAction(runtimeId, "l8-gmsh-resilience");
        ScientificGmshDeclaration("l8.gmsh-resilience", "L8", "l7.gmsh-interop");
        var support = ScientificGmshCurrentL7(profileId);
        var (sourceDirectory, sourceElement) = ScientificHistoryFind(profileId, support["runId"]!.GetValue<string>());
        var sourceResult = JsonNode.Parse(sourceElement.GetRawText()) as JsonObject;
        var evidence = sourceResult?["l7GmshEvidence"] as JsonObject;
        if (sourceResult?["runtimeId"]?.GetValue<string>() != runtimeId
            || sourceResult["recipeId"]?.GetValue<string>() != "l7.gmsh-interop"
            || sourceResult["state"]?.GetValue<string>() != "succeeded" || evidence == null
            || !ScientificQualificationRecords.Verify(sourceDirectory, sourceElement).OfType<JsonObject>()
                .Any(item => item["recordId"]?.GetValue<string>() == support["recordId"]?.GetValue<string>()
                    && item["level"]?.GetValue<string>() == "L7"))
            throw new InvalidDataException("The Gmsh L7 source run is not verified.");
        var artifact = ScientificArtifactFiles.ResolveRegistered(sourceDirectory, sourceElement, "handoff/mesh.obj");
        if (ScientificHash(artifact) != evidence["artifactHashes"]?["mesh.obj"]?.GetValue<string>())
            throw new InvalidDataException("The Gmsh L7 OBJ artifact changed.");
        var vtkPrefix = ScientificPrefix("vtk-win-conda");
        if (!_scientificGate.Wait(0)) throw new InvalidOperationException("Another Scientific job is running.");
        try
        {
            var directory = Path.Combine(ScientificDataRoot, "runs", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(directory);
            var job = new ScientificJob { ProfileId = profileId, RuntimeId = runtimeId,
                RecipeId = "l8.gmsh-resilience", Directory = directory };
            var input = new JsonObject { ["path"] = artifact, ["mediaType"] = "model/obj",
                ["bytes"] = new FileInfo(artifact).Length, ["sha256"] = ScientificHash(artifact),
                ["sourceRunId"] = support["runId"]?.GetValue<string>() };
            var parameters = JsonSerializer.SerializeToElement(new { suiteId = "l8-gmsh-resilience-v1",
                sourceRunId = support["runId"]?.GetValue<string>(),
                sourceRecordId = support["recordId"]?.GetValue<string>(), repeatCount = 3,
                memoryLimitBytes = 134217728 }, ScientificJson);
            var outputs = new JsonArray();
            foreach (var name in new[] { "repeat-1.json", "repeat-2.json", "repeat-3.json", "observations.json" })
                outputs.Add(new JsonObject { ["path"] = "resilience/" + name, ["mediaType"] = "application/json" });
            ScientificWriteRequest(job, parameters, input, additionalOutputs: outputs);
            _scientificJobs[profileId + ":" + runtimeId] = job;
            ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) });
            _ = ScientificGmshL8RunAsync(job, vtkPrefix, artifact, support, sourceDirectory, evidence);
            return ScientificJobSnapshot(job);
        }
        catch { _scientificGate.Release(); throw; }
    }

    private async Task ScientificGmshL8RunAsync(ScientificJob job, string vtkPrefix, string artifact,
        JsonObject support, string sourceDirectory, JsonObject l7, bool volume = false)
    {
        var timer = Stopwatch.StartNew();
        try
        {
            const long memoryLimit = 134217728;
            const long repeatMemoryLimit = 536870912;
            var python = Path.Combine(vtkPrefix, "python.exe");
            var tool = Path.Combine(ScientificSourceRoot, "tools", volume ? "scientific-gmsh-volume-vtk.py" : "scientific-gmsh-vtk-consumer.py");
            var folder = Path.Combine(job.Directory, "resilience"); Directory.CreateDirectory(folder);
            var repeats = new JsonArray();
            for (var index = 1; index <= 3; index++)
            {
                job.Stage = "repeat-" + index;
                var output = Path.Combine(folder, $"repeat-{index}.json");
                long peak = 0; var step = Stopwatch.StartNew();
                await ScientificProcessAsync(job, vtkPrefix, python,
                    [tool, "--input", artifact, "--result", output], folder, 60,
                    memoryLimitBytes: repeatMemoryLimit, peakMemory: value => peak = value);
                repeats.Add(new JsonObject { ["caseId"] = "repeat-" + index,
                    ["resultSha256"] = ScientificHash(output), ["durationMs"] = step.ElapsedMilliseconds,
                    ["peakProcessMemoryBytes"] = peak,
                    ["result"] = JsonNode.Parse(File.ReadAllText(output))?.DeepClone() });
            }
            if (repeats[0]?["resultSha256"]?.GetValue<string>() != repeats[1]?["resultSha256"]?.GetValue<string>()
                || repeats[0]?["resultSha256"]?.GetValue<string>() != repeats[2]?["resultSha256"]?.GetValue<string>())
                throw new InvalidDataException("Repeated VTK reads of the Gmsh artifact changed.");
            var childCode = "import pathlib,sys,time; print('started',flush=True); time.sleep(30); pathlib.Path(sys.argv[1]).write_text('unexpected')";
            var cancelledOutput = Path.Combine(folder, "cancelled-output.txt");
            var cancelled = new ScientificJob { ProfileId = job.ProfileId, RuntimeId = job.RuntimeId,
                RecipeId = "l8.gmsh.cancel", Directory = folder };
            job.Stage = "cancel-case"; var cancellationTimer = Stopwatch.StartNew();
            using (job.Cancellation.Token.Register(cancelled.Cancellation.Cancel))
            {
                var pending = ScientificProcessAsync(cancelled, vtkPrefix, python, ["-c", childCode, cancelledOutput], folder, 40,
                    memoryLimitBytes: memoryLimit);
                await Task.Delay(500, job.Cancellation.Token);
                cancelled.Cancellation.Cancel();
                try { await pending; throw new InvalidDataException("Cancellation case unexpectedly completed."); }
                catch (OperationCanceledException) when (cancelled.Cancellation.IsCancellationRequested) { }
            }
            if (File.Exists(cancelledOutput)) throw new InvalidDataException("Cancelled child created output.");
            var timed = new ScientificJob { ProfileId = job.ProfileId, RuntimeId = job.RuntimeId,
                RecipeId = "l8.gmsh.timeout", Directory = folder };
            var timedOutput = Path.Combine(folder, "timeout-output.txt");
            job.Stage = "timeout-case"; var timeoutTimer = Stopwatch.StartNew();
            using (job.Cancellation.Token.Register(timed.Cancellation.Cancel))
            {
                try
                {
                    await ScientificProcessAsync(timed, vtkPrefix, python, ["-c", childCode, timedOutput], folder, 1,
                        memoryLimitBytes: memoryLimit);
                    throw new InvalidDataException("Timeout case unexpectedly completed.");
                }
                catch (TimeoutException) { }
            }
            if (File.Exists(timedOutput)) throw new InvalidDataException("Timed-out child created output.");
            const string allocation = "import pathlib,sys\nprint('memory probe',flush=True)\ntry: bytearray(512*1024*1024)\nexcept MemoryError: print('memory limit observed',flush=True); sys.exit(42)\npathlib.Path(sys.argv[1]).write_text('unexpected')\nsys.exit(0)";
            var capped = new ScientificJob { ProfileId = job.ProfileId, RuntimeId = job.RuntimeId,
                RecipeId = "l8.gmsh.memory", Directory = folder };
            var memoryOutput = Path.Combine(folder, "memory-output.txt");
            job.Stage = "memory-case";
            using (job.Cancellation.Token.Register(capped.Cancellation.Cancel))
            {
                try
                {
                    await ScientificProcessAsync(capped, vtkPrefix, python, ["-c", allocation, memoryOutput], folder, 15,
                        memoryLimitBytes: memoryLimit);
                    throw new InvalidDataException("Memory cap case unexpectedly completed.");
                }
                catch (InvalidOperationException) when (capped.ExitCode == 42
                    && capped.Log.ToString().Contains("memory limit observed", StringComparison.Ordinal)) { }
            }
            if (File.Exists(memoryOutput)) throw new InvalidDataException("Memory-limited child created output.");
            if ((volume ? ScientificGmshVolumeCurrentL7(job.ProfileId) : ScientificGmshCurrentL7(job.ProfileId))["recordId"]?.GetValue<string>() != support["recordId"]?.GetValue<string>())
                throw new InvalidDataException("The Gmsh L7 support record is no longer current.");
            var lower = (JsonArray)l7["lowerQualification"]!["records"]!.DeepClone(); lower.Add(support.DeepClone());
            var observations = new JsonObject { ["repeatCount"] = 3, ["repeatLimitSeconds"] = 60,
                ["repeatMemoryLimitBytes"] = repeatMemoryLimit, ["memoryLimitBytes"] = memoryLimit,
                ["repeats"] = repeats.DeepClone(),
                ["cancellation"] = new JsonObject { ["state"] = "cancelled", ["durationMs"] = cancellationTimer.ElapsedMilliseconds,
                    ["outputAbsent"] = true, ["childStopped"] = true },
                ["timeout"] = new JsonObject { ["state"] = "timed-out", ["durationMs"] = timeoutTimer.ElapsedMilliseconds,
                    ["limitSeconds"] = 1, ["outputAbsent"] = true, ["childStopped"] = true },
                ["memory"] = new JsonObject { ["state"] = "limited", ["limitBytes"] = memoryLimit,
                    ["requestedBytes"] = 536870912, ["exitCode"] = capped.ExitCode, ["outputAbsent"] = true,
                    ["childStopped"] = true } };
            var observationsFile = Path.Combine(folder, "observations.json");
            File.WriteAllText(observationsFile, observations.ToJsonString(), new UTF8Encoding(false));
            var evidence = new JsonObject { ["suiteId"] = volume ? "l8-gmsh-volume-v1" : "l8-gmsh-resilience-v1", ["capabilityId"] = volume ? "mesh.generate3d" : "mesh.generate",
                ["sourceL7RunId"] = support["runId"]?.GetValue<string>(),
                ["sourceL7FolderId"] = Path.GetFileName(sourceDirectory),
                ["sourceL7RecordId"] = support["recordId"]?.GetValue<string>(),
                ["sourceArtifactSha256"] = ScientificHash(artifact),
                ["sourceConsumerContractSha256"] = (volume ? l7["candidateRecordSha256"] : l7["consumerContractSha256"])?.GetValue<string>(),
                ["readerSha256"] = ScientificHash(tool), ["vtkPythonSha256"] = ScientificHash(python),
                ["observations"] = observations.DeepClone(), ["observationsSha256"] = ScientificHash(observationsFile),
                ["lowerQualification"] = new JsonObject { ["records"] = lower } };
            File.WriteAllText(Path.Combine(job.Directory, "results.json"), new JsonObject {
                [volume ? "l8GmshVolumeEvidence" : "l8GmshEvidence"] = evidence,
                ["validatedCapabilities"] = new JsonArray(volume ? "mesh.generate3d" : "mesh.generate")
            }.ToJsonString(), new UTF8Encoding(false));
            job.State = "succeeded"; job.Stage = "completed";
        }
        catch (OperationCanceledException) { job.State = "cancelled"; job.Error = "The owned Gmsh L8 run was stopped."; }
        catch (TimeoutException exception) { job.State = "timed-out"; job.Error = exception.Message; }
        catch (Exception exception) { job.State = "failed"; job.Error = exception.Message; }
        finally
        {
            job.DurationMs = timer.ElapsedMilliseconds;
            try { ScientificFinish(job); ScientificLog(job, $"\n[{job.State}] Gmsh L8 / {job.DurationMs} ms {job.Error}\n"); }
            catch (Exception exception) { Debug.WriteLine($"Gmsh L8 finalization failed: {exception}"); }
            finally { ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) }); _scientificGate.Release(); }
        }
    }
}
