using System.Diagnostics;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace BatchLauncher;

public partial class Form1
{
    private string ScientificL7Checkout()
    {
        var configured = Environment.GetEnvironmentVariable("MATH3D_CHECKOUT");
        var candidates = new[] { configured, Math3DCheckout,
            Path.Combine(Path.GetDirectoryName(Path.GetDirectoryName(ScientificPrefix("vtk-win-conda"))!)!, "Math3D") };
        return candidates.FirstOrDefault(path => !string.IsNullOrWhiteSpace(path)
            && File.Exists(Path.Combine(path, "renderer", "src", "mesh", "surfaceMesh.ts")))
            ?? Math3DCheckout;
    }

    private JsonObject ScientificCurrentL6(string profileId, string runtimeId = "vtk-win-conda")
    {
        var summary = ScientificQualificationSummary(profileId, runtimeId);
        var capability = runtimeId == "cgal-win-conda" ? "mesh.validate" : "mesh.read";
        var support = summary["currentRecords"]?.AsArray().OfType<JsonObject>()
            .Where(item => item["capabilityId"]?.GetValue<string>() == capability
                && item["level"]?.GetValue<string>() == "L6")
            .OrderByDescending(item => item["finishedAtUtc"]?.GetValue<string>(), StringComparer.Ordinal)
            .FirstOrDefault();
        if (support == null) throw new InvalidOperationException("A current L6 round-trip qualification is required before L7.");
        return new JsonObject { ["runId"] = support["runId"]?.GetValue<string>(),
            ["recordId"] = support["recordId"]?.GetValue<string>(), ["capabilityId"] = capability, ["level"] = "L6" };
    }

    private static void ScientificCheckL7Declaration()
    {
        var path = Path.Combine(AppContext.BaseDirectory, "runtimes", "vtk-win-conda", "runtime.json");
        var declaration = (JsonNode.Parse(File.ReadAllText(path))?["qualificationRecipes"] as JsonArray)?
            .OfType<JsonObject>().FirstOrDefault(item => item["id"]?.GetValue<string>() == "l7.math3d-import");
        if (declaration?["readinessLevel"]?.GetValue<string>() != "L7"
            || declaration["capability"]?.GetValue<string>() != "mesh.interop.math3d"
            || declaration["referenceRecipe"]?.GetValue<string>() != "l6.reproduce"
            || declaration["consumer"]?.GetValue<string>() != "MATH3D desktop loadSurfaceMeshFromFile")
            throw new InvalidOperationException("L7 MATH3D handoff is not registered in the VTK manifest.");
    }

    private static JsonObject ScientificL7Source(string profileId, JsonObject support, string runtimeId = "vtk-win-conda")
    {
        var runId = support["runId"]?.GetValue<string>() ?? "";
        var (directory, result) = ScientificHistoryFind(profileId, runId);
        var source = JsonNode.Parse(result.GetRawText()) as JsonObject;
        var evidence = source?["l6Evidence"] as JsonObject;
        var recordId = support["recordId"]?.GetValue<string>();
        if (source?["runtimeId"]?.GetValue<string>() != runtimeId
            || source["recipeId"]?.GetValue<string>() != "l6.reproduce"
            || source["state"]?.GetValue<string>() != "succeeded"
            || evidence?["verdict"]?.GetValue<string>() != "matched"
            || evidence["roundTrip"]?["closed"]?.GetValue<bool>() != true
            || !ScientificQualificationRecords.Verify(directory, result).OfType<JsonObject>()
                .Any(item => item["recordId"]?.GetValue<string>() == recordId && item["level"]?.GetValue<string>() == "L6"))
            throw new InvalidDataException("The L6 source is not a verified round-trip run.");
        var relative = evidence["positive"]?["artifactPath"]?.GetValue<string>() ?? "";
        var artifact = ScientificArtifactFiles.ResolveRegistered(directory, result, relative);
        var hash = ScientificHash(artifact);
        if (hash != evidence["positive"]?["artifactSha256"]?.GetValue<string>())
            throw new InvalidDataException("The L6 VTK artifact hash changed.");
        return new JsonObject { ["runId"] = runId, ["folderId"] = Path.GetFileName(directory), ["recordId"] = recordId,
            ["runFingerprintSha256"] = source["runFingerprintSha256"]?.GetValue<string>(),
            ["artifactPath"] = relative, ["artifactSha256"] = hash, ["artifactBytes"] = new FileInfo(artifact).Length,
            ["absolutePath"] = artifact, ["roundTrip"] = evidence["roundTrip"]?.DeepClone(),
            ["lowerQualification"] = evidence["lowerQualification"]?.DeepClone() };
    }

    private object ScientificL7Start(string profileId, string runtimeId)
    {
        ScientificProviderRegistry.RequireAction(runtimeId, "l7-math3d-import");
        ScientificCheckL7Declaration();
        var support = ScientificCurrentL6(profileId);
        var source = ScientificL7Source(profileId, support);
        var checkout = ScientificL7Checkout();
        var importer = Path.Combine(checkout, "renderer", "src", "mesh", "surfaceMesh.ts");
        var vite = Path.Combine(checkout, "renderer", "node_modules", "vite");
        if (!File.Exists(importer) || !Directory.Exists(vite))
            throw new InvalidOperationException("The local MATH3D desktop importer and its renderer dependencies are required for L7.");
        var node = Math3DNode;
        var prefix = ScientificPrefix(runtimeId);
        if (!_scientificGate.Wait(0)) throw new InvalidOperationException("Another Scientific job is running; stop or wait for it.");
        try
        {
            var directory = Path.Combine(ScientificDataRoot, "runs", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(directory);
            var job = new ScientificJob { ProfileId = profileId, RuntimeId = runtimeId,
                RecipeId = "l7.math3d-import", Directory = directory };
            var input = new JsonObject { ["path"] = source["absolutePath"]?.GetValue<string>(),
                ["mediaType"] = "application/vnd.vtk.vtp", ["bytes"] = source["artifactBytes"]?.GetValue<long>(),
                ["sha256"] = source["artifactSha256"]?.GetValue<string>(),
                ["sourceRunId"] = source["runId"]?.GetValue<string>() };
            var parameters = JsonSerializer.SerializeToElement(new { suiteId = "l7-math3d-import-v1",
                sourceRunId = source["runId"]?.GetValue<string>(), sourceRecordId = support["recordId"]?.GetValue<string>() }, ScientificJson);
            ScientificWriteRequest(job, parameters, input, additionalOutputs: new JsonArray(
                new JsonObject { ["path"] = "handoff/vtk-math3d.obj", ["mediaType"] = "model/obj" },
                new JsonObject { ["path"] = "handoff/reload.json", ["mediaType"] = "application/json" },
                new JsonObject { ["path"] = "handoff/consumed.json", ["mediaType"] = "application/json" }));
            _scientificJobs[profileId + ":" + runtimeId] = job;
            ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) });
            _ = ScientificL7RunAsync(job, prefix, node, checkout, importer, source, support);
            return ScientificJobSnapshot(job);
        }
        catch { _scientificGate.Release(); throw; }
    }

    private async Task ScientificL7RunAsync(ScientificJob job, string prefix, string node, string checkout,
        string importer, JsonObject source, JsonObject support)
    {
        var timer = Stopwatch.StartNew();
        try
        {
            var handoff = Path.Combine(job.Directory, "handoff");
            Directory.CreateDirectory(handoff);
            var converted = Path.Combine(handoff, "vtk-math3d.obj");
            var reloadPath = Path.Combine(handoff, "reload.json");
            var consumedPath = Path.Combine(handoff, "consumed.json");
            job.Stage = "convert";
            await ScientificProcessAsync(job, prefix, Path.Combine(prefix, "python.exe"),
                [Path.Combine(ScientificSourceRoot, "tools", "scientific-artifact-roundtrip.py"),
                    "--input", source["absolutePath"]!.GetValue<string>(), "--result", reloadPath,
                    "--export-obj", converted], handoff, 60);
            job.Stage = "consume";
            await ScientificProcessAsync(job, prefix, node,
                [Path.Combine(ScientificSourceRoot, "tools", "math3d-vtk-import-handoff.mjs"),
                    "--checkout", checkout, "--input", converted, "--result", consumedPath], handoff, 120);
            var reload = JsonNode.Parse(File.ReadAllText(reloadPath)) as JsonObject;
            var consumed = JsonNode.Parse(File.ReadAllText(consumedPath)) as JsonObject;
            var previous = source["roundTrip"] as JsonObject;
            if (reload == null || consumed == null || previous == null
                || reload["artifactSha256"]?.GetValue<string>() != source["artifactSha256"]?.GetValue<string>()
                || reload["points"]?.GetValue<int>() != previous["points"]?.GetValue<int>()
                || reload["triangles"]?.GetValue<int>() != previous["triangles"]?.GetValue<int>()
                || reload["bounds"]?.ToJsonString() != previous["bounds"]?.ToJsonString()
                || consumed["inputObjSha256"]?.GetValue<string>() != ScientificHash(converted)
                || consumed["importerSourceSha256"]?.GetValue<string>() != ScientificHash(importer)
                || !ScientificQualificationRecords.ValidMath3DImport(reload, consumed))
                throw new InvalidDataException("The MATH3D importer did not preserve the VTK mesh geometry.");
            var current = ScientificCurrentL6(job.ProfileId);
            if (current["recordId"]?.GetValue<string>() != support["recordId"]?.GetValue<string>())
                throw new InvalidOperationException("The pinned L6 VTK evidence is no longer current.");
            var lowerRecords = (JsonArray)source["lowerQualification"]!["records"]!.DeepClone();
            lowerRecords.Add(support.DeepClone());
            var reference = (JsonObject)source.DeepClone();
            reference.Remove("absolutePath");
            var evidence = new JsonObject { ["suiteId"] = "l7-math3d-import-v1", ["capabilityId"] = "mesh.interop.math3d",
                ["source"] = reference, ["conversion"] = reload.DeepClone(), ["conversionSha256"] = ScientificHash(reloadPath),
                ["objSha256"] = ScientificHash(converted), ["consumer"] = consumed.DeepClone(),
                ["consumerSha256"] = ScientificHash(consumedPath), ["importerSourceSha256"] = ScientificHash(importer),
                ["lowerQualification"] = new JsonObject { ["records"] = lowerRecords } };
            File.WriteAllText(Path.Combine(job.Directory, "results.json"), new JsonObject
            {
                ["l7Evidence"] = evidence, ["validatedCapabilities"] = new JsonArray("mesh.interop.math3d")
            }.ToJsonString(), new UTF8Encoding(false));
            job.State = "succeeded"; job.Stage = "completed";
        }
        catch (OperationCanceledException) { job.State = "cancelled"; job.Error = "The owned L7 handoff was stopped."; }
        catch (TimeoutException exception) { job.State = "timed-out"; job.Error = exception.Message; }
        catch (Exception exception) { job.State = "failed"; job.Error = exception.Message; }
        finally
        {
            job.DurationMs = timer.ElapsedMilliseconds;
            try { ScientificFinish(job); ScientificLog(job, $"\n[{job.State}] L7 MATH3D importer handoff / {job.DurationMs} ms {job.Error}\n"); }
            catch (Exception exception) { Debug.WriteLine($"L7 handoff finalization failed: {exception}"); }
            finally { ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) }); _scientificGate.Release(); }
        }
    }
}
