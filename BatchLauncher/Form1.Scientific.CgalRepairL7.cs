using System.Diagnostics;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace BatchLauncher;

public partial class Form1
{
    private JsonObject ScientificCurrentRepairLevel(string profileId, string level)
    {
        var summary = ScientificQualificationSummary(profileId, "cgal-win-conda");
        var support = summary["currentRecords"]?.AsArray().OfType<JsonObject>()
            .Where(item => item["capabilityId"]?.GetValue<string>() == "mesh.repair"
                && item["level"]?.GetValue<string>() == level)
            .OrderByDescending(item => item["finishedAtUtc"]?.GetValue<string>(), StringComparer.Ordinal)
            .FirstOrDefault() ?? throw new InvalidOperationException($"Current mesh.repair {level} evidence is required.");
        return new JsonObject { ["runId"] = support["runId"]?.GetValue<string>(),
            ["recordId"] = support["recordId"]?.GetValue<string>(),
            ["capabilityId"] = "mesh.repair", ["level"] = level };
    }

    private static void ScientificCheckRepairL7Declaration()
    {
        var path = Path.Combine(AppContext.BaseDirectory, "runtimes", "cgal-win-conda", "runtime.json");
        var declaration = (JsonNode.Parse(File.ReadAllText(path))?["qualificationRecipes"] as JsonArray)?
            .OfType<JsonObject>().SingleOrDefault(item => item["id"]?.GetValue<string>() == "l7.cgal-repair");
        if (declaration?["readinessLevel"]?.GetValue<string>() != "L7"
            || declaration["capability"]?.GetValue<string>() != "mesh.repair"
            || declaration["referenceRecipe"]?.GetValue<string>() != "l6.cgal-repair"
            || declaration["consumer"]?.GetValue<string>() != "VTK+MATH3D")
            throw new InvalidOperationException("The repair L7 consumer handoff is not declared.");
    }

    private object ScientificCgalRepairL7Start(string profileId, string runtimeId)
    {
        ScientificProviderRegistry.RequireAction(runtimeId, "l7-cgal-repair");
        ScientificCheckRepairL7Declaration();
        var support = ScientificCurrentRepairLevel(profileId, "L6");
        var (sourceDirectory, saved) = ScientificHistoryFind(profileId, support["runId"]!.GetValue<string>());
        var source = JsonNode.Parse(saved.GetRawText()) as JsonObject
            ?? throw new InvalidDataException("The repair L6 source is invalid.");
        var evidence = source["repairReproductionEvidence"] as JsonObject;
        if (source["runtimeId"]?.GetValue<string>() != runtimeId
            || source["recipeId"]?.GetValue<string>() != "l6.cgal-repair"
            || source["state"]?.GetValue<string>() != "succeeded"
            || evidence?["verdict"]?.GetValue<string>() != "matched"
            || evidence["cases"] is not JsonArray cases || cases.Count != 6
            || !ScientificQualificationRecords.Verify(sourceDirectory, saved).OfType<JsonObject>()
                .Any(item => item["recordId"]?.GetValue<string>() == support["recordId"]?.GetValue<string>()
                    && item["capabilityId"]?.GetValue<string>() == "mesh.repair" && item["level"]?.GetValue<string>() == "L6"))
            throw new InvalidDataException("The repair L6 source does not verify.");
        var selected = RepairL5Cases.Where(item => item.Positive).Select(test =>
        {
            var entry = cases.OfType<JsonObject>().Single(item => item["caseId"]?.GetValue<string>() == test.Id);
            var relative = entry["artifactPath"]?.GetValue<string>() ?? "";
            if (relative != $"cases/{test.Id}/repaired.obj")
                throw new InvalidDataException("The L6 repair output path changed.");
            var path = ScientificArtifactFiles.ResolveRegistered(sourceDirectory, saved, relative);
            var hash = ScientificHash(path);
            if (hash != entry["artifactSha256"]?.GetValue<string>())
                throw new InvalidDataException("The L6 repair output hash changed.");
            return (test.Id, Relative: relative, Path: path, Hash: hash, Bytes: new FileInfo(path).Length);
        }).ToArray();
        var checkout = ScientificL7Checkout();
        var importer = Path.Combine(checkout, "renderer", "src", "mesh", "surfaceMesh.ts");
        if (!File.Exists(importer) || !Directory.Exists(Path.Combine(checkout, "renderer", "node_modules", "vite")))
            throw new InvalidOperationException("The MATH3D desktop importer is unavailable.");
        var vtkPrefix = ScientificPrefix("vtk-win-conda");
        var vtkPython = Path.Combine(vtkPrefix, "python.exe");
        if (!File.Exists(vtkPython)) throw new InvalidOperationException("The VTK reader is unavailable.");
        var node = Math3DNode;
        if (!_scientificGate.Wait(0)) throw new InvalidOperationException("A Scientific recipe is already running.");
        try
        {
            var directory = Path.Combine(ScientificDataRoot, "runs", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(directory);
            var job = new ScientificJob { ProfileId = profileId, RuntimeId = runtimeId,
                RecipeId = "l7.cgal-repair", Directory = directory };
            var inputs = selected.Select(item => new JsonObject { ["path"] = item.Path, ["mediaType"] = "model/obj",
                ["bytes"] = item.Bytes, ["sha256"] = item.Hash,
                ["sourceRunId"] = support["runId"]?.GetValue<string>() }).ToArray();
            var outputs = new JsonArray();
            foreach (var item in selected)
                foreach (var name in new[] { "source-reload.json", "vtk-consumed.json", "math3d-consumed.json" })
                    outputs.Add(new JsonObject { ["path"] = $"handoff/{item.Id}/{name}", ["mediaType"] = "application/json" });
            outputs.Add(new JsonObject { ["path"] = "handoff/malformed.obj", ["mediaType"] = "model/obj" });
            outputs.Add(new JsonObject { ["path"] = "handoff/rejection.json", ["mediaType"] = "application/json" });
            var parameters = JsonSerializer.SerializeToElement(new { suiteId = "cgal-repair-interop-v1",
                sourceL6RunId = support["runId"]?.GetValue<string>(), sourceL6RecordId = support["recordId"]?.GetValue<string>() }, ScientificJson);
            ScientificWriteRequest(job, parameters, inputs[0], "repair-l7-evidence.json",
                new JsonArray(inputs.Skip(1).Select(item => (JsonNode)item.DeepClone()).ToArray()), outputs);
            _scientificJobs[profileId + ":" + runtimeId] = job;
            ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) });
            _ = ScientificCgalRepairL7RunAsync(job, vtkPrefix, vtkPython, node, checkout, importer,
                sourceDirectory, source, evidence, selected, support);
            return ScientificJobSnapshot(job);
        }
        catch { _scientificGate.Release(); throw; }
    }

    private async Task ScientificCgalRepairL7RunAsync(ScientificJob job, string vtkPrefix, string vtkPython,
        string node, string checkout, string importer, string sourceDirectory, JsonObject source,
        JsonObject l6Evidence, (string Id, string Relative, string Path, string Hash, long Bytes)[] selected,
        JsonObject support)
    {
        var timer = Stopwatch.StartNew();
        try
        {
            var handoff = Path.Combine(job.Directory, "handoff");
            Directory.CreateDirectory(handoff);
            var reloadTool = Path.Combine(ScientificSourceRoot, "tools", "scientific-artifact-roundtrip.py");
            var vtkTool = Path.Combine(ScientificSourceRoot, "tools", "scientific-vtk-interop.py");
            var math3dTool = Path.Combine(ScientificSourceRoot, "tools", "math3d-vtk-import-handoff.mjs");
            var malformed = Path.Combine(handoff, "malformed.obj");
            var rejectionFile = Path.Combine(handoff, "rejection.json");
            File.WriteAllText(malformed, "v 0 0 0\nf 1 2 3\n", new UTF8Encoding(false));
            await ScientificProcessAsync(job, vtkPrefix, vtkPython,
                [vtkTool, "--input", malformed, "--result", rejectionFile, "--expect-reject"], handoff, 60);
            var rejection = JsonNode.Parse(File.ReadAllText(rejectionFile)) as JsonObject
                ?? throw new InvalidDataException("The VTK malformed-input rejection is missing.");
            var outcomes = new JsonArray();
            foreach (var item in selected)
            {
                job.Cancellation.Token.ThrowIfCancellationRequested();
                job.Stage = item.Id;
                var caseDirectory = Path.Combine(handoff, item.Id);
                Directory.CreateDirectory(caseDirectory);
                var reloadFile = Path.Combine(caseDirectory, "source-reload.json");
                var vtkFile = Path.Combine(caseDirectory, "vtk-consumed.json");
                var math3dFile = Path.Combine(caseDirectory, "math3d-consumed.json");
                await ScientificProcessAsync(job, vtkPrefix, vtkPython,
                    [reloadTool, "--input", item.Path, "--result", reloadFile], caseDirectory, 60);
                await ScientificProcessAsync(job, vtkPrefix, vtkPython,
                    [vtkTool, "--input", item.Path, "--result", vtkFile], caseDirectory, 60);
                await ScientificProcessAsync(job, vtkPrefix, node,
                    [math3dTool, "--checkout", checkout, "--input", item.Path, "--result", math3dFile], caseDirectory, 120);
                var reload = JsonNode.Parse(File.ReadAllText(reloadFile)) as JsonObject;
                var vtk = JsonNode.Parse(File.ReadAllText(vtkFile)) as JsonObject;
                var math3d = JsonNode.Parse(File.ReadAllText(math3dFile)) as JsonObject;
                if (reload == null || vtk == null || math3d == null
                    || reload["artifactSha256"]?.GetValue<string>() != item.Hash
                    || !ScientificQualificationRecords.ValidRepairInteropSemantics(reload, vtk, math3d,
                        rejection, ScientificHash(malformed), ScientificHash(vtkTool), ScientificHash(importer)))
                    throw new InvalidDataException($"Repair case {item.Id} changed across independent consumers.");
                outcomes.Add(new JsonObject { ["caseId"] = item.Id, ["artifactPath"] = item.Relative,
                    ["artifactSha256"] = item.Hash, ["sourceReload"] = reload.DeepClone(),
                    ["sourceReloadSha256"] = ScientificHash(reloadFile), ["vtkConsumer"] = vtk.DeepClone(),
                    ["vtkConsumerSha256"] = ScientificHash(vtkFile), ["math3dConsumer"] = math3d.DeepClone(),
                    ["math3dConsumerSha256"] = ScientificHash(math3dFile) });
            }
            if (ScientificCurrentRepairLevel(job.ProfileId, "L6")["recordId"]?.GetValue<string>()
                != support["recordId"]?.GetValue<string>())
                throw new InvalidOperationException("The repair L6 support is no longer current.");
            var lower = (JsonArray)l6Evidence["lowerQualification"]!["records"]!.DeepClone();
            lower.Add(support.DeepClone());
            var vtkEnvironment = ScientificRunFingerprint.Capture("vtk-win-conda", job.ProfileId,
                ScientificSourceRoot, AppContext.BaseDirectory, ScientificReportPath())["environment"];
            var contract = new JsonObject { ["schemaVersion"] = 1, ["format"] = "obj",
                ["comparisonTolerance"] = 1e-6, ["vtkReaderSourceSha256"] = ScientificHash(vtkTool),
                ["vtkPythonSha256"] = ScientificHash(vtkPython),
                ["vtkEnvironmentSha256"] = ScientificL6Digest(vtkEnvironment),
                ["math3dImporterSourceSha256"] = ScientificHash(importer),
                ["math3dHarnessSha256"] = ScientificHash(math3dTool),
                ["reloadParserSha256"] = ScientificHash(reloadTool) };
            var evidence = new JsonObject { ["suiteId"] = "cgal-repair-interop-v1",
                ["capabilityId"] = "mesh.repair", ["source"] = new JsonObject {
                    ["runId"] = source["runId"]?.GetValue<string>(), ["folderId"] = Path.GetFileName(sourceDirectory),
                    ["recordId"] = support["recordId"]?.GetValue<string>(),
                    ["runFingerprintSha256"] = source["runFingerprintSha256"]?.GetValue<string>() },
                ["cases"] = outcomes, ["malformedSha256"] = ScientificHash(malformed),
                ["rejection"] = rejection.DeepClone(), ["rejectionSha256"] = ScientificHash(rejectionFile),
                ["consumerContract"] = contract.DeepClone(), ["consumerContractSha256"] = ScientificL6Digest(contract),
                ["lowerQualification"] = new JsonObject { ["records"] = lower } };
            File.WriteAllText(Path.Combine(job.Directory, "repair-l7-evidence.json"), evidence.ToJsonString(), new UTF8Encoding(false));
            File.WriteAllText(Path.Combine(job.Directory, "results.json"), new JsonObject {
                ["repairInteropEvidence"] = evidence, ["validatedCapabilities"] = new JsonArray("mesh.repair")
            }.ToJsonString(), new UTF8Encoding(false));
            job.State = "succeeded"; job.Stage = "completed";
        }
        catch (OperationCanceledException) { job.State = "cancelled"; job.Error = "Only this repair interoperability job was stopped."; }
        catch (TimeoutException error) { job.State = "timed-out"; job.Error = error.Message; }
        catch (Exception error) { job.State = "failed"; job.Error = error.Message; }
        finally
        {
            job.DurationMs = timer.ElapsedMilliseconds;
            try { ScientificFinish(job); ScientificLog(job, $"\n[{job.State}] repair L7 interoperability / {job.DurationMs} ms {job.Error}\n"); }
            catch (Exception error) { Debug.WriteLine($"Repair L7 finalization failed: {error}"); }
            finally { ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) }); _scientificGate.Release(); }
        }
    }
}
