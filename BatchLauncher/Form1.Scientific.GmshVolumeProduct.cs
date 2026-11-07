using System.Diagnostics;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace BatchLauncher;

public partial class Form1
{
    private object ScientificGmshVolumeProductReadinessStart(string profileId, string runtimeId)
    {
        ScientificProviderRegistry.RequireAction(runtimeId, "gmsh-volume-product-readiness");
        var summary = ScientificQualificationSummary(profileId, runtimeId);
        var support = summary["currentRecords"]?.AsArray().OfType<JsonObject>()
            .Where(item => item["capabilityId"]?.GetValue<string>() == "mesh.generate3d"
                && item["level"]?.GetValue<string>() == "L8")
            .OrderByDescending(item => item["finishedAtUtc"]?.GetValue<string>(), StringComparer.Ordinal)
            .FirstOrDefault() ?? throw new InvalidOperationException("Current Gmsh volume L8 evidence is required.");
        var (supportDirectory, supportElement) = ScientificHistoryFind(profileId, support["runId"]!.GetValue<string>());
        if (!ScientificQualificationRecords.Verify(supportDirectory, supportElement).OfType<JsonObject>().Any(item =>
            item["recordId"]?.GetValue<string>() == support["recordId"]?.GetValue<string>()
            && item["level"]?.GetValue<string>() == "L8"))
            throw new InvalidDataException("Gmsh volume L8 support is not verified.");
        var l8 = JsonNode.Parse(supportElement.GetRawText())?["l8GmshVolumeEvidence"];
        var l7Folder = l8?["sourceL7FolderId"]?.GetValue<string>();
        if (l7Folder is not { Length: 32 } || !l7Folder.All(Uri.IsHexDigit))
            throw new InvalidDataException("The volume L7 source is missing.");
        var l7Directory = Path.Combine(Path.GetDirectoryName(supportDirectory)!, l7Folder);
        var msh = Path.Combine(l7Directory, "volume", "positive-a", "cube.msh");
        var l7 = JsonNode.Parse(File.ReadAllText(Path.Combine(l7Directory, "results.json")));
        if (!File.Exists(msh) || ScientificHash(msh) != l7?["volumeEvidence"]?["artifactSha256"]?.GetValue<string>()
            || l7["volumeEvidence"]?["reload"]?["tetrahedra"]?.GetValue<int>() is not > 5)
            throw new InvalidDataException("The tetrahedral source artifact changed.");
        if (!_scientificGate.Wait(0)) throw new InvalidOperationException("Another Scientific job is running.");
        try
        {
            var directory = Path.Combine(ScientificDataRoot, "runs", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(directory);
            var job = new ScientificJob { ProfileId = profileId, RuntimeId = runtimeId,
                RecipeId = "product-readiness.gmsh-volume", Directory = directory };
            var input = new JsonObject { ["path"] = msh, ["mediaType"] = "application/vnd.gmsh.msh",
                ["bytes"] = new FileInfo(msh).Length, ["sha256"] = ScientificHash(msh),
                ["sourceRunId"] = l7?["runId"]?.GetValue<string>() };
            var parameters = JsonSerializer.SerializeToElement(new { suiteId = "gmsh-volume-product-readiness-v1",
                sourceL8RunId = support["runId"]?.GetValue<string>(),
                sourceL8RecordId = support["recordId"]?.GetValue<string>() }, ScientificJson);
            var outputs = new JsonArray(new JsonObject { ["path"] = "readiness.json", ["mediaType"] = "application/json" });
            ScientificWriteRequest(job, parameters, input, additionalOutputs: outputs);
            _scientificJobs[profileId + ":" + runtimeId] = job;
            ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) });
            _ = ScientificGmshVolumeProductReadinessRunAsync(job, msh, support, l8!, l7!);
            return ScientificJobSnapshot(job);
        }
        catch { _scientificGate.Release(); throw; }
    }

    private async Task ScientificGmshVolumeProductReadinessRunAsync(ScientificJob job, string msh,
        JsonObject support, JsonNode l8, JsonNode l7)
    {
        var timer = Stopwatch.StartNew();
        try
        {
            var checkout = ScientificL7Checkout();
            var prefix = ScientificPrefix(job.RuntimeId);
            var reportPath = Path.Combine(job.Directory, "readiness.json");
            job.Stage = "product-contract-check";
            await ScientificProcessAsync(job, prefix, Path.Combine(prefix, "python.exe"),
                [Path.Combine(ScientificSourceRoot, "tools", "scientific-gmsh-volume-product-readiness.py"),
                    "--msh", msh, "--checkout", checkout, "--result", reportPath], job.Directory, 30);
            var report = JsonNode.Parse(File.ReadAllText(reportPath))?.AsObject()
                ?? throw new InvalidDataException("Volume product readiness report is missing.");
            if (report["sourceMshSha256"]?.GetValue<string>() != ScientificHash(msh)
                || report["status"]?.GetValue<string>() is not ("blocked" or "ready-for-l9"))
                throw new InvalidDataException("Volume product readiness source or status changed.");
            report["sourceL8RunId"] = support["runId"]?.GetValue<string>();
            report["sourceL8RecordId"] = support["recordId"]?.GetValue<string>();
            report["sourceL7RunId"] = l8["sourceL7RunId"]?.GetValue<string>();
            report["tetrahedra"] = l7["volumeEvidence"]?["reload"]?["tetrahedra"]?.GetValue<int>();
            File.WriteAllText(reportPath, report.ToJsonString(), new UTF8Encoding(false));
            File.WriteAllText(Path.Combine(job.Directory, "results.json"), new JsonObject {
                ["volumeProductReadiness"] = report.DeepClone(), ["validatedCapabilities"] = new JsonArray()
            }.ToJsonString(), new UTF8Encoding(false));
            job.State = "succeeded"; job.Stage = report["status"]?.GetValue<string>() == "ready-for-l9"
                ? "ready-for-l9-check" : "blocked-volume-product";
        }
        catch (Exception error) { job.State = "failed"; job.Error = error.Message; }
        finally
        {
            job.DurationMs = timer.ElapsedMilliseconds;
            try { ScientificFinish(job); ScientificLog(job, $"\n[{job.State}] Gmsh volume product readiness / {job.DurationMs} ms {job.Error}\n"); }
            catch (Exception error) { Debug.WriteLine($"Gmsh volume readiness finalization failed: {error}"); }
            finally { ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) }); _scientificGate.Release(); }
        }
    }
}
