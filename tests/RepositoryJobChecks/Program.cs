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
    Console.WriteLine("PASS: successful build/run, failed-build gate, logs, duplicate prevention, Stop during build, child processes after shell exit");
}
finally { runner.Dispose(); }
