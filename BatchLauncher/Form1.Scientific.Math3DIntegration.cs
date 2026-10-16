using System.Diagnostics;
using System.Text.Json;

namespace BatchLauncher;

public partial class Form1
{
    private object ScientificMath3DIntegrationStart(string profileId, string runtimeId)
    {
        if (runtimeId != "cgal-win-conda")
            throw new InvalidOperationException("The MATH3D integration test requires the Windows Native CGAL runtime.");

        var prefix = ScientificPrefix(runtimeId);
        var sourceRoot = Path.GetDirectoryName(ScientificDataRoot)
            ?? throw new InvalidOperationException("Scientific data root has no parent directory.");
        var script = Path.Combine(sourceRoot, "tools", "compare-math3d-native-worker.mjs");
        var worker = Path.Combine(ScientificDataRoot, "builds", "math3d-native-worker", "Release", "math3d-cgal-worker.exe");
        var node = (Environment.GetEnvironmentVariable("PATH") ?? string.Empty)
            .Split(Path.PathSeparator)
            .Select(directory => Path.Combine(directory.Trim('"'), "node.exe"))
            .FirstOrDefault(File.Exists);
        if (node is null) throw new FileNotFoundException("Node.js is required to run the MATH3D integration harness.");
        if (!File.Exists(script)) throw new FileNotFoundException("MATH3D integration harness is missing.", script);
        if (!File.Exists(worker))
            throw new FileNotFoundException("MATH3D native worker is not built in the local Scientific builds folder.", worker);

        if (!_scientificGate.Wait(0))
            throw new InvalidOperationException("Another Scientific job is running; stop or wait for it.");
        try
        {
            var directory = Path.Combine(ScientificDataRoot, "runs", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(directory);
            var job = new ScientificJob
            {
                ProfileId = profileId,
                RuntimeId = runtimeId,
                RecipeId = "integration.math3d.native-boolean",
                Directory = directory
            };
            ScientificWriteRequest(job, null);
            _scientificJobs[profileId + ":" + runtimeId] = job;
            ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) });
            _ = ScientificMath3DIntegrationRunAsync(job, prefix, node, script, worker);
            return ScientificJobSnapshot(job);
        }
        catch
        {
            _scientificGate.Release();
            throw;
        }
    }

    private async Task ScientificMath3DIntegrationRunAsync(ScientificJob job, string prefix,
        string node, string script, string worker)
    {
        var timer = Stopwatch.StartNew();
        try
        {
            await ScientificProcessAsync(job, prefix, node,
                new[] { script, worker, job.Directory, job.ProfileId }, job.Directory, 60);
            using var saved = JsonDocument.Parse(File.ReadAllText(Path.Combine(job.Directory, "results.json")));
            if (!saved.RootElement.TryGetProperty("comparison", out var comparison) ||
                !comparison.TryGetProperty("verdict", out var verdict) || verdict.GetString() != "pass")
                throw new InvalidOperationException("MATH3D integration comparison did not pass; see the saved result and log.");
            job.State = "succeeded";
            job.Stage = "completed";
        }
        catch (OperationCanceledException) { job.State = "cancelled"; job.Stage = "stopped"; job.Error = "The owned MATH3D integration job was stopped."; }
        catch (TimeoutException exception) { job.State = "timed-out"; job.Stage = "timed-out"; job.Error = exception.Message; }
        catch (Exception exception) { job.State = "failed"; job.Stage = "failed"; job.Error = exception.Message; }
        finally
        {
            job.DurationMs = timer.ElapsedMilliseconds;
            try { ScientificFinish(job); ScientificLog(job, $"\n[{job.State}] {job.DurationMs} ms {job.Error}\n"); }
            catch (Exception exception) { Debug.WriteLine($"MATH3D integration finalization failed: {exception}"); }
            finally { ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) }); _scientificGate.Release(); }
        }
    }
}
