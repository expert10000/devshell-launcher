using System.Diagnostics;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace BatchLauncher;

public partial class Form1
{
    private static void ScientificCheckL7InteropDeclaration()
    {
        var path = Path.Combine(AppContext.BaseDirectory, "runtimes", "cgal-win-conda", "runtime.json");
        var declaration = (JsonNode.Parse(File.ReadAllText(path))?["qualificationRecipes"] as JsonArray)?
            .OfType<JsonObject>().FirstOrDefault(item => item["id"]?.GetValue<string>() == "l7.cgal-vtk-math3d");
        if (declaration?["readinessLevel"]?.GetValue<string>() != "L7"
            || declaration["capability"]?.GetValue<string>() != "mesh.interop.vtk-math3d"
            || declaration["referenceRecipe"]?.GetValue<string>() != "l6.reproduce"
            || declaration["format"]?.GetValue<string>() != "obj")
            throw new InvalidOperationException("CGAL interoperability is not registered in its manifest.");
    }

    private object ScientificL7InteropStart(string profileId, string runtimeId)
    {
        ScientificProviderRegistry.RequireAction(runtimeId, "l7-cgal-vtk-math3d");
        ScientificCheckL7InteropDeclaration();
        var support = ScientificCurrentL6(profileId, runtimeId);
        var source = ScientificL7Source(profileId, support, runtimeId);
        var checkout = ScientificL7Checkout();
        var importer = Path.Combine(checkout, "renderer", "src", "mesh", "surfaceMesh.ts");
        if (!File.Exists(importer) || !Directory.Exists(Path.Combine(checkout, "renderer", "node_modules", "vite")))
            throw new InvalidOperationException("The MATH3D desktop importer is required for CGAL interoperability.");
        var vtkPrefix = ScientificPrefix("vtk-win-conda");
        var vtkPython = Path.Combine(vtkPrefix, "python.exe");
        if (!File.Exists(vtkPython)) throw new InvalidOperationException("The VTK reader environment is unavailable.");
        var node = Math3DNode;
        if (!_scientificGate.Wait(0)) throw new InvalidOperationException("Another Scientific job is running; stop or wait for it.");
        try
        {
            var directory = Path.Combine(ScientificDataRoot, "runs", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(directory);
            var job = new ScientificJob { ProfileId = profileId, RuntimeId = runtimeId,
                RecipeId = "l7.cgal-vtk-math3d", Directory = directory };
            var input = new JsonObject { ["path"] = source["absolutePath"]?.GetValue<string>(),
                ["mediaType"] = "model/obj", ["bytes"] = source["artifactBytes"]?.GetValue<long>(),
                ["sha256"] = source["artifactSha256"]?.GetValue<string>(),
                ["sourceRunId"] = source["runId"]?.GetValue<string>() };
            var parameters = JsonSerializer.SerializeToElement(new { suiteId = "l7-cgal-vtk-math3d-v1",
                sourceRunId = source["runId"]?.GetValue<string>(), sourceRecordId = support["recordId"]?.GetValue<string>() }, ScientificJson);
            ScientificWriteRequest(job, parameters, input, additionalOutputs: new JsonArray(
                new JsonObject { ["path"] = "handoff/source-reload.json", ["mediaType"] = "application/json" },
                new JsonObject { ["path"] = "handoff/vtk-consumed.json", ["mediaType"] = "application/json" },
                new JsonObject { ["path"] = "handoff/math3d-consumed.json", ["mediaType"] = "application/json" },
                new JsonObject { ["path"] = "handoff/malformed.obj", ["mediaType"] = "model/obj" },
                new JsonObject { ["path"] = "handoff/rejection.json", ["mediaType"] = "application/json" }));
            _scientificJobs[profileId + ":" + runtimeId] = job;
            ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) });
            _ = ScientificL7InteropRunAsync(job, vtkPrefix, vtkPython, node, checkout, importer, source, support);
            return ScientificJobSnapshot(job);
        }
        catch { _scientificGate.Release(); throw; }
    }

    private async Task ScientificL7InteropRunAsync(ScientificJob job, string vtkPrefix, string vtkPython,
        string node, string checkout, string importer, JsonObject source, JsonObject support)
    {
        var timer = Stopwatch.StartNew();
        try
        {
            var handoff = Path.Combine(job.Directory, "handoff");
            Directory.CreateDirectory(handoff);
            var artifact = source["absolutePath"]!.GetValue<string>();
            var reloadFile = Path.Combine(handoff, "source-reload.json");
            var vtkFile = Path.Combine(handoff, "vtk-consumed.json");
            var math3dFile = Path.Combine(handoff, "math3d-consumed.json");
            var malformed = Path.Combine(handoff, "malformed.obj");
            var rejectionFile = Path.Combine(handoff, "rejection.json");
            var reloadTool = Path.Combine(ScientificSourceRoot, "tools", "scientific-artifact-roundtrip.py");
            var vtkTool = Path.Combine(ScientificSourceRoot, "tools", "scientific-vtk-interop.py");
            var math3dTool = Path.Combine(ScientificSourceRoot, "tools", "math3d-vtk-import-handoff.mjs");
            job.Stage = "source-reload";
            await ScientificProcessAsync(job, vtkPrefix, vtkPython,
                [reloadTool, "--input", artifact, "--result", reloadFile], handoff, 60);
            job.Stage = "vtk-consume";
            await ScientificProcessAsync(job, vtkPrefix, vtkPython,
                [vtkTool, "--input", artifact, "--result", vtkFile], handoff, 60);
            job.Stage = "math3d-consume";
            await ScientificProcessAsync(job, vtkPrefix, node,
                [math3dTool, "--checkout", checkout, "--input", artifact, "--result", math3dFile], handoff, 120);
            job.Stage = "rejection";
            File.WriteAllText(malformed, "v 0 0 0\nf 1 2 3\n", new UTF8Encoding(false));
            await ScientificProcessAsync(job, vtkPrefix, vtkPython,
                [vtkTool, "--input", malformed, "--result", rejectionFile, "--expect-reject"], handoff, 60);
            var reload = JsonNode.Parse(File.ReadAllText(reloadFile)) as JsonObject;
            var vtk = JsonNode.Parse(File.ReadAllText(vtkFile)) as JsonObject;
            var math3d = JsonNode.Parse(File.ReadAllText(math3dFile)) as JsonObject;
            var rejection = JsonNode.Parse(File.ReadAllText(rejectionFile)) as JsonObject;
            if (reload == null || vtk == null || math3d == null || rejection == null
                || reload["artifactSha256"]?.GetValue<string>() != source["artifactSha256"]?.GetValue<string>()
                || !ScientificQualificationRecords.ValidInteropSemantics(reload, vtk, math3d, rejection,
                    ScientificHash(malformed), ScientificHash(vtkTool), ScientificHash(importer)))
                throw new InvalidDataException("The CGAL mesh did not preserve geometry, topology, orientation and scale across consumers.");
            if (ScientificCurrentL6(job.ProfileId, job.RuntimeId)["recordId"]?.GetValue<string>() != support["recordId"]?.GetValue<string>())
                throw new InvalidOperationException("The CGAL L6 source is no longer current.");
            var lower = (JsonArray)source["lowerQualification"]!["records"]!.DeepClone();
            lower.Add(support.DeepClone());
            var reference = (JsonObject)source.DeepClone();
            reference.Remove("absolutePath");
            var vtkEnvironment = ScientificRunFingerprint.Capture("vtk-win-conda", job.ProfileId,
                ScientificSourceRoot, AppContext.BaseDirectory, ScientificReportPath())["environment"];
            var contract = new JsonObject { ["schemaVersion"] = 1, ["format"] = "obj",
                ["comparisonTolerance"] = 1e-6, ["vtkReaderSourceSha256"] = ScientificHash(vtkTool),
                ["vtkPythonSha256"] = ScientificHash(vtkPython), ["vtkEnvironmentSha256"] = ScientificL6Digest(vtkEnvironment),
                ["vtkVersion"] = vtk["vtkVersion"]?.GetValue<string>(),
                ["math3dImporterSourceSha256"] = ScientificHash(importer),
                ["math3dHarnessSha256"] = ScientificHash(math3dTool),
                ["reloadParserSha256"] = ScientificHash(reloadTool) };
            var evidence = new JsonObject { ["suiteId"] = "l7-cgal-vtk-math3d-v1",
                ["capabilityId"] = "mesh.interop.vtk-math3d", ["source"] = reference,
                ["sourceReload"] = reload.DeepClone(), ["sourceReloadSha256"] = ScientificHash(reloadFile),
                ["vtkConsumer"] = vtk.DeepClone(), ["vtkConsumerSha256"] = ScientificHash(vtkFile),
                ["math3dConsumer"] = math3d.DeepClone(), ["math3dConsumerSha256"] = ScientificHash(math3dFile),
                ["malformedSha256"] = ScientificHash(malformed), ["rejection"] = rejection.DeepClone(),
                ["rejectionSha256"] = ScientificHash(rejectionFile), ["consumerContract"] = contract.DeepClone(),
                ["consumerContractSha256"] = ScientificL6Digest(contract),
                ["lowerQualification"] = new JsonObject { ["records"] = lower } };
            File.WriteAllText(Path.Combine(job.Directory, "results.json"), new JsonObject
            {
                ["l7InteropEvidence"] = evidence,
                ["validatedCapabilities"] = new JsonArray("mesh.interop.vtk-math3d")
            }.ToJsonString(), new UTF8Encoding(false));
            job.State = "succeeded"; job.Stage = "completed";
        }
        catch (OperationCanceledException) { job.State = "cancelled"; job.Error = "The owned L7 interoperability run was stopped."; }
        catch (TimeoutException exception) { job.State = "timed-out"; job.Error = exception.Message; }
        catch (Exception exception) { job.State = "failed"; job.Error = exception.Message; }
        finally
        {
            job.DurationMs = timer.ElapsedMilliseconds;
            try { ScientificFinish(job); ScientificLog(job, $"\n[{job.State}] L7 CGAL → VTK → MATH3D / {job.DurationMs} ms {job.Error}\n"); }
            catch (Exception exception) { Debug.WriteLine($"L7 interoperability finalization failed: {exception}"); }
            finally { ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) }); _scientificGate.Release(); }
        }
    }
}
