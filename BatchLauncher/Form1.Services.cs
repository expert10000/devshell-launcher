using System.Diagnostics;
using System.Text.Json;

namespace BatchLauncher;

public partial class Form1
{
    private readonly SemaphoreSlim _serviceGate = new(1, 1);

    private string ExpandProjectValue(WorkspaceProject project, string value)
    {
        var variables = new Dictionary<string, string>(_workspace.Globals?.Vars ?? new());
        foreach (var pair in project.Vars ?? new()) variables[pair.Key] = pair.Value;
        foreach (var pair in variables) value = value.Replace("${vars." + pair.Key + "}", pair.Value);
        return value;
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
                throw new InvalidOperationException($"Python environment is missing: {environment}");
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
        if (action is not ("status" or "start" or "stop" or "restart" or "open")) return;
        var profileId = _activeWorkspaceProfileId;
        var project = _workspace.Projects?.FirstOrDefault(item => item.Id == projectId);
        if (project?.Service == null) return;
        // Polls never queue up behind a lifecycle action.
        if (action == "status") { if (!await _serviceGate.WaitAsync(0)) return; }
        else await _serviceGate.WaitAsync();
        try
        {
            if (action != "status")
                SendMessage(new { type = "service.status", projectId, profileId, state = "busy", message = action + "…", port = project.Service.Port });
            var start = new ProcessStartInfo(ExpandProjectValue(project, project.Service.Python))
            {
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true
            };
            foreach (var argument in new[] { Path.Combine(AppContext.BaseDirectory, "service_control.py"), action,
                         "--root", ExpandProjectValue(project, project.Root ?? ""), "--port", project.Service.Port.ToString() })
                start.ArgumentList.Add(argument);
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
}
