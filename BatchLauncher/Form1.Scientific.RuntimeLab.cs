using System.Diagnostics;

namespace BatchLauncher;

public partial class Form1
{
    private object ScientificLabProbeStart(string profileId, string runtimeId)
    {
        if (runtimeId is not ("cgal-win-conda" or "vtk-win-conda"))
            throw new InvalidOperationException("This runtime has no registered runtime-lab probe manifest.");

        var prefix = ScientificPrefix(runtimeId);
        var executable = Path.Combine(AppContext.BaseDirectory, "runtime-lab", "runtime-lab.exe");
        var manifests = Path.Combine(AppContext.BaseDirectory, "runtimes");
        if (!File.Exists(executable))
            throw new FileNotFoundException("runtime-lab is not installed with this DevShell build.", executable);
        if (!File.Exists(Path.Combine(manifests, runtimeId, "runtime.json")))
            throw new FileNotFoundException("The runtime-lab probe manifest is missing.");

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
                RecipeId = "lab.probe",
                Directory = directory
            };
            ScientificWriteRequest(job, null);
            _scientificJobs[profileId + ":" + runtimeId] = job;
            ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) });
            _ = ScientificLabProbeRunAsync(job, prefix, executable, manifests);
            return ScientificJobSnapshot(job);
        }
        catch
        {
            _scientificGate.Release();
            throw;
        }
    }

    private async Task ScientificLabProbeRunAsync(ScientificJob job, string prefix,
        string executable, string manifests)
    {
        var timer = Stopwatch.StartNew();
        try
        {
            var arguments = new[]
            {
                "probe", job.RuntimeId,
                "--manifest-root", manifests,
                "--prefix", prefix,
                "--run-id", job.Id,
                "--output", job.Directory
            };
            await ScientificProcessAsync(job, prefix, executable, arguments, job.Directory, 120);
            job.State = "succeeded";
            job.Stage = "completed";
        }
        catch (OperationCanceledException)
        {
            job.State = "cancelled";
            job.Stage = "stopped";
            job.Error = "The owned runtime-lab job was stopped.";
        }
        catch (TimeoutException exception)
        {
            job.State = "timed-out";
            job.Stage = "timed-out";
            job.Error = exception.Message;
        }
        catch (Exception exception)
        {
            job.State = "failed";
            job.Stage = "failed";
            job.Error = exception.Message;
        }
        finally
        {
            job.DurationMs = timer.ElapsedMilliseconds;
            try
            {
                ScientificFinish(job);
                ScientificLog(job, $"\n[{job.State}] {job.DurationMs} ms {job.Error}\n");
            }
            catch (Exception exception)
            {
                Debug.WriteLine($"Runtime-lab final log failed: {exception}");
            }
            finally
            {
                ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) });
                _scientificGate.Release();
            }
        }
    }
}
