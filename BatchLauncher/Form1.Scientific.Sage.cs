using System.Diagnostics;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace BatchLauncher;

public partial class Form1
{
    private const string SageCandidates = "for candidate in /usr/bin/sage /usr/local/bin/sage \"$HOME/miniforge3/envs/sage/bin/sage\" \"$HOME/mambaforge/envs/sage/bin/sage\" \"$HOME/miniconda3/envs/sage/bin/sage\"; do if test -x \"$candidate\"; then ";
    private const string SageMissing = "fi; done; echo 'SageMath is missing in the selected WSL distribution. Install Sage in a conda environment named sage.' >&2; exit 127";
    private const string SageSmokeCode = "from sage.all import PolynomialRing, QQ; R = PolynomialRing(QQ, \"x\"); x = R.gen(); result = (x*x - 1).factor(); assert str(result) == \"(x - 1) * (x + 1)\"; print(\"verified: \" + str(result))";
    private static string ScientificSageDistro()
    {
        var distro = Environment.GetEnvironmentVariable("MATH3D_WSL_DISTRO") ?? "Ubuntu";
        if (!Regex.IsMatch(distro, "^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")) throw new InvalidOperationException("Invalid MATH3D_WSL_DISTRO name.");
        return distro;
    }

    private object ScientificSageStart(string profileId, string runtimeId, JsonElement request)
    {
        if (runtimeId != "sage-wsl") throw new InvalidOperationException("Select SageMath / WSL Ubuntu.");
        var recipe = request.GetProperty("recipeId").GetString() ?? "";
        if (recipe is not ("sage.version" or "sage.factor-smoke")) throw new InvalidOperationException("Sage recipe is not registered.");
        if (!_scientificGate.Wait(0)) throw new InvalidOperationException("Another Scientific job is running; stop or wait for it.");
        try
        {
            var directory = Path.Combine(ScientificDataRoot, "runs", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(directory);
            var job = new ScientificJob { ProfileId = profileId, RuntimeId = runtimeId, RecipeId = recipe, Directory = directory };
            _scientificJobs[profileId + ":" + runtimeId] = job;
            ScientificWriteRequest(job, null, timeoutSeconds: 120);
            _ = ScientificRunSageAsync(job);
            return ScientificJobSnapshot(job);
        }
        catch { _scientificGate.Release(); throw; }
    }

    private async Task ScientificRunSageAsync(ScientificJob job)
    {
        var timer = Stopwatch.StartNew();
        try
        {
            job.Stage = "wsl-start";
            var script = SageCandidates + (job.RecipeId == "sage.version"
                ? "exec /usr/bin/timeout --kill-after=1s 15s \"$candidate\" --version; "
                : "exec /usr/bin/timeout --kill-after=1s 45s \"$candidate\" -c '" + SageSmokeCode + "'; ") + SageMissing;
            var start = new ProcessStartInfo("wsl.exe")
            {
                UseShellExecute = false, CreateNoWindow = true,
                RedirectStandardOutput = true, RedirectStandardError = true,
                StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8
            };
            var distro = ScientificSageDistro();
            foreach (var argument in new[] { "-d", distro, "--exec", "/bin/sh", "-c", script }) start.ArgumentList.Add(argument);
            ScientificLog(job, job.RecipeId == "sage.version" ? "$ wsl Ubuntu / SageMath --version\n" : "$ wsl Ubuntu / SageMath exact factorization smoke test\n");
            using var process = new Process { StartInfo = start };
            using var owner = new OwnedProcessJob();
            using var cancellation = CancellationTokenSource.CreateLinkedTokenSource(job.Cancellation.Token, _scientificLifetime.Token);
            cancellation.CancelAfter(TimeSpan.FromSeconds(120));
            if (!process.Start()) throw new InvalidOperationException("Could not start WSL.");
            owner.Add(process);
            var output = new StringBuilder();
            async Task Drain(StreamReader reader, bool capture)
            {
                var buffer = new char[1024]; int count;
                while ((count = await reader.ReadAsync(buffer.AsMemory())) > 0)
                {
                    var chunk = new string(buffer, 0, count);
                    if (capture && output.Length < 4096) output.Append(chunk.AsSpan(0, Math.Min(count, 4096 - output.Length)));
                    ScientificLog(job, chunk);
                }
            }
            var stdout = Drain(process.StandardOutput, true);
            var stderr = Drain(process.StandardError, false);
            try { await process.WaitForExitAsync(cancellation.Token); }
            catch (OperationCanceledException)
            {
                owner.Stop(); await process.WaitForExitAsync(); await Task.WhenAll(stdout, stderr);
                if (job.Cancellation.IsCancellationRequested || _scientificLifetime.IsCancellationRequested) throw;
                throw new TimeoutException("SageMath WSL test exceeded 120 seconds.");
            }
            await Task.WhenAll(stdout, stderr);
            job.ExitCode = process.ExitCode;
            if (process.ExitCode != 0) throw new InvalidOperationException($"SageMath test exited {process.ExitCode}. See the job log.");
            var text = output.ToString().Trim();
            if (job.RecipeId == "sage.version" && !text.Contains("10.", StringComparison.Ordinal) && !text.Contains("SageMath", StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("SageMath version response was not recognized.");
            if (job.RecipeId == "sage.factor-smoke" && text != "verified: (x - 1) * (x + 1)")
                throw new InvalidOperationException("Exact factorization result did not match the expected value.");
            File.WriteAllText(Path.Combine(job.Directory, "results.json"), JsonSerializer.Serialize(new
            {
                versions = job.RecipeId == "sage.version" ? new Dictionary<string, string> { ["sage"] = text } : new Dictionary<string, string>(),
                validatedCapabilities = job.RecipeId == "sage.factor-smoke" ? new[] { "math.symbolic" } : Array.Empty<string>(),
                diagnostics = new[] { new { severity = "info", message = text } },
                evidence = new { distro, test = job.RecipeId, output = text }
            }, ScientificJson), Encoding.UTF8);
            job.Stage = "completed"; job.State = "succeeded";
        }
        catch (OperationCanceledException) { job.State = "cancelled"; job.Error = "Only this owned Sage test was stopped."; }
        catch (TimeoutException exception) { job.State = "timed-out"; job.Error = exception.Message; }
        catch (Exception exception) { job.State = "failed"; job.Error = exception.Message; }
        finally
        {
            job.DurationMs = timer.ElapsedMilliseconds;
            try { ScientificFinish(job); ScientificLog(job, $"\n[{job.State}] {job.DurationMs} ms {job.Error}\n"); }
            catch (Exception exception) { Debug.WriteLine($"Sage test finalization failed: {exception}"); }
            finally { ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) }); _scientificGate.Release(); }
        }
    }
}
