using System.Text.Json;

namespace BatchLauncher;

public static class QuantumRuntimeDiagnostics
{
    public static async Task<HealthCheck> Inspect(string projectId, string repositoryId, string repository,
        string? python, string diagnosticsScript)
    {
        if (!File.Exists(Path.Combine(repository, "workers", "quantum-python", "quantum_worker", "main.py")))
            return new("Quantum worker", "error", "Worker source is missing.", projectId, repositoryId);
        if (python == null || !File.Exists(python))
            return new("Quantum worker", "error", "Configure an existing Python with Theory Lab worker requirements.", projectId, repositoryId);
        if (!File.Exists(diagnosticsScript))
            return new("Quantum worker", "error", "DevShell diagnostics script is missing.", projectId, repositoryId);
        try
        {
            var result = await DashboardInspector.Run(python, new[] { diagnosticsScript, repository });
            if (result.Code != 0)
                return new("Quantum worker", "error", (result.Error + result.Output).Trim()[..Math.Min(1000, (result.Error + result.Output).Trim().Length)], projectId, repositoryId);
            using var parsed = JsonDocument.Parse(result.Output);
            var root = parsed.RootElement;
            var fixture = root.GetProperty("fixture");
            var passed = fixture.GetProperty("passed").GetBoolean();
            var worker = root.GetProperty("workerVersion").GetString();
            var digest = fixture.GetProperty("energySha256").GetString();
            return new("Quantum worker", passed ? "ok" : "error",
                $"Worker {worker}; health {root.GetProperty("workerHealth").GetString()}; native fixture {(passed ? "passed" : "failed")}; energy SHA-256 {digest}.",
                projectId, repositoryId);
        }
        catch (Exception error)
        {
            return new("Quantum worker", "error", error.Message, projectId, repositoryId);
        }
    }
}
