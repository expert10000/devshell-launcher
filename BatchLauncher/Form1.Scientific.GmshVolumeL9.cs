using System.Diagnostics;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace BatchLauncher;

public partial class Form1
{
    private static JsonObject ScientificGmshVolumeL9Contract() => new() {
        ["id"] = "math3d.tetrahedral-product-handoff", ["version"] = 1,
        ["documentFormat"] = "math3d.tetrahedral-mesh-document",
        ["resourceEncoding"] = "math3d.tetmesh-buffers.v1", ["viewer"] = "TetrahedralMeshViewport" };

    private static string? ScientificCurrentMath3DVolumeSources(string checkout)
    {
        var files = new[] { "scientific/volume-consumer.v1.json", "packages/core/src/tetrahedralMeshDocument.ts",
            "renderer/src/volume/tetrahedralMeshDocumentAdapter.ts", "renderer/src/volume/TetrahedralMeshViewport.tsx",
            "renderer/src/workspace/MeshDocumentViewport.tsx", "renderer/src/components/SurfaceViewer.tsx" };
        var sources = new JsonObject();
        foreach (var name in files)
        {
            var path = Path.Combine(checkout, name.Replace('/', Path.DirectorySeparatorChar));
            if (!File.Exists(path)) return null;
            sources[name] = ScientificHash(path);
        }
        return ScientificL6Digest(sources);
    }

    private JsonObject ScientificGmshVolumeCurrentL8(string profileId)
    {
        var summary = ScientificQualificationSummary(profileId, "gmsh-win-conda");
        var record = summary["currentRecords"]?.AsArray().OfType<JsonObject>()
            .Where(item => item["capabilityId"]?.GetValue<string>() == "mesh.generate3d"
                && item["level"]?.GetValue<string>() == "L8")
            .OrderByDescending(item => item["finishedAtUtc"]?.GetValue<string>(), StringComparer.Ordinal)
            .FirstOrDefault() ?? throw new InvalidOperationException("Current Gmsh volume L8 support is required.");
        return new JsonObject { ["runId"] = record["runId"]?.GetValue<string>(),
            ["recordId"] = record["recordId"]?.GetValue<string>(),
            ["capabilityId"] = "mesh.generate3d", ["level"] = "L8" };
    }

    private object ScientificGmshVolumeL9Start(string profileId, string runtimeId)
    {
        ScientificProviderRegistry.RequireAction(runtimeId, "l9-gmsh-volume");
        ScientificGmshVolumeDeclaration("l9.gmsh-volume", "L9");
        var support = ScientificGmshVolumeCurrentL8(profileId);
        var (l8Directory, l8Element) = ScientificHistoryFind(profileId, support["runId"]!.GetValue<string>());
        if (!ScientificQualificationRecords.Verify(l8Directory, l8Element).OfType<JsonObject>().Any(item =>
            item["recordId"]?.GetValue<string>() == support["recordId"]?.GetValue<string>()
            && item["level"]?.GetValue<string>() == "L8"))
            throw new InvalidDataException("Gmsh volume L8 support is not verified.");
        var l8 = JsonNode.Parse(l8Element.GetRawText())?["l8GmshVolumeEvidence"] as JsonObject
            ?? throw new InvalidDataException("Gmsh volume L8 evidence is missing.");
        var l7RunId = l8["sourceL7RunId"]?.GetValue<string>() ?? "";
        var (l7Directory, l7Element) = ScientificHistoryFind(profileId, l7RunId);
        var l7 = JsonNode.Parse(l7Element.GetRawText())?["volumeEvidence"] as JsonObject
            ?? throw new InvalidDataException("Gmsh volume L7 evidence is missing.");
        var sourceMsh = ScientificArtifactFiles.ResolveRegistered(l7Directory, l7Element, "volume/positive-a/cube.msh");
        if (ScientificHash(sourceMsh) != l7["artifactSha256"]?.GetValue<string>())
            throw new InvalidDataException("Qualified tetrahedral MSH changed.");
        var checkout = ScientificL7Checkout();
        if (ScientificCurrentMath3DVolumeSources(checkout) == null
            || !File.Exists("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"))
            throw new InvalidOperationException("MATH3D tetrahedral consumer and headless Edge are required.");
        var fixture = ScientificDatasetArtifact("gmsh/fixed-cube.geo");
        var prefix = ScientificPrefix(runtimeId);
        var vtkPrefix = ScientificPrefix("vtk-win-conda");
        if (!_scientificGate.Wait(0)) throw new InvalidOperationException("Another Scientific job is running.");
        try
        {
            var directory = Path.Combine(ScientificDataRoot, "runs", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(directory);
            var job = new ScientificJob { ProfileId = profileId, RuntimeId = runtimeId,
                RecipeId = "l9.gmsh-volume", Directory = directory };
            var parameters = JsonSerializer.SerializeToElement(new { suiteId = "l9-gmsh-volume-v1",
                sourceL8RunId = support["runId"]?.GetValue<string>(), sourceL8RecordId = support["recordId"]?.GetValue<string>(),
                handoffContractVersion = 1, documentFormat = "math3d.tetrahedral-mesh-document" }, ScientificJson);
            var outputs = new JsonArray();
            foreach (var (name, media) in new[] {
                ("volume/positive-a/cube.msh", "application/vnd.gmsh.msh"),
                ("product/volume.m3dt", "application/octet-stream"), ("product/exporter.json", "application/json"),
                ("product/handoff.json", "application/json"), ("product/tetra-document.json", "application/json"),
                ("product/tetra-resource.m3dt", "application/octet-stream"),
                ("product/viewer.png", "image/png"), ("product/regression.json", "application/json"),
                ("product/roundtrip.json", "application/json") })
                outputs.Add(new JsonObject { ["path"] = name, ["mediaType"] = media });
            ScientificWriteRequest(job, parameters, fixture, additionalOutputs: outputs, timeoutSeconds: 300);
            _scientificJobs[profileId + ":" + runtimeId] = job;
            ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) });
            _ = ScientificGmshVolumeL9RunAsync(job, prefix, vtkPrefix, checkout, support, l8, l7, l8Directory, l7Directory);
            return ScientificJobSnapshot(job);
        }
        catch { _scientificGate.Release(); throw; }
    }

    private async Task ScientificGmshVolumeL9RunAsync(ScientificJob job, string prefix, string vtkPrefix,
        string checkout, JsonObject support, JsonObject l8, JsonObject l7, string l8Directory, string l7Directory)
    {
        var timer = Stopwatch.StartNew();
        try
        {
            var tools = Path.Combine(ScientificSourceRoot, "tools");
            var product = Path.Combine(job.Directory, "product");
            Directory.CreateDirectory(product);
            string At(string name) => Path.Combine(product, name);
            job.Stage = "fresh-tetrahedral-worker";
            var suitePath = Path.Combine(tools, "scientific-broker", "gmsh_volume.py");
            var suiteResult = Path.Combine(job.Directory, "suite.json");
            await ScientificProcessAsync(job, prefix, Path.Combine(prefix, "python.exe"),
                [suitePath, "run", "--gmsh-python", Path.Combine(prefix, "python.exe"),
                    "--vtk-python", Path.Combine(vtkPrefix, "python.exe"), "--math3d-checkout", checkout,
                    "--output-root", job.Directory, "--folder-id", "volume", "--result", suiteResult], job.Directory, 240);
            var msh = Path.Combine(job.Directory, "volume", "positive-a", "cube.msh");
            var mshHash = ScientificHash(msh);
            if (JsonNode.Parse(File.ReadAllText(suiteResult))?["verdict"]?.GetValue<string>() != "passed"
                || mshHash != l7["artifactSha256"]?.GetValue<string>())
                throw new InvalidDataException("Fresh tetrahedral worker output differs from current L7 evidence.");
            job.Stage = "export-cell-resource";
            await ScientificProcessAsync(job, prefix, Path.Combine(prefix, "python.exe"),
                [Path.Combine(tools, "scientific-gmsh-tetmesh-export.py"), "--input", msh,
                    "--output", At("volume.m3dt"), "--result", At("exporter.json")], product, 60);
            var exported = JsonNode.Parse(File.ReadAllText(At("exporter.json"))) as JsonObject
                ?? throw new InvalidDataException("Tetrahedral exporter report is missing.");
            if (exported["sourceMshSha256"]?.GetValue<string>() != mshHash
                || exported["resourceSha256"]?.GetValue<string>() != ScientificHash(At("volume.m3dt"))
                || exported["points"]?.GetValue<int>() != l7["reload"]?["points"]?.GetValue<int>()
                || exported["tetrahedra"]?.GetValue<int>() != l7["reload"]?["tetrahedra"]?.GetValue<int>()
                || exported["boundaryTriangles"]?.GetValue<int>() != l7["reload"]?["boundaryTriangles"]?.GetValue<int>())
                throw new InvalidDataException("Tetrahedral resource differs from the worker artifact.");
            var contract = ScientificGmshVolumeL9Contract();
            var handoff = new JsonObject { ["schemaVersion"] = 1, ["contract"] = contract.DeepClone(),
                ["runtimeId"] = job.RuntimeId, ["capabilityId"] = "mesh.generate3d",
                ["sourceL8RunId"] = support["runId"]?.GetValue<string>(),
                ["sourceL8RecordId"] = support["recordId"]?.GetValue<string>(),
                ["sourceMsh"] = new JsonObject { ["path"] = msh, ["sha256"] = mshHash },
                ["resource"] = new JsonObject { ["path"] = At("volume.m3dt"), ["sha256"] = ScientificHash(At("volume.m3dt")) },
                ["exporterReport"] = new JsonObject { ["path"] = At("exporter.json"), ["sha256"] = ScientificHash(At("exporter.json")) } };
            File.WriteAllText(At("handoff.json"), handoff.ToJsonString(), new UTF8Encoding(false));
            job.Stage = "math3d-tetrahedral-document-and-viewer";
            await ScientificProcessAsync(job, prefix, Math3DNode,
                [Path.Combine(tools, "math3d-gmsh-tetmesh-product.mjs"), "--checkout", checkout,
                    "--handoff", At("handoff.json"), "--output", product], product, 240);
            job.Stage = "independent-tetrahedral-reload";
            await ScientificProcessAsync(job, prefix, Path.Combine(prefix, "python.exe"),
                [Path.Combine(tools, "scientific-gmsh-tetmesh-roundtrip.py"),
                    "--document", At("tetra-document.json"), "--resource", At("tetra-resource.m3dt"),
                    "--source-msh", msh, "--result", At("roundtrip.json")], product, 60);
            var regression = JsonNode.Parse(File.ReadAllText(At("regression.json"))) as JsonObject
                ?? throw new InvalidDataException("MATH3D tetrahedral regression report is missing.");
            var roundtrip = JsonNode.Parse(File.ReadAllText(At("roundtrip.json"))) as JsonObject
                ?? throw new InvalidDataException("Independent tetrahedral reload report is missing.");
            if (regression["regression"]?.GetValue<string>() != "passed"
                || regression["viewerState"]?.GetValue<string>() != "mounted"
                || regression["blueMeshPixels"]?.GetValue<int>() is not > 1000
                || regression["points"]?.GetValue<int>() != exported["points"]?.GetValue<int>()
                || regression["tetrahedra"]?.GetValue<int>() != exported["tetrahedra"]?.GetValue<int>()
                || regression["boundaryTriangles"]?.GetValue<int>() != exported["boundaryTriangles"]?.GetValue<int>()
                || regression["sourceMshSha256"]?.GetValue<string>() != mshHash
                || regression["contractSha256"]?.GetValue<string>() != ScientificL6Digest(contract)
                || roundtrip["verdict"]?.GetValue<string>() != "passed"
                || roundtrip["sourceMshSha256"]?.GetValue<string>() != mshHash
                || roundtrip["documentSha256"]?.GetValue<string>() != regression["documentSha256"]?.GetValue<string>()
                || roundtrip["resourceSha256"]?.GetValue<string>() != regression["resourceSha256"]?.GetValue<string>()
                || ScientificGmshVolumeCurrentL8(job.ProfileId)["recordId"]?.GetValue<string>() != support["recordId"]?.GetValue<string>())
                throw new InvalidDataException("Gmsh volume L9 document, reload or viewer gate did not pass.");
            var lower = (JsonArray)l8["lowerQualification"]!["records"]!.DeepClone();
            lower.Add(support.DeepClone());
            var hashes = new JsonObject();
            foreach (var name in new[] { "volume.m3dt", "exporter.json", "handoff.json", "tetra-document.json",
                "tetra-resource.m3dt", "viewer.png", "regression.json", "roundtrip.json" })
                hashes[name] = ScientificHash(At(name));
            var evidence = new JsonObject { ["suiteId"] = "l9-gmsh-volume-v1", ["capabilityId"] = "mesh.generate3d",
                ["sourceL8RunId"] = support["runId"]?.GetValue<string>(),
                ["sourceL8FolderId"] = Path.GetFileName(l8Directory),
                ["sourceL8RecordId"] = support["recordId"]?.GetValue<string>(),
                ["sourceL7FolderId"] = Path.GetFileName(l7Directory),
                ["sourceMshSha256"] = mshHash, ["freshWorkerRecordSha256"] = ScientificHash(Path.Combine(job.Directory, "volume", "DS-SCI-067.json")),
                ["productContract"] = contract.DeepClone(), ["productContractSha256"] = ScientificL6Digest(contract),
                ["brokerHandoff"] = handoff.DeepClone(), ["artifactHashes"] = hashes,
                ["exporter"] = exported.DeepClone(), ["regression"] = regression.DeepClone(),
                ["roundtrip"] = roundtrip.DeepClone(),
                ["consumerSourcesSha256"] = regression["consumerSourcesSha256"]?.GetValue<string>(),
                ["lowerQualification"] = new JsonObject { ["records"] = lower } };
            File.WriteAllText(Path.Combine(job.Directory, "results.json"), new JsonObject {
                ["l9GmshVolumeEvidence"] = evidence, ["validatedCapabilities"] = new JsonArray("mesh.generate3d")
            }.ToJsonString(), new UTF8Encoding(false));
            job.State = "succeeded"; job.Stage = "completed";
        }
        catch (OperationCanceledException) { job.State = "cancelled"; job.Error = "The owned Gmsh volume L9 run was stopped."; }
        catch (TimeoutException error) { job.State = "timed-out"; job.Error = error.Message; }
        catch (Exception error) { job.State = "failed"; job.Error = error.Message; }
        finally
        {
            job.DurationMs = timer.ElapsedMilliseconds;
            try { ScientificFinish(job); ScientificLog(job, $"\n[{job.State}] Gmsh volume L9 / {job.DurationMs} ms {job.Error}\n"); }
            catch (Exception error) { Debug.WriteLine($"Gmsh volume L9 finalization failed: {error}"); }
            finally { ScientificSend(new { type = "scientific.runtime.job", job = ScientificJobSnapshot(job) }); _scientificGate.Release(); }
        }
    }
}
