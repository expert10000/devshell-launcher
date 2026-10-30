using System.Text.RegularExpressions;

namespace BatchLauncher;

public static class ProcessServiceCommand
{
    public static RepositoryCommand Create(WorkspaceService service, string shell, string projectRoot, Func<string, string> expand)
    {
        if (service.Kind != "process") throw new ArgumentException("A process service is required.");
        var cwd = Path.GetFullPath(expand(service.Cwd ?? projectRoot));
        if (!Directory.Exists(cwd)) throw new DirectoryNotFoundException("Service folder is missing: " + cwd);
        var executable = expand(service.Command ?? "").Trim();
        if (string.IsNullOrWhiteSpace(executable)) throw new InvalidOperationException("Configure a worker command before starting the service.");
        var resolved = DashboardInspector.FindTool(executable) ?? throw new FileNotFoundException("Worker command is unavailable: " + executable);
        static string Quote(string value) => "'" + value.Replace("'", "''") + "'";
        var script = "$ErrorActionPreference='Stop'\n$PSNativeCommandUseErrorActionPreference=$false\n";
        foreach (var pair in service.Environment ?? new())
        {
            if (!Regex.IsMatch(pair.Key, @"^[A-Za-z_][A-Za-z0-9_]*$")) throw new InvalidOperationException("Invalid worker environment variable: " + pair.Key);
            script += "$env:" + pair.Key + "=" + Quote(expand(pair.Value)) + "\n";
        }
        script += "& " + Quote(resolved);
        foreach (var argument in service.Arguments ?? new()) script += " " + Quote(expand(argument));
        script += "\nif ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; exit 0\n";
        return new RepositoryCommand(shell, script, cwd);
    }

    public static string State(RepositoryJobStatus? job) => job == null ? "stopped" : job.State switch
    {
        "queued" or "building" => "starting",
        "running" when job.BrowserState is "waiting" or "queued" => "starting",
        "running" => "running",
        "failed" => "failed",
        _ => "stopped"
    };
}
