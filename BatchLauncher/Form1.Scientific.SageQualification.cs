using System.Diagnostics;
using System.Text;
using System.Text.Json;

namespace BatchLauncher;

public partial class Form1
{
    private async Task ScientificExecuteSageQualificationAsync(ScientificJob job)
    {
        var source = ScientificSourceRoot;
        var suite = Path.Combine(source, "tools", "scientific-sage-qualify.py");
        var adapter = Path.Combine(source, "tools", "scientific-sage-wsl.py");
        var worker = Path.Combine(source, "tools", "scientific-sage-worker.py");
        var schema = Path.Combine(source, "schemas", "scientific-sage-exact.v1.json");
        if (!File.Exists(suite) || !File.Exists(adapter) || !File.Exists(worker) || !File.Exists(schema))
            throw new FileNotFoundException("The Sage qualification worker or schema is missing from this installation.");
        var evidence = await Task.Run(() => ScientificSageCurrentEvidence(90000), job.Cancellation.Token);
        if (evidence == null || job.FingerprintComponents == null)
            throw new InvalidOperationException("Sage WSL environment fingerprint is unavailable. Check Ubuntu and retry.");
        ScientificRunFingerprint.RecordWslEvidence(job.FingerprintComponents, job.ExecutedFiles, evidence);
        var python = ScientificExecutable("python.exe");
        foreach (var path in new[] { python, suite, adapter, worker, schema })
            job.ExecutedFiles.Add(ScientificRunFingerprint.ExecutedFile(path, path == python ? "executable" : "argument"));
        var distro = ScientificSageDistro();
        job.Stage = "sage-exact-suite";
        var start = new ProcessStartInfo(python)
        {
            WorkingDirectory = source, UseShellExecute = false, CreateNoWindow = true,
            RedirectStandardOutput = true, RedirectStandardError = true,
            StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8
        };
        foreach (var argument in new[] { suite, "--output-root", job.Directory, "--distro", distro })
            start.ArgumentList.Add(argument);
        start.Environment.Remove("PYTHONPATH");
        start.Environment["PYTHONNOUSERSITE"] = "1";
        ScientificLog(job, "$ Sage exact qualification / Ubuntu WSL\n");
        using var process = new Process { StartInfo = start };
        using var owner = new OwnedProcessJob();
        using var cancellation = CancellationTokenSource.CreateLinkedTokenSource(job.Cancellation.Token, _scientificLifetime.Token);
        cancellation.CancelAfter(TimeSpan.FromSeconds(600));
        if (!process.Start()) throw new InvalidOperationException("Could not start the Sage qualification suite.");
        owner.Add(process);
        async Task Drain(StreamReader reader)
        {
            var buffer = new char[2048]; int count;
            while ((count = await reader.ReadAsync(buffer.AsMemory())) > 0)
                ScientificLog(job, new string(buffer, 0, count));
        }
        var stdout = Drain(process.StandardOutput);
        var stderr = Drain(process.StandardError);
        try { await process.WaitForExitAsync(cancellation.Token); }
        catch (OperationCanceledException)
        {
            owner.Stop(); await process.WaitForExitAsync(); await Task.WhenAll(stdout, stderr);
            if (job.Cancellation.IsCancellationRequested || _scientificLifetime.IsCancellationRequested) throw;
            throw new TimeoutException("Sage exact qualification exceeded 600 seconds.");
        }
        await Task.WhenAll(stdout, stderr);
        job.ExitCode = process.ExitCode;
        job.Steps.Add(new { stage = job.Stage, executable = python, arguments = new[] { suite, "--output-root", job.Directory, "--distro", distro }, exitCode = process.ExitCode });
        if (process.ExitCode != 0)
            throw new InvalidOperationException("Sage exact qualification failed. See the case log and saved results.");
        var resultPath = Path.Combine(job.Directory, "results.json");
        if (!File.Exists(resultPath) || new FileInfo(resultPath).Length > 1048576)
            throw new InvalidDataException("Sage qualification result is missing or too large.");
        using var document = JsonDocument.Parse(File.ReadAllText(resultPath));
        var result = document.RootElement;
        if (result.GetProperty("state").GetString() != "succeeded"
            || result.GetProperty("sageExactEvidence").GetProperty("verdict").GetString() != "passed")
            throw new InvalidDataException("Sage qualification did not save passed evidence.");
    }
}
