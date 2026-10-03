namespace BatchLauncher;

internal static class PdfFile
{
    internal static string ResolveDirectory(string root, string relativePath)
    {
        if (!Path.IsPathFullyQualified(root) || string.IsNullOrWhiteSpace(relativePath) ||
            !WorkspaceTabsStore.IsRelativePath(relativePath) || relativePath.Split('/').Any(string.IsNullOrWhiteSpace))
            throw new ArgumentException("Configure a relative PDF directory inside the repository.");
        root = Path.GetFullPath(root);
        var path = Path.GetFullPath(Path.Combine(root, relativePath.Replace('/', Path.DirectorySeparatorChar)));
        var prefix = Path.TrimEndingDirectorySeparator(root) + Path.DirectorySeparatorChar;
        if (!path.StartsWith(prefix, StringComparison.OrdinalIgnoreCase)) throw new ArgumentException("PDF directories cannot leave the repository.");
        if (!Directory.Exists(root)) throw new DirectoryNotFoundException("Repository folder is missing.");
        var component = root;
        foreach (var part in relativePath.Split('/').Prepend(""))
        {
            if (part.Length > 0) component = Path.Combine(component, part);
            if (File.Exists(component)) throw new ArgumentException("PDF collection path must be a directory.");
            if (!Directory.Exists(component)) return path; // A new checkout may not have build output yet.
            if ((File.GetAttributes(component) & FileAttributes.ReparsePoint) != 0)
                throw new ArgumentException("PDF directories cannot traverse symlinks or junctions.");
        }
        return path;
    }

    internal static bool IsRelativePdf(string? path) => !string.IsNullOrWhiteSpace(path) &&
        WorkspaceTabsStore.IsRelativePath(path) && !path.Split('/').Any(string.IsNullOrWhiteSpace) &&
        path.EndsWith(".pdf", StringComparison.OrdinalIgnoreCase);

    internal static string Resolve(string root, string relativePath)
    {
        if (!Path.IsPathFullyQualified(root) || !IsRelativePdf(relativePath))
            throw new ArgumentException("Select a relative PDF path inside a configured repository.");
        root = Path.GetFullPath(root);
        var prefix = Path.TrimEndingDirectorySeparator(root) + Path.DirectorySeparatorChar;
        var path = Path.GetFullPath(Path.Combine(root, relativePath.Replace('/', Path.DirectorySeparatorChar)));
        if (!path.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
            throw new ArgumentException("PDF paths cannot leave the repository.");
        if (!Directory.Exists(root)) throw new DirectoryNotFoundException("Repository folder is missing.");
        // Do not follow junctions or symlinks into files outside the configured checkout.
        var component = root;
        foreach (var part in relativePath.Split('/').Prepend(""))
        {
            if (part.Length > 0) component = Path.Combine(component, part);
            if (!File.Exists(component) && !Directory.Exists(component))
                throw new FileNotFoundException("PDF is missing. Build the repository first, then Refresh.");
            if ((File.GetAttributes(component) & FileAttributes.ReparsePoint) != 0)
                throw new ArgumentException("PDF paths cannot traverse symlinks or junctions.");
        }
        using var file = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
        Span<byte> header = stackalloc byte[5];
        if (file.Read(header) != header.Length || !header.SequenceEqual("%PDF-"u8))
            throw new InvalidDataException("The selected output is not a PDF document.");
        return path;
    }
}
