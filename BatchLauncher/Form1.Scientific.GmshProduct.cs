using System.Diagnostics;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace BatchLauncher;

public partial class Form1
{
    private JsonObject ScientificGmshCurrentL8(string profileId)
    {
        var summary = ScientificQualificationSummary(profileId, "gmsh-win-conda");
        var support = summary["currentRecords"]?.AsArray().OfType<JsonObject>()
            .Where(item => item["capabilityId"]?.GetValue<string>() == "mesh.generate"
                && item["level"]?.GetValue<string>() == "L8")
            .OrderByDescending(item => item["finishedAtUtc"]?.GetValue<string>(), StringComparer.Ordinal)
            .FirstOrDefault() ?? throw new InvalidOperationException("A current Gmsh L8 qualification is required for L9.");
        return new JsonObject { ["runId"] = support["runId"]?.GetValue<string>(),
            ["recordId"] = support["recordId"]?.GetValue<string>(),
            ["capabilityId"] = "mesh.generate", ["level"] = "L8" };
    }

    private object ScientificGmshL9Start(string profileId, string runtimeId)
    {
        ScientificProviderRegistry.RequireAction(runtimeId, "l9-gmsh-product");
        ScientificGmshDeclaration("l9.gmsh-product", "L9", "l8.gmsh-resilience");
        var support = ScientificGmshCurrentL8(profileId);
        var (l8Directory, l8Result) = ScientificHistoryFind(profileId, support["runId"]!.GetValue<string>());
        var l8 = JsonNode.Parse(l8Result.GetRawText())?["l8GmshEvidence"] as JsonObject
            ?? throw new InvalidDataException("Gmsh L8 evidence is missing.");
        if (!ScientificQualificationRecords.Verify(l8Directory, l8Result).OfType<JsonObject>()
            .Any(item => item["recordId"]?.GetValue<string>() == support["recordId"]?.GetValue<string>()
                && item["level"]?.GetValue<string>() == "L8"))
            throw new InvalidDataException("The Gmsh L8 record is not verified.");
        var l7RunId = l8["sourceL7RunId"]?.GetValue<string>() ?? "";
        var (l7Directory, l7Result) = ScientificHistoryFind(profileId, l7RunId);
        var l7 = JsonNode.Parse(l7Result.GetRawText())?["l7GmshEvidence"] as JsonObject
            ?? throw new InvalidDataException("Gmsh L7 source evidence is missing.");
        if (l7["artifactHashes"]?["mesh.obj"]?.GetValue<string>() != l8["sourceArtifactSha256"]?.GetValue<string>()
            || l7["consumerContractSha256"]?.GetValue<string>() != l8["sourceConsumerContractSha256"]?.GetValue<string>())
            throw new InvalidDataException("Gmsh L7 and L8 consumer contracts differ.");
        var checkout = ScientificL7Checkout();
        if (!File.Exists(Path.Combine(checkout, "renderer", "src", "workspace", "MeshDocumentViewport.tsx"))
            || !File.Exists(Path.Combine(checkout, "src", "main", "python", "nativeCgalProtocol.ts"))
            || !File.Exists("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"))
            throw new InvalidOperationException("MATH3D Mesh viewer, codec and headless Edge are required.");
        var prefix = ScientificPrefix(runtimeId);
        var (capability, positive, rejection) = ScientificL5Cases(runtimeId);
        ScientificCheckL5Declaration(runtimeId, capability, positive, rejection);
        var fixture = ScientificDatasetArtifact(positive.DatasetId);
        if (!_scientificGate.Wait(0)) throw new InvalidOperationException("Another Scientific job is running.");
        try
        {
            var directory = Path.Combine(ScientificDataRoot, "runs", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(directory);
            var job = new ScientificJob { ProfileId = profileId, RuntimeId = runtimeId,
                RecipeId = "l9.gmsh-product", Directory = directory };
            var parameters = JsonSerializer.SerializeToElement(new { suiteId = "l9-gmsh-product-v1",
                sourceL8RunId = support["runId"]?.GetValue<string>(), sourceL8RecordId = support["recordId"]?.GetValue<string>(),
                handoffContractVersion = 1, documentFormat = "M3DM" }, ScientificJson);
            var outputs = new JsonArray();
            foreach (var name in new[] { "positive/l5-positive.msh", "handoff/mesh.obj", "handoff/conversion.json",
                "handoff/handoff.json", "product/mesh-document.json", "product/mesh-resource.bin",
                "product/viewer.png", "product/regression.json", "product/qualified-mesh.m3dm",
                "product/roundtrip.json" })
                outputs.Add(new JsonObject { ["path"] = name, ["mediaType"] = ScientificMediaType(name) });
            ScientificWriteRequest(job, parameters, fixture, additionalOutputs: outputs);
            _scientificJobs[profileId + ":" + runtimeId] = job;
            ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) });
            _ = ScientificGmshL9RunAsync(job, prefix, checkout, fixture, positive, support,
                l8, l8Directory, l7, l7Directory);
            return ScientificJobSnapshot(job);
        }
        catch { _scientificGate.Release(); throw; }
    }

    private async Task ScientificGmshL9RunAsync(ScientificJob job, string prefix, string checkout,
        JsonObject fixture, ScientificL5Case positive, JsonObject support, JsonObject l8,
        string l8Directory, JsonObject l7, string l7Directory)
    {
        var timer = Stopwatch.StartNew();
        try
        {
            job.Stage = "worker";
            var worker = await ScientificL5CaseAsync(job, prefix, "positive", positive, fixture);
            var mshPath = Path.Combine(job.Directory, "positive", positive.OutputName);
            if (worker["state"]?.GetValue<string>() != "succeeded"
                || worker["artifactSha256"]?.GetValue<string>() != ScientificHash(mshPath)
                || worker["artifactSha256"]?.GetValue<string>() != l7["source"]?["artifactSha256"]?.GetValue<string>())
                throw new InvalidDataException("The fresh Gmsh worker output differs from qualified L7 evidence.");
            var handoffDirectory = Path.Combine(job.Directory, "handoff");
            var productDirectory = Path.Combine(job.Directory, "product");
            Directory.CreateDirectory(handoffDirectory); Directory.CreateDirectory(productDirectory);
            var objPath = Path.Combine(handoffDirectory, "mesh.obj");
            var conversionPath = Path.Combine(handoffDirectory, "conversion.json");
            job.Stage = "convert";
            await ScientificProcessAsync(job, prefix, Path.Combine(prefix, "python.exe"),
                [Path.Combine(ScientificSourceRoot, "tools", "scientific-gmsh-handoff.py"),
                    "--input", mshPath, "--output", objPath, "--result", conversionPath], handoffDirectory, 60);
            var conversion = JsonNode.Parse(File.ReadAllText(conversionPath)) as JsonObject
                ?? throw new InvalidDataException("Gmsh conversion report is missing.");
            if (conversion["sourceMshSha256"]?.GetValue<string>() != worker["artifactSha256"]?.GetValue<string>()
                || conversion["outputObjSha256"]?.GetValue<string>() != ScientificHash(objPath)
                || conversion["outputObjSha256"]?.GetValue<string>() != l8["sourceArtifactSha256"]?.GetValue<string>())
                throw new InvalidDataException("Gmsh OBJ handoff differs from qualified L8 evidence.");
            var contract = ScientificL9Contract();
            var contractHash = ScientificL6Digest(contract);
            var requestPath = Path.Combine(job.Directory, "positive", "request.json");
            var resultPath = Path.Combine(job.Directory, "positive", "results.json");
            var handoff = new JsonObject { ["schemaVersion"] = 1, ["contract"] = contract.DeepClone(),
                ["runtimeId"] = job.RuntimeId, ["capabilityId"] = "mesh.generate",
                ["sourceL8RunId"] = support["runId"]?.GetValue<string>(),
                ["sourceL8RecordId"] = support["recordId"]?.GetValue<string>(),
                ["workerRequest"] = new JsonObject { ["path"] = requestPath, ["sha256"] = ScientificHash(requestPath) },
                ["workerResult"] = new JsonObject { ["path"] = resultPath, ["sha256"] = ScientificHash(resultPath) },
                ["workerArtifact"] = new JsonObject { ["path"] = mshPath, ["sha256"] = ScientificHash(mshPath) },
                ["artifact"] = new JsonObject { ["path"] = objPath, ["sha256"] = ScientificHash(objPath) } };
            var handoffPath = Path.Combine(handoffDirectory, "handoff.json");
            File.WriteAllText(handoffPath, handoff.ToJsonString(), new UTF8Encoding(false));
            job.Stage = "math3d-product";
            await ScientificProcessAsync(job, prefix, Math3DNode,
                [Path.Combine(ScientificSourceRoot, "tools", "math3d-l9-product-handoff.mjs"),
                    "--checkout", checkout, "--handoff", handoffPath, "--output", productDirectory], productDirectory, 240);
            job.Stage = "independent-m3dm-reload";
            var roundtripPath = Path.Combine(productDirectory, "roundtrip.json");
            await ScientificProcessAsync(job, prefix, Path.Combine(prefix, "python.exe"),
                [Path.Combine(ScientificSourceRoot, "tools", "scientific-gmsh-m3dm-roundtrip.py"),
                    "--input-obj", objPath, "--input-m3dm", Path.Combine(productDirectory, "qualified-mesh.m3dm"),
                    "--result", roundtripPath], productDirectory, 60);
            var report = JsonNode.Parse(File.ReadAllText(Path.Combine(productDirectory, "regression.json"))) as JsonObject
                ?? throw new InvalidDataException("MATH3D product report is missing.");
            var roundtrip = JsonNode.Parse(File.ReadAllText(roundtripPath)) as JsonObject
                ?? throw new InvalidDataException("Independent M3DM reload report is missing.");
            if (report["regression"]?.GetValue<string>() != "passed"
                || report["viewerState"]?.GetValue<string>() != "mounted"
                || report["blueMeshPixels"]?.GetValue<int>() is not > 1000
                || report["points"]?.GetValue<int>() != 44 || report["triangles"]?.GetValue<int>() != 66
                || report["contractSha256"]?.GetValue<string>() != contractHash
                || report["sourceArtifactSha256"]?.GetValue<string>() != ScientificHash(objPath)
                || report["workerArtifactSha256"]?.GetValue<string>() != ScientificHash(mshPath)
                || roundtrip["verdict"]?.GetValue<string>() != "passed"
                || roundtrip["sourceObjSha256"]?.GetValue<string>() != ScientificHash(objPath)
                || roundtrip["m3dmSha256"]?.GetValue<string>() != report["m3dmSha256"]?.GetValue<string>()
                || ScientificGmshCurrentL8(job.ProfileId)["recordId"]?.GetValue<string>() != support["recordId"]?.GetValue<string>())
                throw new InvalidDataException("The Gmsh L9 document or viewer gate did not pass.");
            var lower = (JsonArray)l8["lowerQualification"]!["records"]!.DeepClone(); lower.Add(support.DeepClone());
            var evidence = new JsonObject { ["suiteId"] = "l9-gmsh-product-v1", ["capabilityId"] = "mesh.generate",
                ["sourceL8RunId"] = support["runId"]?.GetValue<string>(), ["sourceL8FolderId"] = Path.GetFileName(l8Directory),
                ["sourceL8RecordId"] = support["recordId"]?.GetValue<string>(),
                ["sourceL7FolderId"] = Path.GetFileName(l7Directory),
                ["sourceL8ContractSha256"] = l8["sourceConsumerContractSha256"]?.GetValue<string>(),
                ["worker"] = worker.DeepClone(), ["conversion"] = conversion.DeepClone(),
                ["conversionSha256"] = ScientificHash(conversionPath), ["brokerHandoff"] = handoff.DeepClone(),
                ["brokerHandoffSha256"] = ScientificHash(handoffPath),
                ["productContract"] = contract.DeepClone(), ["productContractSha256"] = contractHash,
                ["documentSha256"] = ScientificHash(Path.Combine(productDirectory, "mesh-document.json")),
                ["resourceSha256"] = ScientificHash(Path.Combine(productDirectory, "mesh-resource.bin")),
                ["viewerSha256"] = ScientificHash(Path.Combine(productDirectory, "viewer.png")),
                ["m3dmSha256"] = ScientificHash(Path.Combine(productDirectory, "qualified-mesh.m3dm")),
                ["roundtrip"] = roundtrip.DeepClone(), ["roundtripSha256"] = ScientificHash(roundtripPath),
                ["regression"] = report.DeepClone(),
                ["regressionSha256"] = ScientificHash(Path.Combine(productDirectory, "regression.json")),
                ["consumerSourcesSha256"] = ScientificL6Digest(report["consumerSources"]),
                ["lowerQualification"] = new JsonObject { ["records"] = lower } };
            File.WriteAllText(Path.Combine(job.Directory, "results.json"), new JsonObject {
                ["l9GmshEvidence"] = evidence, ["validatedCapabilities"] = new JsonArray("mesh.generate")
            }.ToJsonString(), new UTF8Encoding(false));
            job.State = "succeeded"; job.Stage = "completed";
        }
        catch (OperationCanceledException) { job.State = "cancelled"; job.Error = "The owned Gmsh L9 run was stopped."; }
        catch (TimeoutException error) { job.State = "timed-out"; job.Error = error.Message; }
        catch (Exception error) { job.State = "failed"; job.Error = error.Message; }
        finally
        {
            job.DurationMs = timer.ElapsedMilliseconds;
            try { ScientificFinish(job); ScientificLog(job, $"\n[{job.State}] Gmsh L9 / {job.DurationMs} ms {job.Error}\n"); }
            catch (Exception error) { Debug.WriteLine($"Gmsh L9 finalization failed: {error}"); }
            finally { ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) }); _scientificGate.Release(); }
        }
    }
}
