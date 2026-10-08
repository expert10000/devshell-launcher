using System.Text;

namespace BatchLauncher;

internal sealed record WorkspaceFileEntry(string Name, string Path, string Kind, bool Artifact, long? Size, string Modified);
internal sealed record WorkspaceFileListing(string Path, List<WorkspaceFileEntry> Entries, bool Truncated);
internal sealed record WorkspaceFilePreview(string Path, string Text, bool Truncated);
internal sealed record WorkspaceImagePreview(string Path, string MimeType, string DataUrl, long Size);
internal sealed record WorkspaceFileLocation(WorkspaceFileListing Listing, WorkspaceFileEntry Entry);
internal sealed record WorkspaceDiagnosticLocation(string Path, int Line, int Column);

internal static class WorkspaceFiles
{
    internal const int MaxEntries = 1000, MaxPreviewChars = 128 * 1024;
    internal const int MaxImageBytes = 8 * 1024 * 1024;
    private static readonly HashSet<string> TextExtensions = new(StringComparer.OrdinalIgnoreCase)
        { ".md", ".markdown", ".txt", ".log", ".json", ".ipynb", ".csv", ".tsv", ".yaml", ".yml", ".toml", ".tex", ".svg" };
    private static readonly HashSet<string> CodeExtensions = new(StringComparer.OrdinalIgnoreCase)
        { ".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".cs", ".fs", ".vb", ".c", ".cpp", ".h", ".hpp", ".java", ".go", ".rs", ".sh", ".ps1", ".psm1", ".bat", ".cmd", ".sql", ".html", ".htm", ".css", ".scss", ".less", ".xml", ".xaml", ".ini", ".cfg", ".conf", ".properties", ".csproj", ".fsproj", ".vbproj", ".props", ".targets", ".gradle", ".kt", ".kts" };
    private static readonly HashSet<string> CodeNames = new(StringComparer.OrdinalIgnoreCase)
        { "Dockerfile", "Makefile", ".gitignore", ".gitattributes", ".editorconfig" };
    private static readonly Dictionary<string, string> ImageExtensions = new(StringComparer.OrdinalIgnoreCase)
        { [".png"] = "image/png", [".jpg"] = "image/jpeg", [".jpeg"] = "image/jpeg", [".gif"] = "image/gif", [".webp"] = "image/webp" };
    private static readonly HashSet<string> ArtifactExtensions = new(StringComparer.OrdinalIgnoreCase)
        { ".pdf", ".log", ".json", ".ipynb", ".csv", ".tsv", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".zip", ".exe", ".msi" };

    internal static WorkspaceFileListing List(string root, string relativePath)
    {
        root = Path.GetFullPath(root);
        var directory = PdfFile.ResolveDirectory(root, relativePath, allowRoot: true);
        if (!Directory.Exists(directory)) throw new DirectoryNotFoundException("Folder is missing. Refresh or return to the repository root.");
        var paths = Directory.EnumerateFileSystemEntries(directory)
            .Where(path => !Path.GetFileName(path).Equals(".git", StringComparison.OrdinalIgnoreCase) &&
                (File.GetAttributes(path) & FileAttributes.ReparsePoint) == 0).Take(MaxEntries + 1).ToList();
        var entries = new List<WorkspaceFileEntry>();
        foreach (var path in paths.Take(MaxEntries))
        {
            var folder = Directory.Exists(path);
            FileSystemInfo info = folder ? new DirectoryInfo(path) : new FileInfo(path);
            var extension = Path.GetExtension(path);
            var kind = folder ? "folder" : KindOfFile(path);
            entries.Add(new(info.Name, Path.GetRelativePath(root, path).Replace('\\', '/'), kind,
                !folder && ArtifactExtensions.Contains(extension), folder ? null : ((FileInfo)info).Length, info.LastWriteTimeUtc.ToString("O")));
        }
        return new(relativePath, entries.OrderBy(entry => entry.Kind == "folder" ? 0 : 1)
            .ThenBy(entry => entry.Name, StringComparer.OrdinalIgnoreCase).ToList(), paths.Count > MaxEntries);
    }

    internal static WorkspaceFileLocation Locate(string root, string relativePath)
    {
        var path = ResolvePreviewPath(root, relativePath);
        var parent = (Path.GetDirectoryName(relativePath) ?? "").Replace('\\', '/');
        var listing = List(root, parent);
        var info = new FileInfo(path); var extension = info.Extension;
        var kind = KindOfFile(path);
        var entry = new WorkspaceFileEntry(info.Name, relativePath, kind, ArtifactExtensions.Contains(extension), info.Length, info.LastWriteTimeUtc.ToString("O"));
        // Keep the selected search result visible even in a capped folder listing.
        if (!listing.Entries.Any(item => item.Path == relativePath))
            listing = listing with { Entries = listing.Entries.Prepend(entry).Take(MaxEntries).ToList(), Truncated = true };
        return new(listing, entry);
    }

    internal static WorkspaceFilePreview Preview(string root, string relativePath)
    {
        if (string.IsNullOrWhiteSpace(relativePath) || !WorkspaceTabsStore.IsRelativePath(relativePath) ||
            relativePath.Split('/').Any(string.IsNullOrWhiteSpace) || !(TextExtensions.Contains(Path.GetExtension(relativePath)) || IsCode(relativePath)))
            throw new ArgumentException("Only supported source files, text documents, and reports can be previewed.");
        var path = ResolvePreviewPath(root, relativePath);
        using var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
        using var reader = new StreamReader(stream, Encoding.UTF8, detectEncodingFromByteOrderMarks: true);
        var buffer = new char[MaxPreviewChars + 1];
        var length = reader.ReadBlock(buffer, 0, buffer.Length);
        return new(relativePath, new string(buffer, 0, Math.Min(length, MaxPreviewChars)), length > MaxPreviewChars);
    }

    internal static WorkspaceDiagnosticLocation ResolveDiagnostic(string root, string file, int line, int column)
    {
        file = file.Trim().Trim('"');
        if (file.Length == 0 || file.Length > 2048 || file.Contains('\0')) throw new ArgumentException("The diagnostic does not contain a supported source path.");
        root = Path.GetFullPath(root);
        string relative;
        if (Path.IsPathFullyQualified(file))
        {
            var absolute = Path.GetFullPath(file);
            var prefix = Path.TrimEndingDirectorySeparator(root) + Path.DirectorySeparatorChar;
            if (!absolute.StartsWith(prefix, StringComparison.OrdinalIgnoreCase)) throw new ArgumentException("This diagnostic points outside the build repository. Open external SDK/dependency files explicitly in your editor.");
            relative = Path.GetRelativePath(root, absolute).Replace('\\', '/');
        }
        else
        {
            relative = file.Replace('\\', '/');
            if (relative.StartsWith("./", StringComparison.Ordinal)) relative = relative[2..];
        }
        if (KindOfFile(relative) is not ("code" or "text")) throw new ArgumentException("This diagnostic file has no safe source preview.");
        ResolvePreviewPath(root, relative); // Enforces containment, existence, and no symlink traversal.
        return new(relative, Math.Clamp(line, 1, 1000000), Math.Clamp(column, 1, 1000000));
    }

    internal static WorkspaceImagePreview ImagePreview(string root, string relativePath)
    {
        if (!ImageExtensions.TryGetValue(Path.GetExtension(relativePath), out var mimeType))
            throw new ArgumentException("Image preview supports PNG, JPEG, GIF, and WebP only. SVG is displayed as text, never executed.");
        var path = ResolvePreviewPath(root, relativePath);
        using var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
        if (stream.Length > MaxImageBytes) throw new ArgumentException("Image exceeds the 8 MiB preview limit.");
        var bytes = new byte[(int)stream.Length];
        stream.ReadExactly(bytes);
        var valid = mimeType switch
        {
            "image/png" => bytes.AsSpan().StartsWith(new byte[] { 137, 80, 78, 71, 13, 10, 26, 10 }),
            "image/jpeg" => bytes.Length >= 4 && bytes[0] == 255 && bytes[1] == 216 && bytes[2] == 255,
            "image/gif" => bytes.Length >= 10 && (Encoding.ASCII.GetString(bytes, 0, 6) is "GIF87a" or "GIF89a"),
            "image/webp" => bytes.Length >= 12 && Encoding.ASCII.GetString(bytes, 0, 4) == "RIFF" && Encoding.ASCII.GetString(bytes, 8, 4) == "WEBP",
            _ => false
        };
        if (!valid) throw new ArgumentException("The file does not have the expected image format.");
        return new(relativePath, mimeType, $"data:{mimeType};base64,{Convert.ToBase64String(bytes)}", bytes.Length);
    }

    internal static string FindOutputDirectory(string root, WorkspaceRepository repo)
    {
        var configured = repo.OutputDirectory ?? repo.PdfDirectory;
        if (configured == null && !string.IsNullOrEmpty(repo.PdfPath)) configured = (Path.GetDirectoryName(repo.PdfPath) ?? "").Replace('\\', '/');
        if (configured != null)
        {
            var directory = PdfFile.ResolveDirectory(root, configured, allowRoot: true);
            if (!Directory.Exists(directory)) throw new DirectoryNotFoundException("The configured build output folder is missing. Refresh after building, or adjust outputDirectory in the repository profile.");
            return configured;
        }
        foreach (var candidate in new[] { "dist", "build", "bin" })
        {
            var directory = PdfFile.ResolveDirectory(root, candidate);
            if (Directory.Exists(directory)) return candidate;
        }
        throw new DirectoryNotFoundException("No build output folder was found. Configure a repository-relative outputDirectory in the profile.");
    }

    private static string ResolvePreviewPath(string root, string relativePath)
    {
        if (string.IsNullOrWhiteSpace(relativePath) || !WorkspaceTabsStore.IsRelativePath(relativePath) || relativePath.Split('/').Any(string.IsNullOrWhiteSpace))
            throw new ArgumentException("Preview paths must stay inside the repository.");
        var parent = (Path.GetDirectoryName(relativePath) ?? "").Replace('\\', '/');
        var directory = PdfFile.ResolveDirectory(root, parent, allowRoot: true);
        var path = Path.Combine(directory, Path.GetFileName(relativePath));
        if (!File.Exists(path)) throw new FileNotFoundException("File is missing. Refresh the listing.");
        if ((File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0) throw new ArgumentException("File previews cannot follow symlinks.");
        return path;
    }

    internal static string KindOfFile(string path)
    {
        var extension = Path.GetExtension(path);
        return extension.Equals(".pdf", StringComparison.OrdinalIgnoreCase) ? "pdf" : ImageExtensions.ContainsKey(extension) ? "image" : IsCode(path) ? "code" : TextExtensions.Contains(extension) ? "text" : "file";
    }

    private static bool IsCode(string path) => CodeExtensions.Contains(Path.GetExtension(path)) || CodeNames.Contains(Path.GetFileName(path));
}
