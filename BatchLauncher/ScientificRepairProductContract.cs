using System.Text.Json.Nodes;

namespace BatchLauncher;

internal static class ScientificRepairProductContract
{
    internal const string RelativePath = "scientific/fixtures/cgal-repair-qualification/product-contract.v1.json";
    internal const string Id = "cgal-repair-math3d-product-v1";
    internal static readonly string[] Artifacts = ["handoff.json", "math3d-consumed.json",
        "product/repair-mesh-document.json", "product/repair-mesh-resource.bin", "product/repaired.m3dm",
        "product/product.json", "product/roundtrip.json", "product/viewer.png", "product/viewer.json"];
    internal static readonly string[] ConsumerSources = ["renderer/src/mesh/surfaceMesh.ts",
        "renderer/src/mesh/meshDocumentAdapter.ts", "renderer/src/mesh/meshResourceStore.ts",
        "packages/core/src/meshDocument.ts", "src/main/python/nativeCgalProtocol.ts",
        "renderer/src/workspace/MeshDocumentViewport.tsx"];

    internal static JsonObject Load(string sourceRoot)
    {
        var path = ScientificArtifactFiles.ScopedFile(sourceRoot, RelativePath);
        if (!File.Exists(path) || new FileInfo(path).Length is <= 0 or > 65536)
            throw new InvalidDataException("The repair product contract is unavailable.");
        var contract = JsonNode.Parse(File.ReadAllText(path)) as JsonObject
            ?? throw new InvalidDataException("The repair product contract is invalid.");
        Validate(contract);
        var manifestPath = ScientificArtifactFiles.ScopedFile(sourceRoot, ScientificRepairFixtures.ManifestPath);
        ScientificRepairFixtures.Manifest(sourceRoot);
        if (ScientificArtifactFiles.Hash(manifestPath) != contract["fixtureManifestSha256"]?.GetValue<string>())
            throw new InvalidDataException("The repair product fixture manifest changed.");
        return contract;
    }

    internal static void Validate(JsonObject contract)
    {
        if (contract["schemaVersion"]?.GetValue<int>() != 1
            || contract["id"]?.GetValue<string>() != Id
            || contract["capabilityId"]?.GetValue<string>() != "mesh.repair"
            || contract["level"]?.GetValue<string>() != "L9"
            || contract["referenceRecipe"]?.GetValue<string>() != "l8.cgal-repair"
            || contract["fixtureManifest"]?.GetValue<string>() != ScientificRepairFixtures.ManifestPath
            || contract["fixtureManifestSha256"]?.GetValue<string>() is not { Length: 64 }
            || contract["cases"] is not JsonArray cases || cases.Count != 4
            || contract["artifacts"] is not JsonArray artifacts || artifacts.Count != Artifacts.Length
            || contract["consumerSources"] is not JsonArray sources || sources.Count != ConsumerSources.Length
            || contract["verification"] is not JsonObject verification
            || verification["geometry"]?.GetValue<string>() != "oriented-faces-bounds-area-volume"
            || verification["viewer"]?.GetValue<string>() != "MeshDocumentViewport"
            || verification["negative"]?.GetValue<string>() != "changed-m3dm-rejected"
            || verification["comparisonTolerance"]?.GetValue<double>() != 1e-5)
            throw new InvalidDataException("The repair product contract changed.");
        var expected = new[] { ("triangle", "cgal.fill-one-hole"), ("square", "cgal.fill-quad-hole"),
            ("two-squares", "cgal.fill-two-quad-holes"), ("pentagon", "cgal.fill-bounded-holes") };
        for (var i = 0; i < expected.Length; i++)
            if (cases[i]?["caseId"]?.GetValue<string>() != expected[i].Item1
                || cases[i]?["recipeId"]?.GetValue<string>() != expected[i].Item2
                || cases[i]?["output"]?.GetValue<string>() != "repaired.obj")
                throw new InvalidDataException("A repair product case changed.");
        for (var i = 0; i < Artifacts.Length; i++)
            if (artifacts[i]?.GetValue<string>() != Artifacts[i])
                throw new InvalidDataException("A repair product artifact changed.");
        for (var i = 0; i < ConsumerSources.Length; i++)
            if (sources[i]?.GetValue<string>() != ConsumerSources[i])
                throw new InvalidDataException("A repair product consumer source changed.");
    }
}
