using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace BatchLauncher;

// A run keeps the inputs observed when its request was made. The final record is
// created once, after the executed tools are known. No local path or environment
// variable value is included in the portable fingerprint.
public static class ScientificRunFingerprint
{
    public static string CmakePath(string prefix, string runtimeId)
    {
        var own = Path.Combine(prefix, "Library", "bin", "cmake.exe");
        if (File.Exists(own) || runtimeId != "gmsh-win-conda") return own;
        return Path.Combine(Path.GetDirectoryName(prefix)!, "devshell-cgal", "Library", "bin", "cmake.exe");
    }

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
        var names = new List<string> { "tools/scientific_worker_contract.py", "tools/runtime-lab/Program.cs",
            "BatchLauncher/ScientificProviderRegistry.cs", "BatchLauncher/ScientificRunFingerprint.cs",
            "BatchLauncher/ScientificQualificationRecords.cs",
            $"runtimes/{runtimeId}/runtime.json" };
        if (runtimeId is "cgal-win-conda" or "vtk-win-conda" or "gmsh-win-conda") names.AddRange(new[] { "BatchLauncher/Form1.Scientific.L5.cs", "BatchLauncher/Form1.Scientific.L6.cs", "tools/scientific-artifact-roundtrip.py" });
        if (runtimeId == "gmsh-win-conda") names.AddRange(new[] { "tools/scientific-gmsh-worker.py",
            "tools/scientific-gmsh-roundtrip.py", "tools/scientific-gmsh-handoff.py",
            "tools/scientific-gmsh-vtk-consumer.py", "tools/math3d-gmsh-import-handoff.mjs",
            "BatchLauncher/Form1.Scientific.L7.cs", "BatchLauncher/Form1.Scientific.GmshGates.cs",
            "BatchLauncher/Form1.Scientific.GmshProduct.cs", "BatchLauncher/Form1.Scientific.L9.cs",
            "BatchLauncher/ScientificQualificationRecords.Gmsh.cs", "BatchLauncher/OwnedProcessJob.cs",
            "tools/math3d-l9-product-handoff.mjs", "tools/scientific-gmsh-m3dm-roundtrip.py",
            "scientific/fixtures/gmsh/square.geo", "scientific/fixtures/gmsh/tampered-square.geo",
            "BatchLauncher/Form1.Scientific.GmshVolume.cs", "BatchLauncher/Form1.Scientific.GmshVolumeProduct.cs",
            "BatchLauncher/Form1.Scientific.GmshVolumeL9.cs",
            "BatchLauncher/ScientificQualificationRecords.GmshVolume.cs",
            "tools/scientific-broker/gmsh_volume.py", "tools/scientific-gmsh-volume-worker.py",
            "tools/scientific-gmsh-volume-handoff.py", "tools/scientific-gmsh-volume-vtk.py",
            "tools/math3d-gmsh-volume-consumer.mjs", "scientific/fixtures/gmsh/cube.geo",
            "scientific/fixtures/gmsh/tampered-cube.geo",
            "tools/scientific-gmsh-volume-product-readiness.py",
            "tools/scientific-gmsh-tetmesh-export.py", "tools/math3d-gmsh-tetmesh-product.mjs",
            "tools/scientific-gmsh-tetmesh-roundtrip.py" });
        if (runtimeId == "vtk-win-conda") names.AddRange(new[] { "BatchLauncher/Form1.Scientific.L7.cs", "tools/math3d-vtk-import-handoff.mjs" });
        if (runtimeId == "cgal-win-conda") names.AddRange(new[] { "BatchLauncher/Form1.Scientific.L7Interop.cs", "BatchLauncher/Form1.Scientific.L8.cs", "BatchLauncher/Form1.Scientific.L9.cs", "BatchLauncher/OwnedProcessJob.cs", "tools/scientific-vtk-interop.py", "tools/math3d-vtk-import-handoff.mjs", "tools/math3d-l9-product-handoff.mjs" });
        if (runtimeId.StartsWith("cgal", StringComparison.Ordinal))
            names.AddRange(new[] { "tools/scientific-cgal-worker.py", "scientific/cgal-worker/main.cpp", "scientific/cgal-worker/CMakeLists.txt", "tools/math3d-native-protocol.mjs", "tools/run-math3d-boolean.mjs" });
        if (runtimeId == "cgal-win-conda") names.AddRange(new[] { "tools/scientific-cgal-hole-repair-worker.py",
            "tools/scientific_cgal_mesh_metrics.py", "scientific/cgal-worker/hole_repair.cpp" });
        if (runtimeId.StartsWith("vtk", StringComparison.Ordinal))
            names.AddRange(new[] { "tools/scientific-mesh-worker.py", "tools/scientific-vtk-render-check.py" });
        if (runtimeId == "sage-wsl") names.AddRange(new[] { "BatchLauncher/Form1.Scientific.Sage.cs",
            "BatchLauncher/Form1.Scientific.SageQualification.cs", "tools/scientific-sage-worker.py",
            "tools/scientific-sage-wsl.py", "tools/scientific-sage-qualify.py",
            "schemas/scientific-sage-exact.v1.json", "BatchLauncher/ScientificQualificationRecords.Sage.cs" });
        foreach (var name in names)
            files[name] = FileIdentity(Path.Combine(root, name.Replace('/', Path.DirectorySeparatorChar)));
        return files;
    }

    private static JsonObject PackageIdentity(string? prefix)
    {
        if (prefix == null) return new JsonObject { ["state"] = "unavailable" };
        try
        {
            var meta = Path.Combine(prefix, "conda-meta");
            if (!Directory.Exists(meta)) return new JsonObject { ["state"] = "unavailable" };
            var records = Directory.EnumerateFiles(meta, "*.json", SearchOption.TopDirectoryOnly)
                .OrderBy(Path.GetFileName, StringComparer.Ordinal).ToArray();
            if (records.Length == 0) return new JsonObject { ["state"] = "unavailable" };
            var inventory = new StringBuilder();
            foreach (var record in records)
                inventory.Append(Path.GetFileName(record)).Append('\0').Append(Hash(record)).Append('\n');
            return new JsonObject { ["state"] = "recorded", ["count"] = records.Length,
                ["sha256"] = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(inventory.ToString()))).ToLowerInvariant() };
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return new JsonObject { ["state"] = "unavailable" };
        }
    }

    private static JsonObject GpuDriverIdentity()
    {
        try
        {
            using var process = new Process { StartInfo = new ProcessStartInfo("nvidia-smi.exe")
            {
                UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true,
                RedirectStandardError = true
            } };
            process.StartInfo.ArgumentList.Add("--query-gpu=driver_version");
            process.StartInfo.ArgumentList.Add("--format=csv,noheader");
            if (!process.Start()) return new JsonObject { ["state"] = "unavailable" };
            if (!process.WaitForExit(2500)) { process.Kill(entireProcessTree: true); return new JsonObject { ["state"] = "unavailable" }; }
            if (process.ExitCode != 0) return new JsonObject { ["state"] = "unavailable" };
            var versions = process.StandardOutput.ReadToEnd().Split('\n', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
            if (versions.Length == 0 || versions.Any(value => !Regex.IsMatch(value, "^[0-9]+(?:\\.[0-9]+)*$")))
                return new JsonObject { ["state"] = "unavailable" };
            var digest = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(string.Join("\n", versions)))).ToLowerInvariant();
            return new JsonObject { ["state"] = "recorded", ["sha256"] = digest };
        }
        catch (Exception error) when (error is IOException or InvalidOperationException or System.ComponentModel.Win32Exception)
        {
            return new JsonObject { ["state"] = "unavailable" };
        }
    }

    private static JsonObject SuiteIdentity(string root, string runtimeId, string? recipeId)
    {
        var names = new List<string> { "BatchLauncher/Form1.Scientific.cs", "BatchLauncher/Form1.Scientific.Artifacts.cs",
            "BatchLauncher/ScientificArtifactFiles.cs", "BatchLauncher/ScientificQualificationRecords.cs",
            $"runtimes/{runtimeId}/runtime.json" };
        if (recipeId == "diagnostics") names.Add("tools/Inspect-ScientificRuntimes.ps1");
        if (recipeId == "setup.install") names.AddRange(new[] { "BatchLauncher/Form1.Scientific.Setup.cs",
            "tools/Install-ScientificRuntimes.ps1", "tools/Inspect-ScientificRuntimes.ps1",
            "tools/scientific-runtime-probe.py" });
        if (recipeId == "version") names.Add("tools/scientific-runtime-probe.py");
        if (recipeId?.StartsWith("mesh.", StringComparison.Ordinal) == true)
            names.Add("tools/scientific-mesh-worker.py");
        if (recipeId is "configure" or "build" or "run" or "test-all" or "compile-link")
        {
            var kind = runtimeId.StartsWith("cgal", StringComparison.Ordinal) ? "cgal" :
                runtimeId.StartsWith("vtk", StringComparison.Ordinal) ? "vtk" :
                runtimeId.StartsWith("gmsh", StringComparison.Ordinal) ? "gmsh" : null;
            if (kind != null) names.AddRange(new[] { $"scientific/smoke/{kind}/main.cpp", $"scientific/smoke/{kind}/CMakeLists.txt" });
            if (kind == "vtk" && recipeId == "test-all") names.Add("tools/scientific-vtk-render-check.py");
        }
        if (recipeId is "matrix.cgal.validation" or "cgal.validate" or "matrix.cgal.real-mesh")
            names.AddRange(new[] { "BatchLauncher/Form1.Scientific.Matrix.cs", "BatchLauncher/Form1.Scientific.Cgal.cs" });
        if (recipeId is "cgal.fill-one-hole" or "cgal.fill-quad-hole" or "cgal.fill-two-quad-holes" or "cgal.fill-bounded-holes")
            names.AddRange(new[] { "BatchLauncher/Form1.Scientific.Cgal.cs", "tools/scientific-cgal-hole-repair-worker.py",
                "tools/scientific_cgal_mesh_metrics.py", "scientific/cgal-worker/hole_repair.cpp" });
        if (recipeId == "integration.math3d.repair-handoff")
            names.AddRange(new[] { "BatchLauncher/Form1.Scientific.CgalRepairHandoff.cs",
                "tools/scientific-cgal-repair-math3d-handoff.py", "tools/math3d-vtk-import-handoff.mjs",
                "tools/scientific-cgal-hole-repair-worker.py", "tools/scientific_cgal_mesh_metrics.py",
                "tools/math3d-cgal-repair-product.mjs", "tools/scientific-cgal-repair-m3dm-roundtrip.py",
                "tools/math3d-cgal-repair-viewer.mjs" });
        if (recipeId == "l5.cgal-repair")
            names.AddRange(new[] { "BatchLauncher/Form1.Scientific.CgalRepairL5.cs",
                "BatchLauncher/ScientificRepairFixtures.cs", "BatchLauncher/ScientificQualificationRecords.Repair.cs",
                "scientific/fixtures/cgal-repair-qualification/manifest.json",
                "tools/scientific-cgal-hole-repair-worker.py", "scientific/cgal-worker/hole_repair.cpp" });
        if (recipeId == "l6.cgal-repair")
            names.AddRange(new[] { "BatchLauncher/Form1.Scientific.CgalRepairL5.cs",
                "BatchLauncher/Form1.Scientific.CgalRepairL6.cs", "BatchLauncher/ScientificRepairFixtures.cs",
                "BatchLauncher/ScientificQualificationRecords.Repair.cs",
                "scientific/fixtures/cgal-repair-qualification/manifest.json",
                "tools/scientific-cgal-hole-repair-worker.py", "scientific/cgal-worker/hole_repair.cpp" });
        if (recipeId == "l7.cgal-repair")
            names.AddRange(new[] { "BatchLauncher/Form1.Scientific.CgalRepairL7.cs",
                "BatchLauncher/ScientificQualificationRecords.RepairInterop.cs",
                "tools/scientific-artifact-roundtrip.py", "tools/scientific-vtk-interop.py",
                "tools/math3d-vtk-import-handoff.mjs" });
        if (recipeId == "l8.cgal-repair")
            names.AddRange(new[] { "BatchLauncher/Form1.Scientific.CgalRepairL8.cs",
                "BatchLauncher/ScientificQualificationRecords.RepairResilience.cs",
                "BatchLauncher/OwnedProcessJob.cs", "tools/scientific-vtk-interop.py" });
        if (recipeId == "matrix.cgal.real-mesh") names.Add("BatchLauncher/Form1.Scientific.RealMesh.cs");
        if (recipeId == "cgal.boolean") names.Add("BatchLauncher/Form1.Scientific.Boolean.cs");
        if (recipeId == "datasets.import") names.Add("BatchLauncher/Form1.Scientific.MeshImport.cs");
        if (recipeId == "matrix.vtk.rejections") names.Add("BatchLauncher/Form1.Scientific.VtkRejections.cs");
        if (recipeId == "integration.math3d.native-boolean")
            names.AddRange(new[] { "BatchLauncher/Form1.Scientific.Math3DIntegration.cs", "tools/compare-math3d-native-worker.mjs", "tools/math3d-native-protocol.mjs" });
        if (recipeId?.StartsWith("sage.", StringComparison.Ordinal) == true)
            names.Add("BatchLauncher/Form1.Scientific.Sage.cs");
        if (recipeId == "sage.qualify-exact") names.AddRange(new[] {
            "BatchLauncher/Form1.Scientific.SageQualification.cs", "tools/scientific-sage-qualify.py",
            "tools/scientific-sage-wsl.py", "tools/scientific-sage-worker.py",
            "schemas/scientific-sage-exact.v1.json", "BatchLauncher/ScientificQualificationRecords.Sage.cs" });
        if (recipeId == "lab.probe") names.AddRange(new[] { "BatchLauncher/Form1.Scientific.RuntimeLab.cs", "tools/runtime-lab/Program.cs" });
        if (recipeId == "l5.worker") names.AddRange(new[] { "BatchLauncher/Form1.Scientific.L5.cs", "BatchLauncher/Form1.Scientific.Cgal.cs",
            "tools/scientific-cgal-worker.py", "tools/scientific-mesh-worker.py", "tools/scientific-gmsh-worker.py", "tools/scientific_worker_contract.py" });
        if (recipeId == "l6.reproduce") names.AddRange(new[] { "BatchLauncher/Form1.Scientific.L5.cs", "BatchLauncher/Form1.Scientific.L6.cs", "BatchLauncher/Form1.Scientific.Cgal.cs",
            "tools/scientific-cgal-worker.py", "tools/scientific-mesh-worker.py", "tools/scientific_worker_contract.py", "tools/scientific-artifact-roundtrip.py" });
        if (recipeId == "l6.reproduce" && runtimeId == "gmsh-win-conda") names.AddRange(new[] {
            "tools/scientific-gmsh-worker.py", "tools/scientific-gmsh-handoff.py", "tools/scientific-gmsh-roundtrip.py" });
        if (recipeId == "l7.math3d-import") names.AddRange(new[] { "BatchLauncher/Form1.Scientific.L7.cs",
            "tools/scientific-artifact-roundtrip.py", "tools/math3d-vtk-import-handoff.mjs" });
        if (recipeId == "l7.gmsh-interop") names.AddRange(new[] { "BatchLauncher/Form1.Scientific.GmshGates.cs",
            "tools/scientific-gmsh-handoff.py", "tools/scientific-gmsh-vtk-consumer.py",
            "tools/math3d-gmsh-import-handoff.mjs" });
        if (recipeId == "l7.cgal-vtk-math3d") names.AddRange(new[] { "BatchLauncher/Form1.Scientific.L7Interop.cs",
            "tools/scientific-artifact-roundtrip.py", "tools/scientific-vtk-interop.py", "tools/math3d-vtk-import-handoff.mjs" });
        if (recipeId == "l8.resilience") names.AddRange(new[] { "BatchLauncher/Form1.Scientific.L8.cs",
            "BatchLauncher/OwnedProcessJob.cs", "tools/scientific-vtk-interop.py" });
        if (recipeId == "l8.gmsh-resilience") names.AddRange(new[] { "BatchLauncher/Form1.Scientific.GmshGates.cs",
            "BatchLauncher/OwnedProcessJob.cs", "tools/scientific-gmsh-vtk-consumer.py" });
        if (recipeId == "l9.math3d-product") names.AddRange(new[] { "BatchLauncher/Form1.Scientific.L9.cs",
            "tools/math3d-l9-product-handoff.mjs", "tools/scientific-cgal-worker.py", "tools/runtime-lab/Program.cs" });
        if (recipeId == "l9.gmsh-product") names.AddRange(new[] { "BatchLauncher/Form1.Scientific.GmshProduct.cs",
            "BatchLauncher/Form1.Scientific.L9.cs", "tools/scientific-gmsh-worker.py",
            "tools/scientific-gmsh-handoff.py", "tools/math3d-l9-product-handoff.mjs",
            "tools/scientific-gmsh-m3dm-roundtrip.py" });
        if (recipeId is "l5.gmsh-volume" or "l6.gmsh-volume" or "l7.gmsh-volume") names.AddRange(new[] {
            "BatchLauncher/Form1.Scientific.GmshVolume.cs", "BatchLauncher/ScientificQualificationRecords.GmshVolume.cs",
            "tools/scientific-broker/gmsh_volume.py", "tools/scientific-gmsh-volume-worker.py",
            "tools/scientific-gmsh-volume-handoff.py", "tools/scientific-gmsh-volume-vtk.py",
            "tools/math3d-gmsh-volume-consumer.mjs", "scientific/fixtures/gmsh/cube.geo",
            "scientific/fixtures/gmsh/tampered-cube.geo" });
        if (recipeId == "l8.gmsh-volume") names.AddRange(new[] {
            "BatchLauncher/Form1.Scientific.GmshVolume.cs", "BatchLauncher/Form1.Scientific.GmshGates.cs",
            "BatchLauncher/ScientificQualificationRecords.GmshVolume.cs", "BatchLauncher/OwnedProcessJob.cs",
            "tools/scientific-gmsh-volume-vtk.py", "tools/scientific-broker/gmsh_volume.py" });
        if (recipeId == "product-readiness.gmsh-volume") names.AddRange(new[] {
            "BatchLauncher/Form1.Scientific.GmshVolumeProduct.cs",
            "BatchLauncher/ScientificQualificationRecords.GmshVolume.cs",
            "tools/scientific-gmsh-volume-product-readiness.py" });
        if (recipeId == "l9.gmsh-volume") names.AddRange(new[] {
            "BatchLauncher/Form1.Scientific.GmshVolumeL9.cs",
            "BatchLauncher/ScientificQualificationRecords.GmshVolume.cs",
            "tools/scientific-broker/gmsh_volume.py", "tools/scientific-gmsh-tetmesh-export.py",
            "tools/math3d-gmsh-tetmesh-product.mjs", "tools/scientific-gmsh-tetmesh-roundtrip.py" });
        if (recipeId == "test-hold") names.Add("BatchLauncher/Form1.Scientific.StopTest.cs");
        var files = new JsonObject();
        foreach (var name in names.Distinct(StringComparer.Ordinal))
            files[name] = FileIdentity(Path.Combine(root, name.Replace('/', Path.DirectorySeparatorChar)));
        var revision = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(files.ToJsonString()))).ToLowerInvariant();
        return new JsonObject { ["recipeId"] = recipeId ?? "unavailable", ["schemaVersion"] = 1,
            ["revisionSha256"] = revision, ["files"] = files };
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

    private static JsonObject EnvironmentIdentity(string runtimeId, string installedRoot,
        string? runtimeReportPath, string? wslDistro)
    {
        var backend = runtimeId.EndsWith("-wsl", StringComparison.Ordinal) ? "wsl" : "windows-native";
        string? prefix = null;
        string? compilerPath = null;
        if (runtimeReportPath != null && File.Exists(runtimeReportPath))
        {
            try
            {
                var report = JsonNode.Parse(File.ReadAllText(runtimeReportPath));
                compilerPath = report?["compiler"]?["path"]?.GetValue<string>();
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
        return new JsonObject
        {
            ["backend"] = backend,
            ["os"] = RuntimeInformation.OSDescription,
            ["architecture"] = RuntimeInformation.OSArchitecture.ToString(),
            ["condaHistory"] = prefix == null ? new JsonObject { ["state"] = "unavailable" } : FileIdentity(Path.Combine(prefix, "conda-meta", "history")),
            ["condaPackageRecords"] = PackageIdentity(prefix),
            ["systemPackageRecords"] = backend == "wsl" ? new JsonObject { ["state"] = "unavailable" } : null,
            ["pythonExecutable"] = prefix == null ? new JsonObject { ["state"] = "unavailable" } : FileIdentity(Path.Combine(prefix, "python.exe")),
            ["gmshModule"] = runtimeId == "gmsh-win-conda" && prefix != null
                ? FileIdentity(Path.Combine(prefix, "Lib", "site-packages", "gmsh.py")) : null,
            ["gpuDriver"] = GpuDriverIdentity(),
            ["toolchain"] = new JsonObject
            {
                ["cmake"] = prefix == null ? new JsonObject { ["state"] = "unavailable" } : FileIdentity(CmakePath(prefix, runtimeId)),
                ["ninja"] = prefix == null ? new JsonObject { ["state"] = "unavailable" } : FileIdentity(Path.Combine(prefix, "Library", "bin", "ninja.exe")),
                ["msvcCompiler"] = compilerPath == null ? new JsonObject { ["state"] = "unavailable" } : FileIdentity(compilerPath),
                ["runtimeLab"] = FileIdentity(Path.Combine(installedRoot, "runtime-lab", "runtime-lab.exe"))
            },
            ["wslDistro"] = backend == "wsl" ? wslDistro ?? "unavailable" : null,
            ["wslProviderBinary"] = backend == "wsl" ? "unavailable from Windows host" : null
        };
    }

    public static JsonObject Capture(string runtimeId, string profileId, string sourceRoot,
        string installedRoot, string? runtimeReportPath = null, string? wslDistro = null, string? recipeId = null)
    {
        var environment = EnvironmentIdentity(runtimeId, installedRoot, runtimeReportPath, wslDistro);
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
                ["providerRegistryVersion"] = ScientificProviderRegistry.ContractVersion,
                ["runtimeManifest"] = FileIdentity(File.Exists(manifest) ? manifest : Path.Combine(sourceRoot, "runtimes", runtimeId, "runtime.json")),
                ["workerContractModule"] = FileIdentity(Path.Combine(sourceRoot, "tools", "scientific_worker_contract.py"))
            },
            ["suite"] = SuiteIdentity(sourceRoot, runtimeId, recipeId)
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

    public static void RecordWslEvidence(JsonObject captured, IList<JsonObject> executedFiles, string stderr)
    {
        if (captured["environment"] is not JsonObject environment) return;
        var sage = Regex.Match(stderr, @"\[fingerprint\] sage=([0-9a-f]{64})(?:\r?\n|$)").Groups[1].Value;
        if (sage.Length == 64)
        {
            environment["wslProviderBinary"] = new JsonObject { ["state"] = "recorded", ["sha256"] = sage };
            executedFiles.Add(new JsonObject { ["name"] = "sage", ["role"] = "wsl-provider", ["state"] = "recorded", ["sha256"] = sage });
        }
        var history = Regex.Match(stderr, @"\[fingerprint\] condaHistory=([0-9a-f]{64})(?:\r?\n|$)").Groups[1].Value;
        if (history.Length == 64)
            environment["condaHistory"] = new JsonObject { ["state"] = "recorded", ["sha256"] = history };
        var packages = Regex.Match(stderr, @"\[fingerprint\] condaPackages=([0-9a-f]{64})(?:\r?\n|$)").Groups[1].Value;
        if (packages.Length == 64)
            environment["condaPackageRecords"] = new JsonObject { ["state"] = "recorded", ["sha256"] = packages };
        var systemPackages = Regex.Match(stderr, @"\[fingerprint\] systemPackages=([0-9a-f]{64})(?:\r?\n|$)").Groups[1].Value;
        if (systemPackages.Length == 64)
            environment["systemPackageRecords"] = new JsonObject { ["state"] = "recorded", ["sha256"] = systemPackages };
        if (environment["toolchain"] is JsonObject toolchain)
            foreach (var name in new[] { "wslShell", "wslTimeout" })
            {
                var hash = Regex.Match(stderr, @"\[fingerprint\] " + name + @"=([0-9a-f]{64})(?:\r?\n|$)").Groups[1].Value;
                if (hash.Length == 64)
                    toolchain[name] = new JsonObject { ["state"] = "recorded", ["sha256"] = hash };
            }
    }

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

    public static JsonObject AssessSourceDrift(string directory, string sourceRoot, string installedRoot)
    {
        var record = JsonNode.Parse(File.ReadAllText(Path.Combine(directory, "fingerprint.json")));
        var components = record?["components"] as JsonObject;
        var runtimeId = components?["runtimeId"]?.GetValue<string>();
        if (runtimeId == null || !ScientificProviderRegistry.Providers.Any(item => item.RuntimeId == runtimeId))
            return new JsonObject { ["state"] = "unknown", ["reasons"] = new JsonArray("Provider identity is unavailable.") };
        var reasons = new JsonArray();
        var compared = 0;
        var unavailable = 0;
        void Compare(JsonNode? saved, JsonNode? current, string label)
        {
            var before = saved as JsonObject;
            var now = current as JsonObject;
            if (before?["state"]?.GetValue<string>() != "recorded") { unavailable++; return; }
            if (now?["state"]?.GetValue<string>() != "recorded") { unavailable++; return; }
            compared++;
            if (!string.Equals(before["sha256"]?.GetValue<string>(), now["sha256"]?.GetValue<string>(), StringComparison.OrdinalIgnoreCase))
                reasons.Add(label + " changed");
        }
        var savedSource = components?["source"]?["files"] as JsonObject;
        var currentSource = SourceFiles(sourceRoot, runtimeId);
        if (savedSource == null) unavailable++;
        else foreach (var (name, identity) in savedSource)
            Compare(identity, currentSource[name], "Source " + name);
        var installedManifest = Path.Combine(installedRoot, "runtimes", runtimeId, "runtime.json");
        var manifest = File.Exists(installedManifest) ? installedManifest : Path.Combine(sourceRoot, "runtimes", runtimeId, "runtime.json");
        Compare(components?["contract"]?["runtimeManifest"], FileIdentity(manifest), "Runtime contract manifest");
        Compare(components?["contract"]?["workerContractModule"], FileIdentity(Path.Combine(sourceRoot, "tools", "scientific_worker_contract.py")), "Worker contract module");
        var savedSuite = components?["suite"] as JsonObject;
        var recipeId = savedSuite?["recipeId"]?.GetValue<string>();
        if (recipeId == null) unavailable++;
        else
        {
            var currentSuite = SuiteIdentity(sourceRoot, runtimeId, recipeId);
            if (savedSuite?["schemaVersion"]?.GetValue<int>() != currentSuite["schemaVersion"]?.GetValue<int>())
                reasons.Add("Suite schema changed");
            var savedSuiteFiles = savedSuite?["files"] as JsonObject;
            var currentSuiteFiles = currentSuite["files"] as JsonObject;
            if (savedSuiteFiles == null || currentSuiteFiles == null) unavailable++;
            else foreach (var (name, identity) in savedSuiteFiles)
                Compare(identity, currentSuiteFiles[name], "Suite " + name);
            if (savedSuite?["revisionSha256"]?.GetValue<string>() != currentSuite["revisionSha256"]?.GetValue<string>()
                && reasons.Count == 0)
                reasons.Add("Suite revision changed");
        }
        return new JsonObject { ["state"] = reasons.Count > 0 ? "stale" : unavailable > 0 ? "unknown" : "current",
            ["comparedFiles"] = compared, ["unavailableFiles"] = unavailable, ["reasons"] = reasons };
    }

    public static JsonObject AssessEnvironmentDrift(string directory, string installedRoot, string? runtimeReportPath,
        string? wslDistro = null, string? wslEvidence = null)
    {
        var record = JsonNode.Parse(File.ReadAllText(Path.Combine(directory, "fingerprint.json")));
        var components = record?["components"] as JsonObject;
        var runtimeId = components?["runtimeId"]?.GetValue<string>();
        var saved = components?["environment"] as JsonObject;
        if (runtimeId == null || saved == null || !ScientificProviderRegistry.Providers.Any(item => item.RuntimeId == runtimeId))
            return new JsonObject { ["state"] = "unknown", ["comparedComponents"] = 0,
                ["unavailableComponents"] = 1, ["reasons"] = new JsonArray("Environment identity is unavailable.") };
        var current = EnvironmentIdentity(runtimeId, installedRoot, runtimeReportPath, wslDistro);
        if (runtimeId.EndsWith("-wsl", StringComparison.Ordinal) && wslEvidence != null)
            RecordWslEvidence(new JsonObject { ["environment"] = current }, new List<JsonObject>(), wslEvidence);
        var reasons = new JsonArray();
        var compared = 0;
        var unavailable = 0;
        void CompareValue(string name)
        {
            var before = saved[name]?.GetValue<string>();
            var now = current[name]?.GetValue<string>();
            if (before == null || now == null) { unavailable++; return; }
            compared++;
            if (!string.Equals(before, now, StringComparison.Ordinal)) reasons.Add(name + " changed");
        }
        void CompareHash(JsonNode? beforeNode, JsonNode? nowNode, string name)
        {
            var before = beforeNode as JsonObject;
            var now = nowNode as JsonObject;
            if (before?["state"]?.GetValue<string>() != "recorded" || now?["state"]?.GetValue<string>() != "recorded")
            { unavailable++; return; }
            compared++;
            if (!string.Equals(before["sha256"]?.GetValue<string>(), now["sha256"]?.GetValue<string>(), StringComparison.OrdinalIgnoreCase))
                reasons.Add(name + " changed");
        }
        foreach (var name in new[] { "backend", "os", "architecture" }) CompareValue(name);
        if (runtimeId.EndsWith("-wsl", StringComparison.Ordinal))
        {
            CompareValue("wslDistro");
            CompareHash(saved["wslProviderBinary"], current["wslProviderBinary"], "WSL provider");
            var packageFields = new[] { "condaPackageRecords", "systemPackageRecords" }
                .Where(name => saved[name]?["state"]?.GetValue<string>() == "recorded").ToArray();
            if (packageFields.Length == 0) unavailable++;
            foreach (var name in packageFields) CompareHash(saved[name], current[name], name);
            foreach (var name in new[] { "wslShell", "wslTimeout", "runtimeLab" })
                CompareHash(saved["toolchain"]?[name], current["toolchain"]?[name], "toolchain " + name);
            if (wslEvidence == null) reasons.Add("Current WSL evidence could not be collected");
        }
        else
        {
            foreach (var name in new[] { "condaHistory", "condaPackageRecords", "pythonExecutable" })
                CompareHash(saved[name], current[name], name);
            if (runtimeId == "gmsh-win-conda") CompareHash(saved["gmshModule"], current["gmshModule"], "Gmsh Python binding");
            var toolNames = runtimeId is "cgal-win-conda" or "vtk-win-conda"
                ? new[] { "cmake", "ninja", "msvcCompiler", "runtimeLab" }
                : runtimeId == "gmsh-win-conda" ? new[] { "cmake", "msvcCompiler", "runtimeLab" }
                : new[] { "runtimeLab" };
            foreach (var name in toolNames)
                CompareHash(saved["toolchain"]?[name], current["toolchain"]?[name], "toolchain " + name);
        }
        if (saved["gpuDriver"]?["state"]?.GetValue<string>() == "recorded")
            CompareHash(saved["gpuDriver"], current["gpuDriver"], "gpuDriver");
        return new JsonObject { ["state"] = reasons.Any(item => item?.GetValue<string>()?.EndsWith(" changed", StringComparison.Ordinal) == true)
                ? "stale" : unavailable > 0 ? "unknown" : "current",
            ["comparedComponents"] = compared, ["unavailableComponents"] = unavailable, ["reasons"] = reasons };
    }
}
