using System.Diagnostics;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace BatchLauncher;

public partial class Form1
{
    private JsonObject ScientificCurrentL8Product(string profileId)
    {
        var summary = ScientificQualificationSummary(profileId, "cgal-win-conda");
        var record = summary["currentRecords"]?.AsArray().OfType<JsonObject>()
            .Where(item => item["capabilityId"]?.GetValue<string>() == "mesh.interop.vtk-math3d"
                && item["level"]?.GetValue<string>() == "L8")
            .OrderByDescending(item => item["finishedAtUtc"]?.GetValue<string>(), StringComparer.Ordinal)
            .FirstOrDefault();
        if (record == null) throw new InvalidOperationException("A current CGAL L8 mesh qualification is required before L9.");
        return new JsonObject { ["runId"] = record["runId"]?.GetValue<string>(),
            ["recordId"] = record["recordId"]?.GetValue<string>(),
            ["capabilityId"] = "mesh.interop.vtk-math3d", ["level"] = "L8" };
    }

    private static JsonObject ScientificL9Contract() => new()
    {
        ["id"] = "math3d.mesh-product-handoff", ["version"] = 1,
        ["workerResultSchemaVersion"] = 1, ["meshDocumentSchemaVersion"] = 1,
        ["inputFormat"] = "obj", ["viewer"] = "MeshDocumentViewport"
    };

    private static string? ScientificCurrentMath3DProductSources(string checkout)
    {
        var names = new[] { "renderer/src/mesh/surfaceMesh.ts", "renderer/src/mesh/meshDocumentAdapter.ts",
            "renderer/src/mesh/meshResourceStore.ts", "renderer/src/workspace/MeshDocumentViewport.tsx",
            "renderer/src/components/SurfaceViewer.tsx", "packages/core/src/meshDocument.ts" };
        var sources = new JsonObject();
        foreach (var name in names)
        {
            var path = Path.Combine(checkout, name.Replace('/', Path.DirectorySeparatorChar));
            if (!File.Exists(path)) return null;
            sources[name] = ScientificHash(path);
        }
        return ScientificL6Digest(sources);
    }

    private static void ScientificCheckL9Declaration()
    {
        var path = Path.Combine(AppContext.BaseDirectory, "runtimes", "cgal-win-conda", "runtime.json");
        var declaration = (JsonNode.Parse(File.ReadAllText(path))?["qualificationRecipes"] as JsonArray)?
            .OfType<JsonObject>().FirstOrDefault(item => item["id"]?.GetValue<string>() == "l9.math3d-product");
        if (declaration?["readinessLevel"]?.GetValue<string>() != "L9"
            || declaration["capability"]?.GetValue<string>() != "mesh.interop.vtk-math3d"
            || declaration["referenceRecipe"]?.GetValue<string>() != "l8.resilience"
            || declaration["contractVersion"]?.GetValue<int>() != 1
            || declaration["viewer"]?.GetValue<string>() != "MeshDocumentViewport")
            throw new InvalidOperationException("The L9 product integration contract is not registered.");
    }

    private object ScientificL9Start(string profileId, string runtimeId)
    {
        ScientificProviderRegistry.RequireAction(runtimeId, "l9-math3d-product");
        ScientificCheckL9Declaration();
        var support = ScientificCurrentL8Product(profileId);
        var (l8Directory, l8Result) = ScientificHistoryFind(profileId, support["runId"]!.GetValue<string>());
        var l8 = JsonNode.Parse(l8Result.GetRawText())?["l8Evidence"] as JsonObject
            ?? throw new InvalidDataException("The supporting L8 run has no resilience evidence.");
        if (l8["sourceL7ContractSha256"]?.GetValue<string>() is not { Length: 64 })
            throw new InvalidDataException("The supporting consumer contract is missing.");
        var checkout = ScientificL7Checkout();
        if (!File.Exists(Path.Combine(checkout, "renderer", "src", "workspace", "MeshDocumentViewport.tsx"))
            || !File.Exists("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"))
            throw new InvalidOperationException("The MATH3D Mesh viewer and headless Edge are required for L9.");
        var node = Math3DNode;
        var prefix = ScientificPrefix(runtimeId);
        var (capability, positive, _) = ScientificL5Cases(runtimeId);
        ScientificCheckL5Declaration(runtimeId, capability, positive, ScientificL5Cases(runtimeId).Rejection);
        var fixture = ScientificDatasetArtifact(positive.DatasetId);
        if (!_scientificGate.Wait(0)) throw new InvalidOperationException("Another Scientific job is running; stop or wait for it.");
        try
        {
            var directory = Path.Combine(ScientificDataRoot, "runs", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(directory);
            var job = new ScientificJob { ProfileId = profileId, RuntimeId = runtimeId,
                RecipeId = "l9.math3d-product", Directory = directory };
            var parameters = JsonSerializer.SerializeToElement(new { suiteId = "l9-math3d-product-v1",
                sourceL8RunId = support["runId"]?.GetValue<string>(),
                sourceL8RecordId = support["recordId"]?.GetValue<string>(),
                handoffContractVersion = 1 }, ScientificJson);
            ScientificWriteRequest(job, parameters, fixture, additionalOutputs: new JsonArray(
                new JsonObject { ["path"] = "positive/l5-positive.obj", ["mediaType"] = "model/obj" },
                new JsonObject { ["path"] = "handoff/handoff.json", ["mediaType"] = "application/json" },
                new JsonObject { ["path"] = "product/mesh-document.json", ["mediaType"] = "application/json" },
                new JsonObject { ["path"] = "product/mesh-resource.bin", ["mediaType"] = "application/octet-stream" },
                new JsonObject { ["path"] = "product/viewer.png", ["mediaType"] = "image/png" },
                new JsonObject { ["path"] = "product/regression.json", ["mediaType"] = "application/json" }));
            _scientificJobs[profileId + ":" + runtimeId] = job;
            ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) });
            _ = ScientificL9RunAsync(job, prefix, node, checkout, fixture, positive, support, l8, l8Directory);
            return ScientificJobSnapshot(job);
        }
        catch { _scientificGate.Release(); throw; }
    }

    private async Task ScientificL9RunAsync(ScientificJob job, string prefix, string node, string checkout,
        JsonObject fixture, ScientificL5Case positive, JsonObject support, JsonObject l8, string l8Directory)
    {
        var timer = Stopwatch.StartNew();
        try
        {
            job.Stage = "broker-worker";
            var worker = await ScientificL5CaseAsync(job, prefix, "positive", positive, fixture);
            var sourcePath = Path.Combine(job.Directory, "positive", positive.OutputName);
            if (worker["artifactSha256"]?.GetValue<string>() != ScientificHash(sourcePath)
                || worker["artifactSha256"]?.GetValue<string>() != l8["sourceArtifactSha256"]?.GetValue<string>()
                || worker["state"]?.GetValue<string>() != "succeeded")
                throw new InvalidDataException("Fresh broker worker output is unverified.");
            var contract = ScientificL9Contract();
            var contractHash = ScientificL6Digest(contract);
            var handoffDirectory = Path.Combine(job.Directory, "handoff");
            var productDirectory = Path.Combine(job.Directory, "product");
            Directory.CreateDirectory(handoffDirectory);
            Directory.CreateDirectory(productDirectory);
            var handoffPath = Path.Combine(handoffDirectory, "handoff.json");
            var workerRequestPath = Path.Combine(job.Directory, "positive", "request.json");
            var workerResultPath = Path.Combine(job.Directory, "positive", "results.json");
            var handoff = new JsonObject { ["schemaVersion"] = 1, ["contract"] = contract.DeepClone(),
                ["runtimeId"] = job.RuntimeId, ["capabilityId"] = "mesh.interop.vtk-math3d",
                ["sourceL8RunId"] = support["runId"]?.GetValue<string>(),
                ["sourceL8RecordId"] = support["recordId"]?.GetValue<string>(),
                ["workerRequest"] = new JsonObject { ["path"] = workerRequestPath, ["sha256"] = ScientificHash(workerRequestPath) },
                ["workerResult"] = new JsonObject { ["path"] = workerResultPath, ["sha256"] = ScientificHash(workerResultPath) },
                ["artifact"] = new JsonObject { ["path"] = sourcePath, ["sha256"] = ScientificHash(sourcePath) } };
            File.WriteAllText(handoffPath, handoff.ToJsonString(), new UTF8Encoding(false));
            job.Stage = "math3d-product";
            var productTool = Path.Combine(ScientificSourceRoot, "tools", "math3d-l9-product-handoff.mjs");
            await ScientificProcessAsync(job, prefix, node,
                [productTool, "--checkout", checkout, "--handoff", handoffPath, "--output", productDirectory],
                productDirectory, 240);
            var reportPath = Path.Combine(productDirectory, "regression.json");
            var report = JsonNode.Parse(File.ReadAllText(reportPath)) as JsonObject
                ?? throw new InvalidDataException("The MATH3D product regression report is missing.");
            if (report["regression"]?.GetValue<string>() != "passed"
                || report["viewerState"]?.GetValue<string>() != "mounted"
                || report["blueMeshPixels"]?.GetValue<int>() < 1000
                || report["contractSha256"]?.GetValue<string>() != contractHash
                || report["sourceArtifactSha256"]?.GetValue<string>() != worker["artifactSha256"]?.GetValue<string>())
                throw new InvalidDataException("The MATH3D scene import or viewer regression failed.");
            if (ScientificCurrentL8Product(job.ProfileId)["recordId"]?.GetValue<string>() != support["recordId"]?.GetValue<string>())
                throw new InvalidOperationException("The pinned L8 qualification is no longer current.");
            var lower = (JsonArray)l8["lowerQualification"]!["records"]!.DeepClone();
            lower.Add(support.DeepClone());
            var sourcesHash = ScientificL6Digest(report["consumerSources"]);
            var evidence = new JsonObject { ["suiteId"] = "l9-math3d-product-v1",
                ["capabilityId"] = "mesh.interop.vtk-math3d",
                ["sourceL8RunId"] = support["runId"]?.GetValue<string>(),
                ["sourceL8FolderId"] = Path.GetFileName(l8Directory),
                ["sourceL8RecordId"] = support["recordId"]?.GetValue<string>(),
                ["sourceL8ContractSha256"] = l8["sourceL7ContractSha256"]?.GetValue<string>(),
                ["worker"] = worker.DeepClone(), ["brokerHandoff"] = handoff.DeepClone(),
                ["brokerHandoffSha256"] = ScientificHash(handoffPath),
                ["productContract"] = contract.DeepClone(), ["productContractSha256"] = contractHash,
                ["documentSha256"] = ScientificHash(Path.Combine(productDirectory, "mesh-document.json")),
                ["resourceSha256"] = ScientificHash(Path.Combine(productDirectory, "mesh-resource.bin")),
                ["viewerSha256"] = ScientificHash(Path.Combine(productDirectory, "viewer.png")),
                ["regression"] = report.DeepClone(), ["regressionSha256"] = ScientificHash(reportPath),
                ["consumerSourcesSha256"] = sourcesHash,
                ["lowerQualification"] = new JsonObject { ["records"] = lower } };
            File.WriteAllText(Path.Combine(job.Directory, "results.json"), new JsonObject
            {
                ["l9Evidence"] = evidence,
                ["validatedCapabilities"] = new JsonArray("mesh.interop.vtk-math3d")
            }.ToJsonString(), new UTF8Encoding(false));
            job.State = "succeeded"; job.Stage = "completed";
        }
        catch (OperationCanceledException) { job.State = "cancelled"; job.Error = "The owned L9 product run was stopped."; }
        catch (TimeoutException exception) { job.State = "timed-out"; job.Error = exception.Message; }
        catch (Exception exception) { job.State = "failed"; job.Error = exception.Message; }
        finally
        {
            job.DurationMs = timer.ElapsedMilliseconds;
            try { ScientificFinish(job); ScientificLog(job, $"\n[{job.State}] L9 MATH3D product integration / {job.DurationMs} ms {job.Error}\n"); }
            catch (Exception exception) { Debug.WriteLine($"L9 product finalization failed: {exception}"); }
            finally { ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) }); _scientificGate.Release(); }
        }
    }
}
