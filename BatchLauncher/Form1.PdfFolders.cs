namespace BatchLauncher;

public partial class Form1
{
    private sealed record FolderPdfTarget(string ProjectId, string RepositoryId, string FilePath);

    private FolderPdfTarget? FindFolderPdfTarget(string filePath)
    {
        if (!Path.IsPathFullyQualified(filePath) || !filePath.EndsWith(".pdf", StringComparison.OrdinalIgnoreCase)) return null;
        var fullPath = Path.GetFullPath(filePath);
        FolderPdfTarget? target = null;
        var longestRoot = 0;
        foreach (var project in _workspace.Projects ?? new())
        foreach (var repo in project.Repositories ?? new())
        {
            try
            {
                var root = ExpandProjectValue(project, repo.Path);
                if (!Path.IsPathFullyQualified(root)) continue;
                root = Path.GetFullPath(root);
                var prefix = Path.TrimEndingDirectorySeparator(root) + Path.DirectorySeparatorChar;
                if (prefix.Length <= longestRoot || !fullPath.StartsWith(prefix, StringComparison.OrdinalIgnoreCase)) continue;
                var relative = Path.GetRelativePath(root, fullPath).Replace('\\', '/');
                if (!PdfFile.IsRelativePdf(relative)) continue;
                target = new(project.Id, repo.Id, relative);
                longestRoot = prefix.Length;
            }
            catch (ArgumentException) { }
            catch (NotSupportedException) { }
        }
        // Opening still validates the real file and rejects links/junctions in PdfFile.Resolve.
        return target;
    }
}
