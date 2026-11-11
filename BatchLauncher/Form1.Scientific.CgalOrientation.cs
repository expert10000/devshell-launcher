using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace BatchLauncher;

public partial class Form1
{
    private const string OrientationSuiteId = "cgal-orientation-v2";

    private JsonObject ScientificCurrentOrientationLevel(string profileId, int level)
    {
        var summary = ScientificQualificationSummary(profileId, "cgal-win-conda");
        var support = summary["currentRecords"]?.AsArray().OfType<JsonObject>()
            .Where(item => item["capabilityId"]?.GetValue<string>() == "mesh.orient"
                && item["level"]?.GetValue<string>() == $"L{level}")
            .OrderByDescending(item => item["finishedAtUtc"]?.GetValue<string>(), StringComparer.Ordinal)
            .FirstOrDefault() ?? throw new InvalidOperationException($"Current mesh.orient L{level} evidence is required.");
        return new JsonObject { ["runId"] = support["runId"]?.GetValue<string>(),
            ["recordId"] = support["recordId"]?.GetValue<string>(), ["capabilityId"] = "mesh.orient",
            ["level"] = $"L{level}" };
    }

    private object ScientificCgalOrientationLevelStart(string profileId, string runtimeId, int level)
    {
        if (runtimeId != "cgal-win-conda" || level is < 5 or > 9)
            throw new InvalidOperationException("Unsupported guarded orientation qualification.");
        ScientificProviderRegistry.RequireAction(runtimeId, $"l{level}-cgal-orient");
        var recipe = $"l{level}.cgal-orient";
        var declarationPath = Path.Combine(AppContext.BaseDirectory, "runtimes", runtimeId, "runtime.json");
        var declaration = (JsonNode.Parse(File.ReadAllText(declarationPath))?["qualificationRecipes"] as JsonArray)?
            .OfType<JsonObject>().SingleOrDefault(item => item["id"]?.GetValue<string>() == recipe);
        if (declaration?["readinessLevel"]?.GetValue<string>() != $"L{level}"
            || declaration["capability"]?.GetValue<string>() != "mesh.orient"
            || (level == 5 && declaration["suiteId"]?.GetValue<string>() != OrientationSuiteId)
            || (level > 5 && declaration["referenceRecipe"]?.GetValue<string>() != $"l{level - 1}.cgal-orient"))
            throw new InvalidOperationException("Guarded orientation qualification is not declared.");
        var manifest = Path.Combine(ScientificSourceRoot, "scientific", "fixtures", "cgal", "orientation", "manifest.v2.json");
        if (!File.Exists(manifest) || new FileInfo(manifest).Length > 65536
            || JsonNode.Parse(File.ReadAllText(manifest))?["suiteId"]?.GetValue<string>() != OrientationSuiteId)
            throw new InvalidDataException("Pinned orientation fixture manifest is unavailable.");
        JsonObject lower;
        string? sourceReport = null;
        JsonObject? support = null;
        if (level == 5) lower = ScientificCurrentLowerLevels(profileId, runtimeId);
        else
        {
            support = ScientificCurrentOrientationLevel(profileId, level - 1);
            var (sourceDirectory, saved) = ScientificHistoryFind(profileId, support["runId"]!.GetValue<string>());
            var previous = JsonNode.Parse(saved.GetRawText()) as JsonObject;
            var evidence = previous?["orientationQualificationEvidence"] as JsonObject;
            if (previous?["recipeId"]?.GetValue<string>() != $"l{level - 1}.cgal-orient"
                || previous["state"]?.GetValue<string>() != "succeeded"
                || evidence?["lowerQualification"]?["records"] is not JsonArray previousLower
                || previousLower.Count != level - 1
                || !ScientificQualificationRecords.Verify(sourceDirectory, saved).OfType<JsonObject>()
                    .Any(item => item["recordId"]?.GetValue<string>() == support["recordId"]?.GetValue<string>()))
                throw new InvalidDataException("Previous guarded orientation level does not verify.");
            sourceReport = Path.GetFullPath(Path.Combine(sourceDirectory, evidence["reportPath"]!.GetValue<string>()));
            if (!sourceReport.StartsWith(sourceDirectory.TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar,
                    StringComparison.OrdinalIgnoreCase)
                || !File.Exists(sourceReport) || ScientificHash(sourceReport) != evidence["reportSha256"]?.GetValue<string>())
                throw new InvalidDataException("Previous guarded orientation report changed.");
            var records = (JsonArray)previousLower.DeepClone();
            records.Add(support.DeepClone());
            lower = new JsonObject { ["records"] = records };
        }
        var prefix = ScientificPrefix(runtimeId);
        var vtkPython = Path.Combine(ScientificPrefix("vtk-win-conda"), "python.exe");
        if (level >= 7 && !File.Exists(vtkPython))
            throw new InvalidOperationException("The VTK consumer Python is unavailable.");
        if (!_scientificGate.Wait(0)) throw new InvalidOperationException("A Scientific recipe is already running.");
        try
        {
            var directory = Path.Combine(ScientificDataRoot, "runs", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(directory);
            var job = new ScientificJob { ProfileId = profileId, RuntimeId = runtimeId,
                RecipeId = recipe, Directory = directory };
            var parameters = JsonSerializer.SerializeToElement(new { suiteId = OrientationSuiteId, level,
                sourceRunId = support?["runId"]?.GetValue<string>(),
                sourceRecordId = support?["recordId"]?.GetValue<string>() }, ScientificJson);
            var input = new JsonObject { ["path"] = manifest, ["mediaType"] = "application/json",
                ["bytes"] = new FileInfo(manifest).Length, ["sha256"] = ScientificHash(manifest),
                ["datasetId"] = OrientationSuiteId };
            ScientificWriteRequest(job, parameters, input, "orientation-qualification-evidence.json",
                additionalOutputs: new JsonArray(new JsonObject { ["path"] = "fixture-manifest.json", ["mediaType"] = "application/json" }),
                timeoutSeconds: 600);
            _scientificJobs[profileId + ":" + runtimeId] = job;
            ScientificSend(new { type = "scientific.runtime.job", profileId, job = ScientificJobSnapshot(job) });
            _ = ScientificCgalOrientationLevelRunAsync(job, prefix, vtkPython, level, lower, sourceReport, support);
            return ScientificJobSnapshot(job);
        }
        catch { _scientificGate.Release(); throw; }
    }

    private async Task ScientificCgalOrientationLevelRunAsync(ScientificJob job, string prefix, string vtkPython,
        int level, JsonObject lower, string? sourceReport, JsonObject? support)
    {
        var timer = Stopwatch.StartNew();
        try
        {
            File.Copy(Path.Combine(ScientificSourceRoot, "scientific", "fixtures", "cgal", "orientation", "manifest.v2.json"),
                Path.Combine(job.Directory, "fixture-manifest.json"));
            var python = ScientificExecutable("python.exe");
            var scripts = new[] { "scientific_cgal_orientation_qualification.py", "scientific_cgal_orientation_qualification.py",
                "scientific_cgal_orientation_l7.py", "scientific_cgal_orientation_l8.py", "scientific_cgal_orientation_l9.py" };
            var script = Path.Combine(ScientificSourceRoot, "tools", scripts[level - 5]);
            var arguments = new List<string> { script, level is 5 or 6 ? $"l{level}" : "run" };
            if (level == 5)
            {
                var key = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(job.ProfileId + "|" + prefix)))[..12];
                var build = Path.Combine(ScientificDataRoot, "builds", key, "cgal-worker");
                var cmake = Path.Combine(prefix, "Library", "bin", "cmake.exe");
                await ScientificProcessAsync(job, prefix, cmake, ["-S", Path.Combine(ScientificSourceRoot, "scientific", "cgal-worker"),
                    "-B", build, "-G", "Visual Studio 17 2022", "-A", "x64",
                    "-DCMAKE_PREFIX_PATH=" + Path.Combine(prefix, "Library")], job.Directory, 180);
                await ScientificProcessAsync(job, prefix, cmake,
                    ["--build", build, "--config", "Release", "--target", "devshell_cgal_orientation", "--parallel", "1"],
                    job.Directory, 180);
                var worker = Path.Combine(build, "Release", "devshell_cgal_orientation.exe");
                job.ExecutedFiles.Add(ScientificRunFingerprint.ExecutedFile(worker, "cgal-orientation-worker"));
                arguments.AddRange(["--worker", worker, "--prefix", prefix]);
            }
            else arguments.AddRange(["--source", sourceReport!]);
            if (level == 7)
                arguments.AddRange(["--vtk-python", vtkPython, "--node", Math3DNode,
                    "--math3d-checkout", ScientificL7Checkout()]);
            if (level == 8) arguments.AddRange(["--vtk-python", vtkPython]);
            if (level == 9) arguments.AddRange(["--node", Math3DNode]);
            arguments.AddRange(["--output-root", job.Directory]);
            await ScientificProcessAsync(job, prefix, python, arguments.ToArray(), job.Directory, level == 9 ? 300 : 180);
            var reportPath = Directory.EnumerateFiles(job.Directory, $"l{level}.json", SearchOption.AllDirectories).Single();
            var report = JsonNode.Parse(File.ReadAllText(reportPath)) as JsonObject
                ?? throw new InvalidDataException("Orientation qualification report is invalid.");
            if (report["verdict"]?.GetValue<string>() != "passed")
                throw new InvalidDataException("Orientation qualification did not pass.");
            var evidence = new JsonObject { ["suiteId"] = OrientationSuiteId, ["level"] = $"L{level}",
                ["capabilityId"] = "mesh.orient", ["reportPath"] = Path.GetRelativePath(job.Directory, reportPath).Replace('\\', '/'),
                ["reportSha256"] = ScientificHash(reportPath), ["manifestSha256"] = report["manifestSha256"]?.GetValue<string>(),
                ["sourceRoot"] = ScientificSourceRoot, ["lowerQualification"] = lower.DeepClone(),
                ["sourceRunId"] = support?["runId"]?.GetValue<string>(),
                ["sourceRecordId"] = support?["recordId"]?.GetValue<string>(),
                ["sourceReportSha256"] = sourceReport == null ? null : ScientificHash(sourceReport) };
            if (level == 7) evidence["consumerSourceSha256"] = report["math3dImporterSha256"]?.GetValue<string>();
            if (level == 9) evidence["consumerSourceSha256"] = ScientificCurrentOrientationProductSources(ScientificL7Checkout());
            File.WriteAllText(Path.Combine(job.Directory, "orientation-qualification-evidence.json"), evidence.ToJsonString(), new UTF8Encoding(false));
            File.WriteAllText(Path.Combine(job.Directory, "results.json"), new JsonObject
            {
                ["orientationQualificationEvidence"] = evidence.DeepClone(),
                ["validatedCapabilities"] = new JsonArray("mesh.orient")
            }.ToJsonString(), new UTF8Encoding(false));
            job.State = "succeeded"; job.Stage = "completed";
        }
        catch (OperationCanceledException) { job.State = "cancelled"; job.Error = "Only this orientation qualification was stopped."; }
        catch (TimeoutException error) { job.State = "timed-out"; job.Error = error.Message; }
        catch (Exception error) { job.State = "failed"; job.Error = error.Message; }
        finally
        {
            job.DurationMs = timer.ElapsedMilliseconds;
            try { ScientificFinish(job); ScientificLog(job, $"\n[{job.State}] orientation L{level} / {job.DurationMs} ms {job.Error}\n"); }
            catch (Exception error) { Debug.WriteLine($"Orientation L{level} finalization failed: {error}"); }
            finally { ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) }); _scientificGate.Release(); }
        }
    }

    private static string? ScientificCurrentOrientationProductSources(string checkout)
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
