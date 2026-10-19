using System.Diagnostics;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace BatchLauncher;

public partial class Form1
{
    private object ScientificBooleanStart(string profileId, string runtimeId, JsonElement request)
    {
        if (runtimeId != "cgal-win-conda") throw new InvalidOperationException("Select CGAL / Windows Native to run a Boolean operation.");
        var parameters = ScientificBooleanParameters.Parse(request.GetProperty("parameters"));
        var prefix = ScientificPrefix(runtimeId);
        var node = Math3DNode;
        var script = Path.Combine(ScientificSourceRoot, "tools", "run-math3d-boolean.mjs");
        if (!File.Exists(script) || !File.Exists(Math3DWorker)) throw new InvalidOperationException("Prepare the MATH3D native worker under Integration > Prepare & Run first.");
        var inputA = ScientificDatasetArtifact(parameters.InputAId);
        var inputB = ScientificDatasetArtifact(parameters.InputBId);
        foreach (var input in new[] { inputA, inputB })
            if (!new[] { ".obj", ".stl", ".ply", ".off" }.Contains(Path.GetExtension(input["path"]!.GetValue<string>()).ToLowerInvariant()))
                throw new InvalidOperationException("Boolean inputs must be registered OBJ/STL/PLY/OFF mesh copies.");
        if (!_scientificGate.Wait(0)) throw new InvalidOperationException("Another Scientific job is running; stop or wait for it.");
        try
        {
            var id = Guid.NewGuid().ToString("N");
            var directory = Path.Combine(ScientificDataRoot, "runs", id);
            Directory.CreateDirectory(directory);
            var job = new ScientificJob { Id = id, ProfileId = profileId, RuntimeId = runtimeId, RecipeId = "cgal.boolean", Directory = directory };
            inputA["role"] = "A"; inputB["role"] = "B";
            var outputs = new JsonArray(new JsonObject { ["path"] = Path.ChangeExtension(parameters.OutputName, ".obj"), ["mediaType"] = "model/obj", ["role"] = "result" },
                new JsonObject { ["path"] = "operand-a.m3dm", ["mediaType"] = "application/octet-stream", ["role"] = "operand" },
                new JsonObject { ["path"] = "operand-b.m3dm", ["mediaType"] = "application/octet-stream", ["role"] = "operand" });
            ScientificWriteRequest(job, JsonSerializer.SerializeToElement(parameters, ScientificJson), inputA, parameters.OutputName, new JsonArray(inputB), outputs);
            _scientificJobs[profileId + ":" + runtimeId] = job;
            ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) });
            _ = ScientificBooleanRunAsync(job, prefix, node, script, parameters);
            return ScientificJobSnapshot(job);
        }
        catch { _scientificGate.Release(); throw; }
    }

    private async Task ScientificBooleanRunAsync(ScientificJob job, string prefix, string node, string script, ScientificBooleanParameters parameters)
    {
        await Task.Yield();
        var timer = Stopwatch.StartNew();
        try
        {
            foreach (var (role, inputId) in new[] { ("a", parameters.InputAId), ("b", parameters.InputBId) })
            {
                job.Cancellation.Token.ThrowIfCancellationRequested();
                ScientificLog(job, $"Validating mesh {role.ToUpperInvariant()}: {inputId}\n");
                var directory = Path.Combine(job.Directory, "validation-" + role);
                Directory.CreateDirectory(directory);
                var validation = new ScientificJob { ProfileId = job.ProfileId, RuntimeId = job.RuntimeId, RecipeId = "cgal.validate", Directory = directory, Cancellation = job.Cancellation };
                ScientificWriteRequest(validation, JsonSerializer.SerializeToElement(new { inputId, outputName = "operand.obj" }), ScientificDatasetArtifact(inputId), "operand.obj");
                await ScientificCgalExecuteAsync(validation, prefix, job);
                using var result = JsonDocument.Parse(File.ReadAllText(Path.Combine(directory, "results.json")));
                if (result.RootElement.GetProperty("state").GetString() != "succeeded" || !result.RootElement.GetProperty("after").GetProperty("closed").GetBoolean())
                    throw new InvalidOperationException($"Mesh {role.ToUpperInvariant()} must pass CGAL validation and be a closed solid.");
                job.EnvironmentFingerprint = validation.EnvironmentFingerprint;
            }
            job.Cancellation.Token.ThrowIfCancellationRequested();
            ScientificLog(job, "Both inputs validated. Running native Boolean operation...\n");
            await ScientificProcessAsync(job, prefix, node, new[] { script, Path.Combine(job.Directory, "request.json"), Math3DWorker }, job.Directory, 120);
            using var output = JsonDocument.Parse(File.ReadAllText(Path.Combine(job.Directory, "results.json")));
            if (output.RootElement.GetProperty("state").GetString() != "succeeded") throw new InvalidOperationException("Native Boolean did not succeed; see the saved log.");
            job.Cancellation.Token.ThrowIfCancellationRequested();
            job.State = "succeeded"; job.Stage = "completed";
        }
        catch (OperationCanceledException) { job.State = "cancelled"; job.Stage = "stopped"; job.Error = "The owned Boolean job was stopped."; }
        catch (TimeoutException exception) { job.State = "timed-out"; job.Stage = "timed-out"; job.Error = exception.Message; }
        catch (Exception exception)
        {
            job.State = "failed"; job.Stage = "failed"; job.Error = exception.Message;
            foreach (var relative in new[] { "results.json", "validation-b/results.json", "validation-a/results.json" })
            {
                try
                {
                    var file = ScientificScopedFile(job.Directory, relative);
                    if (!File.Exists(file) || new FileInfo(file).Length > 1048576) continue;
                    using var failed = JsonDocument.Parse(File.ReadAllText(file));
                    if (failed.RootElement.GetProperty("state").GetString() != "failed") continue;
                    var diagnostic = failed.RootElement.GetProperty("diagnostics").EnumerateArray().FirstOrDefault();
                    if (diagnostic.ValueKind == JsonValueKind.Object) job.Error = diagnostic.GetProperty("message").GetString() ?? exception.Message;
                    break;
                }
                catch (Exception readError) when (readError is IOException or JsonException or InvalidOperationException or KeyNotFoundException) { Debug.WriteLine(readError.Message); }
            }
        }
        finally
        {
            job.DurationMs = timer.ElapsedMilliseconds;
            try { ScientificFinish(job); ScientificLog(job, $"\n[{job.State}] {job.DurationMs} ms {job.Error}\n"); }
            catch (Exception exception) { Debug.WriteLine($"Boolean finalization failed: {exception}"); }
            finally { ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) }); _scientificGate.Release(); }
        }
    }
}
