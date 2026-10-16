using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;

internal static class Program
{
    private const int OutputLimit = 32768;
    private static readonly JsonSerializerOptions Json = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        PropertyNameCaseInsensitive = true,
        WriteIndented = true
    };

    private static async Task<int> Main(string[] args)
    {
        using var cancellation = new CancellationTokenSource();
        Console.CancelKeyPress += (_, e) => { e.Cancel = true; cancellation.Cancel(); };
        try
        {
            if (args.Length == 0 || args[0] is not ("inventory" or "probe" or "run"))
                throw new ArgumentException("Usage: runtime-lab inventory|probe|run [runtime-id] [--manifest-root DIR] [--prefix DIR] [--run-id ID] [--output DIR] [--source-root DIR] [--request FILE] [--worker FILE]");

            var options = ParseOptions(args.Skip(1).ToArray());
            var root = Path.GetFullPath(options.GetValueOrDefault("manifest-root") ?? DefaultManifestRoot());
            var manifests = LoadManifests(root);
            if (args[0] == "inventory")
            {
                Console.WriteLine(JsonSerializer.Serialize(manifests.Select(m => new
                {
                    m.Id, m.Kind, m.Execution, m.Description,
                    probes = m.Probes.Select(p => new { p.Id, p.ReadinessLevel, p.Capability }),
                    recipes = m.Recipes.Select(r => new { r.Id, r.Capability })
                }), Json));
                return 0;
            }

            var id = options.GetValueOrDefault("id") ?? throw new ArgumentException("probe requires a runtime-id");
            var manifest = manifests.SingleOrDefault(m => string.Equals(m.Id, id, StringComparison.OrdinalIgnoreCase))
                ?? throw new ArgumentException($"Unknown runtime: {id}");
            var prefix = Path.GetFullPath(options.GetValueOrDefault("prefix") ?? throw new ArgumentException("probe requires --prefix"));
            var runId = options.GetValueOrDefault("run-id") ?? Guid.NewGuid().ToString("N");
            if (runId.Length is < 1 or > 100 || runId.Any(c => !char.IsAsciiLetterOrDigit(c) && c is not '-' and not '_'))
                throw new ArgumentException("Invalid run-id");
            var output = Path.GetFullPath(options.GetValueOrDefault("output") ?? Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "DevShellLauncher", "runtime-lab", "runs", runId));
            if (args[0] == "run")
                return await RunRecipeAsync(manifest, prefix, runId, output,
                    options.GetValueOrDefault("source-root") ?? throw new ArgumentException("run requires --source-root"),
                    options.GetValueOrDefault("request") ?? throw new ArgumentException("run requires --request"),
                    options.GetValueOrDefault("worker") ?? throw new ArgumentException("run requires --worker"),
                    cancellation.Token);
            return await ProbeAsync(manifest, prefix, runId, output, cancellation.Token);
        }
        catch (Exception ex) when (ex is not OutOfMemoryException)
        {
            Console.Error.WriteLine(ex.Message);
            return 2;
        }
    }

    private static Dictionary<string, string> ParseOptions(string[] args)
    {
        var result = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        for (var i = 0; i < args.Length; i++)
        {
            if (args[i].StartsWith("--", StringComparison.Ordinal))
            {
                if (++i >= args.Length || args[i].StartsWith("--", StringComparison.Ordinal))
                    throw new ArgumentException("Every option requires a value");
                result[args[i - 1][2..]] = args[i];
            }
            else if (!result.TryAdd("id", args[i]))
                throw new ArgumentException("Unexpected positional argument");
        }
        return result;
    }

    private static string DefaultManifestRoot()
    {
        var installed = Path.Combine(AppContext.BaseDirectory, "runtimes");
        return Directory.Exists(installed) ? installed : Path.Combine(Environment.CurrentDirectory, "runtimes");
    }

    private static List<RuntimeManifest> LoadManifests(string root)
    {
        if (!Directory.Exists(root)) throw new DirectoryNotFoundException($"Manifest root not found: {root}");
        var manifests = new List<RuntimeManifest>();
        foreach (var directory in Directory.EnumerateDirectories(root))
        {
            var file = Path.Combine(directory, "runtime.json");
            if (!File.Exists(file)) continue;
            var manifest = JsonSerializer.Deserialize<RuntimeManifest>(File.ReadAllText(file), Json)
                ?? throw new InvalidDataException($"Invalid manifest: {file}");
            if (manifest.SchemaVersion != 1 || string.IsNullOrWhiteSpace(manifest.Id)
                || manifest.Probes.Count == 0 || manifest.Execution != "windows-native")
                throw new InvalidDataException($"Unsupported manifest: {file}");
            if (manifest.Probes.Any(p => string.IsNullOrWhiteSpace(p.Id) || p.Arguments.Count == 0
                || p.TimeoutSeconds is < 1 or > 120))
                throw new InvalidDataException($"Invalid probe in {file}");
            if (manifest.Recipes.Any(r => r.Id != "cgal.validate" || r.Adapter != "tools/scientific-cgal-worker.py"
                || r.TimeoutSeconds is < 1 or > 120 || r.Capability != "mesh.validate")
                || (manifest.Id != "cgal-win-conda" && manifest.Recipes.Count != 0))
                throw new InvalidDataException($"Unsupported recipe in {file}");
            manifests.Add(manifest);
        }
        if (manifests.Select(m => m.Id).Distinct(StringComparer.OrdinalIgnoreCase).Count() != manifests.Count)
            throw new InvalidDataException("Duplicate runtime IDs");
        return manifests;
    }

    private static async Task<int> ProbeAsync(RuntimeManifest manifest, string prefix, string runId,
        string output, CancellationToken cancellation)
    {
        Directory.CreateDirectory(output);
        var started = DateTimeOffset.UtcNow;
        var executable = Path.Combine(prefix, "python.exe");
        var probes = new List<ProbeResult>();
        var diagnostics = new List<string>();
        if (!File.Exists(executable))
            diagnostics.Add($"Python executable missing from selected prefix: {executable}");
        else
        {
            foreach (var definition in manifest.Probes)
            {
                cancellation.ThrowIfCancellationRequested();
                Console.WriteLine($"[{manifest.Id}] {definition.Id}: starting");
                var probe = await RunProbeAsync(definition, executable, prefix, cancellation);
                probes.Add(probe);
                Console.WriteLine($"[{manifest.Id}] {definition.Id}: {probe.Status}");
                if (probe.Status != "passed") diagnostics.Add($"{definition.Id}: {probe.Status}");
            }
        }
        var status = diagnostics.Count == 0 && probes.Count == manifest.Probes.Count ? "succeeded" : "failed";
        var result = new
        {
            schemaVersion = 1,
            runId,
            runtimeId = manifest.Id,
            recipeId = "lab.probe",
            status,
            startedAtUtc = started,
            completedAtUtc = DateTimeOffset.UtcNow,
            environmentSnapshot = new
            {
                execution = manifest.Execution,
                prefix,
                executable,
                os = RuntimeInformation.OSDescription,
                architecture = RuntimeInformation.ProcessArchitecture.ToString()
            },
            probeResults = probes,
            validatedCapabilities = manifest.Probes.Where(p => p.Capability is not null
                && probes.Any(r => r.Id == p.Id && r.Status == "passed"))
                .Select(p => p.Capability).Distinct().ToArray(),
            diagnostics,
            artifacts = Array.Empty<object>()
        };
        var target = Path.Combine(output, "results.json");
        var temporary = target + ".tmp";
        await File.WriteAllTextAsync(temporary, JsonSerializer.Serialize(result, Json));
        File.Move(temporary, target, true);
        Console.WriteLine($"Result: {target}");
        return status == "succeeded" ? 0 : 1;
    }

    private static async Task<int> RunRecipeAsync(RuntimeManifest manifest, string prefix, string runId,
        string output, string sourceRoot, string requestPath, string workerPath, CancellationToken cancellation)
    {
        var recipe = manifest.Recipes.SingleOrDefault(r => r.Id == "cgal.validate")
            ?? throw new InvalidOperationException("This runtime has no registered validation recipe.");
        var request = Path.GetFullPath(requestPath);
        if (!string.Equals(Path.GetDirectoryName(request), output, StringComparison.OrdinalIgnoreCase)
            || Path.GetFileName(request) != "request.json" || !File.Exists(request)
            || new FileInfo(request).Length > 65536)
            throw new InvalidDataException("Expected a bounded request.json in the owned run folder.");
        using (var document = JsonDocument.Parse(File.ReadAllText(request)))
        {
            var invocation = document.RootElement;
            if (invocation.GetProperty("schemaVersion").GetInt32() != 1
                || invocation.GetProperty("runtimeId").GetString() != manifest.Id
                || invocation.GetProperty("recipeId").GetString() != recipe.Id
                || invocation.GetProperty("runId").GetString() != runId
                || !string.Equals(Path.GetFullPath(invocation.GetProperty("workingDirectory").GetString() ?? ""),
                    output, StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("Runtime-lab request does not match this run.");
        }
        var worker = Path.GetFullPath(workerPath);
        if (Path.GetFileName(worker) != "devshell_cgal_worker.exe" || !File.Exists(worker))
            throw new FileNotFoundException("The registered CGAL worker build is unavailable.", worker);
        var source = Path.GetFullPath(sourceRoot);
        var adapter = Path.GetFullPath(Path.Combine(source, recipe.Adapter.Replace('/', Path.DirectorySeparatorChar)));
        if (!adapter.StartsWith(source.TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar,
                StringComparison.OrdinalIgnoreCase) || !File.Exists(adapter))
            throw new FileNotFoundException("The registered CGAL adapter is unavailable.", adapter);
        var executable = Path.Combine(prefix, "python.exe");
        if (!File.Exists(executable)) throw new FileNotFoundException("CGAL Python is unavailable.", executable);
        var info = new ProcessStartInfo(executable)
        {
            UseShellExecute = false, RedirectStandardOutput = true, RedirectStandardError = true,
            CreateNoWindow = true, WorkingDirectory = output
        };
        foreach (var argument in new[] { adapter, "--request", request, "--worker", worker })
            info.ArgumentList.Add(argument);
        info.Environment.Remove("PYTHONPATH");
        info.Environment.Remove("PYTHONHOME");
        info.Environment["PYTHONNOUSERSITE"] = "1";
        info.Environment["PYTHONIOENCODING"] = "utf-8";
        info.Environment["CONDA_PREFIX"] = prefix;
        info.Environment.TryGetValue("PATH", out var inheritedPath);
        info.Environment["PATH"] = string.Join(Path.PathSeparator,
            new[] { prefix, Path.Combine(prefix, "Scripts"), Path.Combine(prefix, "Library", "bin"), inheritedPath ?? "" });
        Console.WriteLine($"[{manifest.Id}] {recipe.Id}: starting run {runId}");
        using var process = new Process { StartInfo = info };
        if (!process.Start()) throw new InvalidOperationException("Registered adapter did not start.");
        var stdout = DrainAsync(process.StandardOutput, Console.Write);
        var stderr = DrainAsync(process.StandardError, Console.Error.Write);
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellation);
        timeout.CancelAfter(TimeSpan.FromSeconds(recipe.TimeoutSeconds));
        try { await process.WaitForExitAsync(timeout.Token); }
        catch (OperationCanceledException)
        {
            if (!process.HasExited) process.Kill(entireProcessTree: true);
            await process.WaitForExitAsync();
            await Task.WhenAll(stdout, stderr);
            throw cancellation.IsCancellationRequested ? new OperationCanceledException("Validation was stopped.")
                : new TimeoutException($"Validation exceeded {recipe.TimeoutSeconds} seconds.");
        }
        await Task.WhenAll(stdout, stderr);
        if (process.ExitCode != 0) return 1;
        var resultPath = Path.Combine(output, "results.json");
        if (!File.Exists(resultPath) || new FileInfo(resultPath).Length > 1048576)
            throw new InvalidDataException("Validation completed without a bounded result contract.");
        using var result = JsonDocument.Parse(File.ReadAllText(resultPath));
        if (result.RootElement.GetProperty("runId").GetString() != runId
            || result.RootElement.GetProperty("recipeId").GetString() != recipe.Id
            || result.RootElement.GetProperty("state").GetString() != "succeeded")
            throw new InvalidDataException("Validation result does not match the registered run.");
        Console.WriteLine($"[{manifest.Id}] {recipe.Id}: result {resultPath}");
        return 0;
    }

    private static async Task<ProbeResult> RunProbeAsync(ProbeDefinition definition,
        string executable, string prefix, CancellationToken cancellation)
    {
        var start = DateTimeOffset.UtcNow;
        var watch = Stopwatch.StartNew();
        var info = new ProcessStartInfo(executable)
        {
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
            WorkingDirectory = prefix
        };
        foreach (var argument in definition.Arguments) info.ArgumentList.Add(argument);
        info.Environment.Remove("PYTHONPATH");
        info.Environment.Remove("PYTHONHOME");
        info.Environment["PYTHONNOUSERSITE"] = "1";
        info.Environment["CONDA_PREFIX"] = prefix;
        info.Environment.TryGetValue("PATH", out var inheritedPath);
        info.Environment["PATH"] = string.Join(Path.PathSeparator,
            new[] { prefix, Path.Combine(prefix, "Scripts"), Path.Combine(prefix, "Library", "bin"),
                inheritedPath ?? "" });
        try
        {
            using var process = new Process { StartInfo = info };
            if (!process.Start()) throw new InvalidOperationException("Child did not start");
            var stdout = DrainAsync(process.StandardOutput);
            var stderr = DrainAsync(process.StandardError);
            using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellation);
            timeout.CancelAfter(TimeSpan.FromSeconds(definition.TimeoutSeconds));
            string status;
            try
            {
                await process.WaitForExitAsync(timeout.Token);
                status = process.ExitCode == 0 ? "passed" : "failed";
            }
            catch (OperationCanceledException)
            {
                if (!process.HasExited) process.Kill(entireProcessTree: true);
                await process.WaitForExitAsync();
                status = cancellation.IsCancellationRequested ? "cancelled" : "timed-out";
            }
            return new ProbeResult(definition.Id, definition.ReadinessLevel, status,
                process.ExitCode, start, watch.ElapsedMilliseconds, await stdout, await stderr);
        }
        catch (Exception ex) when (ex is not OutOfMemoryException)
        {
            return new ProbeResult(definition.Id, definition.ReadinessLevel, "failed", null,
                start, watch.ElapsedMilliseconds, "", ex.Message);
        }
    }

    private static async Task<string> DrainAsync(StreamReader reader, Action<string>? mirror = null)
    {
        var text = new StringBuilder();
        var buffer = new char[4096];
        int read;
        while ((read = await reader.ReadAsync(buffer.AsMemory())) > 0)
            if (text.Length < OutputLimit)
            {
                var retained = Math.Min(read, OutputLimit - text.Length);
                text.Append(buffer, 0, retained);
                mirror?.Invoke(new string(buffer, 0, retained));
            }
        return text.ToString();
    }

    private sealed class RuntimeManifest
    {
        public int SchemaVersion { get; set; }
        public string Id { get; set; } = "";
        public string Kind { get; set; } = "";
        public string Execution { get; set; } = "";
        public string Description { get; set; } = "";
        public List<ProbeDefinition> Probes { get; set; } = new();
        public List<RecipeDefinition> Recipes { get; set; } = new();
    }

    private sealed class ProbeDefinition
    {
        public string Id { get; set; } = "";
        public string ReadinessLevel { get; set; } = "";
        public string? Capability { get; set; }
        public int TimeoutSeconds { get; set; } = 15;
        public List<string> Arguments { get; set; } = new();
    }

    private sealed class RecipeDefinition
    {
        public string Id { get; set; } = "";
        public string Adapter { get; set; } = "";
        public string Capability { get; set; } = "";
        public int TimeoutSeconds { get; set; } = 120;
    }

    private sealed record ProbeResult(string Id, string ReadinessLevel, string Status,
        int? ExitCode, DateTimeOffset StartedAtUtc, long DurationMs, string Stdout, string Stderr);
}
