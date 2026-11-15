using System.Diagnostics;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace BatchLauncher;

public partial class Form1
{
    private object ScientificWorkbenchHandoffStart(string profileId, string runtimeId, JsonElement request)
    {
        if (runtimeId is not ("cgal-win-conda" or "vtk-win-conda"))
            throw new InvalidOperationException("Select a CGAL or VTK Workbench result.");
        var sourceRunId = request.GetProperty("jobId").GetString() ?? "";
        var artifactPath = request.GetProperty("artifactPath").GetString() ?? "";
        var (sourceDirectory, source) = ScientificHistoryFind(profileId, sourceRunId);
        if (source.GetProperty("runtimeId").GetString() != runtimeId || source.GetProperty("state").GetString() != "succeeded"
            || source.GetProperty("recipeId").GetString() is not ("cgal.validate" or "cgal.remesh" or "cgal.repair-orientation"
                or "cgal.fill-bounded-holes" or "mesh.inspect" or "mesh.simplify" or "mesh.normals"))
            throw new InvalidOperationException("Choose a successful saved Workbench operation.");
        var artifact = ScientificArtifactFiles.ResolveRegistered(sourceDirectory, source, artifactPath);
        if (Path.GetExtension(artifact).ToLowerInvariant() is not (".obj" or ".vtp"))
            throw new InvalidOperationException("MATH3D handoff accepts saved OBJ or VTP geometry.");
        var snapshot = ScientificSourceSnapshot.Verify(sourceDirectory, source.GetProperty("sourceSnapshotSha256").GetString() ?? "");
        if (ScientificSourceSnapshot.Assess(snapshot)["state"]?.GetValue<string>() != "current")
            throw new InvalidOperationException("Saved Workbench source is stale; rerun the operation at the current source.");
        var checkout = ScientificL7Checkout();
        if (!File.Exists(Path.Combine(checkout, "renderer", "node_modules", "vite", "package.json")))
            throw new InvalidOperationException("Pulled MATH3D checkout lacks renderer dependencies. Run npm ci in its renderer first.");
        var math3d = ScientificSourceSnapshot.Capture(checkout)["repositories"]?["devshell"] as JsonObject;
        if (math3d?["state"]?.GetValue<string>() != "captured" || math3d["dirty"]?.GetValue<bool>() != false)
            throw new InvalidOperationException("MATH3D checkout must be a clean, hash-verified Git commit.");
        var commit = math3d["commit"]?.GetValue<string>() ?? throw new InvalidOperationException("MATH3D commit is unavailable.");
        var node = Math3DNode;
        var vtkPrefix = ScientificPrefix("vtk-win-conda");
        if (!_scientificGate.Wait(0)) throw new InvalidOperationException("A Scientific recipe is already running.");
        try
        {
            var directory = Path.Combine(ScientificDataRoot, "runs", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(directory);
            var job = new ScientificJob { ProfileId = profileId, RuntimeId = runtimeId,
                RecipeId = "workbench.math3d-handoff", Directory = directory,
                SourceSnapshot = ScientificSourceSnapshot.Capture(ScientificSourceRoot, checkout) };
            var sourceSha = ScientificArtifactFiles.Hash(artifact);
            var input = new JsonObject { ["path"] = artifact, ["sha256"] = sourceSha,
                ["bytes"] = new FileInfo(artifact).Length, ["mediaType"] = ScientificArtifactFiles.MediaType(artifact) };
            var parameters = JsonSerializer.SerializeToElement(new { sourceRunId, artifactPath, math3dCommit = commit });
            ScientificWriteRequest(job, parameters, additionalInputs: new JsonArray(input), additionalOutputs: new JsonArray(
                new JsonObject { ["path"] = "converted.obj" }, new JsonObject { ["path"] = "conversion.json" },
                new JsonObject { ["path"] = "handoff-provenance.json" },
                new JsonObject { ["path"] = "product/vtk-mesh-document.json" },
                new JsonObject { ["path"] = "product/vtk-mesh-resource.bin" },
                new JsonObject { ["path"] = "product/read.m3dm" },
                new JsonObject { ["path"] = "product/product.json" }), timeoutSeconds: 300);
            _scientificJobs[profileId + ":" + runtimeId] = job;
            ScientificSend(new { type = "scientific.runtime.job", profileId, job = ScientificJobSnapshot(job) });
            _ = ScientificWorkbenchHandoffRunAsync(job, vtkPrefix, node, checkout, sourceDirectory, source, artifact, artifactPath, sourceSha, commit);
            return ScientificJobSnapshot(job);
        }
        catch { _scientificGate.Release(); throw; }
    }

    private async Task ScientificWorkbenchHandoffRunAsync(ScientificJob job, string vtkPrefix, string node, string checkout,
        string sourceDirectory, JsonElement source, string artifact, string artifactPath, string sourceSha, string commit)
    {
        var timer = Stopwatch.StartNew();
        try
        {
            var converted = Path.Combine(job.Directory, "converted.obj");
            await ScientificProcessAsync(job, vtkPrefix, Path.Combine(vtkPrefix, "python.exe"),
                new[] { Path.Combine(ScientificSourceRoot, "tools", "scientific-workbench-math3d-convert.py"),
                    "--source", artifact, "--expected-sha", sourceSha, "--output", converted }, job.Directory, 90);
            var conversion = JsonNode.Parse(File.ReadAllText(Path.Combine(job.Directory, "conversion.json"))) as JsonObject
                ?? throw new InvalidDataException("Workbench conversion evidence is missing.");
            var provenance = new JsonObject { ["schemaVersion"] = 1, ["kind"] = "scientific.workbench-math3d-handoff",
                ["sourceRunId"] = source.GetProperty("runId").GetString(), ["sourceRecipeId"] = source.GetProperty("recipeId").GetString(),
                ["sourceRuntimeId"] = source.GetProperty("runtimeId").GetString(), ["sourceArtifactPath"] = artifactPath,
                ["sourceArtifactSha256"] = sourceSha, ["sourceResultSha256"] = ScientificArtifactFiles.Hash(Path.Combine(sourceDirectory, "results.json")),
                ["sourceSnapshotSha256"] = source.GetProperty("sourceSnapshotSha256").GetString(),
                ["convertedObjSha256"] = conversion["objSha256"]?.GetValue<string>(), ["math3dCommit"] = commit,
                ["operationCatalogVersion"] = ScientificWorkbenchOperationCatalog.Version };
            var provenancePath = Path.Combine(job.Directory, "handoff-provenance.json");
            File.WriteAllText(provenancePath, provenance.ToJsonString());
            var productDirectory = Path.Combine(job.Directory, "product");
            job.ExecutedFiles.Add(ScientificRunFingerprint.ExecutedFile(node, "math3d-node"));
            job.ExecutedFiles.Add(ScientificRunFingerprint.ExecutedFile(Path.Combine(checkout, "renderer", "src", "mesh", "surfaceMesh.ts"), "math3d-importer-source"));
            await ScientificProcessAsync(job, vtkPrefix, node,
                new[] { Path.Combine(ScientificSourceRoot, "tools", "math3d-vtk-read-product.mjs"),
                    "--checkout", checkout, "--source", converted, "--expected-sha", conversion["objSha256"]!.GetValue<string>(),
                    "--provenance", provenancePath, "--provenance-sha", ScientificArtifactFiles.Hash(provenancePath),
                    "--output", productDirectory }, job.Directory, 150);
            var product = JsonNode.Parse(File.ReadAllText(Path.Combine(productDirectory, "product.json"))) as JsonObject
                ?? throw new InvalidDataException("MATH3D saved document evidence is missing.");
            if (product["verdict"]?.GetValue<string>() != "passed"
                || product["provenanceSha256"]?.GetValue<string>() != ScientificArtifactFiles.Hash(provenancePath)
                || product["consumerCommit"]?.GetValue<string>() != commit
                || product["sourceObjSha256"]?.GetValue<string>() != conversion["objSha256"]?.GetValue<string>())
                throw new InvalidDataException("MATH3D document reload or consumer identity did not match.");
            File.WriteAllText(Path.Combine(job.Directory, "results.json"), new JsonObject {
                ["sourceRunId"] = source.GetProperty("runId").GetString(),
                ["math3dWorkbenchHandoff"] = new JsonObject { ["conversion"] = conversion.DeepClone(),
                    ["provenanceSha256"] = ScientificArtifactFiles.Hash(provenancePath), ["product"] = product.DeepClone() },
                ["validatedCapabilities"] = new JsonArray() }.ToJsonString());
            job.State = "succeeded"; job.Stage = "completed";
        }
        catch (OperationCanceledException) { job.State = "cancelled"; job.Error = "Only this owned handoff was stopped."; }
        catch (TimeoutException error) { job.State = "timed-out"; job.Error = error.Message; }
        catch (Exception error) { job.State = "failed"; job.Error = error.Message; }
        finally
        {
            job.DurationMs = timer.ElapsedMilliseconds;
            try { ScientificFinish(job); ScientificLog(job, $"\n[{job.State}] {job.DurationMs} ms {job.Error}\n"); }
            catch (Exception error) { Debug.WriteLine($"Workbench handoff finalization failed: {error}"); }
            finally { ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) }); _scientificGate.Release(); }
        }
    }
}
