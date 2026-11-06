using System.Diagnostics;
using System.Text.Json;

namespace BatchLauncher;

public partial class Form1
{
    private string ScientificRuntimeRoot()
    {
        var workspaceRoot = _workspace.Globals?.WorkspaceRoot;
        if (!string.IsNullOrWhiteSpace(workspaceRoot) && Directory.Exists(workspaceRoot))
            return Path.Combine(Path.GetFullPath(workspaceRoot), ".conda");

        var projectRoot = _workspace.Projects?.FirstOrDefault(project =>
            project.Name.Equals("GitHub Repos", StringComparison.OrdinalIgnoreCase)
            && !string.IsNullOrWhiteSpace(project.Root) && Directory.Exists(project.Root))?.Root;
        if (projectRoot != null) return Path.Combine(Path.GetFullPath(projectRoot), ".conda");

        var reportPath = ScientificReportPath();
        if (File.Exists(reportPath))
        {
            using var report = JsonDocument.Parse(File.ReadAllText(reportPath));
            if (report.RootElement.TryGetProperty("runtimeRoot", out var value)
                && value.GetString() is { } runtimeRoot && Directory.Exists(runtimeRoot))
                return Path.GetFullPath(runtimeRoot);
        }
        throw new InvalidOperationException("Choose an existing workspace root in Configuration before installing scientific runtimes.");
    }

    private static string ScientificCondaExecutable(string runtimeRoot)
    {
        var workspaceRoot = Path.GetDirectoryName(runtimeRoot)!;
        var home = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
        var candidates = new List<string?>
        {
            Path.Combine(workspaceRoot, ".tools", "miniforge3", "Scripts", "conda.exe"),
            Path.Combine(workspaceRoot, ".tools", "miniconda3", "Scripts", "conda.exe"),
            Environment.GetEnvironmentVariable("CONDA_EXE"),
            Path.Combine(home, "miniforge3", "Scripts", "conda.exe"),
            Path.Combine(home, "miniconda3", "Scripts", "conda.exe")
        };
        candidates.AddRange((Environment.GetEnvironmentVariable("PATH") ?? "")
            .Split(Path.PathSeparator, StringSplitOptions.RemoveEmptyEntries)
            .Select(folder => Path.Combine(folder.Trim('"'), "conda.exe")));
        return candidates.FirstOrDefault(path => !string.IsNullOrWhiteSpace(path) && File.Exists(path))
            ?? throw new FileNotFoundException("Conda was not found. Install Miniforge under the workspace .tools folder or add conda.exe to PATH, then retry.");
    }

    private object ScientificInstallStart(string profileId, string runtimeId)
    {
        ScientificProviderRegistry.RequireAction(runtimeId, "install-runtime");
        if (profileId != _activeWorkspaceProfileId)
            throw new InvalidOperationException("The workspace profile changed. Select the runtime again.");
        var runtimeRoot = ScientificRuntimeRoot();
        var conda = ScientificCondaExecutable(runtimeRoot);
        var script = Path.Combine(ScientificSourceRoot, "tools", "Install-ScientificRuntimes.ps1");
        if (!File.Exists(script)) throw new FileNotFoundException("Scientific installer is missing from this build.", script);
        var shell = ScientificExecutable("pwsh.exe");
        if (!_scientificGate.Wait(0)) throw new InvalidOperationException("Another Scientific job is running; stop or wait for it.");
        try
        {
            var directory = Path.Combine(ScientificDataRoot, "runs", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(directory);
            var job = new ScientificJob { ProfileId = profileId, RuntimeId = runtimeId,
                RecipeId = "setup.install", Directory = directory, Stage = "install" };
            ScientificWriteRequest(job, JsonSerializer.SerializeToElement(new { workspaceRoot = Path.GetDirectoryName(runtimeRoot), kind = "gmsh" }), timeoutSeconds: 1800);
            _scientificJobs[profileId + ":" + runtimeId] = job;
            _ = ScientificInstallRunAsync(job, runtimeRoot, conda, script, shell);
            return ScientificJobSnapshot(job);
        }
        catch { _scientificGate.Release(); throw; }
    }

    private async Task ScientificInstallRunAsync(ScientificJob job, string runtimeRoot,
        string conda, string script, string shell)
    {
        var timer = Stopwatch.StartNew();
        try
        {
            var arguments = new[] { "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script,
                "-WorkspaceRoot", Path.GetDirectoryName(runtimeRoot)!, "-CondaExecutable", conda,
                "-Kind", "gmsh", "-PublishToLauncher" };
            await ScientificProcessAsync(job, runtimeRoot, shell, arguments, job.Directory, 1800);
            job.State = "succeeded";
            job.Stage = "completed";
        }
        catch (OperationCanceledException) { job.State = "cancelled"; job.Stage = "stopped"; job.Error = "Scientific installation was stopped."; }
        catch (TimeoutException error) { job.State = "timed-out"; job.Error = error.Message; }
        catch (Exception error) { job.State = "failed"; job.Error = error.Message; }
        finally
        {
            job.DurationMs = timer.ElapsedMilliseconds;
            try { ScientificFinish(job); ScientificLog(job, $"\n[{job.State}] {job.DurationMs} ms {job.Error}\n"); }
            catch (Exception error) { Debug.WriteLine($"Scientific install finalization failed: {error}"); }
            finally { ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) }); _scientificGate.Release(); }
        }
    }
}
