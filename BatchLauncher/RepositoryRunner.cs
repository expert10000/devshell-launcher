using System.Diagnostics;
using System.Text;

namespace BatchLauncher;

public sealed record RepositoryCommand(string Shell, string Script, string Cwd);
public sealed record RepositoryJobStatus(string Key, string State, string BuildState, int? ExitCode, string Log, string LogPath);

public sealed class RepositoryRunner : IDisposable
{
    private sealed class Job
    {
        public readonly object Sync = new();
        public readonly CancellationTokenSource Cancellation = new();
        public readonly StringBuilder Log = new();
        public string State = "queued", BuildState = "not-run", LogPath = "";
        public int? ExitCode;
        public volatile bool Active = true;
    }
    private readonly Dictionary<string, Job> _jobs = new();
    private readonly object _sync = new();
    private bool _disposed;
    public bool Start(string key, RepositoryCommand? build, RepositoryCommand? run, string logDirectory)
    {
        Job job;
        lock (_sync)
        {
            if (_disposed) throw new ObjectDisposedException(nameof(RepositoryRunner));
            if (_jobs.TryGetValue(key, out var previous) && previous.Active) return false;
            Directory.CreateDirectory(logDirectory);
            job = new Job { LogPath = Path.Combine(logDirectory, $"repo-{DateTime.Now:yyyyMMdd-HHmmss}-{Guid.NewGuid():N}.log") };
            if (build == null && previous != null) job.BuildState = previous.BuildState;
            _jobs[key] = job;
        }
        _ = Task.Run(() => Execute(job, build, run));
        return true;
    }
    public List<RepositoryJobStatus> Snapshot()
    {
        lock (_sync) return _jobs.Select(pair =>
        {
            lock (pair.Value.Sync) return new RepositoryJobStatus(pair.Key, pair.Value.State, pair.Value.BuildState, pair.Value.ExitCode, pair.Value.Log.ToString(), pair.Value.LogPath);
        }).ToList();
    }
    public void Stop(string key)
    {
        lock (_sync) if (_jobs.TryGetValue(key, out var job) && job.Active) job.Cancellation.Cancel();
    }
    private static async Task Execute(Job job, RepositoryCommand? build, RepositoryCommand? run)
    {
        try
        {
            using var log = new StreamWriter(job.LogPath, false, new UTF8Encoding(false)) { AutoFlush = true };
            void Append(string line)
            {
                lock (job.Sync)
                {
                    log.WriteLine(line);
                    job.Log.AppendLine(line);
                    if (job.Log.Length > 24000) job.Log.Remove(0, job.Log.Length - 24000);
                }
            }
            foreach (var (phase, command) in new[] { ("building", build), ("running", run) })
            {
                if (command == null) continue;
                job.Cancellation.Token.ThrowIfCancellationRequested();
                lock (job.Sync) { job.State = phase; if (phase == "building") job.BuildState = "building"; }
                Append($"[{DateTime.Now:T}] {phase} — {command.Cwd}");
                var start = new ProcessStartInfo(command.Shell) { WorkingDirectory = command.Cwd, UseShellExecute = false, CreateNoWindow = true,
                    RedirectStandardOutput = true, RedirectStandardError = true, RedirectStandardInput = true };
                foreach (var arg in new[] { "-NoLogo", "-NoProfile", "-NonInteractive", "-OutputFormat", "Text", "-EncodedCommand", Convert.ToBase64String(Encoding.Unicode.GetBytes("[Console]::ReadLine() | Out-Null\n" + command.Script)) }) start.ArgumentList.Add(arg);
                using var owned = new OwnedProcessJob();
                using var process = Process.Start(start) ?? throw new InvalidOperationException("Could not launch repository action.");
                try { owned.Add(process); } catch { if (!process.HasExited) process.Kill(true); throw; }
                await process.StandardInput.WriteLineAsync("start");
                process.StandardInput.Close();
                using var registration = job.Cancellation.Token.Register(owned.Stop);
                async Task Read(StreamReader reader) { while (await reader.ReadLineAsync() is { } line) Append(line); }
                var output = Read(process.StandardOutput);
                var error = Read(process.StandardError);
                await process.WaitForExitAsync();
                if (process.ExitCode != 0) owned.Stop();
                // Descendants may outlive the shell; keep Stop available until the whole job exits.
                while (owned.HasProcesses && !job.Cancellation.IsCancellationRequested) await Task.Delay(150);
                await Task.WhenAll(output, error);
                job.Cancellation.Token.ThrowIfCancellationRequested();
                lock (job.Sync)
                {
                    job.ExitCode = process.ExitCode;
                    if (phase == "building") job.BuildState = process.ExitCode == 0 ? "succeeded" : "failed";
                }
                Append($"[{DateTime.Now:T}] {phase} finished, exit code {process.ExitCode}");
                if (process.ExitCode != 0) { lock (job.Sync) job.State = "failed"; return; }
            }
            lock (job.Sync) job.State = "succeeded";
        }
        catch (OperationCanceledException) { lock (job.Sync) { job.State = "stopped"; if (job.BuildState == "building") job.BuildState = "stopped"; } }
        catch (Exception error) { lock (job.Sync) { job.State = "failed"; if (job.BuildState == "building") job.BuildState = "failed"; job.Log.AppendLine(error.Message); } }
        finally { lock (job.Sync) job.Active = false; }
    }
    public void Dispose()
    {
        lock (_sync) { _disposed = true; foreach (var job in _jobs.Values) if (job.Active) job.Cancellation.Cancel(); }
    }
}
