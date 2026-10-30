using System.Diagnostics;

namespace BatchLauncher;

internal sealed record WorkspaceDeclaredArtifact(string Id, string Name, string Path, string Kind, string State, WorkspaceFileEntry? Entry);
internal sealed record WorkspaceArtifactOverview(List<WorkspaceFileEntry> Entries, string? OutputDirectory, int DirectoriesScanned, bool Truncated, string ScannedAt, List<string> Warnings, List<WorkspaceDeclaredArtifact> Declared);

internal static class WorkspaceArtifacts
{
    private const int MaxArtifacts = 500, MaxDirectories = 200, MaxPaths = 10000, MaxDepth = 8;
    private static readonly HashSet<string> ExcludedFolders = new(StringComparer.OrdinalIgnoreCase)
        { ".git", "node_modules", ".venv", ".venvs", "venv", ".cache", "__pycache__", "obj", ".vs", ".idea", ".devshell-logs" };
    private static readonly HashSet<string> DocumentExtensions = new(StringComparer.OrdinalIgnoreCase)
        { ".md", ".markdown", ".txt", ".log", ".json", ".ipynb", ".csv", ".tsv", ".yaml", ".yml", ".toml" };

    internal static WorkspaceArtifactOverview Scan(string root, WorkspaceRepository repo)
    {
        PdfFile.ResolveDirectory(root, "", allowRoot: true);
        var watch = Stopwatch.StartNew(); var pending = new Queue<(string Path, int Depth)>();
        var visited = new HashSet<string>(StringComparer.OrdinalIgnoreCase); var found = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var entries = new List<WorkspaceFileEntry>(); var warnings = new List<string>(); var declared = new List<WorkspaceDeclaredArtifact>();
        string? output = null; var truncated = false; var scanned = 0; var paths = 0;
        try { output = WorkspaceFiles.FindOutputDirectory(root, repo); }
        catch (DirectoryNotFoundException) { }
        if (output != null) pending.Enqueue((output, output.Split('/', StringSplitOptions.RemoveEmptyEntries).Length));
        foreach (var artifact in (repo.Artifacts ?? new()).Take(32))
        {
            var relative = artifact.Path.Replace('\\', '/');
            try
            {
                if (artifact.Kind == "folder")
                {
                    var directory = PdfFile.ResolveDirectory(root, relative);
                    var exists = Directory.Exists(directory);
                    declared.Add(new(artifact.Id, artifact.Name, relative, artifact.Kind, exists ? "available" : "missing", null));
                    if (exists) pending.Enqueue((relative, relative.Split('/').Length));
                }
                else if (artifact.Kind == "file")
                {
                    var entry = WorkspaceFiles.Locate(root, relative).Entry;
                    declared.Add(new(artifact.Id, artifact.Name, relative, artifact.Kind, "available", entry));
                    if (entry.Kind is "pdf" or "image" or "text" or "code" && found.Add(entry.Path)) entries.Add(entry);
                }
                else declared.Add(new(artifact.Id, artifact.Name, relative, artifact.Kind, "blocked", null));
            }
            catch (FileNotFoundException) { declared.Add(new(artifact.Id, artifact.Name, relative, artifact.Kind, "missing", null)); }
            catch (DirectoryNotFoundException) { declared.Add(new(artifact.Id, artifact.Name, relative, artifact.Kind, "missing", null)); }
            catch (Exception error) when (error is IOException or UnauthorizedAccessException or ArgumentException)
            {
                declared.Add(new(artifact.Id, artifact.Name, relative, artifact.Kind, "blocked", null));
                if (warnings.Count < 8) warnings.Add($"Could not inspect declared artifact {artifact.Name}: {error.Message}");
            }
        }
        foreach (var folder in new[] { "reports", "artifacts", "build", "dist", "bin", "" }) pending.Enqueue((folder, string.IsNullOrEmpty(folder) ? 0 : 1));
        while (pending.Count > 0)
        {
            if (scanned >= MaxDirectories || paths >= MaxPaths || entries.Count >= MaxArtifacts || watch.Elapsed > TimeSpan.FromSeconds(8)) { truncated = true; break; }
            var (relative, depth) = pending.Dequeue();
            if (!visited.Add(relative)) continue;
            WorkspaceFileListing listing;
            try
            {
                var directory = PdfFile.ResolveDirectory(root, relative, allowRoot: true);
                if (!Directory.Exists(directory)) continue;
                listing = WorkspaceFiles.List(root, relative);
            }
            catch (Exception error) when (error is IOException or UnauthorizedAccessException or ArgumentException)
            {
                if (warnings.Count < 8) warnings.Add($"Skipped {relative}: {error.Message}");
                continue;
            }
            scanned++; truncated |= listing.Truncated;
            foreach (var entry in listing.Entries)
            {
                if (++paths > MaxPaths || entries.Count >= MaxArtifacts) { truncated = true; break; }
                if (entry.Kind == "folder")
                {
                    if (ExcludedFolders.Contains(entry.Name)) continue;
                    if (depth < MaxDepth) pending.Enqueue((entry.Path, depth + 1)); else truncated = true;
                }
                else if ((entry.Kind is "pdf" or "image" || entry.Kind == "text" && DocumentExtensions.Contains(Path.GetExtension(entry.Path))) && found.Add(entry.Path)) entries.Add(entry);
            }
        }
        return new(entries.OrderByDescending(entry => entry.Modified).ThenBy(entry => entry.Path, StringComparer.OrdinalIgnoreCase).ToList(), output, scanned, truncated, DateTimeOffset.UtcNow.ToString("O"), warnings, declared);
    }
}
