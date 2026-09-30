namespace BatchLauncher;

public static class RepositoryGitCommand
{
    public static RepositoryCommand Create(string shell, string scriptPath, string path, string? url, string action, string workingDirectory)
    {
        if (action is not ("fetch" or "pull" or "clone" or "sync")) throw new ArgumentException("Unknown Git action.");
        if (!File.Exists(scriptPath)) throw new FileNotFoundException("Repository sync helper is missing.", scriptPath);
        if (!Path.IsPathFullyQualified(path)) throw new ArgumentException("An absolute repository path is required.");
        string Quote(string value) => "'" + value.Replace("'", "''") + "'";
        var script = "$ErrorActionPreference = 'Stop'\ntry { & " + Quote(scriptPath)
            + " -Destination " + Quote(Path.GetFullPath(path)) + " -Action " + Quote(action)
            + (string.IsNullOrWhiteSpace(url) ? "" : " -RepositoryUrl " + Quote(url))
            + "; exit 0 } catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 }";
        return new(shell, script, workingDirectory);
    }
}
