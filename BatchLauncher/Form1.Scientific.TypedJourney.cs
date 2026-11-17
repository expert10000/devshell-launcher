using System.Diagnostics;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace BatchLauncher;

public partial class Form1
{
    private object ScientificTypedJourneyStart(string profileId, string runtimeId, JsonElement request)
    {
        if (runtimeId != "cgal-win-conda") throw new InvalidOperationException("Select CGAL to continue a saved Boolean result.");
        var sourceRunId = request.GetProperty("jobId").GetString() ?? "";
        var (sourceDirectory, source) = ScientificHistoryFind(profileId, sourceRunId);
        if (source.GetProperty("runtimeId").GetString() != runtimeId || source.GetProperty("recipeId").GetString() != "cgal.boolean"
            || source.GetProperty("state").GetString() != "succeeded")
            throw new InvalidOperationException("Choose a successful saved CGAL Boolean run.");
        var operands = source.GetProperty("inputArtifacts");
        if (operands.GetArrayLength() != 2 || operands[0].GetProperty("sha256").GetString() == operands[1].GetProperty("sha256").GetString())
            throw new InvalidOperationException("The journey requires two distinct registered Boolean input hashes.");
        foreach (var role in new[] { "a", "b" })
        {
            var path = ScientificScopedFile(sourceDirectory, $"validation-{role}/results.json");
            using var validated = JsonDocument.Parse(File.ReadAllText(path));
            var index = role == "a" ? 0 : 1;
            if (validated.RootElement.GetProperty("state").GetString() != "succeeded"
                || !validated.RootElement.GetProperty("after").GetProperty("closed").GetBoolean()
                || validated.RootElement.GetProperty("inputArtifacts")[0].GetProperty("sha256").GetString() != operands[index].GetProperty("sha256").GetString())
                throw new InvalidOperationException($"Boolean input {role.ToUpperInvariant()} lacks matching closed-topology validation.");
        }
        var surfaceRelative = source.GetProperty("boolean").GetProperty("outputArtifact").GetString() ?? "";
        var surface = ScientificArtifactFiles.ResolveRegistered(sourceDirectory, source, surfaceRelative);
        if (Path.GetExtension(surface).ToLowerInvariant() != ".obj" || source.GetProperty("boolean").GetProperty("empty").GetBoolean())
            throw new InvalidOperationException("The Boolean result must be a nonempty registered OBJ surface.");
        var snapshotSha = source.GetProperty("sourceSnapshotSha256").GetString() ?? "";
        var sourceSnapshot = ScientificSourceSnapshot.Verify(sourceDirectory, snapshotSha);
        if (ScientificSourceSnapshot.Assess(sourceSnapshot)["state"]?.GetValue<string>() != "current")
            throw new InvalidOperationException("The Boolean source snapshot is stale; rerun it at the current source.");
        var sourceCommit = sourceSnapshot["repositories"]?["devshell"]?["commit"]?.GetValue<string>()
            ?? throw new InvalidDataException("Boolean source commit is unavailable.");
        var checkout = ScientificL7Checkout();
        if (!File.Exists(Path.Combine(checkout, "renderer", "node_modules", "vite", "package.json")))
            throw new InvalidOperationException("Pulled MATH3D renderer dependencies are missing.");
        var math3d = ScientificSourceSnapshot.Capture(checkout)["repositories"]?["devshell"];
        if (math3d?["state"]?.GetValue<string>() != "captured" || math3d["dirty"]?.GetValue<bool>() != false)
            throw new InvalidOperationException("MATH3D must be a clean, hash-verified Git checkout.");
        var consumerCommit = math3d["commit"]?.GetValue<string>() ?? throw new InvalidDataException("MATH3D commit is unavailable.");
        var gmshPrefix = ScientificPrefix("gmsh-win-conda");
        var vtkPrefix = ScientificPrefix("vtk-win-conda");
        var node = Math3DNode;
        if (!_scientificGate.Wait(0)) throw new InvalidOperationException("A Scientific recipe is already running.");
        try
        {
            var directory = Path.Combine(ScientificDataRoot, "runs", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(directory);
            var job = new ScientificJob { ProfileId = profileId, RuntimeId = runtimeId,
                RecipeId = "scientific.typed-journey", Directory = directory,
                SourceSnapshot = ScientificSourceSnapshot.Capture(ScientificSourceRoot, checkout) };
            var input = new JsonObject { ["path"] = surface, ["sha256"] = ScientificArtifactFiles.Hash(surface),
                ["bytes"] = new FileInfo(surface).Length, ["mediaType"] = "model/obj" };
            var parameters = JsonSerializer.SerializeToElement(new { sourceRunId, consumerCommit, lengthUnit = "mm", frame = "world", meshSize = 0.5 });
            var outputs = new JsonArray();
            foreach (var path in new[] { "gmsh/volume.msh", "gmsh/results.json", "boundary/boundary.obj", "boundary/results.json",
                "vtk/analysis.vtp", "vtk/preview.png", "vtk/results.json", "scipy/measurement.json", "converted.obj",
                "conversion.json", "typed-provenance.json", "product/vtk-mesh-document.json", "product/vtk-mesh-resource.bin",
                "product/read.m3dm", "product/product.json", "cold-reopen.json", "verification.json" })
                outputs.Add(new JsonObject { ["path"] = path });
            ScientificWriteRequest(job, parameters, additionalInputs: new JsonArray(input), additionalOutputs: outputs, timeoutSeconds: 600);
            _scientificJobs[profileId + ":" + runtimeId] = job;
            ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) });
            _ = ScientificTypedJourneyRunAsync(job, gmshPrefix, vtkPrefix, node, checkout, sourceDirectory, sourceRunId,
                surface, snapshotSha, sourceCommit, consumerCommit, operands[0].GetProperty("sha256").GetString()!,
                operands[1].GetProperty("sha256").GetString()!);
            return ScientificJobSnapshot(job);
        }
        catch { _scientificGate.Release(); throw; }
    }

    private async Task<(string Id, JsonObject Result, string Output)> ScientificTypedStageAsync(ScientificJob job,
        string folder, string operation, string inputId, string sourceRunId, string sourceCommit, string snapshotSha,
        string inputPath, string artifactRoot, string prefix, string script, string outputName, int timeout,
        double? meshSize = null, bool measurement = false)
    {
        job.Cancellation.Token.ThrowIfCancellationRequested();
        job.Stage = folder;
        ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) });
        var directory = Path.Combine(job.Directory, folder);
        Directory.CreateDirectory(directory);
        var id = Guid.NewGuid().ToString("N");
        var inputHash = ScientificArtifactFiles.Hash(inputPath);
        var request = new JsonObject { ["schemaVersion"] = 1, ["operation"] = operation, ["runId"] = id,
            ["sourceRunId"] = sourceRunId, ["sourceCommit"] = sourceCommit, ["sourceSnapshotSha256"] = snapshotSha,
            ["inputId"] = inputId, ["workingDirectory"] = directory, ["artifactRoot"] = artifactRoot,
            ["lengthUnit"] = "mm", ["frame"] = "world", ["inputArtifact"] = new JsonObject {
                ["path"] = inputPath, ["sha256"] = inputHash, ["bytes"] = new FileInfo(inputPath).Length } };
        if (meshSize is { } size) request["meshSize"] = size;
        var requestPath = Path.Combine(directory, "request.json");
        File.WriteAllText(requestPath, request.ToJsonString(), new UTF8Encoding(false));
        await ScientificProcessAsync(job, prefix, Path.Combine(prefix, "python.exe"),
            [Path.Combine(ScientificSourceRoot, "tools", script), "--request", requestPath], directory, timeout);
        var resultPath = Path.Combine(directory, measurement ? "measurement.json" : "results.json");
        var result = JsonNode.Parse(File.ReadAllText(resultPath)) as JsonObject
            ?? throw new InvalidDataException($"{operation} result is missing.");
        if (result["state"]?.GetValue<string>() != "succeeded" || result["runId"]?.GetValue<string>() != id
            || result["sourceCommit"]?.GetValue<string>() != sourceCommit
            || result["sourceSnapshotSha256"]?.GetValue<string>() != snapshotSha
            || result["inputHashes"]?[inputId]?.GetValue<string>() != inputHash)
            throw new InvalidDataException($"{operation} lost its typed input or source identity.");
        var output = Path.Combine(directory, outputName);
        if (!File.Exists(output) || !measurement && result["output"]?["sha256"]?.GetValue<string>() != ScientificArtifactFiles.Hash(output))
            throw new InvalidDataException($"{operation} output hash differs.");
        return (id, result, output);
    }

    private async Task ScientificTypedJourneyRunAsync(ScientificJob job, string gmshPrefix, string vtkPrefix, string node,
        string checkout, string sourceDirectory, string sourceRunId, string surface, string snapshotSha, string sourceCommit,
        string consumerCommit, string operandA, string operandB)
    {
        await Task.Yield();
        var timer = Stopwatch.StartNew();
        try
        {
            var gmsh = await ScientificTypedStageAsync(job, "gmsh", "gmsh.mesh", "boolean-surface", sourceRunId,
                sourceCommit, snapshotSha, surface, sourceDirectory, gmshPrefix, "scientific-gmsh-boolean-volume.py", "volume.msh", 180, 0.5);
            var boundary = await ScientificTypedStageAsync(job, "boundary", "gmsh.extract-boundary", "gmsh-mesh", gmsh.Id,
                sourceCommit, snapshotSha, gmsh.Output, job.Directory, gmshPrefix, "scientific-gmsh-boundary-extract.py", "boundary.obj", 120);
            var vtk = await ScientificTypedStageAsync(job, "vtk", "mesh.inspect", "gmsh-boundary", boundary.Id,
                sourceCommit, snapshotSha, boundary.Output, job.Directory, vtkPrefix, "scientific-vtk-boundary-inspect.py", "analysis.vtp", 120);
            if (vtk.Result["preview"]?["sha256"]?.GetValue<string>() != ScientificArtifactFiles.Hash(Path.Combine(job.Directory, "vtk", "preview.png")))
                throw new InvalidDataException("VTK preview changed after rendering.");
            var scipy = await ScientificTypedStageAsync(job, "scipy", "scipy.measure", "vtk-analysis", boundary.Id,
                sourceCommit, snapshotSha, vtk.Output, job.Directory, gmshPrefix, "scientific-scipy-surface-measure.py", "measurement.json", 120, measurement: true);
            job.Stage = "math3d-convert";
            var converted = Path.Combine(job.Directory, "converted.obj");
            await ScientificProcessAsync(job, vtkPrefix, Path.Combine(vtkPrefix, "python.exe"),
                [Path.Combine(ScientificSourceRoot, "tools", "scientific-workbench-math3d-convert.py"),
                    "--source", vtk.Output, "--expected-sha", ScientificArtifactFiles.Hash(vtk.Output), "--output", converted], job.Directory, 120);
            var conversion = JsonNode.Parse(File.ReadAllText(Path.Combine(job.Directory, "conversion.json"))) as JsonObject
                ?? throw new InvalidDataException("VTK conversion result is missing.");
            var convertedHash = ScientificArtifactFiles.Hash(converted);
            if (conversion["objSha256"]?.GetValue<string>() != convertedHash) throw new InvalidDataException("Converted OBJ changed.");
            var measurementHash = ScientificArtifactFiles.Hash(scipy.Output);
            var provenance = new JsonObject { ["schemaVersion"] = 1, ["kind"] = "scientific.typed-journey",
                ["sourceCommit"] = sourceCommit, ["sourceSnapshotSha256"] = snapshotSha, ["math3dCommit"] = consumerCommit,
                ["convertedObjSha256"] = convertedHash, ["vtkArtifactSha256"] = ScientificArtifactFiles.Hash(vtk.Output),
                ["measurementSha256"] = measurementHash, ["booleanSourceASha256"] = operandA, ["booleanSourceBSha256"] = operandB,
                ["booleanSurfaceSha256"] = ScientificArtifactFiles.Hash(surface), ["gmshMeshSha256"] = ScientificArtifactFiles.Hash(gmsh.Output),
                ["gmshBoundarySha256"] = ScientificArtifactFiles.Hash(boundary.Output), ["lengthUnit"] = "mm", ["frame"] = "world",
                ["geometryGeneration"] = 4, ["measurementGeneration"] = 5, ["consumerGeneration"] = 6,
                ["measurement"] = scipy.Result["measurement"]?.DeepClone() };
            var provenancePath = Path.Combine(job.Directory, "typed-provenance.json");
            File.WriteAllText(provenancePath, provenance.ToJsonString(), new UTF8Encoding(false));
            var productDirectory = Path.Combine(job.Directory, "product");
            job.Stage = "math3d-save";
            await ScientificProcessAsync(job, vtkPrefix, node,
                [Path.Combine(ScientificSourceRoot, "tools", "math3d-vtk-read-product.mjs"), "--checkout", checkout,
                    "--source", converted, "--expected-sha", convertedHash, "--provenance", provenancePath,
                    "--provenance-sha", ScientificArtifactFiles.Hash(provenancePath), "--measurement", scipy.Output,
                    "--measurement-sha", measurementHash, "--output", productDirectory], job.Directory, 180);
            var coldPath = Path.Combine(job.Directory, "cold-reopen.json");
            job.Stage = "cold-reopen";
            await ScientificProcessAsync(job, vtkPrefix, node,
                [Path.Combine(ScientificSourceRoot, "tools", "math3d-typed-cold-reopen.mjs"), "--checkout", checkout,
                    "--product", productDirectory, "--provenance", provenancePath, "--output", coldPath], job.Directory, 180);
            job.Stage = "independent-verification";
            var verifiedText = new StringBuilder();
            await ScientificProcessAsync(job, gmshPrefix, Path.Combine(gmshPrefix, "python.exe"),
                [Path.Combine(ScientificSourceRoot, "tools", "scientific-broker", "verify_typed_product.py"),
                    "--product", productDirectory, "--provenance", provenancePath, "--measurement", scipy.Output,
                    "--vtk", vtk.Output, "--obj", converted, "--cold", coldPath, "--math3d", checkout],
                job.Directory, 120, stdoutCapture: chunk => verifiedText.Append(chunk));
            var verified = JsonNode.Parse(verifiedText.ToString()) as JsonObject;
            if (verified?["verdict"]?.GetValue<string>() != "verified-typed-product-relations")
                throw new InvalidDataException("Independent typed product verification failed.");
            File.WriteAllText(Path.Combine(job.Directory, "verification.json"), verified.ToJsonString(), new UTF8Encoding(false));
            var product = JsonNode.Parse(File.ReadAllText(Path.Combine(productDirectory, "product.json"))) as JsonObject;
            var cold = JsonNode.Parse(File.ReadAllText(coldPath)) as JsonObject;
            File.WriteAllText(Path.Combine(job.Directory, "results.json"), new JsonObject {
                ["sourceRunId"] = sourceRunId, ["typedJourney"] = new JsonObject {
                    ["verdict"] = "passed", ["gmsh"] = gmsh.Result.DeepClone(), ["boundary"] = boundary.Result.DeepClone(),
                    ["vtk"] = vtk.Result.DeepClone(), ["scipy"] = scipy.Result.DeepClone(),
                    ["product"] = product?.DeepClone(), ["coldReopen"] = cold?.DeepClone(),
                    ["verification"] = verified.DeepClone(), ["provenanceSha256"] = ScientificArtifactFiles.Hash(provenancePath) },
                ["validatedCapabilities"] = new JsonArray() }.ToJsonString(), new UTF8Encoding(false));
            job.Cancellation.Token.ThrowIfCancellationRequested();
            job.State = "succeeded"; job.Stage = "completed";
        }
        catch (OperationCanceledException) { job.State = "cancelled"; job.Stage = "stopped"; job.Error = "Only this owned journey was stopped."; }
        catch (TimeoutException error) { job.State = "timed-out"; job.Stage = "timed-out"; job.Error = error.Message; }
        catch (Exception error) { job.State = "failed"; job.Stage = "failed"; job.Error = error.Message; }
        finally
        {
            job.DurationMs = timer.ElapsedMilliseconds;
            try { ScientificFinish(job); ScientificLog(job, $"\n[{job.State}] {job.DurationMs} ms {job.Error}\n"); }
            catch (Exception error) { Debug.WriteLine($"Typed journey finalization failed: {error}"); }
            finally { ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) }); _scientificGate.Release(); }
        }
    }
}
