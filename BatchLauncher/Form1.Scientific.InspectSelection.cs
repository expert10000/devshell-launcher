using System.Diagnostics;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace BatchLauncher;

public partial class Form1
{
    private static string? InspectSelectionPath(JsonElement request, string name)
    {
        if (!request.TryGetProperty(name, out var value) || value.ValueKind is JsonValueKind.Null or JsonValueKind.Undefined) return null;
        var text = value.GetString();
        if (string.IsNullOrWhiteSpace(text)) return null;
        var path = Path.GetFullPath(text);
        if (!Path.IsPathFullyQualified(path) || Path.GetExtension(path) != ".json" || !File.Exists(path)
            || new FileInfo(path).Length is <= 0 or > 8388608)
            throw new InvalidOperationException(name + " must be an existing bounded JSON evidence record.");
        return path;
    }

    private static string InspectSelectionInput(JsonElement request)
    {
        var text = request.GetProperty("inputPath").GetString() ?? "";
        var path = Path.GetFullPath(text);
        if (!Path.IsPathFullyQualified(path) || Path.GetExtension(path).ToLowerInvariant() != ".obj"
            || !File.Exists(path) || new FileInfo(path).Length is <= 0 or > 131072)
            throw new InvalidOperationException("Select a local bounded OBJ input (up to 128 KiB).");
        return path;
    }

    private static string? InspectSelectionManual(JsonElement request)
    {
        var value = request.TryGetProperty("manualProvider", out var manual) && manual.ValueKind == JsonValueKind.String
            ? manual.GetString() : null;
        if (string.IsNullOrWhiteSpace(value)) return null;
        if (value is not "cgal-win-conda" and not "vtk-win-conda")
            throw new InvalidOperationException("Manual provider must be CGAL or VTK.");
        return value;
    }

    private static string[] InspectSelectionArguments(string action, string script, string input,
        string? shared, string? classes, string? manual, string? checkout = null, string? output = null)
    {
        var args = new List<string> { script, action, "--input", input };
        if (shared != null) args.AddRange(["--shared-record", shared]);
        if (classes != null) args.AddRange(["--class-record", classes]);
        if (manual != null) args.AddRange(["--manual-provider", manual]);
        if (checkout != null) args.AddRange(["--math3d-checkout", checkout]);
        if (output != null) args.AddRange(["--output", output]);
        return args.ToArray();
    }

    private object ScientificInspectPreviewStart(string profileId, JsonElement request)
    {
        var input = InspectSelectionInput(request);
        var shared = InspectSelectionPath(request, "sharedRecord");
        var classes = InspectSelectionPath(request, "classRecord");
        if (shared == null && classes == null) throw new InvalidOperationException("Supply a shared or bounded class evidence record.");
        var manual = InspectSelectionManual(request);
        if (!_scientificGate.Wait(0)) throw new InvalidOperationException("Another Scientific job is running; stop or wait for it.");
        try
        {
            var runId = Guid.NewGuid().ToString("N");
            var directory = Path.Combine(ScientificDataRoot, "runs", runId);
            Directory.CreateDirectory(directory);
            var job = new ScientificJob { Id = runId, ProfileId = profileId, RuntimeId = "cgal-win-conda",
                RecipeId = "l9.math3d-inspect-preview", Directory = directory };
            var inputArtifact = new JsonObject { ["path"] = input, ["sha256"] = ScientificHash(input),
                ["mediaType"] = "model/obj", ["bytes"] = new FileInfo(input).Length };
            ScientificWriteRequest(job, JsonSerializer.SerializeToElement(new { sharedRecord = shared,
                classRecord = classes, manualProvider = manual }), inputArtifact, "preview.json", timeoutSeconds: 180);
            _scientificJobs[profileId + ":cgal-win-conda"] = job;
            ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) });
            _ = ScientificInspectPreviewRunAsync(job, input, shared, classes, manual);
            return ScientificJobSnapshot(job);
        }
        catch { _scientificGate.Release(); throw; }
    }

    private async Task ScientificInspectPreviewRunAsync(ScientificJob job, string input, string? shared,
        string? classes, string? manual)
    {
        await Task.Yield();
        var timer = Stopwatch.StartNew();
        try
        {
            var prefix = ScientificPrefix("gmsh-win-conda");
            var script = Path.Combine(ScientificSourceRoot, "tools", "scientific-broker", "math3d_inspect_product.py");
            var output = new System.Text.StringBuilder();
            await ScientificProcessAsync(job, prefix, Path.Combine(prefix, "python.exe"),
                InspectSelectionArguments("preview", script, input, shared, classes, manual),
                job.Directory, 180, stdoutCapture: chunk => output.Append(chunk));
            var selection = JsonNode.Parse(output.ToString()) ?? throw new InvalidDataException("Inspection preview returned no selection.");
            File.WriteAllText(Path.Combine(job.Directory, "preview.json"), selection.ToJsonString());
            File.WriteAllText(Path.Combine(job.Directory, "results.json"),
                new JsonObject { ["selection"] = selection.DeepClone(), ["validatedCapabilities"] = new JsonArray() }.ToJsonString());
            job.State = "succeeded"; job.Stage = "completed";
        }
        catch (OperationCanceledException) { job.State = "cancelled"; job.Stage = "stopped"; job.Error = "Inspection preview was stopped."; }
        catch (TimeoutException exception) { job.State = "timed-out"; job.Stage = "timed-out"; job.Error = exception.Message; }
        catch (Exception exception) { job.State = "failed"; job.Stage = "failed"; job.Error = exception.Message; }
        finally
        {
            job.DurationMs = timer.ElapsedMilliseconds;
            try { ScientificFinish(job); ScientificLog(job, $"\n[{job.State}] {job.DurationMs} ms {job.Error}\n"); }
            catch (Exception exception) { Debug.WriteLine($"Inspection preview finalization failed: {exception}"); }
            finally { ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) }); _scientificGate.Release(); }
        }
    }

    private object ScientificInspectSelectionStart(string profileId, JsonElement request)
    {
        var input = InspectSelectionInput(request);
        var shared = InspectSelectionPath(request, "sharedRecord");
        var classes = InspectSelectionPath(request, "classRecord");
        if (shared == null && classes == null) throw new InvalidOperationException("Supply a shared or bounded class evidence record.");
        var manual = InspectSelectionManual(request);
        if (!_scientificGate.Wait(0)) throw new InvalidOperationException("Another Scientific job is running; stop or wait for it.");
        try
        {
            var runId = Guid.NewGuid().ToString("N");
            var directory = Path.Combine(ScientificDataRoot, "runs", runId);
            Directory.CreateDirectory(directory);
            var job = new ScientificJob { Id = runId, ProfileId = profileId, RuntimeId = "cgal-win-conda",
                RecipeId = "l9.math3d-inspect-selection", Directory = directory };
            var inputArtifact = new JsonObject { ["path"] = input, ["sha256"] = ScientificHash(input),
                ["mediaType"] = "model/obj", ["bytes"] = new FileInfo(input).Length };
            var outputs = new JsonArray(new JsonObject { ["path"] = "product-selection/product/viewer.png", ["mediaType"] = "image/png" },
                new JsonObject { ["path"] = "product-selection/product/read.m3dm", ["mediaType"] = "application/octet-stream" },
                new JsonObject { ["path"] = "product-selection/selection.html", ["mediaType"] = "text/html" });
            ScientificWriteRequest(job, JsonSerializer.SerializeToElement(new { sharedRecord = shared, classRecord = classes,
                manualProvider = manual }), inputArtifact, "product-selection/selection.json", additionalOutputs: outputs,
                timeoutSeconds: 600);
            _scientificJobs[profileId + ":cgal-win-conda"] = job;
            ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) });
            _ = ScientificInspectSelectionRunAsync(job, input, shared, classes, manual);
            return ScientificJobSnapshot(job);
        }
        catch { _scientificGate.Release(); throw; }
    }

    private async Task ScientificInspectSelectionRunAsync(ScientificJob job, string input, string? shared,
        string? classes, string? manual)
    {
        await Task.Yield();
        var timer = Stopwatch.StartNew();
        try
        {
            var prefix = ScientificPrefix("gmsh-win-conda");
            var python = Path.Combine(prefix, "python.exe");
            var script = Path.Combine(ScientificSourceRoot, "tools", "scientific-broker", "math3d_inspect_product.py");
            var output = Path.Combine(job.Directory, "product-selection");
            var args = InspectSelectionArguments("run", script, input, shared, classes, manual, ScientificL7Checkout(), output);
            await ScientificProcessAsync(job, prefix, python, args, job.Directory, 600);
            var selection = JsonNode.Parse(File.ReadAllText(Path.Combine(output, "selection.json")))!;
            var result = new JsonObject { ["selection"] = selection, ["validatedCapabilities"] = new JsonArray(),
                ["before"] = new JsonObject(), ["after"] = new JsonObject() };
            File.WriteAllText(Path.Combine(job.Directory, "results.json"), result.ToJsonString());
            job.State = "succeeded"; job.Stage = "completed";
        }
        catch (OperationCanceledException) { job.State = "cancelled"; job.Stage = "stopped"; job.Error = "Inspection selection was stopped."; }
        catch (TimeoutException exception) { job.State = "timed-out"; job.Stage = "timed-out"; job.Error = exception.Message; }
        catch (Exception exception) { job.State = "failed"; job.Stage = "failed"; job.Error = exception.Message; }
        finally
        {
            job.DurationMs = timer.ElapsedMilliseconds;
            try { ScientificFinish(job); ScientificLog(job, $"\n[{job.State}] {job.DurationMs} ms {job.Error}\n"); }
            catch (Exception exception) { Debug.WriteLine($"Inspection selection finalization failed: {exception}"); }
            finally { ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) }); _scientificGate.Release(); }
        }
    }
}
