using System.Diagnostics;

namespace BatchLauncher;

public partial class Form1
{
    private object ScientificStopTestStart(string profileId, string runtimeId)
    {
        var prefix = ScientificPrefix(runtimeId);
        if (!_scientificGate.Wait(0)) throw new InvalidOperationException("Another Scientific job is running; stop or wait for it.");
        try
        {
            var directory = Path.Combine(ScientificDataRoot, "runs", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(directory);
            var job = new ScientificJob { ProfileId = profileId, RuntimeId = runtimeId, RecipeId = "test-hold", Directory = directory };
            ScientificWriteRequest(job, null, null, "stop-test-triangle.obj");
            _scientificJobs[profileId + ":" + runtimeId] = job;
            ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) });
            _ = ScientificStopTestRunAsync(job, prefix);
            return ScientificJobSnapshot(job);
        }
        catch { _scientificGate.Release(); throw; }
    }

    private async Task ScientificStopTestRunAsync(ScientificJob job, string prefix)
    {
        var timer = Stopwatch.StartNew();
        try
        {
            const string code = "import pathlib,time\n"
                + "print('Managed Stop test: waiting 30 seconds',flush=True)\n"
                + "time.sleep(30)\n"
                + "pathlib.Path('stop-test-triangle.obj').write_text('v 0 0 0\\nv 1 0 0\\nv 0 1 0\\nf 1 2 3\\n',encoding='utf-8')\n"
                + "print('Test fixture written',flush=True)\n";
            await ScientificProcessAsync(job, prefix, Path.Combine(prefix, "python.exe"), new[] { "-c", code }, job.Directory, 45);
            job.State = "succeeded";
            job.Stage = "completed";
        }
        catch (OperationCanceledException) { job.State = "cancelled"; job.Stage = "stopped"; job.Error = "Only this owned test job was stopped."; }
        catch (TimeoutException exception) { job.State = "timed-out"; job.Stage = "timed-out"; job.Error = exception.Message; }
        catch (Exception exception) { job.State = "failed"; job.Stage = "failed"; job.Error = exception.Message; }
        finally
        {
            job.DurationMs = timer.ElapsedMilliseconds;
            try { ScientificFinish(job); ScientificLog(job, $"\n[{job.State}] {job.DurationMs} ms {job.Error}\n"); }
            catch (Exception exception) { Debug.WriteLine($"Stop test final log failed: {exception}"); }
            finally { ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) }); _scientificGate.Release(); }
        }
    }
}
