using System.Diagnostics;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace BatchLauncher;

public partial class Form1
{
    private object ScientificCgalRepairHandoffStart(string profileId, string runtimeId, string sourceRunId)
    {
        if (runtimeId != "cgal-win-conda") throw new InvalidOperationException("Select the Windows Native CGAL profile.");
        var (sourceDirectory, source) = ScientificHistoryFind(profileId, sourceRunId);
        if (source.GetProperty("runtimeId").GetString() != runtimeId
            || source.GetProperty("recipeId").GetString() is not ("cgal.fill-one-hole" or "cgal.fill-quad-hole" or "cgal.fill-two-quad-holes" or "cgal.fill-bounded-holes")
            || source.GetProperty("state").GetString() != "succeeded"
            || !source.GetProperty("validatedCapabilities").EnumerateArray().Any(item => item.GetString() == "mesh.repair"))
            throw new InvalidOperationException("Choose a successful managed CGAL repair run.");
        var checkout = Math3DCheckout;
        if (!File.Exists(Path.Combine(checkout, "renderer", "src", "mesh", "surfaceMesh.ts")))
            throw new InvalidOperationException("The MATH3D desktop importer is unavailable.");
        var node = Math3DNode;
        var prefix = ScientificPrefix(runtimeId);
        if (!_scientificGate.Wait(0)) throw new InvalidOperationException("A Scientific recipe is already running.");
        try
        {
            var directory = Path.Combine(ScientificDataRoot, "runs", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(directory);
            var job = new ScientificJob { ProfileId = profileId, RuntimeId = runtimeId,
                RecipeId = "integration.math3d.repair-handoff", Directory = directory };
            var parameters = JsonSerializer.SerializeToElement(new { sourceRunId });
            ScientificWriteRequest(job, parameters, output: "handoff.json",
                additionalOutputs: new JsonArray(new JsonObject { ["path"] = "math3d-consumed.json", ["mediaType"] = "application/json" }));
            _scientificJobs[profileId + ":" + runtimeId] = job;
            ScientificSend(new { type = "scientific.runtime.job", profileId, job = ScientificJobSnapshot(job) });
            _ = ScientificCgalRepairHandoffRunAsync(job, prefix, node, checkout, sourceDirectory, sourceRunId);
            return ScientificJobSnapshot(job);
        }
        catch { _scientificGate.Release(); throw; }
    }

    private async Task ScientificCgalRepairHandoffRunAsync(ScientificJob job, string prefix, string node,
        string checkout, string sourceDirectory, string sourceRunId)
    {
        var timer = Stopwatch.StartNew();
        try
        {
            var tool = Path.Combine(ScientificSourceRoot, "tools", "scientific-cgal-repair-math3d-handoff.py");
            var report = Path.Combine(job.Directory, "handoff.json");
            job.ExecutedFiles.Add(ScientificRunFingerprint.ExecutedFile(node, "math3d-node"));
            job.ExecutedFiles.Add(ScientificRunFingerprint.ExecutedFile(
                Path.Combine(checkout, "renderer", "src", "mesh", "surfaceMesh.ts"), "math3d-importer-source"));
            job.Stage = "math3d-import";
            await ScientificProcessAsync(job, prefix, Path.Combine(prefix, "python.exe"),
                new[] { tool, "--run-directory", sourceDirectory, "--checkout", checkout,
                    "--node", node, "--report", report }, job.Directory, 150);
            var handoff = JsonNode.Parse(File.ReadAllText(report)) as JsonObject
                ?? throw new InvalidDataException("MATH3D handoff report is invalid.");
            if (handoff["verdict"]?.GetValue<string>() != "passed"
                || handoff["runId"]?.GetValue<string>() != sourceRunId)
                throw new InvalidDataException("MATH3D handoff did not verify the selected source run.");
            File.WriteAllText(Path.Combine(job.Directory, "results.json"),
                new JsonObject { ["sourceRunId"] = sourceRunId, ["handoff"] = handoff.DeepClone(),
                    ["validatedCapabilities"] = new JsonArray() }.ToJsonString());
            job.State = "succeeded";
            job.Stage = "completed";
        }
        catch (OperationCanceledException) { job.State = "cancelled"; job.Error = "Only this owned handoff was stopped."; }
        catch (TimeoutException error) { job.State = "timed-out"; job.Error = error.Message; }
        catch (Exception error) { job.State = "failed"; job.Error = error.Message; }
        finally
        {
            job.DurationMs = timer.ElapsedMilliseconds;
            try { ScientificFinish(job); ScientificLog(job, $"\n[{job.State}] {job.DurationMs} ms {job.Error}\n"); }
            catch (Exception error) { Debug.WriteLine($"Repair handoff finalization failed: {error}"); }
            finally { ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) }); _scientificGate.Release(); }
        }
    }
}
