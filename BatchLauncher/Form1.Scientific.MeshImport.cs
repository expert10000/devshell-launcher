using System.Diagnostics;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace BatchLauncher;

public partial class Form1
{
    private object ScientificMeshImportStart(string profileId, string runtimeId)
    {
        if (runtimeId != "cgal-win-conda") throw new InvalidOperationException("Select CGAL / Windows Native to import meshes.");
        if (!_scientificGate.Wait(0)) throw new InvalidOperationException("Another Scientific job is running; stop or wait for it.");
        try
        {
            using var dialog = new OpenFileDialog { Title = "Import meshes into the Scientific lab", Filter = "Mesh files (*.obj;*.stl;*.ply;*.off)|*.obj;*.stl;*.ply;*.off", Multiselect = true, CheckFileExists = true, RestoreDirectory = true };
            if (dialog.ShowDialog(this) != DialogResult.OK) { _scientificGate.Release(); return new { cancelled = true }; }
            var files = dialog.FileNames.Distinct(StringComparer.OrdinalIgnoreCase).ToArray();
            if (files.Length is 0 or > 16) throw new InvalidOperationException("Import between 1 and 16 meshes at a time.");
            var id = Guid.NewGuid().ToString("N");
            var directory = Path.Combine(ScientificDataRoot, "runs", id);
            Directory.CreateDirectory(directory);
            var job = new ScientificJob { Id = id, ProfileId = profileId, RuntimeId = runtimeId, RecipeId = "datasets.import", Directory = directory };
            ScientificWriteRequest(job, JsonSerializer.SerializeToElement(new { files = files.Select(Path.GetFileName).ToArray() }));
            _scientificJobs[profileId + ":" + runtimeId] = job;
            _ = ScientificMeshImportRunAsync(job, files);
            return ScientificJobSnapshot(job);
        }
        catch { _scientificGate.Release(); throw; }
    }

    private async Task ScientificMeshImportRunAsync(ScientificJob job, string[] files)
    {
        await Task.Yield();
        var timer = Stopwatch.StartNew();
        var records = new JsonArray(files.Select(file => (JsonNode)new JsonObject { ["name"] = Path.GetFileName(file), ["state"] = "queued" }).ToArray());
        try
        {
            for (var index = 0; index < files.Length; index++)
            {
                job.Cancellation.Token.ThrowIfCancellationRequested();
                var record = (JsonObject)records[index]!;
                JsonObject? entry = null;
                try
                {
                    job.Stage = $"copy {index + 1}/{files.Length}";
                    ScientificLog(job, $"Importing {Path.GetFileName(files[index])}\n");
                    entry = await Task.Run(() => ScientificMeshImports.Import(ScientificDataRoot, files[index], job.Cancellation.Token));
                    record["id"] = entry["id"]!.DeepClone(); record["sha256"] = entry["sha256"]!.DeepClone(); record["bytes"] = entry["bytes"]!.DeepClone();
                    record["state"] = "validating";
                    job.Result = JsonSerializer.SerializeToElement(ScientificMeshImports.Progress(job.Id, job.ProfileId, records));
                    ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) });
                    var directory = Path.Combine(job.Directory, $"validation-{index + 1}");
                    Directory.CreateDirectory(directory);
                    var validation = new ScientificJob { ProfileId = job.ProfileId, RuntimeId = job.RuntimeId, RecipeId = "cgal.validate", Directory = directory, Cancellation = job.Cancellation };
                    var inputId = entry["id"]!.GetValue<string>();
                    ScientificWriteRequest(validation, JsonSerializer.SerializeToElement(new { inputId, outputName = "validated.obj" }), ScientificDatasetArtifact(inputId), "validated.obj");
                    await ScientificCgalExecuteAsync(validation, ScientificPrefix(job.RuntimeId), job);
                    using var result = JsonDocument.Parse(File.ReadAllText(Path.Combine(directory, "results.json")));
                    if (result.RootElement.GetProperty("state").GetString() != "succeeded") throw new InvalidOperationException("CGAL validation failed.");
                    var after = result.RootElement.GetProperty("after");
                    var closed = after.GetProperty("closed").GetBoolean();
                    record["state"] = closed ? "passed" : "open"; record["closed"] = closed;
                    record["triangles"] = after.GetProperty("faces").GetInt64();
                    record["message"] = closed ? "CGAL validation passed; closed mesh. Boolean runs also check solid orientation." : "Imported and validated, but open. Boolean operations require a closed solid.";
                    record["validationReference"] = $"validation-{index + 1}/results.json";
                }
                catch (OperationCanceledException) { record["state"] = "cancelled"; record["message"] = "Validation was stopped; any registered copy remains available."; throw; }
                catch (Exception exception)
                {
                    var message = exception.Message;
                    try
                    {
                        var failed = Path.Combine(job.Directory, $"validation-{index + 1}", "results.json");
                        if (File.Exists(failed) && new FileInfo(failed).Length <= 1048576)
                        {
                            using var parsed = JsonDocument.Parse(File.ReadAllText(failed));
                            var diagnostics = parsed.RootElement.GetProperty("diagnostics");
                            if (diagnostics.GetArrayLength() > 0) message = diagnostics[0].GetProperty("message").GetString() ?? message;
                        }
                    }
                    catch (Exception diagnosticError) { Debug.WriteLine(diagnosticError.Message); }
                    record["state"] = "failed"; record["message"] = message;
                    ScientificLog(job, $"Rejected {Path.GetFileName(files[index])}: {message}\n");
                }
                finally
                {
                    if (entry != null)
                    {
                        var validation = (JsonObject)record.DeepClone(); validation["runId"] = job.Id; validation["profileId"] = job.ProfileId; validation["checkedAt"] = DateTimeOffset.UtcNow.ToString("O");
                        ScientificMeshImports.SaveValidation(ScientificDataRoot, entry["id"]!.GetValue<string>(), entry["sha256"]!.GetValue<string>(), validation);
                    }
                    job.Result = JsonSerializer.SerializeToElement(ScientificMeshImports.Progress(job.Id, job.ProfileId, records));
                    ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) });
                }
            }
            job.State = records.Any(item => item?["state"]?.GetValue<string>() == "failed") ? "failed" : "succeeded";
            job.Stage = "completed";
            if (job.State == "failed") job.Error = "Some meshes could not be copied or validated. See results for each file.";
        }
        catch (OperationCanceledException) { job.State = "cancelled"; job.Stage = "stopped"; job.Error = "Mesh import and validation stopped."; }
        catch (Exception exception) { job.State = "failed"; job.Stage = "failed"; job.Error = exception.Message; }
        finally
        {
            job.DurationMs = timer.ElapsedMilliseconds;
            foreach (var record in records.OfType<JsonObject>().Where(item => item["state"]?.GetValue<string>() == "queued")) { record["state"] = "not-started"; }
            try
            {
                File.WriteAllText(Path.Combine(job.Directory, "results.json"), new JsonObject { ["imports"] = records.DeepClone() }.ToJsonString());
                ScientificFinish(job);
                ScientificLog(job, $"\n[{job.State}] {job.DurationMs} ms {job.Error}\n");
            }
            catch (Exception exception) { Debug.WriteLine(exception); }
            finally { ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) }); _scientificGate.Release(); }
        }
    }

    private object ScientificBooleanDraft(string profileId, string jobId)
    {
        var (request, result) = ScientificBooleanSavedRequest(profileId, jobId);
        var parameters = ScientificBooleanReplay.Read(request, result, profileId);
        foreach (var input in request.GetProperty("inputArtifacts").EnumerateArray())
            ScientificBooleanReplay.VerifyInput(input, ScientificDatasetArtifact(input.GetProperty("datasetId").GetString()!));
        return new { sourceJobId = jobId, parameters };
    }

    private static (JsonElement Request, JsonElement Result) ScientificBooleanSavedRequest(string profileId, string jobId)
    {
        var (directory, result) = ScientificHistoryFind(profileId, jobId);
        var file = ScientificScopedFile(directory, "request.json");
        if (!File.Exists(file) || new FileInfo(file).Length > 1048576) throw new InvalidOperationException("The saved Boolean request is unavailable.");
        using var document = JsonDocument.Parse(File.ReadAllText(file));
        ScientificBooleanReplay.Read(document.RootElement, result, profileId);
        return (document.RootElement.Clone(), result);
    }
}
