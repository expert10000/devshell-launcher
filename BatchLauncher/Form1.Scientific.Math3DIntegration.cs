using System.Diagnostics;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace BatchLauncher;

public partial class Form1
{
    private sealed record Math3DCheck(string Id, string Label, bool Ready, bool CanPrepare, string Detail);
    private sealed record Math3DReadiness(bool Ready, bool CanPrepare, Math3DCheck[] Checks);
    private string Math3DCheckout => Path.Combine(_workspace.Globals?.WorkspaceRoot ?? Path.GetDirectoryName(ScientificRepositoryRoot())!, "Math3D");
    private static string Math3DWorker => Path.Combine(ScientificDataRoot, "builds", "math3d-native-worker", "Release", "math3d-cgal-worker.exe");
    private string Math3DNode => EnvironmentTools().TryGetValue("node", out var node) && File.Exists(node) ? node : ScientificExecutable("node.exe");

    private Math3DReadiness ScientificMath3DReadiness(string profileId)
    {
        var checks = new List<Math3DCheck>();
        void Check(string id, string label, Func<string> inspect, bool repair = false)
        {
            try { checks.Add(new(id, label, true, true, inspect())); }
            catch (Exception exception) when (exception is IOException or InvalidOperationException or JsonException or KeyNotFoundException or UnauthorizedAccessException or ArgumentException)
            { checks.Add(new(id, label, false, repair, exception.Message)); }
        }
        string Require(string file, string help) => File.Exists(file) ? file : throw new InvalidOperationException(help);
        Check("node", "Node.js", () => Math3DNode);
        Check("harness", "Boolean test harness", () => {
            foreach (var name in new[] { "compare-math3d-native-worker.mjs", "math3d-boolean-fixtures.mjs", "math3d-mesh-comparison.mjs", "math3d-native-protocol.mjs" })
                Require(Path.Combine(ScientificSourceRoot, "tools", name), "Rebuild DevShell: the Boolean test harness is missing.");
            return "Installed";
        });
        string? prefix = null;
        Check("environment", "Dedicated CGAL environment", () => {
            prefix = ScientificPrefix("cgal-win-conda");
            Require(Path.Combine(prefix, "python.exe"), "Install the dedicated CGAL environment from Environment setup.");
            Require(Path.Combine(prefix, "Library", "bin", "cmake.exe"), "Install CMake in the dedicated CGAL environment.");
            Require(Path.Combine(prefix, "Library", "lib", "cmake", "CGAL", "CGALConfig.cmake"), "Install the CGAL C++ SDK in the dedicated environment.");
            return prefix;
        });
        Check("compiler", "Visual Studio C++ compiler", () => {
            var compiler = ScientificReport().GetProperty("compiler");
            return Require(compiler.GetProperty("path").GetString() ?? "", "Install Visual Studio 2022 C++ Build Tools, then refresh the local runtime report.");
        });
        Check("adapter", "Validation adapter", () => {
            Require(Path.Combine(AppContext.BaseDirectory, "runtime-lab", "runtime-lab.exe"), "Rebuild DevShell to install runtime-lab.");
            Require(Path.Combine(ScientificSourceRoot, "scientific", "cgal-worker", "CMakeLists.txt"), "Rebuild DevShell to install the CGAL validation worker sources.");
            return "Installed";
        });
        var source = Path.Combine(Math3DCheckout, "native", "cgal-worker", "CMakeLists.txt");
        Check("worker", "MATH3D native worker", () => Require(Math3DWorker, "Native worker will be configured and built from the local MATH3D checkout."), File.Exists(source));
        foreach (var id in ScientificMath3DPreparation.DatasetIds)
        {
            JsonObject? input = null;
            var name = Path.GetFileName(id);
            Check(id, name + " local copy", () => { input = ScientificDatasetArtifact(id); return "Registered SHA-256 verified"; },
                File.Exists(Path.Combine(Math3DCheckout, "tests", "assets", "meshes", "basic", name)));
            Check(id + ":baseline", name + " validation baseline", () => {
                if (input == null || prefix == null) throw new InvalidOperationException("Prepare the local fixture and CGAL environment first.");
                return ScientificMath3DPreparation.FindBaseline(ScientificDataRoot, profileId, prefix, input)
                    ?? throw new InvalidOperationException("A matching validation baseline will be created for this profile.");
            }, true);
        }
        var items = checks.ToArray();
        return new(items.All(item => item.Ready), items.All(item => item.Ready || item.CanPrepare), items);
    }

    private object ScientificMath3DIntegrationStart(string profileId, string runtimeId, bool prepare = false)
    {
        if (runtimeId != "cgal-win-conda") throw new InvalidOperationException("The MATH3D integration test requires the Windows Native CGAL runtime.");
        var readiness = ScientificMath3DReadiness(profileId);
        if (prepare ? !readiness.CanPrepare : !readiness.Ready)
            throw new InvalidOperationException(string.Join(" ", readiness.Checks.Where(item => !item.Ready && (!prepare || !item.CanPrepare)).Select(item => item.Label + ": " + item.Detail)));
        var prefix = ScientificPrefix(runtimeId);
        var node = Math3DNode;
        if (!_scientificGate.Wait(0)) throw new InvalidOperationException("Another Scientific job is running; stop or wait for it.");
        try
        {
            var runId = Guid.NewGuid().ToString("N");
            var directory = Path.Combine(ScientificDataRoot, "runs", runId);
            Directory.CreateDirectory(directory);
            var job = new ScientificJob { Id = runId, ProfileId = profileId, RuntimeId = runtimeId,
                RecipeId = "integration.math3d.native-boolean", Directory = directory };
            ScientificWriteRequest(job, JsonSerializer.SerializeToElement(new { prepare }));
            _scientificJobs[profileId + ":" + runtimeId] = job;
            ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) });
            _ = ScientificMath3DIntegrationRunAsync(job, prefix, node, prepare);
            return ScientificJobSnapshot(job);
        }
        catch { _scientificGate.Release(); throw; }
    }

    private async Task ScientificMath3DPrepareAsync(ScientificJob suite, string prefix)
    {
        foreach (var id in ScientificMath3DPreparation.DatasetIds)
        {
            suite.Cancellation.Token.ThrowIfCancellationRequested();
            try { ScientificDatasetArtifact(id); }
            catch (Exception exception) when (exception is IOException or InvalidOperationException or JsonException or KeyNotFoundException)
            {
                suite.Stage = "prepare: " + Path.GetFileName(id);
                ScientificLog(suite, "Preparing registered local copy: " + id + "\n");
                ScientificMath3DPreparation.ImportFixture(ScientificDataRoot, Math3DCheckout, id);
            }
        }
        var source = Path.Combine(Math3DCheckout, "native", "cgal-worker");
        if (File.Exists(Path.Combine(source, "CMakeLists.txt")))
        {
            ScientificLog(suite, "Preparing MATH3D native worker...\n");
            var build = Path.GetDirectoryName(Path.GetDirectoryName(Math3DWorker))!;
            var cmake = Path.Combine(prefix, "Library", "bin", "cmake.exe");
            await ScientificProcessAsync(suite, prefix, cmake, new[] { "-S", source, "-B", build, "-G", "Visual Studio 17 2022", "-A", "x64", "-DCMAKE_PREFIX_PATH=" + Path.Combine(prefix, "Library") }, suite.Directory, 180);
            await ScientificProcessAsync(suite, prefix, cmake, new[] { "--build", build, "--config", "Release", "--parallel", "1" }, suite.Directory, 600);
        }
        foreach (var id in ScientificMath3DPreparation.DatasetIds)
        {
            suite.Cancellation.Token.ThrowIfCancellationRequested();
            var input = ScientificDatasetArtifact(id);
            var baseline = ScientificMath3DPreparation.FindBaseline(ScientificDataRoot, suite.ProfileId, prefix, input);
            if (baseline != null) { ScientificLog(suite, "Reusing baseline " + baseline + " for " + id + "\n"); continue; }
            var directory = Path.Combine(ScientificDataRoot, "runs", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(directory);
            var child = new ScientificJob { ProfileId = suite.ProfileId, RuntimeId = suite.RuntimeId, RecipeId = "cgal.validate", Directory = directory, Cancellation = suite.Cancellation };
            ScientificWriteRequest(child, JsonSerializer.SerializeToElement(new { inputId = id, outputName = "integration-baseline.obj" }), input, "integration-baseline.obj");
            ScientificLog(suite, "Preparing validation baseline for " + id + " / run " + child.Id + "\n");
            var timer = Stopwatch.StartNew();
            _scientificJobs[suite.ProfileId + ":" + suite.RuntimeId] = child;
            try { await ScientificCgalExecuteAsync(child, prefix); child.State = "succeeded"; child.Stage = "completed"; }
            catch (OperationCanceledException) { child.State = "cancelled"; child.Stage = "stopped"; throw; }
            catch (Exception exception) { child.State = "failed"; child.Error = exception.Message; throw; }
            finally
            {
                child.DurationMs = timer.ElapsedMilliseconds;
                ScientificFinish(child);
                _scientificJobs[suite.ProfileId + ":" + suite.RuntimeId] = suite;
                ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(suite) });
            }
        }
    }

    private async Task ScientificMath3DIntegrationRunAsync(ScientificJob job, string prefix, string node, bool prepare)
    {
        await Task.Yield();
        var timer = Stopwatch.StartNew();
        try
        {
            if (prepare) await ScientificMath3DPrepareAsync(job, prefix);
            job.Cancellation.Token.ThrowIfCancellationRequested();
            var readiness = ScientificMath3DReadiness(job.ProfileId);
            if (!readiness.Ready) throw new InvalidOperationException(string.Join(" ", readiness.Checks.Where(item => !item.Ready).Select(item => item.Detail)));
            var outputs = new JsonArray(ScientificMath3DPreparation.Outputs.Skip(1).Select(path => (JsonNode)new JsonObject { ["path"] = path, ["mediaType"] = "application/octet-stream" }).ToArray());
            ScientificWriteRequest(job, JsonSerializer.SerializeToElement(new { prepare }), ScientificDatasetArtifact(ScientificMath3DPreparation.DatasetIds[0]),
                ScientificMath3DPreparation.Outputs[0], new JsonArray(ScientificDatasetArtifact(ScientificMath3DPreparation.DatasetIds[1])), outputs);
            await ScientificProcessAsync(job, prefix, node, new[] { Path.Combine(ScientificSourceRoot, "tools", "compare-math3d-native-worker.mjs"), Math3DWorker, job.Directory, job.ProfileId }, job.Directory, 120);
            using var saved = JsonDocument.Parse(File.ReadAllText(Path.Combine(job.Directory, "results.json")));
            if (!saved.RootElement.TryGetProperty("comparison", out var comparison) || !comparison.TryGetProperty("verdict", out var verdict) || verdict.GetString() != "pass")
                throw new InvalidOperationException("MATH3D integration comparison did not pass; see the saved result and log.");
            job.State = "succeeded"; job.Stage = "completed";
        }
        catch (OperationCanceledException) { job.State = "cancelled"; job.Stage = "stopped"; job.Error = "The owned MATH3D preparation/integration job was stopped."; }
        catch (TimeoutException exception) { job.State = "timed-out"; job.Stage = "timed-out"; job.Error = exception.Message; }
        catch (Exception exception) { job.State = "failed"; job.Stage = "failed"; job.Error = exception.Message; }
        finally
        {
            job.DurationMs = timer.ElapsedMilliseconds;
            try { ScientificFinish(job); ScientificLog(job, $"\n[{job.State}] {job.DurationMs} ms {job.Error}\n"); }
            catch (Exception exception) { Debug.WriteLine($"MATH3D integration finalization failed: {exception}"); }
            finally { _scientificJobs[job.ProfileId + ":" + job.RuntimeId] = job; ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) }); _scientificGate.Release(); }
        }
    }
}
