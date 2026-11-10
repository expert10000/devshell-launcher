using System.Diagnostics;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace BatchLauncher;

public partial class Form1
{
    private static string? ScientificCurrentRepairProductSources(string checkout)
    {
        var sources = new JsonObject();
        foreach (var name in ScientificRepairProductContract.ConsumerSources)
        {
            var path = Path.Combine(checkout, name.Replace('/', Path.DirectorySeparatorChar));
            if (!File.Exists(path)) return null;
            sources[name] = ScientificHash(path);
        }
        return ScientificL6Digest(sources);
    }

    private static string? ScientificCurrentRepairProductContract()
    {
        try { return ScientificL6Digest(ScientificRepairProductContract.Load(ScientificSourceRoot)); }
        catch (Exception error) when (error is IOException or InvalidOperationException or ArgumentException or JsonException)
        { return null; }
    }

    private static void ScientificCheckRepairL9Declaration()
    {
        var path = Path.Combine(AppContext.BaseDirectory, "runtimes", "cgal-win-conda", "runtime.json");
        var declaration = (JsonNode.Parse(File.ReadAllText(path))?["qualificationRecipes"] as JsonArray)?
            .OfType<JsonObject>().SingleOrDefault(item => item["id"]?.GetValue<string>() == "l9.cgal-repair");
        if (declaration?["readinessLevel"]?.GetValue<string>() != "L9"
            || declaration["capability"]?.GetValue<string>() != "mesh.repair"
            || declaration["referenceRecipe"]?.GetValue<string>() != "l8.cgal-repair"
            || declaration["contract"]?.GetValue<string>() != ScientificRepairProductContract.Id)
            throw new InvalidOperationException("The repair L9 product recipe is not declared.");
    }

    private object ScientificCgalRepairL9Start(string profileId, string runtimeId)
    {
        ScientificProviderRegistry.RequireAction(runtimeId, "l9-cgal-repair");
        ScientificCheckRepairL9Declaration();
        var contract = ScientificRepairProductContract.Load(ScientificSourceRoot);
        var support = ScientificCurrentRepairLevel(profileId, "L8");
        var (l8Directory, saved) = ScientificHistoryFind(profileId, support["runId"]!.GetValue<string>());
        var l8 = JsonNode.Parse(saved.GetRawText()) as JsonObject;
        var evidence = l8?["repairResilienceEvidence"] as JsonObject;
        if (l8?["runtimeId"]?.GetValue<string>() != runtimeId
            || l8["recipeId"]?.GetValue<string>() != "l8.cgal-repair"
            || l8["state"]?.GetValue<string>() != "succeeded"
            || evidence?["sourceL7RunId"]?.GetValue<string>() is not { Length: 32 }
            || !ScientificQualificationRecords.Verify(l8Directory, saved).OfType<JsonObject>().Any(item =>
                item["recordId"]?.GetValue<string>() == support["recordId"]?.GetValue<string>()
                && item["capabilityId"]?.GetValue<string>() == "mesh.repair" && item["level"]?.GetValue<string>() == "L8"))
            throw new InvalidDataException("The repair L8 support does not verify.");
        var (l7Directory, l7Saved) = ScientificHistoryFind(profileId, evidence["sourceL7RunId"]!.GetValue<string>());
        var l7 = JsonNode.Parse(l7Saved.GetRawText())?["repairInteropEvidence"] as JsonObject
            ?? throw new InvalidDataException("The repair L7 source is missing.");
        if (l7["cases"] is not JsonArray reference || reference.Count != 4
            || Path.GetFileName(l7Directory) != evidence["sourceL7FolderId"]?.GetValue<string>())
            throw new InvalidDataException("The repair L7 reference cases changed.");
        var inputs = RepairL5Cases.Where(item => item.Positive).Select((test, index) =>
        {
            var input = ScientificDatasetArtifact(ScientificRepairFixtures.Dataset(
                ScientificSourceRoot, ScientificDataRoot, test.Fixture)["id"]!.GetValue<string>());
            var baselineHash = reference[index]?["artifactSha256"]?.GetValue<string>();
            if (reference[index]?["caseId"]?.GetValue<string>() != test.Id || baselineHash is not { Length: 64 })
                throw new InvalidDataException("A repair L7 reference case is invalid.");
            return (Test: test, Input: input, BaselineHash: baselineHash);
        }).ToArray();
        var checkout = ScientificL7Checkout();
        if (!File.Exists(Path.Combine(checkout, "renderer", "src", "workspace", "MeshDocumentViewport.tsx"))
            || !File.Exists("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"))
            throw new InvalidOperationException("The MATH3D Mesh viewer and headless Edge are required for repair L9.");
        var node = Math3DNode;
        var prefix = ScientificPrefix(runtimeId);
        if (!_scientificGate.Wait(0)) throw new InvalidOperationException("A Scientific recipe is already running.");
        try
        {
            var directory = Path.Combine(ScientificDataRoot, "runs", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(directory);
            var job = new ScientificJob { ProfileId = profileId, RuntimeId = runtimeId,
                RecipeId = "l9.cgal-repair", Directory = directory };
            var outputs = new JsonArray(new JsonObject { ["path"] = "repair-product-contract.json",
                ["mediaType"] = "application/json" });
            foreach (var (test, _, _) in inputs)
            {
                outputs.Add(new JsonObject { ["path"] = $"cases/{test.Id}/repaired.obj", ["mediaType"] = "model/obj" });
                foreach (var relative in ScientificRepairProductContract.Artifacts)
                    outputs.Add(new JsonObject { ["path"] = $"cases/{test.Id}/{relative}",
                        ["mediaType"] = ScientificMediaType(relative) });
            }
            outputs.Add(new JsonObject { ["path"] = "negative/repaired.m3dm", ["mediaType"] = "application/octet-stream" });
            outputs.Add(new JsonObject { ["path"] = "negative/rejection.json", ["mediaType"] = "application/json" });
            var parameters = JsonSerializer.SerializeToElement(new { suiteId = ScientificRepairProductContract.Id,
                sourceL8RunId = support["runId"]?.GetValue<string>(), sourceL8RecordId = support["recordId"]?.GetValue<string>() }, ScientificJson);
            ScientificWriteRequest(job, parameters, inputs[0].Input, "repair-l9-evidence.json",
                new JsonArray(inputs.Skip(1).Select(item => (JsonNode)item.Input.DeepClone()).ToArray()), outputs);
            _scientificJobs[profileId + ":" + runtimeId] = job;
            ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) });
            _ = ScientificCgalRepairL9RunAsync(job, prefix, node, checkout, l8Directory, evidence,
                inputs, support, contract);
            return ScientificJobSnapshot(job);
        }
        catch { _scientificGate.Release(); throw; }
    }

    private async Task ScientificCgalRepairL9RunAsync(ScientificJob job, string prefix, string node,
        string checkout, string l8Directory, JsonObject l8Evidence,
        (RepairL5Case Test, JsonObject Input, string BaselineHash)[] inputs,
        JsonObject support, JsonObject contract)
    {
        var timer = Stopwatch.StartNew();
        try
        {
            File.Copy(Path.Combine(ScientificSourceRoot,
                    ScientificRepairProductContract.RelativePath.Replace('/', Path.DirectorySeparatorChar)),
                Path.Combine(job.Directory, "repair-product-contract.json"));
            var handoffTool = Path.Combine(ScientificSourceRoot, "tools", "scientific-cgal-repair-math3d-handoff.py");
            var productTool = Path.Combine(ScientificSourceRoot, "tools", "math3d-cgal-repair-product.mjs");
            var roundtripTool = Path.Combine(ScientificSourceRoot, "tools", "scientific-cgal-repair-m3dm-roundtrip.py");
            var viewerTool = Path.Combine(ScientificSourceRoot, "tools", "math3d-cgal-repair-viewer.mjs");
            var python = Path.Combine(prefix, "python.exe");
            var outcomes = new JsonArray();
            foreach (var (test, input, baselineHash) in inputs)
            {
                job.Cancellation.Token.ThrowIfCancellationRequested();
                job.Stage = test.Id;
                var child = await ScientificCgalRepairL5CaseAsync(job, prefix, test, input);
                var caseDirectory = Path.Combine(job.Directory, "cases", test.Id);
                var output = Path.Combine(caseDirectory, "repaired.obj");
                if (child["artifactSha256"]?.GetValue<string>() != baselineHash
                    || ScientificHash(output) != baselineHash)
                    throw new InvalidDataException($"Fresh repair {test.Id} differs from its L7 reference.");
                var handoffFile = Path.Combine(caseDirectory, "handoff.json");
                job.ExecutedFiles.Add(ScientificRunFingerprint.ExecutedFile(node, "math3d-node"));
                job.ExecutedFiles.Add(ScientificRunFingerprint.ExecutedFile(Path.Combine(checkout,
                    "renderer", "src", "mesh", "surfaceMesh.ts"), "math3d-importer-source"));
                await ScientificProcessAsync(job, prefix, python,
                    [handoffTool, "--run-directory", caseDirectory, "--checkout", checkout,
                        "--node", node, "--report", handoffFile], caseDirectory, 150);
                var handoff = JsonNode.Parse(File.ReadAllText(handoffFile)) as JsonObject
                    ?? throw new InvalidDataException("MATH3D repair handoff evidence is missing.");
                var productDirectory = Path.Combine(caseDirectory, "product");
                job.ExecutedFiles.Add(ScientificRunFingerprint.ExecutedFile(Path.Combine(checkout,
                    "src", "main", "python", "nativeCgalProtocol.ts"), "math3d-m3dm-codec-source"));
                await ScientificProcessAsync(job, prefix, node,
                    [productTool, "--checkout", checkout, "--run-directory", caseDirectory,
                        "--handoff", handoffFile, "--output", productDirectory], caseDirectory, 150);
                await ScientificProcessAsync(job, prefix, python,
                    [roundtripTool, "--run-directory", caseDirectory, "--handoff", handoffFile,
                        "--product-directory", productDirectory,
                        "--report", Path.Combine(productDirectory, "roundtrip.json")], caseDirectory, 60);
                job.ExecutedFiles.Add(ScientificRunFingerprint.ExecutedFile(Path.Combine(checkout,
                    "renderer", "src", "workspace", "MeshDocumentViewport.tsx"), "math3d-viewer-source"));
                await ScientificProcessAsync(job, prefix, node,
                    [viewerTool, "--checkout", checkout, "--product", productDirectory], caseDirectory, 150);
                var product = JsonNode.Parse(File.ReadAllText(Path.Combine(productDirectory, "product.json"))) as JsonObject;
                var roundtrip = JsonNode.Parse(File.ReadAllText(Path.Combine(productDirectory, "roundtrip.json"))) as JsonObject;
                var viewer = JsonNode.Parse(File.ReadAllText(Path.Combine(productDirectory, "viewer.json"))) as JsonObject;
                if (handoff["verdict"]?.GetValue<string>() != "passed"
                    || product?["verdict"]?.GetValue<string>() != "passed"
                    || roundtrip?["verdict"]?.GetValue<string>() != "passed"
                    || viewer?["verdict"]?.GetValue<string>() != "passed"
                    || viewer["viewerState"]?.GetValue<string>() != "mounted"
                    || viewer["blueMeshPixels"]?.GetValue<int>() is not > 1000
                    || product["m3dmSha256"]?.GetValue<string>() != roundtrip["m3dmSha256"]?.GetValue<string>()
                    || product["m3dmSha256"]?.GetValue<string>() != viewer["m3dmSha256"]?.GetValue<string>())
                    throw new InvalidDataException($"Repair {test.Id} did not survive MATH3D save, reload and view.");
                var hashes = new JsonObject();
                foreach (var relative in ScientificRepairProductContract.Artifacts)
                    hashes[relative] = ScientificHash(Path.Combine(caseDirectory,
                        relative.Replace('/', Path.DirectorySeparatorChar)));
                outcomes.Add(new JsonObject { ["caseId"] = test.Id, ["recipeId"] = test.Recipe,
                    ["inputSha256"] = input["sha256"]?.GetValue<string>(), ["outputSha256"] = baselineHash,
                    ["requestSha256"] = ScientificHash(Path.Combine(caseDirectory, "request.json")),
                    ["resultSha256"] = ScientificHash(Path.Combine(caseDirectory, "results.json")),
                    ["repairAudit"] = child["patchSha256"]?.GetValue<string>(),
                    ["artifactHashes"] = hashes, ["handoff"] = handoff.DeepClone(),
                    ["product"] = product.DeepClone(), ["roundtrip"] = roundtrip.DeepClone(),
                    ["viewer"] = viewer.DeepClone() });
            }
            job.Stage = "changed-m3dm-rejection";
            var negativeDirectory = Path.Combine(job.Directory, "negative");
            Directory.CreateDirectory(negativeDirectory);
            var referenceDirectory = Path.Combine(job.Directory, "cases", "pentagon");
            var sourceProduct = Path.Combine(referenceDirectory, "product");
            foreach (var name in new[] { "product.json", "repair-mesh-document.json",
                "repair-mesh-resource.bin", "repaired.m3dm" })
                File.Copy(Path.Combine(sourceProduct, name), Path.Combine(negativeDirectory, name));
            var originalM3dm = Path.Combine(sourceProduct, "repaired.m3dm");
            var tamperedM3dm = Path.Combine(negativeDirectory, "repaired.m3dm");
            var changedBytes = File.ReadAllBytes(tamperedM3dm);
            if (changedBytes.Length < 33) throw new InvalidDataException("The M3DM resource is too small to test tampering.");
            changedBytes[^1] ^= 1;
            File.WriteAllBytes(tamperedM3dm, changedBytes);
            var rejected = new ScientificJob { ProfileId = job.ProfileId, RuntimeId = job.RuntimeId,
                RecipeId = "l9.cgal-repair.changed-m3dm", Directory = negativeDirectory,
                Cancellation = job.Cancellation };
            var negativeReport = Path.Combine(negativeDirectory, "roundtrip.json");
            var negativeObserved = false;
            try
            {
                await ScientificProcessAsync(rejected, prefix, python,
                    [roundtripTool, "--run-directory", referenceDirectory,
                        "--handoff", Path.Combine(referenceDirectory, "handoff.json"),
                        "--product-directory", negativeDirectory, "--report", negativeReport], negativeDirectory, 60);
            }
            catch (InvalidOperationException) when (rejected.ExitCode is > 0
                && rejected.Log.ToString().Contains("Saved MATH3D product identity changed", StringComparison.Ordinal))
            { negativeObserved = true; }
            if (!negativeObserved || File.Exists(negativeReport))
                throw new InvalidDataException("A changed M3DM was accepted or produced a reload report.");
            var negative = new JsonObject { ["state"] = "rejected", ["sourceCaseId"] = "pentagon",
                ["sourceM3dmSha256"] = ScientificHash(originalM3dm),
                ["tamperedM3dmSha256"] = ScientificHash(tamperedM3dm),
                ["mutation"] = "last-byte-xor-1", ["outputAbsent"] = true,
                ["exitCode"] = rejected.ExitCode };
            File.WriteAllText(Path.Combine(negativeDirectory, "rejection.json"), negative.ToJsonString(), new UTF8Encoding(false));
            if (ScientificCurrentRepairLevel(job.ProfileId, "L8")["recordId"]?.GetValue<string>()
                != support["recordId"]?.GetValue<string>())
                throw new InvalidOperationException("The pinned repair L8 record is no longer current.");
            var consumerSources = new JsonObject();
            foreach (var name in ScientificRepairProductContract.ConsumerSources)
                consumerSources[name] = ScientificHash(Path.Combine(checkout, name.Replace('/', Path.DirectorySeparatorChar)));
            foreach (var outcome in outcomes.OfType<JsonObject>())
            {
                var sources = outcome["product"]?["consumerSources"] as JsonObject;
                foreach (var name in ScientificRepairProductContract.ConsumerSources[..^1])
                    if (sources?[name]?.GetValue<string>() != consumerSources[name]?.GetValue<string>())
                        throw new InvalidDataException("MATH3D repair product source changed during the run.");
                if (outcome["viewer"]?["viewerSourceSha256"]?.GetValue<string>()
                    != consumerSources[ScientificRepairProductContract.ConsumerSources[^1]]?.GetValue<string>())
                    throw new InvalidDataException("MATH3D repair viewer source changed during the run.");
            }
            var lower = (JsonArray)l8Evidence["lowerQualification"]!["records"]!.DeepClone();
            lower.Add(support.DeepClone());
            var evidence = new JsonObject { ["suiteId"] = ScientificRepairProductContract.Id,
                ["capabilityId"] = "mesh.repair", ["sourceL8RunId"] = support["runId"]?.GetValue<string>(),
                ["sourceL8FolderId"] = Path.GetFileName(l8Directory),
                ["sourceL8RecordId"] = support["recordId"]?.GetValue<string>(),
                ["productContract"] = contract.DeepClone(), ["productContractSha256"] = ScientificL6Digest(contract),
                ["productContractFileSha256"] = ScientificHash(Path.Combine(job.Directory, "repair-product-contract.json")),
                ["consumerSources"] = consumerSources, ["consumerSourcesSha256"] = ScientificL6Digest(consumerSources),
                ["cases"] = outcomes, ["negative"] = negative.DeepClone(),
                ["negativeSha256"] = ScientificHash(Path.Combine(negativeDirectory, "rejection.json")),
                ["lowerQualification"] = new JsonObject { ["records"] = lower } };
            File.WriteAllText(Path.Combine(job.Directory, "repair-l9-evidence.json"), evidence.ToJsonString(), new UTF8Encoding(false));
            File.WriteAllText(Path.Combine(job.Directory, "results.json"), new JsonObject {
                ["repairProductEvidence"] = evidence, ["validatedCapabilities"] = new JsonArray("mesh.repair")
            }.ToJsonString(), new UTF8Encoding(false));
            job.State = "succeeded"; job.Stage = "completed";
        }
        catch (OperationCanceledException) { job.State = "cancelled"; job.Error = "Only this repair product job was stopped."; }
        catch (TimeoutException error) { job.State = "timed-out"; job.Error = error.Message; }
        catch (Exception error) { job.State = "failed"; job.Error = error.Message; }
        finally
        {
            job.DurationMs = timer.ElapsedMilliseconds;
            try { ScientificFinish(job); ScientificLog(job, $"\n[{job.State}] repair L9 product / {job.DurationMs} ms {job.Error}\n"); }
            catch (Exception error) { Debug.WriteLine($"Repair L9 finalization failed: {error}"); }
            finally { ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) }); _scientificGate.Release(); }
        }
    }
}
