using System.Diagnostics;

namespace BatchLauncher;

internal sealed record WorkspaceSearchRepository(string Id, string Name, string Root);
internal sealed record WorkspaceFileSearchHit(string RepositoryId, string RepositoryName, WorkspaceFileEntry Entry);
internal sealed record WorkspaceFileSearchResult(List<WorkspaceFileSearchHit> Entries, int DirectoriesScanned, bool Truncated, List<string> Warnings);

internal static class WorkspaceFileSearch
{
    private const int MaxMatches = 500, MaxDirectories = 500, MaxPaths = 30000, MaxDepth = 12;
    private static readonly HashSet<string> ExcludedFolders = new(StringComparer.OrdinalIgnoreCase)
        { ".git", "node_modules", ".venv", ".venvs", "venv", ".cache", "__pycache__", "obj", ".vs", ".idea", ".devshell-logs" };

    internal static WorkspaceFileSearchResult Search(List<WorkspaceSearchRepository> repositories, string query)
    {
        query = query.Trim().Replace('\\', '/');
        if (query.Length < 2 || query.Length > 160) throw new ArgumentException("Use a filename or relative path between 2 and 160 characters.");
        var entries = new List<WorkspaceFileSearchHit>(); var warnings = new List<string>();
        var pending = new Queue<(WorkspaceSearchRepository Repo, string Path, int Depth)>();
        // Shared BFS gives all repositories a root pass before descending.
        foreach (var repo in repositories) pending.Enqueue((repo, "", 0));
        var watch = Stopwatch.StartNew(); var directories = 0; var paths = 0; var truncated = false;
        while (pending.Count > 0)
        {
            if (entries.Count >= MaxMatches || directories >= MaxDirectories || paths >= MaxPaths || watch.Elapsed > TimeSpan.FromSeconds(8)) { truncated = true; break; }
            var (repo, relative, depth) = pending.Dequeue();
            directories++;
            try
            {
                var listing = WorkspaceFiles.List(repo.Root, relative);
                truncated |= listing.Truncated;
                foreach (var entry in listing.Entries)
                {
                    if (++paths > MaxPaths || entries.Count >= MaxMatches || watch.Elapsed > TimeSpan.FromSeconds(8)) { truncated = true; break; }
                    if (entry.Kind == "folder")
                    {
                        if (ExcludedFolders.Contains(entry.Name)) continue;
                        if (depth < MaxDepth && pending.Count < MaxDirectories) pending.Enqueue((repo, entry.Path, depth + 1)); else truncated = true;
                    }
                    else if (entry.Name.Contains(query, StringComparison.OrdinalIgnoreCase) || entry.Path.Contains(query, StringComparison.OrdinalIgnoreCase))
                        entries.Add(new(repo.Id, repo.Name, entry));
                }
            }
            catch (Exception error) when (error is IOException or UnauthorizedAccessException or ArgumentException)
            {
                if (warnings.Count < 8) warnings.Add($"Skipped {repo.Name}/{relative}: {error.Message}");
                truncated = true;
            }
        }
        return new(entries.OrderBy(hit => hit.RepositoryName, StringComparer.OrdinalIgnoreCase).ThenBy(hit => hit.Entry.Path, StringComparer.OrdinalIgnoreCase).ToList(), directories, truncated, warnings);
    }
}
