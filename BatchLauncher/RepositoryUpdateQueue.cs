namespace BatchLauncher;

public sealed record RepositoryUpdateItem(string Key, string Name, Func<RepositoryCommand> Command);
public sealed record RepositoryUpdateResult(string Key, string Name, string State, string Detail);
public sealed record RepositoryUpdateStatus(string ProfileId, string State, int Completed, int Total, List<RepositoryUpdateResult> Results);

public sealed class RepositoryUpdateQueue(RepositoryRunner runner) : IDisposable
{
    private readonly object _sync = new();
    private readonly Dictionary<string, RepositoryUpdateStatus> _statuses = new();
    private CancellationTokenSource? _cancellation;
    private List<string> _keys = new();
    private bool _active, _disposed;
    public bool Active { get { lock (_sync) return _active; } }
    public List<RepositoryUpdateStatus> Snapshot() { lock (_sync) return _statuses.Values.ToList(); }
    public bool Owns(string key) { lock (_sync) return _active && _keys.Contains(key); }

    public void Start(string profileId, List<RepositoryUpdateItem> items, string logDirectory)
    {
        lock (_sync)
        {
            if (_disposed) throw new ObjectDisposedException(nameof(RepositoryUpdateQueue));
            if (_active) throw new InvalidOperationException("Update All is already running.");
            if (items.Count == 0) throw new InvalidOperationException("No repositories are configured.");
            if (runner.Snapshot().Any(job => items.Any(item => item.Key == job.Key) && job.State is "queued" or "building" or "running"))
                throw new InvalidOperationException("Stop or finish repository jobs before Update All.");
            _active = true;
            _keys = items.Select(item => item.Key).ToList();
            _cancellation?.Dispose();
            _cancellation = new();
            _statuses[profileId] = new(profileId, "running", 0, items.Count, items.Select(item => new RepositoryUpdateResult(item.Key, item.Name, "queued", "Waiting")).ToList());
            var cancellation = _cancellation.Token;
            _ = Task.Run(() => Execute(profileId, items, logDirectory, cancellation));
        }
    }
    private void Result(string profileId, int index, string state, string detail)
    {
        lock (_sync)
        {
            var status = _statuses[profileId];
            var results = status.Results.ToList();
            results[index] = results[index] with { State = state, Detail = detail };
            _statuses[profileId] = status with { Results = results, Completed = results.Count(result => result.State is not ("queued" or "running")) };
        }
    }
    private async Task Execute(string profileId, List<RepositoryUpdateItem> items, string logDirectory, CancellationToken cancellation)
    {
        try
        {
            for (var i = 0; i < items.Count; i++)
            {
                if (cancellation.IsCancellationRequested) { Result(profileId, i, "skipped", "Update All stopped before this repository started."); continue; }
                var item = items[i];
                Result(profileId, i, "running", "Cloning or pulling…");
                try
                {
                    var command = item.Command();
                    lock (_sync)
                    {
                        cancellation.ThrowIfCancellationRequested();
                        if (!runner.Start(item.Key, null, command, logDirectory, "update")) throw new InvalidOperationException("A repository job is already active.");
                    }
                    var job = await runner.Completion(item.Key);
                    var lines = job.Log.Split('\n', StringSplitOptions.RemoveEmptyEntries);
                    var failure = lines.LastOrDefault(line => line.Contains("[sync] FAILED:"))?.Trim();
                    var detail = job.State == "succeeded" ? "Updated successfully" : job.State == "stopped" ? "Stopped by user"
                        : failure ?? lines.LastOrDefault(line => !line.Contains("finished, exit code"))?.Trim() ?? job.State;
                    Result(profileId, i, job.State, detail);
                }
                catch (OperationCanceledException) { Result(profileId, i, "stopped", "Update All stopped."); }
                catch (Exception error) { Result(profileId, i, "failed", error.Message); }
            }
        }
        finally
        {
            lock (_sync)
            {
                var status = _statuses[profileId];
                _statuses[profileId] = status with { State = cancellation.IsCancellationRequested ? "stopped" : status.Results.Any(result => result.State != "succeeded") ? "completed-with-errors" : "succeeded" };
                _active = false;
            }
        }
    }
    public void Stop()
    {
        lock (_sync)
        {
            if (!_active) return;
            _cancellation!.Cancel();
            foreach (var key in _keys) runner.Stop(key);
        }
    }
    public void Dispose() { lock (_sync) { _disposed = true; Stop(); } }
}
