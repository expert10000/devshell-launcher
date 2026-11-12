using System.Diagnostics;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace BatchLauncher;

public partial class Form1
{
    private const string VtkReadSuiteId = "vtk-mesh-read-v4";

    private JsonObject ScientificCurrentVtkReadLevel(string profileId, int level)
    {
        var summary = ScientificQualificationSummary(profileId, "vtk-win-conda");
        var current = summary["currentRecords"]?.AsArray().OfType<JsonObject>()
            .Where(item => item["capabilityId"]?.GetValue<string>() == "mesh.read"
                && item["level"]?.GetValue<string>() == $"L{level}"
                && item["evidenceId"]?.GetValue<string>() == $"l{level}.vtk-read")
            .OrderByDescending(item => item["finishedAtUtc"]?.GetValue<string>(), StringComparer.Ordinal)
            .FirstOrDefault() ?? throw new InvalidOperationException($"Current VTK read L{level} evidence is required.");
        return new JsonObject { ["runId"] = current["runId"]?.GetValue<string>(),
            ["recordId"] = current["recordId"]?.GetValue<string>(),
            ["capabilityId"] = "mesh.read", ["level"] = $"L{level}" };
    }

    private object ScientificVtkReadLevelStart(string profileId, string runtimeId, int level)
    {
        if (runtimeId != "vtk-win-conda" || level is < 5 or > 9)
            throw new InvalidOperationException("Unsupported VTK read qualification.");
        ScientificProviderRegistry.RequireAction(runtimeId, $"l{level}-vtk-read");
        var recipe = $"l{level}.vtk-read";
        var declarationPath = Path.Combine(AppContext.BaseDirectory, "runtimes", runtimeId, "runtime.json");
        var declaration = (JsonNode.Parse(File.ReadAllText(declarationPath))?["qualificationRecipes"] as JsonArray)?
            .OfType<JsonObject>().SingleOrDefault(item => item["id"]?.GetValue<string>() == recipe);
        if (declaration?["readinessLevel"]?.GetValue<string>() != $"L{level}"
            || declaration["capability"]?.GetValue<string>() != "mesh.read"
            || (level == 5 && declaration["suiteId"]?.GetValue<string>() != VtkReadSuiteId)
            || (level > 5 && declaration["referenceRecipe"]?.GetValue<string>() != $"l{level - 1}.vtk-read"))
            throw new InvalidOperationException("VTK read qualification is not declared.");
        var manifest = Path.Combine(ScientificSourceRoot, "scientific", "fixtures", "vtk", "read", "manifest.v4.json");
        if (!File.Exists(manifest) || new FileInfo(manifest).Length > 65536
            || JsonNode.Parse(File.ReadAllText(manifest))?["suiteId"]?.GetValue<string>() != VtkReadSuiteId)
            throw new InvalidDataException("Pinned VTK read fixture manifest is unavailable.");
        JsonObject lower;
        JsonObject? support = null;
        string? sourceReport = null;
        if (level == 5) lower = ScientificCurrentLowerLevels(profileId, runtimeId);
        else
        {
            support = ScientificCurrentVtkReadLevel(profileId, level - 1);
            var (sourceDirectory, saved) = ScientificHistoryFind(profileId, support["runId"]!.GetValue<string>());
            var previous = JsonNode.Parse(saved.GetRawText()) as JsonObject;
            var evidence = previous?["vtkReadQualificationEvidence"] as JsonObject;
            if (previous?["recipeId"]?.GetValue<string>() != $"l{level - 1}.vtk-read"
                || previous["state"]?.GetValue<string>() != "succeeded"
                || evidence?["lowerQualification"]?["records"] is not JsonArray previousLower
                || previousLower.Count != level - 1
                || !ScientificQualificationRecords.Verify(sourceDirectory, saved).OfType<JsonObject>()
                    .Any(item => item["recordId"]?.GetValue<string>() == support["recordId"]?.GetValue<string>()))
                throw new InvalidDataException("Previous VTK read level does not verify.");
            sourceReport = Path.GetFullPath(Path.Combine(sourceDirectory, evidence["reportPath"]!.GetValue<string>()));
            if (!sourceReport.StartsWith(sourceDirectory.TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar,
                    StringComparison.OrdinalIgnoreCase)
                || !File.Exists(sourceReport) || ScientificHash(sourceReport) != evidence["reportSha256"]?.GetValue<string>())
                throw new InvalidDataException("Previous VTK read report changed.");
            var records = (JsonArray)previousLower.DeepClone();
            records.Add(support.DeepClone());
            lower = new JsonObject { ["records"] = records };
        }
        var prefix = ScientificPrefix(runtimeId);
        var vtkPython = Path.Combine(prefix, "python.exe");
        if (!File.Exists(vtkPython)) throw new InvalidOperationException("The VTK worker environment is unavailable.");
        if (!_scientificGate.Wait(0)) throw new InvalidOperationException("A Scientific recipe is already running.");
        try
        {
            var directory = Path.Combine(ScientificDataRoot, "runs", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(directory);
            var job = new ScientificJob { ProfileId = profileId, RuntimeId = runtimeId,
                RecipeId = recipe, Directory = directory };
            var parameters = JsonSerializer.SerializeToElement(new { suiteId = VtkReadSuiteId, level,
                sourceRunId = support?["runId"]?.GetValue<string>(),
                sourceRecordId = support?["recordId"]?.GetValue<string>() }, ScientificJson);
            var input = new JsonObject { ["path"] = manifest, ["mediaType"] = "application/json",
                ["bytes"] = new FileInfo(manifest).Length, ["sha256"] = ScientificHash(manifest),
                ["datasetId"] = VtkReadSuiteId };
            ScientificWriteRequest(job, parameters, input, "vtk-read-qualification-evidence.json",
                additionalOutputs: new JsonArray(new JsonObject { ["path"] = "fixture-manifest.json", ["mediaType"] = "application/json" }),
                timeoutSeconds: 600);
            _scientificJobs[profileId + ":" + runtimeId] = job;
            ScientificSend(new { type = "scientific.runtime.job", profileId, job = ScientificJobSnapshot(job) });
            _ = ScientificVtkReadLevelRunAsync(job, prefix, vtkPython, level, lower, sourceReport, support);
            return ScientificJobSnapshot(job);
        }
        catch { _scientificGate.Release(); throw; }
    }

    private async Task ScientificVtkReadLevelRunAsync(ScientificJob job, string prefix, string vtkPython,
        int level, JsonObject lower, string? sourceReport, JsonObject? support)
    {
        var timer = Stopwatch.StartNew();
        try
        {
            File.Copy(Path.Combine(ScientificSourceRoot, "scientific", "fixtures", "vtk", "read", "manifest.v4.json"),
                Path.Combine(job.Directory, "fixture-manifest.json"));
            var script = Path.Combine(ScientificSourceRoot, "tools", "scientific_vtk_read_qualification.py");
            var arguments = new List<string> { script, $"l{level}" };
            if (level == 5) arguments.AddRange(["--python", vtkPython]);
            else arguments.AddRange(["--source", sourceReport!]);
            if (level == 7) arguments.AddRange(["--vtk-python", vtkPython, "--node", Math3DNode,
                "--math3d-checkout", ScientificL7Checkout()]);
            arguments.AddRange(["--output-root", job.Directory]);
            await ScientificProcessAsync(job, prefix, ScientificExecutable("python.exe"), arguments.ToArray(),
                job.Directory, level == 9 ? 600 : 240);
            var reportPath = Directory.EnumerateFiles(job.Directory, $"l{level}.json", SearchOption.AllDirectories).Single();
            var report = JsonNode.Parse(File.ReadAllText(reportPath)) as JsonObject
                ?? throw new InvalidDataException("VTK read qualification report is invalid.");
            if (report["verdict"]?.GetValue<string>() != "passed")
                throw new InvalidDataException("VTK read qualification did not pass.");
            var evidence = new JsonObject { ["suiteId"] = VtkReadSuiteId, ["level"] = $"L{level}",
                ["capabilityId"] = "mesh.read", ["reportPath"] = Path.GetRelativePath(job.Directory, reportPath).Replace('\\', '/'),
                ["reportSha256"] = ScientificHash(reportPath), ["manifestSha256"] = report["manifestSha256"]?.GetValue<string>(),
                ["sourceRoot"] = ScientificSourceRoot, ["lowerQualification"] = lower.DeepClone(),
                ["sourceRunId"] = support?["runId"]?.GetValue<string>(),
                ["sourceRecordId"] = support?["recordId"]?.GetValue<string>(),
                ["sourceReportSha256"] = sourceReport == null ? null : ScientificHash(sourceReport) };
            if (level == 7) evidence["consumerSourceSha256"] = report["math3dImporterSha256"]?.GetValue<string>();
            if (level == 9) evidence["consumerSourceSha256"] = ScientificCurrentVtkReadProductSources(ScientificL7Checkout());
            File.WriteAllText(Path.Combine(job.Directory, "vtk-read-qualification-evidence.json"), evidence.ToJsonString(), new UTF8Encoding(false));
            File.WriteAllText(Path.Combine(job.Directory, "results.json"), new JsonObject
            {
                ["vtkReadQualificationEvidence"] = evidence.DeepClone(),
                ["validatedCapabilities"] = new JsonArray("mesh.read")
            }.ToJsonString(), new UTF8Encoding(false));
            job.State = "succeeded"; job.Stage = "completed";
        }
        catch (OperationCanceledException) { job.State = "cancelled"; job.Error = "Only this VTK read qualification was stopped."; }
        catch (TimeoutException error) { job.State = "timed-out"; job.Error = error.Message; }
        catch (Exception error) { job.State = "failed"; job.Error = error.Message; }
        finally
        {
            job.DurationMs = timer.ElapsedMilliseconds;
            try { ScientificFinish(job); ScientificLog(job, $"\n[{job.State}] VTK read L{level} / {job.DurationMs} ms {job.Error}\n"); }
            catch (Exception error) { Debug.WriteLine($"VTK read L{level} finalization failed: {error}"); }
            finally { ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) }); _scientificGate.Release(); }
        }
    }

    private static string? ScientificCurrentVtkReadProductSources(string checkout)
    {
        var sources = new JsonObject();
        foreach (var name in new[] { "renderer/src/mesh/surfaceMesh.ts", "renderer/src/mesh/meshDocumentAdapter.ts",
            "renderer/src/mesh/meshResourceStore.ts", "packages/core/src/meshDocument.ts",
            "src/main/python/nativeCgalProtocol.ts", "renderer/src/workspace/MeshDocumentViewport.tsx" })
        {
            var path = Path.Combine(checkout, name.Replace('/', Path.DirectorySeparatorChar));
            if (!File.Exists(path)) return null;
            sources[name] = ScientificHash(path);
        }
        return ScientificL6Digest(sources);
    }
}
