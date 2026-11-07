using System.Diagnostics;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace BatchLauncher;

public partial class Form1
{
    private JsonObject ScientificGmshVolumeLower(string profileId)
    {
        var summary = ScientificQualificationSummary(profileId, "gmsh-win-conda");
        var required = new[] { ("runtime.inventory", "L0"), ("python.version", "L1"),
            ("gmsh.version", "L2"), ("gmsh.volume3d.cube", "L3"), ("gmsh.cpp.compile-link", "L4") };
        var records = new JsonArray();
        foreach (var (capability, level) in required)
        {
            var entry = summary["currentRecords"]?.AsArray().OfType<JsonObject>()
                .Where(item => item["capabilityId"]?.GetValue<string>() == capability
                    && item["level"]?.GetValue<string>() == level)
                .OrderByDescending(item => item["finishedAtUtc"]?.GetValue<string>(), StringComparer.Ordinal)
                .FirstOrDefault() ?? throw new InvalidOperationException($"Current Gmsh volume {level} evidence for {capability} is required.");
            records.Add(new JsonObject { ["runId"] = entry["runId"]?.GetValue<string>(),
                ["recordId"] = entry["recordId"]?.GetValue<string>(), ["capabilityId"] = capability, ["level"] = level });
        }
        return new JsonObject { ["records"] = records };
    }

    private static void ScientificGmshVolumeDeclaration(string recipe, string level)
    {
        var path = Path.Combine(AppContext.BaseDirectory, "runtimes", "gmsh-win-conda", "runtime.json");
        if (!File.Exists(path) || new FileInfo(path).Length > 65536) throw new InvalidOperationException("Gmsh volume manifest is unavailable.");
        var declaration = JsonNode.Parse(File.ReadAllText(path))?["qualificationRecipes"]?.AsArray().OfType<JsonObject>()
            .FirstOrDefault(item => item["id"]?.GetValue<string>() == recipe);
        if (declaration?["readinessLevel"]?.GetValue<string>() != level
            || declaration["capability"]?.GetValue<string>() != "mesh.generate3d"
            || (level == "L5" && (declaration["workerRecipe"]?.GetValue<string>() != "gmsh.volume3d.cube"
                || declaration["fixture"]?.GetValue<string>() != "scientific/fixtures/gmsh/cube.geo"))
            || (level == "L6" && (declaration["referenceRecipe"]?.GetValue<string>() != "l5.gmsh-volume"
                || declaration["comparison"]?.GetValue<string>() != "sha256-exact"))
            || (level == "L7" && (declaration["referenceRecipe"]?.GetValue<string>() != "l6.gmsh-volume"
                || declaration["boundaryFormat"]?.GetValue<string>() != "obj"))
            || (level == "L8" && (declaration["referenceRecipe"]?.GetValue<string>() != "l7.gmsh-volume"
                || declaration["repeatCount"]?.GetValue<int>() != 3
                || declaration["memoryLimitBytes"]?.GetValue<long>() != 134217728))
            || (level == "L9" && (declaration["referenceRecipe"]?.GetValue<string>() != "l8.gmsh-volume"
                || declaration["contractVersion"]?.GetValue<int>() != 1
                || declaration["documentFormat"]?.GetValue<string>() != "math3d.tetrahedral-mesh-document"
                || declaration["viewer"]?.GetValue<string>() != "TetrahedralMeshViewport")))
            throw new InvalidOperationException("Gmsh volume recipe differs from its registered contract.");
    }

    private object ScientificGmshVolumeStart(string profileId, string runtimeId, string level)
    {
        var action = $"{level.ToLowerInvariant()}-gmsh-volume";
        var recipe = $"{level.ToLowerInvariant()}.gmsh-volume";
        ScientificProviderRegistry.RequireAction(runtimeId, action);
        ScientificGmshVolumeDeclaration(recipe, level);
        var lower = ScientificGmshVolumeLower(profileId);
        JsonObject? baseline = null;
        if (level is "L6" or "L7")
        {
            var referenceLevel = level == "L6" ? "L5" : "L6";
            var summary = ScientificQualificationSummary(profileId, runtimeId);
            var current = summary["currentRecords"]?.AsArray().OfType<JsonObject>()
                .Where(item => item["capabilityId"]?.GetValue<string>() == "mesh.generate3d"
                    && item["level"]?.GetValue<string>() == referenceLevel)
                .OrderByDescending(item => item["finishedAtUtc"]?.GetValue<string>(), StringComparer.Ordinal)
                .FirstOrDefault() ?? throw new InvalidOperationException($"Current Gmsh volume {referenceLevel} evidence is required.");
            var (directory, result) = ScientificHistoryFind(profileId, current["runId"]!.GetValue<string>());
            var evidence = JsonNode.Parse(result.GetRawText())?["volumeEvidence"];
            if (!ScientificQualificationRecords.Verify(directory, result).OfType<JsonObject>().Any(item =>
                item["recordId"]?.GetValue<string>() == current["recordId"]?.GetValue<string>()))
                throw new InvalidDataException("Gmsh volume L5 support is not verified.");
            baseline = new JsonObject { ["runId"] = current["runId"]?.GetValue<string>(),
                ["recordId"] = current["recordId"]?.GetValue<string>(),
                ["folderId"] = Path.GetFileName(directory), ["level"] = referenceLevel,
                ["artifactSha256"] = evidence?["artifactSha256"]?.GetValue<string>() };
            if (level == "L7")
                lower = new JsonObject { ["records"] = evidence?["lowerQualification"]?["records"]?.DeepClone()
                    ?? throw new InvalidDataException("The volume L6 support chain is missing.") };
        }
        var fixture = ScientificDatasetArtifact("gmsh/fixed-cube.geo");
        var prefix = ScientificPrefix(runtimeId);
        var vtkPrefix = ScientificPrefix("vtk-win-conda");
        var checkout = ScientificL7Checkout();
        if (!_scientificGate.Wait(0)) throw new InvalidOperationException("Another Scientific job is running.");
        try
        {
            var directory = Path.Combine(ScientificDataRoot, "runs", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(directory);
            var job = new ScientificJob { ProfileId = profileId, RuntimeId = runtimeId, RecipeId = recipe, Directory = directory };
            var parameters = JsonSerializer.SerializeToElement(new { suiteId = "gmsh-volume-managed-v1",
                level, baselineRunId = baseline?["runId"]?.GetValue<string>() }, ScientificJson);
            var outputs = new JsonArray(new JsonObject { ["path"] = "volume/DS-SCI-067.json", ["mediaType"] = "application/json" },
                new JsonObject { ["path"] = "volume/positive-a/cube.msh", ["mediaType"] = "application/vnd.gmsh.msh" },
                new JsonObject { ["path"] = "volume/DS-SCI-068.json", ["mediaType"] = "application/json" },
                new JsonObject { ["path"] = "volume/reload.json", ["mediaType"] = "application/json" },
                new JsonObject { ["path"] = "volume/DS-SCI-069.json", ["mediaType"] = "application/json" },
                new JsonObject { ["path"] = "volume/boundary.obj", ["mediaType"] = "model/obj" },
                new JsonObject { ["path"] = "volume/vtk.json", ["mediaType"] = "application/json" },
                new JsonObject { ["path"] = "volume/math3d.json", ["mediaType"] = "application/json" });
            ScientificWriteRequest(job, parameters, fixture, additionalOutputs: outputs, timeoutSeconds: 240);
            _scientificJobs[profileId + ":" + runtimeId] = job;
            ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) });
            _ = ScientificGmshVolumeRunAsync(job, prefix, vtkPrefix, checkout, lower, baseline);
            return ScientificJobSnapshot(job);
        }
        catch { _scientificGate.Release(); throw; }
    }

    private async Task ScientificGmshVolumeRunAsync(ScientificJob job, string prefix, string vtkPrefix,
        string checkout, JsonObject lower, JsonObject? baseline)
    {
        var timer = Stopwatch.StartNew();
        try
        {
            var suite = Path.Combine(ScientificSourceRoot, "tools", "scientific-broker", "gmsh_volume.py");
            var suiteResult = Path.Combine(job.Directory, "suite.json");
            job.Stage = "candidate-worker-and-reload";
            await ScientificProcessAsync(job, prefix, Path.Combine(prefix, "python.exe"),
                [suite, "run", "--gmsh-python", Path.Combine(prefix, "python.exe"),
                    "--vtk-python", Path.Combine(vtkPrefix, "python.exe"), "--math3d-checkout", checkout,
                    "--output-root", job.Directory, "--folder-id", "volume", "--result", suiteResult],
                job.Directory, 240);
            var candidate = JsonNode.Parse(File.ReadAllText(Path.Combine(job.Directory, "volume", "DS-SCI-067.json")));
            var repeat = JsonNode.Parse(File.ReadAllText(Path.Combine(job.Directory, "volume", "DS-SCI-068.json")));
            var artifact = Path.Combine(job.Directory, "volume", "positive-a", "cube.msh");
            var hash = ScientificHash(artifact);
            if (JsonNode.Parse(File.ReadAllText(suiteResult))?["verdict"]?.GetValue<string>() != "passed"
                || candidate?["verdict"]?.GetValue<string>() != "passed"
                || candidate["capabilityId"]?.GetValue<string>() != "mesh.generate3d"
                || candidate["artifactSha256"]?.GetValue<string>() != hash
                || repeat?["verdict"]?.GetValue<string>() != "passed"
                || repeat["artifactSha256"]?.GetValue<string>() != hash
                || (baseline?["level"]?.GetValue<string>() != "L6"
                    && ScientificGmshVolumeLower(job.ProfileId).ToJsonString() != lower.ToJsonString()))
                throw new InvalidDataException("Gmsh volume candidate or supporting L0–L4 evidence changed.");
            var support = (JsonArray)lower["records"]!.DeepClone();
            if (baseline != null)
            {
                if (baseline["artifactSha256"]?.GetValue<string>() != hash)
                    throw new InvalidDataException("Gmsh cube bytes differ from the current L5 run.");
                support.Add(new JsonObject { ["runId"] = baseline["runId"]?.GetValue<string>(),
                    ["recordId"] = baseline["recordId"]?.GetValue<string>(),
                    ["capabilityId"] = "mesh.generate3d", ["level"] = baseline["level"]?.GetValue<string>() });
            }
            var level = baseline?["level"]?.GetValue<string>() == "L6" ? "L7" : baseline == null ? "L5" : "L6";
            var selected = Path.Combine(job.Directory, "volume", level == "L5" ? "DS-SCI-067.json" : level == "L6" ? "DS-SCI-068.json" : "DS-SCI-069.json");
            var evidence = new JsonObject { ["suiteId"] = "gmsh-volume-managed-v1",
                ["capabilityId"] = "mesh.generate3d", ["level"] = level,
                ["candidateFolder"] = "volume", ["candidateRecordSha256"] = ScientificHash(selected),
                ["artifactSha256"] = hash, ["suiteResultSha256"] = ScientificHash(suiteResult),
                ["lowerQualification"] = new JsonObject { ["records"] = support },
                ["baseline"] = baseline?.DeepClone(),
                ["reloadSha256"] = baseline == null ? null : ScientificHash(Path.Combine(job.Directory, "volume", "reload.json")),
                ["reload"] = baseline == null ? null : JsonNode.Parse(File.ReadAllText(Path.Combine(job.Directory, "volume", "reload.json"))),
                ["boundaryArtifactSha256"] = level == "L7" ? ScientificHash(Path.Combine(job.Directory, "volume", "boundary.obj")) : null,
                ["vtk"] = level == "L7" ? JsonNode.Parse(File.ReadAllText(Path.Combine(job.Directory, "volume", "vtk.json"))) : null,
                ["math3d"] = level == "L7" ? JsonNode.Parse(File.ReadAllText(Path.Combine(job.Directory, "volume", "math3d.json"))) : null };
            File.WriteAllText(Path.Combine(job.Directory, "results.json"), new JsonObject {
                ["volumeEvidence"] = evidence, ["validatedCapabilities"] = new JsonArray("mesh.generate3d")
            }.ToJsonString(), new UTF8Encoding(false));
            job.State = "succeeded"; job.Stage = "completed";
        }
        catch (OperationCanceledException) { job.State = "cancelled"; job.Error = "Gmsh volume run was stopped."; }
        catch (TimeoutException error) { job.State = "timed-out"; job.Error = error.Message; }
        catch (Exception error) { job.State = "failed"; job.Error = error.Message; }
        finally
        {
            job.DurationMs = timer.ElapsedMilliseconds;
            try { ScientificFinish(job); ScientificLog(job, $"\n[{job.State}] Gmsh volume / {job.DurationMs} ms {job.Error}\n"); }
            catch (Exception error) { Debug.WriteLine($"Gmsh volume finalization failed: {error}"); }
            finally { ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) }); _scientificGate.Release(); }
        }
    }

    private JsonObject ScientificGmshVolumeCurrentL7(string profileId)
    {
        var summary = ScientificQualificationSummary(profileId, "gmsh-win-conda");
        var record = summary["currentRecords"]?.AsArray().OfType<JsonObject>()
            .Where(item => item["capabilityId"]?.GetValue<string>() == "mesh.generate3d"
                && item["level"]?.GetValue<string>() == "L7")
            .OrderByDescending(item => item["finishedAtUtc"]?.GetValue<string>(), StringComparer.Ordinal)
            .FirstOrDefault() ?? throw new InvalidOperationException("Current Gmsh volume L7 support is required.");
        return new JsonObject { ["runId"] = record["runId"]?.GetValue<string>(),
            ["recordId"] = record["recordId"]?.GetValue<string>(),
            ["capabilityId"] = "mesh.generate3d", ["level"] = "L7" };
    }

    private object ScientificGmshVolumeL8Start(string profileId, string runtimeId)
    {
        ScientificProviderRegistry.RequireAction(runtimeId, "l8-gmsh-volume");
        ScientificGmshVolumeDeclaration("l8.gmsh-volume", "L8");
        var support = ScientificGmshVolumeCurrentL7(profileId);
        var (sourceDirectory, sourceElement) = ScientificHistoryFind(profileId, support["runId"]!.GetValue<string>());
        var sourceResult = JsonNode.Parse(sourceElement.GetRawText());
        var l7 = sourceResult?["volumeEvidence"] as JsonObject;
        if (sourceResult?["recipeId"]?.GetValue<string>() != "l7.gmsh-volume"
            || sourceResult["state"]?.GetValue<string>() != "succeeded" || l7 == null
            || !ScientificQualificationRecords.Verify(sourceDirectory, sourceElement).OfType<JsonObject>().Any(item =>
                item["recordId"]?.GetValue<string>() == support["recordId"]?.GetValue<string>()
                && item["level"]?.GetValue<string>() == "L7"))
            throw new InvalidDataException("The Gmsh volume L7 source is not verified.");
        var artifact = ScientificArtifactFiles.ResolveRegistered(sourceDirectory, sourceElement, "volume/boundary.obj");
        if (ScientificHash(artifact) != l7["boundaryArtifactSha256"]?.GetValue<string>())
            throw new InvalidDataException("The volume boundary artifact changed.");
        var vtkPrefix = ScientificPrefix("vtk-win-conda");
        if (!_scientificGate.Wait(0)) throw new InvalidOperationException("Another Scientific job is running.");
        try
        {
            var directory = Path.Combine(ScientificDataRoot, "runs", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(directory);
            var job = new ScientificJob { ProfileId = profileId, RuntimeId = runtimeId,
                RecipeId = "l8.gmsh-volume", Directory = directory };
            var input = new JsonObject { ["path"] = artifact, ["mediaType"] = "model/obj",
                ["bytes"] = new FileInfo(artifact).Length, ["sha256"] = ScientificHash(artifact),
                ["sourceRunId"] = support["runId"]?.GetValue<string>() };
            var parameters = JsonSerializer.SerializeToElement(new { suiteId = "l8-gmsh-volume-v1",
                sourceRunId = support["runId"]?.GetValue<string>(), sourceRecordId = support["recordId"]?.GetValue<string>(),
                repeatCount = 3, memoryLimitBytes = 134217728 }, ScientificJson);
            var outputs = new JsonArray();
            foreach (var name in new[] { "repeat-1.json", "repeat-2.json", "repeat-3.json", "observations.json" })
                outputs.Add(new JsonObject { ["path"] = "resilience/" + name, ["mediaType"] = "application/json" });
            ScientificWriteRequest(job, parameters, input, additionalOutputs: outputs);
            _scientificJobs[profileId + ":" + runtimeId] = job;
            ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) });
            _ = ScientificGmshL8RunAsync(job, vtkPrefix, artifact, support, sourceDirectory, l7, volume: true);
            return ScientificJobSnapshot(job);
        }
        catch { _scientificGate.Release(); throw; }
    }
}
