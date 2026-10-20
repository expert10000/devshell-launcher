using System.Diagnostics;
using System.Text;
using System.Text.Json;

namespace BatchLauncher;

public partial class Form1
{
    private sealed record ScientificVtkRejectionCase(string Id, string RecipeId, string DatasetId,
        string OutputName, object Parameters, string ExpectedReason);

    private static ScientificVtkRejectionCase[] ScientificVtkRejectionCases() =>
    [
        new("read-truncated-ply", "mesh.inspect", "math3d/import/truncated-ascii.ply",
            "rejected-read.vtp", new { }, "surface is empty"),
        new("write-unsafe-path", "mesh.inspect", "math3d/basic/01_tetrahedron.obj",
            "../escape.vtp", new { }, "Output must be a safe mesh basename"),
        new("simplify-invalid-reduction", "mesh.simplify", "math3d/basic/05_torus.obj",
            "rejected-simplify.vtp", new { targetReduction = 1.2 }, "Target reduction must be between 0 and 0.95"),
        new("normals-open-auto-orient", "mesh.normals", "math3d/import/triangle.obj",
            "rejected-normals.vtp", new { autoOrient = true }, "Auto orientation requires a closed manifold surface")
    ];

    private object ScientificVtkRejectionsStart(string profileId, string runtimeId)
    {
        if (runtimeId != "vtk-win-conda")
            throw new InvalidOperationException("The VTK rejection suite requires Windows Native VTK.");
        var prefix = ScientificPrefix(runtimeId);
        foreach (var test in ScientificVtkRejectionCases()) ScientificDatasetArtifact(test.DatasetId);
        if (!_scientificGate.Wait(0))
            throw new InvalidOperationException("Another Scientific job is running; stop or wait for it.");
        try
        {
            var directory = Path.Combine(ScientificDataRoot, "runs", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(directory);
            var job = new ScientificJob { ProfileId = profileId, RuntimeId = runtimeId,
                RecipeId = "matrix.vtk.rejections", Directory = directory };
            ScientificWriteRequest(job, JsonSerializer.SerializeToElement(new
            {
                suiteId = "vtk-rejections-v1", caseCount = ScientificVtkRejectionCases().Length
            }, ScientificJson));
            _scientificJobs[profileId + ":" + runtimeId] = job;
            ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) });
            _ = ScientificVtkRejectionsRunAsync(job, prefix);
            return ScientificJobSnapshot(job);
        }
        catch { _scientificGate.Release(); throw; }
    }

    private async Task ScientificVtkRejectionsRunAsync(ScientificJob suite, string prefix)
    {
        var timer = Stopwatch.StartNew();
        var cases = ScientificVtkRejectionCases();
        var outcomes = new List<object>();
        var passed = 0;
        try
        {
            foreach (var test in cases)
            {
                suite.Cancellation.Token.ThrowIfCancellationRequested();
                suite.Stage = "case: " + test.Id;
                ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(suite) });
                var directory = Path.Combine(suite.Directory, test.Id);
                Directory.CreateDirectory(directory);
                var artifact = ScientificDatasetArtifact(test.DatasetId);
                var requestJob = new ScientificJob { ProfileId = suite.ProfileId, RuntimeId = suite.RuntimeId,
                    RecipeId = test.RecipeId, Directory = directory };
                var parameters = JsonSerializer.SerializeToElement(test.Parameters, ScientificJson);
                ScientificWriteRequest(requestJob, parameters, artifact, test.OutputName);
                var caseTimer = Stopwatch.StartNew();
                var exitRejected = false;
                try
                {
                    await ScientificProcessAsync(suite, prefix, Path.Combine(prefix, "python.exe"),
                        [Path.Combine(ScientificSourceRoot, "tools", "scientific-mesh-worker.py"),
                            "--request", Path.Combine(directory, "request.json")], directory, 120);
                }
                catch (InvalidOperationException) { exitRejected = suite.ExitCode is > 0; }
                var resultPath = Path.Combine(directory, "results.json");
                var resultSaved = File.Exists(resultPath) && new FileInfo(resultPath).Length <= 65536;
                var state = "missing";
                var diagnostic = "No structured result was saved.";
                if (resultSaved)
                {
                    using var document = JsonDocument.Parse(File.ReadAllText(resultPath));
                    var result = document.RootElement;
                    state = result.GetProperty("state").GetString() ?? "missing";
                    diagnostic = string.Join("; ", result.GetProperty("diagnostics").EnumerateArray()
                        .Select(item => item.GetProperty("message").GetString()));
                }
                var outputAbsent = !File.Exists(Path.Combine(directory, Path.GetFileName(test.OutputName)))
                    && (test.Id != "write-unsafe-path" || !File.Exists(Path.Combine(suite.Directory, "escape.vtp")));
                var accepted = exitRejected && state == "failed" && outputAbsent
                    && diagnostic.Contains(test.ExpectedReason, StringComparison.OrdinalIgnoreCase);
                if (accepted) passed++;
                outcomes.Add(new { caseId = test.Id, recipeId = test.RecipeId, expected = "rejected",
                    observed = state, verdict = accepted ? "pass" : "fail", durationMs = caseTimer.ElapsedMilliseconds,
                    diagnostic, inputSha256 = artifact["sha256"]?.GetValue<string>(),
                    requestPath = test.Id + "/request.json", resultPath = resultSaved ? test.Id + "/results.json" : null });
                ScientificLog(suite, $"\n{test.Id}: {(accepted ? "PASS" : "FAIL")} ({state}) — {diagnostic}\n");
            }
            suite.State = passed == cases.Length ? "succeeded" : "failed";
            suite.Stage = "completed";
            if (suite.State == "failed") suite.Error = $"{passed}/{cases.Length} VTK rejection cases passed.";
        }
        catch (OperationCanceledException) { suite.State = "cancelled"; suite.Stage = "stopped"; suite.Error = "The owned VTK rejection suite was stopped."; }
        catch (TimeoutException exception) { suite.State = "timed-out"; suite.Stage = "timed-out"; suite.Error = exception.Message; }
        catch (Exception exception) { suite.State = "failed"; suite.Stage = "failed"; suite.Error = exception.Message; }
        finally
        {
            suite.DurationMs = timer.ElapsedMilliseconds;
            try
            {
                File.WriteAllText(Path.Combine(suite.Directory, "results.json"), JsonSerializer.Serialize(new
                {
                    rejectionSummary = new { suiteId = "vtk-rejections-v1", total = cases.Length, passed, cases = outcomes }
                }, ScientificJson), new UTF8Encoding(false));
                ScientificFinish(suite);
                ScientificLog(suite, $"\n[{suite.State}] {passed}/{cases.Length} passed in {suite.DurationMs} ms\n");
            }
            catch (Exception exception) { Debug.WriteLine($"VTK rejection suite finalization failed: {exception}"); }
            finally
            {
                ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(suite) });
                _scientificGate.Release();
            }
        }
    }
}
