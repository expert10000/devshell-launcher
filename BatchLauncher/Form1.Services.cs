using System.Diagnostics;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace BatchLauncher;

public partial class Form1
{
    private readonly SemaphoreSlim _serviceGate = new(1, 1);

    private string ExpandProjectValue(WorkspaceProject project, string value)
    {
        var variables = new Dictionary<string, string>(_workspace.Globals?.Vars ?? new());
        foreach (var pair in project.Vars ?? new()) variables[pair.Key] = pair.Value;
        return PortableWorkspace.Expand(value, variables);
    }

    private Dictionary<string, string>? GetProjectEnvironment(string? cwd)
    {
        if (string.IsNullOrWhiteSpace(cwd)) return null;
        var directory = Path.GetFullPath(cwd).TrimEnd(Path.DirectorySeparatorChar);
        foreach (var project in _workspace.Projects ?? new())
        {
            if (string.IsNullOrWhiteSpace(project.Root) || string.IsNullOrWhiteSpace(project.PythonEnvironment)) continue;
            var root = Path.GetFullPath(ExpandProjectValue(project, project.Root)).TrimEnd(Path.DirectorySeparatorChar);
            if (!directory.Equals(root, StringComparison.OrdinalIgnoreCase) &&
                !directory.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)) continue;
            var environment = ExpandProjectValue(project, project.PythonEnvironment);
            var scripts = Path.Combine(environment, "Scripts");
            if (!File.Exists(Path.Combine(scripts, "python.exe")))
                return null;
            return new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                ["VIRTUAL_ENV"] = environment,
                ["PATH"] = scripts + ";" + Environment.GetEnvironmentVariable("PATH")
            };
        }
        return null;
    }

    private async Task HandleServiceControlAsync(JsonElement payload)
    {
        var projectId = payload.GetProperty("projectId").GetString();
        var action = payload.GetProperty("action").GetString() ?? "status";
        var labPath = payload.TryGetProperty("path", out var pathElement) ? pathElement.GetString() : null;
        var openExternally = payload.TryGetProperty("target", out var targetElement) &&
            targetElement.GetString() == "external";
        if (action is not ("status" or "start" or "stop" or "restart" or "open")) return;
        var profileId = _activeWorkspaceProfileId;
        var project = _workspace.Projects?.FirstOrDefault(item => item.Id == projectId);
        if (project?.Service == null) return;
        // Polls never queue up behind a lifecycle action.
        if (action == "status") { if (!await _serviceGate.WaitAsync(0)) return; }
        else await _serviceGate.WaitAsync();
        try
        {
            if (profileId != _activeWorkspaceProfileId) return;
            if (action is "start" or "restart" or "open" && _repositoryRunner.Snapshot().Any(job => (job.Action is "setup" or "prepare-launch") && job.State is "queued" or "building" or "running"))
                throw new InvalidOperationException("Finish or stop environment repair before starting services.");
            if (project.Service.Kind == "process")
            {
                await HandleProcessServiceControlAsync(project, profileId, action, openExternally);
                return;
            }
            if (project.Service.Kind != "jupyter") throw new InvalidOperationException("Unknown service kind: " + project.Service.Kind);
            var jupyterPython = ExpandProjectValue(project, project.Service.Python);
            if (!File.Exists(jupyterPython))
            {
                SendMessage(new { type = "service.status", projectId, profileId, state = "blocked",
                    message = "Jupyter Python environment is missing. Open Setup / Fix to create it.", port = project.Service.Port });
                return;
            }
            if (action != "status")
                SendMessage(new { type = "service.status", projectId, profileId, state = "busy", message = action + "…", port = project.Service.Port });
            var start = new ProcessStartInfo(jupyterPython)
            {
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true
            };
            foreach (var argument in new[] { Path.Combine(AppContext.BaseDirectory, "service_control.py"), action,
                         "--root", ExpandProjectValue(project, project.Root ?? ""), "--port", project.Service.Port.ToString() })
                start.ArgumentList.Add(argument);
            if (!openExternally) start.ArgumentList.Add("--no-open");
            if (!string.IsNullOrWhiteSpace(labPath))
            {
                start.ArgumentList.Add("--path");
                start.ArgumentList.Add(labPath);
            }
            using var process = Process.Start(start) ?? throw new InvalidOperationException("Could not start service controller.");
            var outputTask = process.StandardOutput.ReadToEndAsync();
            var errorTask = process.StandardError.ReadToEndAsync();
            using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(90));
            try { await process.WaitForExitAsync(timeout.Token); }
            catch (OperationCanceledException)
            {
                // Terminate the controller only; a server finishing startup can be found on the next poll.
                process.Kill();
                throw new InvalidOperationException("Service operation timed out. Refresh status before retrying.");
            }
            var output = await outputTask;
            await errorTask; // Drain stderr without exposing server URLs or tokens.
            if (process.ExitCode != 0) throw new InvalidOperationException("Service controller failed. Check the configured Python environment.");
            using var result = JsonDocument.Parse(output);
            if (!openExternally && profileId == _activeWorkspaceProfileId &&
                result.RootElement.TryGetProperty("url", out var urlElement))
            {
                var url = urlElement.GetString();
                if (url != null) await ShowBrowserAsync(url, profileId, "jupyter", project.Id, servicePath: labPath);
            }
            SendMessage(new { type = "service.status", projectId, profileId,
                state = result.RootElement.GetProperty("state").GetString(),
                message = result.RootElement.GetProperty("message").GetString(), port = project.Service.Port });
        }
        catch (Exception ex)
        {
            SendMessage(new { type = "service.status", projectId, profileId, state = "error", message = ex.Message, port = project.Service.Port });
        }
        finally { _serviceGate.Release(); }
    }

    private async Task HandleServiceLogAsync(JsonElement payload)
    {
        var profileId = _activeWorkspaceProfileId;
        var projectId = payload.GetProperty("projectId").GetString();
        try
        {
            var project = _workspace.Projects?.FirstOrDefault(item => item.Id == projectId && item.Service != null)
                ?? throw new InvalidOperationException("Service not found in this profile.");
            if (project.Service!.Kind == "process")
            {
                var job = _repositoryRunner.Snapshot().FirstOrDefault(item => item.Key == $"{profileId}:{project.Id}:service");
                var output = job?.Log ?? "No worker log has been created yet.";
                if (!IsDisposed && profileId == _activeWorkspaceProfileId)
                    SendMessage(new { type = "service.log.result", profileId, projectId, data = RedactServiceLog(output) });
                return;
            }
            var path = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "DevShellLauncher", "logs", $"jupyter-{project.Service!.Port}.log");
            string log;
            if (!File.Exists(path)) log = "No service log has been created yet.";
            else
            {
                using var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
                var offset = Math.Max(0, stream.Length - 32768);
                stream.Seek(offset, SeekOrigin.Begin);
                using var reader = new StreamReader(stream, Encoding.UTF8, detectEncodingFromByteOrderMarks: false);
                log = await reader.ReadToEndAsync();
                if (offset > 0 && log.Contains('\n')) log = log[(log.IndexOf('\n') + 1)..];
                log = RedactServiceLog(log);
            }
            if (!IsDisposed && profileId == _activeWorkspaceProfileId)
                SendMessage(new { type = "service.log.result", profileId, projectId, data = log });
        }
        catch (Exception error)
        {
            if (!IsDisposed && profileId == _activeWorkspaceProfileId)
                SendMessage(new { type = "service.log.result", profileId, projectId, data = "Log unavailable: " + error.Message });
        }
    }

    private static string RedactServiceLog(string log)
    {
        log = Regex.Replace(log, @"(?i)([?&]token=)[^\s&""']+", "$1[redacted]");
        return Regex.Replace(log, @"(?i)(authorization:\s*token\s+)\S+", "$1[redacted]");
    }

    private async Task HandleProcessServiceControlAsync(WorkspaceProject project, string profileId, string action, bool openExternally)
    {
        var service = project.Service!;
        var key = $"{profileId}:{project.Id}:service";
        RepositoryJobStatus? Current() => _repositoryRunner.Snapshot().FirstOrDefault(item => item.Key == key);
        if (action is "stop" or "restart" && Current() is { State: "queued" or "building" or "running" })
        {
            SendMessage(new { type = "service.status", projectId = project.Id, profileId, state = "busy", message = action + "…" });
            _repositoryRunner.Stop(key);
            await _repositoryRunner.Completion(key).WaitAsync(TimeSpan.FromSeconds(30));
        }
        if (action is "start" or "restart")
        {
            if (Current() is { State: "queued" or "building" or "running" }) throw new InvalidOperationException("This worker is already running.");
            var shell = _profiles.FirstOrDefault(item => item.Id == "pwsh") ?? throw new InvalidOperationException("PowerShell profile missing.");
            if (!_terminalManager.TryResolveProfileCommand(shell, out var resolvedShell)) throw new InvalidOperationException("PowerShell is unavailable.");
            var run = ProcessServiceCommand.Create(service, resolvedShell.Application, project.Root ?? "", value => ExpandProjectValue(project, value));
            var readyUrl = service.ReadyUrl == null ? null : ExpandProjectValue(project, service.ReadyUrl);
            var readiness = readyUrl == null ? null : new RepositoryBrowserLaunch(readyUrl, new[] { readyUrl }, service.ReadyTimeoutSeconds, AutoOpen: false);
            if (!_repositoryRunner.Start(key, null, run, RepositoryLogDirectory, "service", readiness)) throw new InvalidOperationException("This worker is already running.");
            SendRepositoryJobs();
        }
        if (action == "open")
        {
            if (ProcessServiceCommand.State(Current()) != "running") throw new InvalidOperationException("Start the worker before opening it.");
            var url = service.OpenUrl == null ? null : ExpandProjectValue(project, service.OpenUrl);
            if (url == null || !BrowserPane.IsWebUrl(url)) throw new InvalidOperationException("This worker has no valid Open URL.");
            if (openExternally) Process.Start(new ProcessStartInfo(url) { UseShellExecute = true });
            else await ShowBrowserAsync(url, profileId, "browser", project.Id);
        }
        var job = Current();
        var state = ProcessServiceCommand.State(job);
        SendMessage(new { type = "service.status", projectId = project.Id, profileId, state,
            message = job == null ? "Stopped" : state == "running" ? "Running in this DevShell session" :
                state == "starting" ? "Starting and checking readiness…" : state == "failed" ? "Worker failed; open Logs" : "Stopped" });
    }
}
