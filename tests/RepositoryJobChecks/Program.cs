using BatchLauncher;
using System.Diagnostics;

static void Check(bool value, string message) { if (!value) throw new Exception(message); }
static async Task<RepositoryJobStatus> Wait(RepositoryRunner runner, string key, Func<RepositoryJobStatus, bool> condition)
{
    for (var i = 0; i < 200; i++)
    {
        var status = runner.Snapshot().Single(job => job.Key == key);
        if (condition(status)) return status;
        await Task.Delay(100);
    }
    throw new Exception("Timed out: " + runner.Snapshot().Single(job => job.Key == key));
}
static bool Alive(int pid) { try { return !Process.GetProcessById(pid).HasExited; } catch (ArgumentException) { return false; } }
var shell = args[0];
var root = Path.Combine(Path.GetTempPath(), "devshell-job-test-" + Guid.NewGuid().ToString("N"));
Directory.CreateDirectory(root);
using var runner = new RepositoryRunner();
RepositoryCommand Command(string script) => new(shell, script, root);
bool Finished(RepositoryJobStatus job) => job.State is "succeeded" or "failed" or "stopped";
try
{
    var verified = false;
    var preparation = new RepositoryPreparation(_ => Task.FromResult<RepositoryCommand?>(Command("Write-Output 'PREPARE OK'; exit 0")), _ => { verified = true; return Task.CompletedTask; });
    runner.Start("prepare", Command("Write-Output 'STALE BUILD'"), Command("Write-Output 'STALE RUN'"), root, "prepare-launch", preparation: preparation with
    {
        Commands = _ =>
        {
            Check(verified, "Tool paths must refresh only after verification");
            return Task.FromResult((Command("Write-Output 'PREPARED BUILD'; exit 0"), Command("Write-Output 'PREPARED RUN'; exit 0")));
        }
    });
    var prepared = await Wait(runner, "prepare", Finished);
    Check(prepared.State == "succeeded" && verified && !prepared.Log.Contains("STALE") && prepared.Log.IndexOf("PREPARE OK") < prepared.Log.IndexOf("PREPARED BUILD") && prepared.Log.IndexOf("PREPARED BUILD") < prepared.Log.IndexOf("PREPARED RUN"), "Preparation, verification, refreshed commands, build and run ordering");
    runner.Start("prepare-failed", Command("Write-Output 'SHOULD NOT BUILD'"), Command("Write-Output 'SHOULD NOT RUN'"), root, "prepare-launch",
        preparation: preparation with { Check = _ => Task.FromResult<RepositoryCommand?>(Command("exit 9")) });
    prepared = await Wait(runner, "prepare-failed", Finished);
    Check(prepared.State == "failed" && prepared.ExitCode == 9 && prepared.BuildState == "not-run" && !prepared.Log.Contains("SHOULD NOT"), "Failed preparation must block build/run");
    runner.Start("verify-failed", Command("Write-Output 'SHOULD NOT BUILD'"), null, root, "prepare-launch",
        preparation: preparation with { Check = _ => Task.FromResult<RepositoryCommand?>(null), Verify = _ => throw new InvalidOperationException("Still missing dependency") });
    prepared = await Wait(runner, "verify-failed", Finished);
    Check(prepared.State == "failed" && prepared.Log.Contains("Still missing dependency") && !prepared.Log.Contains("SHOULD NOT"), "Failed recheck must block build");
    runner.Start("prepare-stop", Command("Write-Output 'SHOULD NOT BUILD'"), null, root, "prepare-launch",
        preparation: preparation with { Check = async token => { await Task.Delay(60000, token); return null; } });
    await Wait(runner, "prepare-stop", job => job.Step == "Checking environment");
    runner.Stop("prepare-stop");
    prepared = await Wait(runner, "prepare-stop", Finished);
    Check(prepared.State == "stopped" && !prepared.Log.Contains("SHOULD NOT"), "Stop during environment inspection must cancel sequence");
    runner.Start("prepare-stop-process", Command("Write-Output 'SHOULD NOT BUILD'"), null, root, "prepare-launch",
        preparation: preparation with { Check = _ => Task.FromResult<RepositoryCommand?>(Command("Write-Output 'REPAIR STARTED'; Start-Sleep 60")) });
    await Wait(runner, "prepare-stop-process", job => job.Log.Contains("REPAIR STARTED"));
    runner.Stop("prepare-stop-process");
    prepared = await Wait(runner, "prepare-stop-process", Finished);
    Check(prepared.State == "stopped" && !prepared.Log.Contains("SHOULD NOT"), "Stop during repair must cancel sequence");
    runner.Start("success", Command("Write-Output 'BUILD OK'; exit 0"), Command("Write-Output 'RUN OK'; exit 0"), root);
    var result = await Wait(runner, "success", Finished);
    Check(result.State == "succeeded" && result.BuildState == "succeeded" && result.Log.IndexOf("BUILD OK") < result.Log.IndexOf("RUN OK") && File.ReadAllText(result.LogPath).Contains("RUN OK"), "Build/run ordering and persistent logs");
    runner.Start("failure", Command("[Console]::Error.WriteLine('BUILD FAILED'); exit 7"), Command("Write-Output 'SHOULD NOT RUN'"), root);
    result = await Wait(runner, "failure", Finished);
    Check(result.State == "failed" && result.ExitCode == 7 && !result.Log.Contains("SHOULD NOT RUN") && result.Log.Contains("BUILD FAILED"), "Failed build must block run");
    var childScript = "$child = Start-Process -FilePath '" + shell.Replace("'", "''") + "' -ArgumentList @('-NoProfile','-Command','Start-Sleep 60') -PassThru; Write-Output ('CHILD:' + $child.Id); Start-Sleep 60";
    runner.Start("stop", Command(childScript), Command("Write-Output 'SHOULD NOT RUN'"), root);
    Check(!runner.Start("stop", null, Command("exit 0"), root), "Duplicate launch allowed");
    result = await Wait(runner, "stop", job => job.Log.Contains("CHILD:"));
    var child = int.Parse(result.Log.Split('\n').Single(line => line.StartsWith("CHILD:")).Trim()[6..]);
    runner.Stop("stop"); result = await Wait(runner, "stop", Finished);
    Check(result.State == "stopped" && !Alive(child) && !result.Log.Contains("SHOULD NOT RUN"), "Stop child tree and suppress run");
    runner.Start("detached", null, Command(childScript.Replace("; Start-Sleep 60", "; exit 0")), root);
    result = await Wait(runner, "detached", job => job.Log.Contains("CHILD:"));
    child = int.Parse(result.Log.Split('\n').Single(line => line.StartsWith("CHILD:")).Trim()[6..]);
    await Task.Delay(400);
    Check(runner.Snapshot().Single(job => job.Key == "detached").State == "running" && Alive(child), "Child lifetime lost after shell exit");
    runner.Stop("detached"); await Wait(runner, "detached", Finished);
    Check(!Alive(child), "Detached child survived Stop");
    Console.WriteLine("PASS: prepare/verify/build/run ordering, failed repair/recheck gates, Stop during checks/repair/build, logs, duplicate prevention, child processes after shell exit");
}
finally { runner.Dispose(); }
