using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json.Nodes;

namespace BatchLauncher;

// A run keeps the inputs observed when its request was made. The final record is
// created once, after the executed tools are known. No local path or environment
// variable value is included in the portable fingerprint.
public static class ScientificRunFingerprint
{
    private static string Hash(string file)
    {
        using var stream = File.OpenRead(file);
        return Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
    }

    private static JsonObject FileIdentity(string path)
    {
        try
        {
            if (File.Exists(path)) return new JsonObject { ["state"] = "recorded", ["sha256"] = Hash(path) };
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException) { }
        return new JsonObject { ["state"] = "unavailable" };
    }

    private static JsonObject SourceFiles(string root, string runtimeId)
    {
        var files = new JsonObject();
        var names = new List<string> { "tools/scientific_worker_contract.py", $"runtimes/{runtimeId}/runtime.json" };
        if (runtimeId.StartsWith("cgal", StringComparison.Ordinal))
            names.AddRange(new[] { "tools/scientific-cgal-worker.py", "scientific/cgal-worker/main.cpp", "scientific/cgal-worker/CMakeLists.txt", "tools/math3d-native-protocol.mjs", "tools/run-math3d-boolean.mjs" });
        if (runtimeId.StartsWith("vtk", StringComparison.Ordinal))
            names.AddRange(new[] { "tools/scientific-mesh-worker.py", "tools/scientific-vtk-render-check.py", "scientific/smoke/vtk/main.cpp", "scientific/smoke/vtk/CMakeLists.txt" });
        foreach (var name in names)
            files[name] = FileIdentity(Path.Combine(root, name.Replace('/', Path.DirectorySeparatorChar)));
        return files;
    }

    private static string? GitHead(string root)
    {
        try
        {
            using var process = new Process { StartInfo = new ProcessStartInfo("git")
            {
                UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true,
                RedirectStandardError = true, WorkingDirectory = root
            } };
            process.StartInfo.ArgumentList.Add("rev-parse");
            process.StartInfo.ArgumentList.Add("HEAD");
            if (!process.Start()) return null;
            if (!process.WaitForExit(3000)) { process.Kill(entireProcessTree: true); return null; }
            if (process.ExitCode != 0) return null;
            var value = process.StandardOutput.ReadToEnd().Trim();
            return value.Length == 40 && value.All(Uri.IsHexDigit) ? value.ToLowerInvariant() : null;
        }
        catch (Exception exception) when (exception is IOException or InvalidOperationException or System.ComponentModel.Win32Exception)
        {
            return null;
        }
    }

    public static JsonObject Capture(string runtimeId, string profileId, string sourceRoot,
        string installedRoot, string? runtimeReportPath = null, string? wslDistro = null)
    {
        var backend = runtimeId.EndsWith("-wsl", StringComparison.Ordinal) ? "wsl" : "windows-native";
        string? prefix = null;
        if (runtimeReportPath != null && File.Exists(runtimeReportPath))
        {
            try
            {
                var report = JsonNode.Parse(File.ReadAllText(runtimeReportPath));
                prefix = report?["runtimes"]?.AsArray().FirstOrDefault(item => item?["id"]?.GetValue<string>() == runtimeId)?["environmentRoot"]?.GetValue<string>();
                if (prefix == null && runtimeId is ("gmsh-win-conda" or "python-win-conda"))
                {
                    var runtimeRoot = report?["runtimeRoot"]?.GetValue<string>();
                    if (!string.IsNullOrWhiteSpace(runtimeRoot)) prefix = Path.Combine(runtimeRoot, "devshell-scientific");
                }
            }
            catch (Exception exception) when (exception is IOException or System.Text.Json.JsonException or InvalidOperationException)
            {
                // A missing or malformed report is represented by unavailable identities.
            }
        }
        var environment = new JsonObject
        {
            ["backend"] = backend,
            ["os"] = RuntimeInformation.OSDescription,
            ["architecture"] = RuntimeInformation.OSArchitecture.ToString(),
            ["condaHistory"] = prefix == null ? new JsonObject { ["state"] = "unavailable" } : FileIdentity(Path.Combine(prefix, "conda-meta", "history")),
            ["pythonExecutable"] = prefix == null ? new JsonObject { ["state"] = "unavailable" } : FileIdentity(Path.Combine(prefix, "python.exe")),
            ["wslDistro"] = backend == "wsl" ? wslDistro ?? "unavailable" : null,
            ["wslProviderBinary"] = backend == "wsl" ? "unavailable from Windows host" : null
        };
        var manifest = Path.Combine(installedRoot, "runtimes", runtimeId, "runtime.json");
        return new JsonObject
        {
            ["runtimeId"] = runtimeId,
            ["profileIdSha256"] = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(profileId))).ToLowerInvariant(),
            ["environment"] = environment,
            ["source"] = new JsonObject
            {
                ["gitHead"] = GitHead(sourceRoot) ?? "unavailable",
                ["files"] = SourceFiles(sourceRoot, runtimeId),
                ["launcherAssembly"] = FileIdentity(typeof(ScientificRunFingerprint).Assembly.Location)
            },
            ["contract"] = new JsonObject
            {
                ["requestSchemaVersion"] = 1, ["resultSchemaVersion"] = 1,
                ["runtimeManifest"] = FileIdentity(File.Exists(manifest) ? manifest : Path.Combine(sourceRoot, "runtimes", runtimeId, "runtime.json")),
                ["workerContractModule"] = FileIdentity(Path.Combine(sourceRoot, "tools", "scientific_worker_contract.py"))
            }
        };
    }

    public static JsonObject ExecutedFile(string path, string role)
    {
        var identity = FileIdentity(path);
        identity["name"] = Path.GetFileName(path);
        identity["role"] = role;
        return identity;
    }

    public static JsonObject CommandIdentity(string name, string command) => new()
    {
        ["name"] = name, ["role"] = "fixed-command", ["state"] = "recorded",
        ["sha256"] = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(command))).ToLowerInvariant()
    };

    public static string Save(string directory, JsonObject captured, IEnumerable<JsonObject> executedFiles)
    {
        var target = Path.Combine(directory, "fingerprint.json");
        var worker = new JsonObject { ["executedFiles"] = new JsonArray(executedFiles.Select(item => (JsonNode?)item.DeepClone()).ToArray()) };
        if (worker["executedFiles"]!.AsArray().Count == 0)
            worker["state"] = "no managed process recorded";
        var components = (JsonObject)captured.DeepClone();
        components["worker"] = worker;
        var digest = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(components.ToJsonString()))).ToLowerInvariant();
        var record = new JsonObject
        {
            ["schemaVersion"] = 1, ["sha256"] = digest,
            ["capturedAtUtc"] = DateTimeOffset.UtcNow.ToString("O"),
            ["components"] = components
        };
        var temporary = Path.Combine(directory, $".fingerprint-{Guid.NewGuid():N}.tmp");
        try
        {
            File.WriteAllText(temporary, record.ToJsonString(), new UTF8Encoding(false));
            File.Move(temporary, target);
        }
        finally
        {
            if (File.Exists(temporary)) File.Delete(temporary);
        }
        return digest;
    }

    public static void Verify(string directory, string expectedDigest)
    {
        if (expectedDigest.Length != 64 || !expectedDigest.All(Uri.IsHexDigit))
            throw new InvalidDataException("Invalid run fingerprint digest.");
        var path = Path.Combine(directory, "fingerprint.json");
        if (!File.Exists(path) || new FileInfo(path).Length > 1048576)
            throw new InvalidDataException("Run fingerprint is missing or too large.");
        var record = JsonNode.Parse(File.ReadAllText(path));
        var components = record?["components"] as JsonObject;
        if (record?["schemaVersion"]?.GetValue<int>() != 1 || components == null)
            throw new InvalidDataException("Unsupported run fingerprint.");
        var actual = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(components.ToJsonString()))).ToLowerInvariant();
        if (!string.Equals(actual, expectedDigest, StringComparison.OrdinalIgnoreCase)
            || !string.Equals(record["sha256"]?.GetValue<string>(), expectedDigest, StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("Run fingerprint does not match saved evidence.");
    }
}
