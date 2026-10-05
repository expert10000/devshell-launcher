using System.Diagnostics;
using System.Text;
using System.Net.Http;
using System.Net.Sockets;
using System.Text.Json;

namespace BatchLauncher;

public sealed record RepositoryCommand(string Shell, string Script, string Cwd);
public sealed record RepositoryJobStatus(string Key, string State, string BuildState, int? ExitCode, string Log, string LogPath, string Action, string BrowserState = "not-requested", string? BrowserUrl = null, string? LastBuildFinishedAt = null, string? LastBuildState = null, int? LastBuildExitCode = null);
public sealed record RepositoryBrowserLaunch(string Url, IReadOnlyList<string> ReadyUrls, int TimeoutSeconds = 120);

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
        public string Action = "run";
        public string BrowserState = "not-requested";
        public string? BrowserUrl;
        public string? LastBuildFinishedAt, LastBuildState;
        public int? LastBuildExitCode;
        public readonly TaskCompletionSource<RepositoryJobStatus> Completion = new(TaskCreationOptions.RunContinuationsAsynchronously);
    }
    private readonly Dictionary<string, Job> _jobs = new();
    private readonly object _sync = new();
    private bool _disposed;
    public event Action<string, string>? BrowserReady;
    public bool Start(string key, RepositoryCommand? build, RepositoryCommand? run, string logDirectory, string? action = null, RepositoryBrowserLaunch? browser = null)
    {
        if (browser != null)
        {
            if (run == null) throw new ArgumentException("A browser launch requires a run command.");
            foreach (var url in browser.ReadyUrls.Append(browser.Url)) ValidateWebUrl(url);
            if (browser.TimeoutSeconds is < 1 or > 900) throw new ArgumentException("Browser readiness timeout must be between 1 and 900 seconds.");
            browser = browser with { ReadyUrls = browser.ReadyUrls.Append(browser.Url).Distinct().ToArray() };
        }
        Job job;
        lock (_sync)
        {
            if (_disposed) throw new ObjectDisposedException(nameof(RepositoryRunner));
            if (_jobs.TryGetValue(key, out var previous) && previous.Active) return false;
            Directory.CreateDirectory(logDirectory);
            job = new Job { Action = action ?? (build != null ? "build" : "run"), LogPath = Path.Combine(logDirectory, $"repo-{DateTime.Now:yyyyMMdd-HHmmss}-{Guid.NewGuid():N}.log") };
            if (previous != null)
            {
                lock (previous.Sync)
                {
                    job.LastBuildFinishedAt = previous.LastBuildFinishedAt;
                    job.LastBuildState = previous.LastBuildState;
                    job.LastBuildExitCode = previous.LastBuildExitCode;
                }
            }
            if (browser != null) { job.BrowserState = "queued"; job.BrowserUrl = browser.Url; }
            if (build == null && previous != null && (action == null || action is "run" or "fetch")) job.BuildState = previous.BuildState;
            _jobs[key] = job;
        }
        _ = Task.Run(async () =>
        {
            await Execute(key, job, build, run, browser);
            lock (job.Sync) job.Completion.TrySetResult(Status(key, job));
        });
        return true;
    }
    public List<RepositoryJobStatus> Snapshot()
    {
        lock (_sync) return _jobs.Select(pair =>
        {
            lock (pair.Value.Sync) return Status(pair.Key, pair.Value);
        }).ToList();
    }
    private static RepositoryJobStatus Status(string key, Job job) => new(key, job.State, job.BuildState, job.ExitCode, job.Log.ToString(), job.LogPath, job.Action, job.BrowserState, job.BrowserUrl, job.LastBuildFinishedAt, job.LastBuildState, job.LastBuildExitCode);
    private static void FinishBuild(Job job, string state, int? exitCode)
    {
        job.BuildState = state;
        job.LastBuildFinishedAt = DateTimeOffset.UtcNow.ToString("O");
        job.LastBuildState = state;
        job.LastBuildExitCode = exitCode;
    }
    public Task<RepositoryJobStatus> Completion(string key)
    {
        lock (_sync) return _jobs[key].Completion.Task;
    }
    public void Stop(string key)
    {
        lock (_sync) if (_jobs.TryGetValue(key, out var job) && job.Active)
        {
            lock (job.Sync) if (job.BrowserState != "not-requested") job.BrowserState = "stopped";
            job.Cancellation.Cancel();
        }
    }
    private async Task Execute(string key, Job job, RepositoryCommand? build, RepositoryCommand? run, RepositoryBrowserLaunch? browser)
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
            if (browser != null) await EnsurePortsAvailable(browser, job.Cancellation.Token);
            foreach (var (phase, command) in new[] { ("building", build), ("running", run) })
            {
                if (command == null) continue;
                job.Cancellation.Token.ThrowIfCancellationRequested();
                lock (job.Sync) { job.State = phase; if (phase == "building") job.BuildState = "building"; }
                Append($"[{DateTime.Now:T}] {job.Action}: {phase} — {command.Cwd}");
                var start = new ProcessStartInfo(command.Shell) { WorkingDirectory = command.Cwd, UseShellExecute = false, CreateNoWindow = true,
                    RedirectStandardOutput = true, RedirectStandardError = true, RedirectStandardInput = true,
                    StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8, StandardInputEncoding = Encoding.UTF8 };
                // Match native tools, PowerShell pipelines, and the redirected readers to the UTF-8 log file.
                const string outputPreamble = "$global:OutputEncoding = [Console]::InputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)\n[Console]::ReadLine() | Out-Null\n";
                foreach (var arg in new[] { "-NoLogo", "-NoProfile", "-NonInteractive", "-OutputFormat", "Text", "-EncodedCommand", Convert.ToBase64String(Encoding.Unicode.GetBytes(outputPreamble + command.Script)) }) start.ArgumentList.Add(arg);
                using var owned = new OwnedProcessJob();
                using var process = Process.Start(start) ?? throw new InvalidOperationException("Could not launch repository action.");
                try { owned.Add(process); } catch { if (!process.HasExited) process.Kill(true); throw; }
                await process.StandardInput.WriteLineAsync("start");
                process.StandardInput.Close();
                using var registration = job.Cancellation.Token.Register(owned.Stop);
                async Task Read(StreamReader reader) { while (await reader.ReadLineAsync() is { } line) Append(line); }
                var output = Read(process.StandardOutput);
                var error = Read(process.StandardError);
                using var readinessCancellation = CancellationTokenSource.CreateLinkedTokenSource(job.Cancellation.Token);
                var readiness = phase == "running" && browser != null
                    ? MonitorBrowser(key, job, browser, owned, Append, readinessCancellation.Token) : Task.CompletedTask;
                try
                {
                    await process.WaitForExitAsync();
                    if (process.ExitCode != 0) owned.Stop();
                    // Descendants may outlive the shell; keep Stop available until the whole job exits.
                    while (owned.HasProcesses && !job.Cancellation.IsCancellationRequested) await Task.Delay(150);
                    await Task.WhenAll(output, error);
                }
                finally { readinessCancellation.Cancel(); await readiness; }
                job.Cancellation.Token.ThrowIfCancellationRequested();
                lock (job.Sync)
                {
                    job.ExitCode = process.ExitCode;
                    if (phase == "building") FinishBuild(job, process.ExitCode == 0 ? "succeeded" : "failed", process.ExitCode);
                }
                Append($"[{DateTime.Now:T}] {phase} finished, exit code {process.ExitCode}");
                if (process.ExitCode != 0) { lock (job.Sync) job.State = "failed"; return; }
                if (phase == "running" && browser != null && job.BrowserState != "ready")
                {
                    Append("[browser] The app exited before its URLs became ready. Browser was not opened.");
                    lock (job.Sync) { job.State = "failed"; job.ExitCode = 1; }
                    return;
                }
            }
            lock (job.Sync) job.State = "succeeded";
        }
        catch (OperationCanceledException) { lock (job.Sync) { job.State = "stopped"; if (job.BuildState == "building") FinishBuild(job, "stopped", null); } }
        catch (Exception error) { lock (job.Sync) { job.State = "failed"; if (job.BuildState == "building") FinishBuild(job, "failed", null); job.Log.AppendLine(error.Message); } }
        finally
        {
            lock (job.Sync)
            {
                job.Active = false;
                if (job.BrowserState is "queued" or "waiting") job.BrowserState = job.State == "stopped" ? "stopped" : "failed";
            }
        }
    }
    private static Uri ValidateWebUrl(string url)
    {
        if (!Uri.TryCreate(url, UriKind.Absolute, out var uri) || uri.Scheme is not ("http" or "https") || !string.IsNullOrEmpty(uri.UserInfo))
            throw new ArgumentException("Browser launch URLs must use HTTP or HTTPS without embedded credentials.");
        return uri;
    }
    private static async Task EnsurePortsAvailable(RepositoryBrowserLaunch browser, CancellationToken token)
    {
        foreach (var uri in browser.ReadyUrls.Select(ValidateWebUrl).Where(uri => uri.IsLoopback).DistinctBy(uri => (uri.Host, uri.Port)))
        {
            using var client = new TcpClient();
            using var attempt = CancellationTokenSource.CreateLinkedTokenSource(token);
            attempt.CancelAfter(TimeSpan.FromSeconds(1));
            var occupied = false;
            try { await client.ConnectAsync(uri.Host, uri.Port, attempt.Token); occupied = true; }
            catch (SocketException) { }
            catch (OperationCanceledException) when (!token.IsCancellationRequested) { }
            token.ThrowIfCancellationRequested();
            if (occupied) throw new InvalidOperationException($"Port {uri.Port} on {uri.Host} is already in use. Stop the existing server before Build + Run + Open.");
        }
    }
    private async Task MonitorBrowser(string key, Job job, RepositoryBrowserLaunch browser, OwnedProcessJob owned, Action<string> append, CancellationToken token)
    {
        lock (job.Sync) job.BrowserState = "waiting";
        append($"[browser] Waiting up to {browser.TimeoutSeconds}s for: {string.Join(", ", browser.ReadyUrls)}");
        using var deadline = CancellationTokenSource.CreateLinkedTokenSource(token);
        deadline.CancelAfter(TimeSpan.FromSeconds(browser.TimeoutSeconds));
        using var handler = new HttpClientHandler { AllowAutoRedirect = false, UseProxy = false };
        using var client = new HttpClient(handler) { Timeout = TimeSpan.FromSeconds(3), MaxResponseContentBufferSize = 2 * 1024 * 1024 };
        try
        {
            while (true)
            {
                var ready = true;
                foreach (var url in browser.ReadyUrls)
                    if (!await IsReady(client, url, deadline.Token)) { ready = false; break; }
                if (ready)
                {
                    token.ThrowIfCancellationRequested();
                    lock (job.Sync)
                    {
                        if (job.Cancellation.IsCancellationRequested) return;
                        job.BrowserState = "ready";
                    }
                    append("[browser] Ready. Opening in DevShell: " + browser.Url);
                    BrowserReady?.Invoke(key, browser.Url);
                    return;
                }
                await Task.Delay(750, deadline.Token);
            }
        }
        catch (OperationCanceledException) when (token.IsCancellationRequested) { return; }
        catch (OperationCanceledException) { append("[browser] Startup timed out. Stopping the app; browser was not opened."); }
        catch (Exception error) { append("[browser] Startup failed: " + error.Message); }
        lock (job.Sync) job.BrowserState = "failed";
        owned.Stop();
    }
    private static async Task<bool> IsReady(HttpClient client, string url, CancellationToken token)
    {
        try
        {
            using var response = await client.GetAsync(url, token);
            if (!response.IsSuccessStatusCode) return false;
            if (response.Content.Headers.ContentType?.MediaType?.Contains("json", StringComparison.OrdinalIgnoreCase) == true)
            {
                using var json = JsonDocument.Parse(await response.Content.ReadAsStringAsync(token));
                if (json.RootElement.ValueKind == JsonValueKind.Object && json.RootElement.TryGetProperty("ok", out var ok) && ok.ValueKind == JsonValueKind.False) return false;
            }
            return true;
        }
        catch (HttpRequestException) { return false; }
        catch (JsonException) { return false; }
        catch (OperationCanceledException) when (!token.IsCancellationRequested) { return false; }
    }
    public void Dispose()
    {
        lock (_sync) { _disposed = true; foreach (var job in _jobs.Values) if (job.Active) job.Cancellation.Cancel(); }
    }
}
