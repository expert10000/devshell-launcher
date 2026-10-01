namespace BatchLauncher;

public static class RepositoryGitCommand
{
    public static RepositoryCommand CreateInspection(string shell, string path, string action, string workingDirectory)
    {
        if (action is not ("diff" or "history")) throw new ArgumentException("Unknown repository inspection action.");
        if (!Path.IsPathFullyQualified(path)) throw new ArgumentException("An absolute repository path is required.");
        string Quote(string value) => "'" + value.Replace("'", "''") + "'";
        var prefix = "git --no-pager -c color.ui=false -c core.quotePath=false -c " + Quote("safe.directory=" + path.Replace('\\', '/')) + " -C " + Quote(Path.GetFullPath(path));
        var script = "$ErrorActionPreference = 'Stop'\n$PSNativeCommandUseErrorActionPreference = $true\ntry {\n";
        if (action == "history")
            script += prefix + " log -50 --no-show-signature --decorate=short --date=iso-strict --format=" + Quote("%h %d%n%ad %an%n    %s%n") + "\n";
        else
        {
            script += "Write-Output '=== Unstaged tracked changes ==='\n" + prefix + " diff --no-ext-diff --no-textconv --color=never --\n";
            script += "Write-Output '=== Staged changes ==='\n" + prefix + " diff --cached --no-ext-diff --no-textconv --color=never --\n";
            script += "Write-Output '=== Untracked files (names only; not included in patches) ==='\n" + prefix + " ls-files --others --exclude-standard\n";
        }
        script += "exit 0\n} catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 }";
        return new(shell, script, workingDirectory);
    }

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
