using System.Diagnostics;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace BatchLauncher;

public partial class Form1
{
    private object ScientificRealMeshStart(string profileId, string runtimeId, JsonElement request)
    {
        if (runtimeId != "cgal-win-conda")
            throw new InvalidOperationException("The real-mesh suite requires Windows Native CGAL.");
        var cgalPrefix = ScientificPrefix(runtimeId);
        var vtkPrefix = ScientificPrefix("vtk-win-conda");
        var configured = (_workspace.Projects ?? new()).SelectMany(project =>
            (project.Repositories ?? new())
                .Where(repo => string.Equals(repo.Id, "math3d", StringComparison.OrdinalIgnoreCase))
                .Select(repo => new { Project = project, Repository = repo }))
            .FirstOrDefault();
        if (configured == null)
            throw new InvalidOperationException("Configure a local Math3D repository before running the real-mesh suite.");
        var configuredPath = ExpandProjectValue(configured.Project, configured.Repository.Path ?? "");
        if (string.IsNullOrWhiteSpace(configuredPath) || configuredPath.Contains("${", StringComparison.Ordinal))
            throw new InvalidOperationException("The configured Math3D repository path contains an unresolved project variable.");
        var candidate = Path.GetFullPath(configuredPath);
        const string scriptRelativePath = "scripts/qualify-cgal-native-real-mesh.py";
        var repository = File.Exists(Path.Combine(candidate, scriptRelativePath))
            ? candidate : Path.GetFullPath(Path.Combine(candidate, "Math3D"));
        var script = Path.Combine(repository, "scripts", "qualify-cgal-native-real-mesh.py");
        var worker = Path.Combine(ScientificDataRoot, "builds", "math3d-native-worker", "Release", "math3d-cgal-worker.exe");
        if (!File.Exists(script))
            throw new FileNotFoundException($"The configured Math3D location '{candidate}' has no real-mesh qualification script. Select the Math3D repository or its parent folder.");
        if (!File.Exists(worker))
            throw new FileNotFoundException("Build the MATH3D native worker before running the real-mesh suite.");
        var sources = new[] { "11_armadillo.obj", "10_3dbenchy.stl" };
        foreach (var source in sources)
        {
            var path = Path.Combine(repository, "tests", "assets", "meshes", "standard", source);
            if (!File.Exists(path) || new FileInfo(path).Length > 33554432)
                throw new InvalidOperationException($"Real-mesh fixture {source} is missing or exceeds 32 MiB.");
        }
        var recordedVersion = ScientificReport().GetProperty("runtimes").EnumerateArray()
            .First(item => item.GetProperty("id").GetString() == runtimeId).GetProperty("version").GetString() ?? "unknown";
        if (!_scientificGate.Wait(0))
            throw new InvalidOperationException("Another Scientific job is running; stop or wait for it.");
        try
        {
            var runId = Guid.NewGuid().ToString("N");
            var directory = Path.Combine(ScientificDataRoot, "runs", runId);
            var inputs = Path.Combine(directory, "inputs");
            Directory.CreateDirectory(inputs);
            var inputArtifacts = new JsonArray();
            foreach (var source in sources)
            {
                var original = Path.Combine(repository, "tests", "assets", "meshes", "standard", source);
                var copy = Path.Combine(inputs, source);
                File.Copy(original, copy);
                inputArtifacts.Add(new JsonObject { ["path"] = copy, ["sha256"] = ScientificHash(copy),
                    ["bytes"] = new FileInfo(copy).Length, ["sourcePath"] = original, ["mediaType"] = ScientificMediaType(copy) });
            }
            var outputs = new JsonArray();
            foreach (var name in new[] { "armadillo-shift", "armadillo-rotated", "3dbenchy-cutter", "3dbenchy-second-cutter" })
                foreach (var operation in new[] { "union", "intersection", "difference" })
                    outputs.Add(new JsonObject { ["path"] = name + "-" + operation + ".obj", ["mediaType"] = "model/obj" });
            var job = new ScientificJob { Id = runId, ProfileId = profileId, RuntimeId = runtimeId,
                RecipeId = "matrix.cgal.real-mesh", Directory = directory };
            var parameters = JsonSerializer.SerializeToElement(new { models = new[] { "Armadillo", "3DBenchy" },
                operationSeconds = 90, totalSeconds = 540, maxPayloadMiB = 64 }, ScientificJson);
            ScientificWriteRequest(job, parameters, null, null, inputArtifacts, outputs, 600);
            _scientificJobs[profileId + ":" + runtimeId] = job;
            ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) });
            _ = ScientificRealMeshRunAsync(job, vtkPrefix, cgalPrefix, script, worker, recordedVersion);
            return ScientificJobSnapshot(job);
        }
        catch { _scientificGate.Release(); throw; }
    }

    private async Task ScientificRealMeshRunAsync(ScientificJob job, string vtkPrefix, string cgalPrefix,
        string script, string worker, string recordedVersion)
    {
        var timer = Stopwatch.StartNew();
        try
        {
            await ScientificProcessAsync(job, vtkPrefix, Path.Combine(vtkPrefix, "python.exe"), new[] {
                script, "--worker", worker, "--assets-dir", Path.Combine(job.Directory, "inputs"),
                "--output-dir", job.Directory, "--operation-seconds", "90", "--total-seconds", "540",
                "--max-payload-mb", "64", "--recorded-cgal-version", recordedVersion
            }, job.Directory, 600, Path.Combine(cgalPrefix, "Library", "bin"));
            using var saved = JsonDocument.Parse(File.ReadAllText(Path.Combine(job.Directory, "results.json")));
            var suite = saved.RootElement.GetProperty("realMeshSuite");
            if (suite.GetProperty("passed").GetInt32() != suite.GetProperty("total").GetInt32())
                throw new InvalidOperationException("Real-mesh suite recorded failed cases; inspect diagnostics.");
            job.State = "succeeded"; job.Stage = "completed";
        }
        catch (OperationCanceledException) { job.State = "cancelled"; job.Stage = "stopped"; job.Error = "The owned real-mesh suite was stopped."; }
        catch (TimeoutException exception) { job.State = "timed-out"; job.Stage = "timed-out"; job.Error = exception.Message; }
        catch (Exception exception) { job.State = "failed"; job.Stage = "failed"; job.Error = exception.Message; }
        finally
        {
            job.DurationMs = timer.ElapsedMilliseconds;
            try { ScientificFinish(job); ScientificLog(job, $"\n[{job.State}] {job.DurationMs} ms {job.Error}\n"); }
            catch (Exception exception) { Debug.WriteLine($"Real-mesh suite finalization failed: {exception}"); }
            finally { ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) }); _scientificGate.Release(); }
        }
    }
}
