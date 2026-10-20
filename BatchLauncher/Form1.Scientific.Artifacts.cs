using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace BatchLauncher;

public partial class Form1
{
    private readonly SemaphoreSlim _scientificPreviewGate = new(1, 1);
    private readonly CancellationTokenSource _scientificLifetime = new();
    private static readonly string[] ScientificMeshExtensions = ScientificArtifactFiles.MeshExtensions;
    private static string ScientificMediaType(string path) => ScientificArtifactFiles.MediaType(path);
    private static string ScientificHash(string path) => ScientificArtifactFiles.Hash(path);
    private static JsonObject ScientificDatasetArtifact(string inputId)
    {
        var root = Path.Combine(ScientificDataRoot, "datasets");
        var manifest = ScientificScopedFile(root, "manifest.json");
        if (!File.Exists(manifest) || new FileInfo(manifest).Length > 1048576)
            throw new InvalidOperationException("Load registered duplicated datasets first.");
        using var document = JsonDocument.Parse(File.ReadAllText(manifest));
        var entry = document.RootElement.GetProperty("entries").EnumerateArray().FirstOrDefault(item => item.GetProperty("id").GetString() == inputId);
        if (entry.ValueKind != JsonValueKind.Object) throw new InvalidOperationException("Select a registered duplicated dataset.");
        var path = ScientificScopedFile(root, entry.GetProperty("path").GetString() ?? inputId);
        if (!File.Exists(path) || new FileInfo(path).Length > 33554432)
            throw new InvalidOperationException("Dataset must be a local copy up to 32 MiB.");
        var hash = ScientificHash(path);
        if (!string.Equals(entry.GetProperty("sha256").GetString(), hash, StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("Dataset copy changed. Reimport it before running a registered recipe.");
        return new JsonObject
        {
            ["path"] = path, ["mediaType"] = ScientificMediaType(path), ["bytes"] = new FileInfo(path).Length,
            ["sha256"] = hash, ["datasetId"] = inputId,
            ["sourcePath"] = entry.TryGetProperty("sourcePath", out var source) ? source.GetString() : null,
            ["sourceRoot"] = entry.TryGetProperty("sourceRoot", out var sourceRoot) ? sourceRoot.GetString() : null
        };
    }
    private static void ScientificWriteRequest(ScientificJob job, JsonElement? parameters, JsonObject? input = null, string? output = null,
        JsonArray? additionalInputs = null, JsonArray? additionalOutputs = null, int timeoutSeconds = 120, string? rerunOf = null)
    {
        var inputs = input == null ? new JsonArray() : new JsonArray(input.DeepClone());
        var outputs = output == null ? new JsonArray() : new JsonArray(new JsonObject { ["path"] = output, ["mediaType"] = ScientificMediaType(output) });
        foreach (var path in ScientificArtifactFiles.SmokeOutputs(job.RuntimeId, job.RecipeId))
            outputs.Add(new JsonObject { ["path"] = path, ["mediaType"] = ScientificMediaType(path) });
        if (additionalInputs != null) foreach (var item in additionalInputs) inputs.Add(item?.DeepClone());
        if (additionalOutputs != null) foreach (var item in additionalOutputs) outputs.Add(item?.DeepClone());
        var request = new JsonObject
        {
            ["schemaVersion"] = 1, ["runId"] = job.Id, ["profileId"] = job.ProfileId,
            ["runtimeId"] = job.RuntimeId, ["recipeId"] = job.RecipeId, ["operation"] = job.RecipeId,
            ["parameters"] = parameters is { ValueKind: JsonValueKind.Object } value ? JsonNode.Parse(value.GetRawText()) : new JsonObject(),
            ["workingDirectory"] = job.Directory, ["datasetRoot"] = Path.Combine(ScientificDataRoot, "datasets"),
            ["timeoutSeconds"] = timeoutSeconds, ["inputArtifacts"] = inputs,
            ["outputArtifacts"] = outputs,
            ["provenance"] = new JsonObject { ["inputPolicy"] = "Registered local copies; SHA-256 checked before execution", ["transport"] = "JSON request / argv-owned adapter; no shell" }
        };
        if (rerunOf != null) request["rerunOf"] = rerunOf;
        var json = request.ToJsonString(ScientificJson);
        job.Request = JsonSerializer.SerializeToElement(request, ScientificJson);
        File.WriteAllText(Path.Combine(job.Directory, "request.json"), json, new UTF8Encoding(false));
        File.WriteAllText(Path.Combine(job.Directory, "invocation.json"), json, new UTF8Encoding(false));
    }
    private static JsonObject ScientificStatistics(JsonNode? source)
    {
        var values = source?.DeepClone() as JsonObject ?? new JsonObject();
        if (!values.ContainsKey("points") && values["vertices"] != null) values["points"] = values["vertices"]!.DeepClone();
        if (!values.ContainsKey("triangles") && values["faces"] != null) values["triangles"] = values["faces"]!.DeepClone();
        return values;
    }
    private void ScientificFinish(ScientificJob job)
    {
        var path = ScientificScopedFile(job.Directory, "results.json");
        var result = File.Exists(path) && new FileInfo(path).Length <= 1048576
            ? JsonNode.Parse(File.ReadAllText(path)) as JsonObject ?? new JsonObject() : new JsonObject();
        var workerDuration = result["durationMs"]?.DeepClone();
        var diagnostics = result["diagnostics"] as JsonArray ?? new JsonArray();
        result["diagnostics"] = diagnostics;
        if (job.Error != null) diagnostics.Add(new JsonObject { ["severity"] = "error", ["message"] = job.Error });
        if (result["error"]?.GetValue<string>() is { Length: > 0 } engineError)
            diagnostics.Add(new JsonObject { ["severity"] = "error", ["message"] = engineError });
        result["schemaVersion"] = 1; result["runId"] = job.Id; result["profileId"] = job.ProfileId;
        result["runtimeId"] = job.RuntimeId; result["recipeId"] = job.RecipeId;
        if (job.RecipeId != "integration.math3d.native-boolean" || result["operation"] == null)
            result["operation"] = job.RecipeId;
        if (job.EnvironmentFingerprint != null)
        {
            result["environmentFingerprint"] = job.EnvironmentFingerprint;
            result["environmentFingerprintScope"] = "SHA-256 of Conda history, CGAL worker executable, and Python adapter";
        }
        if (job.RecipeId == "cgal.validate" && job.Request is { } caseRequest
            && caseRequest.TryGetProperty("parameters", out var caseParameters)
            && caseParameters.TryGetProperty("testCaseId", out var testCaseId)
            && testCaseId.ValueKind == JsonValueKind.String)
            result["testCaseId"] = testCaseId.GetString();
        result["state"] = job.State; result["exitCode"] = job.State is "cancelled" or "timed-out" ? null : job.State == "succeeded" ? 0 : job.ExitCode is > 0 ? job.ExitCode : 1;
        result["durationMs"] = job.DurationMs; result["workerDurationMs"] = workerDuration;
        if (job.Request is { } savedRequest && savedRequest.TryGetProperty("rerunOf", out var parentRun)) result["rerunOf"] = parentRun.GetString();
        result["stage"] = job.Stage; result["logReference"] = "full.log";
        result["before"] = ScientificStatistics(result["before"]); result["after"] = ScientificStatistics(result["after"]);
        var versions = result["versions"] as JsonObject ?? new JsonObject();
        result["versions"] = versions;
        if (job.CompilerVersion != null) versions["msvc"] = job.CompilerVersion;
        result["inputArtifacts"] = job.Request is { } request ? JsonNode.Parse(request.GetRawText())?["inputArtifacts"]?.DeepClone() ?? new JsonArray() : new JsonArray();
        if (job.RecipeId != "integration.math3d.native-boolean" || result["provenance"] == null)
            result["provenance"] = job.Request is { } invocation ? JsonNode.Parse(invocation.GetRawText())?["provenance"]?.DeepClone() ?? new JsonObject() : new JsonObject();
        result["steps"] = JsonSerializer.SerializeToNode(job.Steps, ScientificJson);
        var artifacts = new JsonArray();
        if ((job.State == "succeeded" || job.RecipeId == "matrix.cgal.real-mesh") && job.Request is { } definition)
        {
            foreach (var artifact in definition.GetProperty("outputArtifacts").EnumerateArray())
            {
                var relative = artifact.GetProperty("path").GetString() ?? "";
                if (ScientificArtifactFiles.Describe(job.Directory, relative) is { } registered)
                {
                    if (artifact.TryGetProperty("role", out var role) && role.ValueKind == JsonValueKind.String) registered["role"] = role.GetString();
                    artifacts.Add(registered);
                }
            }
        }
        result["artifacts"] = artifacts;
        if (job.State != "succeeded") result["validatedCapabilities"] = new JsonArray();
        else if (result["validatedCapabilities"] == null) result["validatedCapabilities"] = new JsonArray();
        if (job.RecipeId == "test-all" && job.RuntimeId == "vtk-win-conda")
        {
            var render = ScientificScopedFile(job.Directory, "render/results.json");
            if (File.Exists(render) && new FileInfo(render).Length <= 65536) result["rendering"] = JsonNode.Parse(File.ReadAllText(render));
        }
        var temporary = Path.Combine(job.Directory, "results.json.tmp");
        File.WriteAllText(temporary, result.ToJsonString(ScientificJson), new UTF8Encoding(false));
        File.Move(temporary, path, true);
        job.Result = JsonSerializer.SerializeToElement(result, ScientificJson);
        ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) });
    }
    private object ScientificEvidence(string profileId, string runtimeId)
    {
        var report = ScientificReport();
        string? compilerVersion = report.GetProperty("compiler").TryGetProperty("actualVersion", out var actual) ? actual.GetString() : null;
        var compilerSource = compilerVersion == null ? "Not probed" : "cl.exe version probe";
        JsonElement? rendering = null;
        if (_scientificJobs.TryGetValue(profileId + ":" + runtimeId, out var job))
        {
            if (job.CompilerVersion != null) { compilerVersion = job.CompilerVersion; compilerSource = "Recorded CMake compiler identification"; }
            if (job.Result is { } result && result.TryGetProperty("rendering", out var render)) rendering = render.Clone();
        }
        var runtime = report.GetProperty("runtimes").EnumerateArray().FirstOrDefault(item => item.GetProperty("id").GetString() == runtimeId);
        if (runtime.ValueKind == JsonValueKind.Object && runtime.TryGetProperty("checks", out var checks))
            foreach (var check in checks.EnumerateArray().Where(item => item.GetProperty("id").GetString() == "vtk.offscreen" && item.GetProperty("state").GetString() == "passed"))
            {
                var file = check.GetProperty("detail").GetString();
                if (file != null && Path.IsPathFullyQualified(file))
                {
                    try
                    {
                        var scoped = ScientificScopedFile(ScientificDataRoot, Path.GetRelativePath(ScientificDataRoot, file).Replace('\\', '/'));
                        if (File.Exists(scoped) && new FileInfo(scoped).Length <= 65536)
                        { using var document = JsonDocument.Parse(File.ReadAllText(scoped)); rendering = document.RootElement.Clone(); }
                    }
                    catch (Exception exception) { Debug.WriteLine($"Rendering evidence unavailable: {exception.Message}"); }
                }
            }
        return new { compilerVersion, compilerSource, rendering };
    }
    private async Task<object> ScientificPreviewAsync(ScientificJob job, JsonElement request)
    {
        if (job.State != "succeeded" || job.Result is not { } result || job.Request is not { } definition)
            throw new InvalidOperationException("Run a mesh recipe successfully before loading its preview.");
        var artifacts = result.GetProperty("artifacts").EnumerateArray().ToArray();
        var requested = request.TryGetProperty("artifactPath", out var selection) ? selection.GetString() : artifacts.FirstOrDefault().TryGetProperty("path", out var first) ? first.GetString() : null;
        if (requested == null || !artifacts.Any(item => item.GetProperty("path").GetString() == requested))
            throw new InvalidOperationException("Select an artifact from this run's result contract.");
        var output = ScientificScopedFile(job.Directory, requested);
        if (!ScientificMeshExtensions.Contains(Path.GetExtension(output).ToLowerInvariant()) || !File.Exists(output) || new FileInfo(output).Length > 67108864)
            throw new InvalidOperationException("Preview requires a bounded OBJ/STL/PLY/VTP/M3DM output.");
        var record = artifacts.First(item => item.GetProperty("path").GetString() == requested);
        if (record.TryGetProperty("sha256", out var expected) && ScientificHash(output) != expected.GetString())
            throw new InvalidOperationException("Output artifact changed since the run completed.");
        JsonElement selectedCase = default;
        if (job.RecipeId == "integration.math3d.native-boolean"
            && result.TryGetProperty("comparison", out var comparison)
            && comparison.TryGetProperty("cases", out var cases)
            && cases.ValueKind == JsonValueKind.Array)
            selectedCase = cases.EnumerateArray().FirstOrDefault(item => item.TryGetProperty("outputArtifact", out var named)
                && named.ValueKind == JsonValueKind.String && named.GetString() == requested);
        var datasetId = selectedCase.ValueKind == JsonValueKind.Object
            && selectedCase.TryGetProperty("datasetId", out var dataset) ? dataset.GetString() : null;
        string? input = null;
        string? inputSecond = null;
        var retainedBoolean = job.RecipeId == "cgal.boolean";
        var realMeshSuite = job.RecipeId == "matrix.cgal.real-mesh";
        foreach (var artifact in definition.GetProperty("inputArtifacts").EnumerateArray()
            .Where(item => !retainedBoolean && !realMeshSuite && (datasetId == null || item.TryGetProperty("datasetId", out var id) && id.GetString() == datasetId)).Take(1))
        {
            var file = artifact.GetProperty("path").GetString() ?? "";
            var root = Path.Combine(ScientificDataRoot, "datasets");
            file = ScientificScopedFile(root, Path.GetRelativePath(root, file).Replace('\\', '/'));
            if (ScientificMeshExtensions.Contains(Path.GetExtension(file).ToLowerInvariant()))
            {
                if (!File.Exists(file) || new FileInfo(file).Length > 33554432 || ScientificHash(file) != artifact.GetProperty("sha256").GetString())
                    throw new InvalidOperationException("Input fixture changed since the run; comparison would be misleading.");
                input = file;
            }
        }
        if (datasetId != null && input == null)
            throw new InvalidOperationException("The selected case's registered input is unavailable for preview.");
        if (realMeshSuite)
        {
            var matchedCase = result.GetProperty("realMeshSuite").GetProperty("cases").EnumerateArray()
                .FirstOrDefault(item => item.GetProperty("operations").EnumerateArray()
                    .Any(operation => operation.TryGetProperty("artifact", out var name) && name.GetString() == requested));
            if (matchedCase.ValueKind != JsonValueKind.Object)
                throw new InvalidOperationException("The selected real-mesh output has no recorded source case.");
            var sourceName = matchedCase.GetProperty("source").GetString();
            if (sourceName is not ("11_armadillo.obj" or "10_3dbenchy.stl"))
                throw new InvalidOperationException("The selected real-mesh source is not registered.");
            var recordedInput = definition.GetProperty("inputArtifacts").EnumerateArray()
                .FirstOrDefault(item => Path.GetFileName(item.GetProperty("path").GetString()) == sourceName);
            if (recordedInput.ValueKind != JsonValueKind.Object)
                throw new InvalidOperationException("The selected real-mesh source copy is missing from the request.");
            input = ScientificScopedFile(job.Directory, "inputs/" + sourceName);
            if (!File.Exists(input) || new FileInfo(input).Length > 33554432
                || !string.Equals(recordedInput.GetProperty("path").GetString(), input, StringComparison.OrdinalIgnoreCase)
                || ScientificHash(input) != recordedInput.GetProperty("sha256").GetString())
                throw new InvalidOperationException("The real-mesh source copy changed since the run completed.");
            if (matchedCase.TryGetProperty("previewInputs", out var previewInputs)
                && previewInputs.TryGetProperty("B", out var secondSnapshot))
            {
                var caseName = matchedCase.GetProperty("name").GetString();
                if (caseName is not ("armadillo-shift" or "armadillo-rotated"
                    or "3dbenchy-cutter" or "3dbenchy-second-cutter"))
                    throw new InvalidOperationException("The selected real-mesh case is not registered for input preview.");
                var relative = "inputs/" + caseName + "-b.obj";
                if (secondSnapshot.GetProperty("path").GetString() != relative)
                    throw new InvalidOperationException("The recorded second input path is invalid.");
                inputSecond = ScientificScopedFile(job.Directory, relative);
                if (!File.Exists(inputSecond) || new FileInfo(inputSecond).Length > 33554432
                    || new FileInfo(inputSecond).Length != secondSnapshot.GetProperty("bytes").GetInt64()
                    || ScientificHash(inputSecond) != secondSnapshot.GetProperty("sha256").GetString())
                    throw new InvalidOperationException("The transformed real-mesh input changed since the run completed.");
            }
        }
        if (retainedBoolean)
        {
            input = ScientificArtifactFiles.ResolveRegistered(job.Directory, result, "operand-a.m3dm");
            inputSecond = ScientificArtifactFiles.ResolveRegistered(job.Directory, result, "operand-b.m3dm");
        }
        double? secondOffsetX = null;
        double secondScale = 1;
        if (selectedCase.ValueKind == JsonValueKind.Object
            && selectedCase.TryGetProperty("rightOperand", out var rightOperand)
            && rightOperand.TryGetProperty("translateX", out var translation)
            && translation.ValueKind == JsonValueKind.Number)
        {
            var offset = translation.GetDouble();
            if (!double.IsFinite(offset) || Math.Abs(offset) > 1000)
                throw new InvalidOperationException("The recorded input translation is invalid.");
            if (rightOperand.TryGetProperty("scale", out var scale)) secondScale = scale.GetDouble();
            if (!double.IsFinite(secondScale) || secondScale <= 0 || secondScale > 1000)
                throw new InvalidOperationException("The recorded input scale is invalid.");
            if (offset != 0 || secondScale != 1) secondOffsetX = offset;
        }
        if (!await _scientificPreviewGate.WaitAsync(0)) throw new InvalidOperationException("A mesh preview is already loading.");
        try
        {
            var prefix = ScientificPrefix("vtk-win-conda");
            var start = new ProcessStartInfo(Path.Combine(prefix, "python.exe"))
            { UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true, WorkingDirectory = job.Directory, StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8 };
            start.ArgumentList.Add(Path.Combine(ScientificSourceRoot, "tools", "scientific-artifact-preview.py"));
            if (input != null) { start.ArgumentList.Add("--before"); start.ArgumentList.Add(input); }
            if (inputSecond != null) { start.ArgumentList.Add("--before-second"); start.ArgumentList.Add(inputSecond); }
            if (secondOffsetX != null)
            {
                start.ArgumentList.Add("--second-translate-x");
                start.ArgumentList.Add(secondOffsetX.Value.ToString("R", System.Globalization.CultureInfo.InvariantCulture));
                start.ArgumentList.Add("--second-scale");
                start.ArgumentList.Add(secondScale.ToString("R", System.Globalization.CultureInfo.InvariantCulture));
            }
            start.ArgumentList.Add("--after"); start.ArgumentList.Add(output);
            foreach (var pair in ScientificEnvironment(prefix)) start.Environment[pair.Key] = pair.Value;
            start.Environment.Remove("PYTHONPATH");
            using var process = new Process { StartInfo = start };
            using var owner = new OwnedProcessJob();
            using var timeout = CancellationTokenSource.CreateLinkedTokenSource(_scientificLifetime.Token);
            timeout.CancelAfter(TimeSpan.FromSeconds(30));
            if (!process.Start()) throw new InvalidOperationException("Could not start the read-only preview adapter.");
            try
            {
                owner.Add(process);
                async Task<string> ReadBounded(StreamReader reader, int limit)
                {
                    var text = new StringBuilder(); var buffer = new char[4096]; int count;
                    while ((count = await reader.ReadAsync(buffer.AsMemory(), timeout.Token)) > 0)
                    { if (text.Length + count > limit) { owner.Stop(); throw new InvalidOperationException("Preview response exceeded its size limit."); } text.Append(buffer, 0, count); }
                    return text.ToString();
                }
                var stdout = ReadBounded(process.StandardOutput, 8388608);
                var stderr = ReadBounded(process.StandardError, 65536);
                await process.WaitForExitAsync(timeout.Token);
                var text = await stdout; var errors = await stderr;
                if (process.ExitCode != 0) throw new InvalidOperationException("Mesh preview failed: " + errors[..Math.Min(errors.Length, 1000)]);
                using var document = JsonDocument.Parse(text);
                return new { jobId = job.Id, artifactPath = requested, geometry = document.RootElement.Clone(), result };
            }
            finally { owner.Stop(); }
        }
        finally { _scientificPreviewGate.Release(); }
    }
}
