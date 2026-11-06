using System.Diagnostics;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace BatchLauncher;

public partial class Form1
{
    private object ScientificDriftDiagnosis(string profileId, string runtimeId, string jobId)
    {
        var (directory, result) = ScientificHistoryFind(profileId, jobId);
        if (result.GetProperty("runtimeId").GetString() != runtimeId)
            throw new InvalidOperationException("Run does not belong to the selected provider.");
        if (!result.TryGetProperty("runFingerprintSha256", out _))
            return new { schemaVersion = 1, runId = jobId, runtimeId, state = "unknown",
                findings = new[] { new { id = "fingerprint", state = "unknown", detail = "This historical run has no verified fingerprint.",
                    nextStep = "Run a fresh managed probe and recipe before requesting qualification." } } };
        var view = ScientificHistoryResult(profileId, jobId);
        var source = view.GetProperty("sourceDrift");
        var environment = view.GetProperty("environmentDrift");
        var findings = new List<object>();
        void Add(string id, string state, string detail, string nextStep) =>
            findings.Add(new { id, state, detail, nextStep });
        string[] Reasons(JsonElement drift) => drift.GetProperty("reasons").EnumerateArray()
            .Select(item => item.GetString() ?? "").Where(item => item.Length > 0).ToArray();
        foreach (var reason in Reasons(source))
        {
            var step = reason.StartsWith("Suite ", StringComparison.Ordinal) || reason.Contains("Suite revision", StringComparison.Ordinal)
                ? "Run the selective retest planner for the changed suite, then rerun affected managed qualification levels."
                : "Review the changed source or contract, then rerun the affected provider qualification chain.";
            Add("source", "stale", reason, step);
        }
        foreach (var reason in Reasons(environment))
        {
            var normalized = reason.ToLowerInvariant();
            if (normalized.Contains("pythonexecutable"))
                Add("interpreter", "stale", reason, "Inspect the dedicated runtime prefix and run its Python version/import probes before requalification.");
            else if (normalized.Contains("conda") || normalized.Contains("packag"))
                Add("packages", "stale", reason, "Compare exact Conda package records, regenerate the environment manifest, then rerun affected probes and worker suites.");
            else if (normalized.Contains("cmake") || normalized.Contains("ninja") || normalized.Contains("msvccompiler"))
                Add("compiler", "stale", reason, "Check the resolved compiler/CMake/Ninja binaries, rerun compile-link L4, then dependent worker levels.");
            else if (normalized.Contains("wsl"))
                Add("wsl", "stale", reason, "Check the selected WSL distribution and path mapping, then rerun Sage probes and exact-math tests.");
            else if (normalized.Contains("gpudriver"))
                Add("driver", "stale", reason, "Check the installed GPU driver and rerun GPU-specific probes before using GPU evidence.");
            else
                Add("environment", environment.GetProperty("state").GetString() ?? "unknown", reason,
                    "Inspect the recorded environment identity and rerun the provider probes before requalification.");
        }
        if (environment.TryGetProperty("unavailableComponents", out var missingEnvironment) && missingEnvironment.GetInt32() > 0)
            Add("missing-evidence", "unknown", "Some package, interpreter, toolchain or WSL identities could not be compared.",
                "Refresh the local runtime inventory and run a new managed probe; do not assume the historical environment still applies.");
        if (source.TryGetProperty("unavailableFiles", out var missingSource) && missingSource.GetInt32() > 0)
            Add("missing-source", "unknown", "Some saved or current source identities are unavailable.",
                "Restore or inspect the missing source files, then rerun the affected suite.");
        if (runtimeId.EndsWith("-conda", StringComparison.Ordinal))
        {
            try
            {
                var report = ScientificReport();
                var prefix = report.GetProperty("runtimes").EnumerateArray()
                    .FirstOrDefault(item => item.GetProperty("id").GetString() == runtimeId)
                    .GetProperty("environmentRoot").GetString();
                if (!string.IsNullOrWhiteSpace(prefix))
                {
                    var expected = Path.GetFullPath(Path.Combine(prefix, "python.exe"));
                    var interactive = (Environment.GetEnvironmentVariable("PATH") ?? "").Split(';', StringSplitOptions.RemoveEmptyEntries)
                        .Select(folder => Path.Combine(folder.Trim('"'), "python.exe")).FirstOrDefault(File.Exists);
                    if (interactive != null && !string.Equals(Path.GetFullPath(interactive), expected, StringComparison.OrdinalIgnoreCase))
                        Add("path", "advisory", "Interactive PATH resolves a different Python than the dedicated runtime prefix.",
                            "Use the managed provider action, which prepends its dedicated prefix; verify the selected interpreter with a version probe.");
                    else if (!File.Exists(expected))
                        Add("path", "unknown", "The dedicated runtime interpreter is unavailable.",
                            "Inspect the recorded environment root and reinstall or select the intended runtime before probing.");
                }
            }
            catch (Exception error) when (error is IOException or JsonException or InvalidOperationException or UnauthorizedAccessException) { }
        }
        if (runtimeId == "sage-wsl")
        {
            var distro = Environment.GetEnvironmentVariable("MATH3D_WSL_DISTRO") ?? "Ubuntu";
            try
            {
                using var process = new Process { StartInfo = new ProcessStartInfo("wsl.exe")
                {
                    UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true,
                    RedirectStandardError = true
                } };
                foreach (var argument in new[] { "-d", distro, "--exec", "wslpath", "-u", ScientificSourceRoot })
                    process.StartInfo.ArgumentList.Add(argument);
                if (!process.Start() || !process.WaitForExit(5000))
                {
                    if (!process.HasExited) process.Kill(entireProcessTree: true);
                    Add("wsl-mapping", "unknown", "WSL source path mapping did not complete.",
                        "Check the selected distro and run wslpath on the DevShell source directory before rerunning Sage.");
                }
                else if (process.ExitCode != 0 || !process.StandardOutput.ReadToEnd().Trim().StartsWith('/'))
                    Add("wsl-mapping", "unknown", "The selected WSL distro cannot map the DevShell source directory.",
                        "Check drive mounts and wslpath in that distro, then rerun the Sage probes.");
            }
            catch (Exception error) when (error is IOException or InvalidOperationException or System.ComponentModel.Win32Exception)
            {
                Add("wsl-mapping", "unknown", "WSL path mapping could not be checked.",
                    "Verify wsl.exe, the selected distro and its drive mounts before rerunning Sage.");
            }
        }
        var saved = JsonNode.Parse(File.ReadAllText(Path.Combine(directory, "fingerprint.json")))?["components"]?["environment"];
        if (saved?["gpuDriver"]?["state"]?.GetValue<string>() != "recorded")
            Add("driver", "not-recorded", "This run has no comparable GPU driver identity.",
                "Capture a new run on a GPU-capable provider before claiming driver stability or GPU qualification.");
        if (findings.Count == 0)
            Add("current", "current", "No source or environment mismatch was found in comparable evidence.",
                "Keep the saved run; requalification is only needed when its dependencies change.");
        return new { schemaVersion = 1, runId = jobId, runtimeId,
            state = source.GetProperty("state").GetString() == "stale" || environment.GetProperty("state").GetString() == "stale"
                ? "stale" : source.GetProperty("state").GetString() == "unknown" || environment.GetProperty("state").GetString() == "unknown"
                    ? "unknown" : "current",
            sourceState = source.GetProperty("state").GetString(), environmentState = environment.GetProperty("state").GetString(),
            findings };
    }
}
