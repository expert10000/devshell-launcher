using System.Diagnostics;
using System.Text;
using System.Text.Json;

namespace BatchLauncher;

public partial class Form1
{
    private async Task<object> ScientificDatasetPreviewAsync(JsonElement request)
    {
        var inputId = request.GetProperty("inputId").GetString() ?? "";
        var manifest = ScientificMeshImports.ReadManifest(ScientificDataRoot);
        if (!manifest["entries"]!.AsArray().Any(item => item?["id"]?.GetValue<string>() == inputId))
            throw new InvalidOperationException("Choose a registered mesh copy for preview.");
        var artifact = ScientificDatasetArtifact(inputId);
        var path = artifact["path"]!.GetValue<string>();
        var hash = artifact["sha256"]!.GetValue<string>();
        if (Path.GetExtension(path).ToLowerInvariant() is not (".obj" or ".stl" or ".ply" or ".vtp"))
            throw new InvalidOperationException("Input preview supports OBJ, STL, PLY, or VTP; OFF remains available for CGAL operations.");
        if (!await _scientificPreviewGate.WaitAsync(0))
            throw new InvalidOperationException("A mesh preview is already loading.");
        try
        {
            var prefix = ScientificPrefix("vtk-win-conda");
            var start = new ProcessStartInfo(Path.Combine(prefix, "python.exe"))
            {
                UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true,
                RedirectStandardError = true, WorkingDirectory = Path.Combine(ScientificDataRoot, "datasets"),
                StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8
            };
            start.ArgumentList.Add(Path.Combine(ScientificSourceRoot, "tools", "scientific-artifact-preview.py"));
            start.ArgumentList.Add("--after"); start.ArgumentList.Add(path);
            foreach (var pair in ScientificEnvironment(prefix)) start.Environment[pair.Key] = pair.Value;
            start.Environment.Remove("PYTHONPATH");
            using var process = new Process { StartInfo = start };
            using var owner = new OwnedProcessJob();
            using var timeout = CancellationTokenSource.CreateLinkedTokenSource(_scientificLifetime.Token);
            timeout.CancelAfter(TimeSpan.FromSeconds(30));
            if (!process.Start()) throw new InvalidOperationException("Could not start the read-only input preview.");
            try
            {
                owner.Add(process);
                async Task<string> ReadBounded(StreamReader reader, int limit)
                {
                    var text = new StringBuilder(); var buffer = new char[4096]; int count;
                    while ((count = await reader.ReadAsync(buffer.AsMemory(), timeout.Token)) > 0)
                    {
                        if (text.Length + count > limit)
                        { owner.Stop(); throw new InvalidOperationException("Input preview exceeded its response size limit."); }
                        text.Append(buffer, 0, count);
                    }
                    return text.ToString();
                }
                var stdout = ReadBounded(process.StandardOutput, 8388608);
                var stderr = ReadBounded(process.StandardError, 65536);
                await process.WaitForExitAsync(timeout.Token);
                var body = await stdout; var errors = await stderr;
                if (process.ExitCode != 0)
                    throw new InvalidOperationException("Input preview failed: " + errors[..Math.Min(errors.Length, 1000)]);
                if (ScientificHash(path) != hash)
                    throw new InvalidOperationException("Registered mesh copy changed while its preview was loading.");
                using var document = JsonDocument.Parse(body);
                return new { inputId, sha256 = hash, geometry = document.RootElement.GetProperty("after").Clone() };
            }
            finally { owner.Stop(); }
        }
        finally { _scientificPreviewGate.Release(); }
    }
}
