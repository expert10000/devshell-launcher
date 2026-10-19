using BatchLauncher;
using System.Text.Json;
using System.Text.Json.Nodes;

var directory = Path.Combine(Path.GetTempPath(), "devshell-scientific-artifacts-" + Guid.NewGuid().ToString("N"));
Directory.CreateDirectory(Path.Combine(directory, "render"));
File.WriteAllText(Path.Combine(directory, "sphere.vtp"), "<VTKFile/>\n");
var png = Convert.FromBase64String("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=");
File.WriteAllBytes(Path.Combine(directory, "render", "vtk-offscreen.png"), png);
int count = 0;
void Check(bool condition, string label) { if (!condition) throw new Exception(label); count++; Console.WriteLine("PASS: " + label); }
void Reject(Action action, string label)
{
    try { action(); } catch (Exception exception) when (exception is InvalidOperationException or ArgumentException or IOException) { Check(true, label); return; }
    throw new Exception(label);
}
JsonElement Element(JsonNode node) => JsonSerializer.SerializeToElement(node);
var legacy = new JsonObject {
    ["runId"] = new string('a', 32), ["profileId"] = "test-profile", ["runtimeId"] = "vtk-win-conda", ["recipeId"] = "test-all",
    ["state"] = "succeeded", ["artifact"] = "sphere.vtp", ["artifacts"] = new JsonArray(),
    ["rendering"] = new JsonObject { ["state"] = "succeeded", ["artifact"] = "vtk-offscreen.png" }
};
var request = new JsonObject {
    ["runId"] = new string('a', 32), ["profileId"] = "test-profile", ["runtimeId"] = "vtk-win-conda", ["recipeId"] = "test-all", ["outputArtifacts"] = new JsonArray()
};
void SaveRequest() => File.WriteAllText(Path.Combine(directory, "request.json"), request.ToJsonString());
SaveRequest();
Check(ScientificArtifactFiles.SmokeOutputs("vtk-win-conda", "test-all").SequenceEqual(new[] { "sphere.vtp", "render/vtk-offscreen.png" }), "VTK test-all declares mesh and PNG");
Check(ScientificArtifactFiles.SmokeOutputs("vtk-win-conda", "run").SequenceEqual(new[] { "sphere.vtp" }), "VTK run declares only its mesh");
Check(ScientificArtifactFiles.SmokeOutputs("vtk-win-conda", "configure").Length == 0 && ScientificArtifactFiles.SmokeOutputs("cgal-win-conda", "test-all").Length == 0, "other recipes do not acquire VTK outputs");
var artifacts = new JsonArray(ScientificArtifactFiles.SmokeOutputs("vtk-win-conda", "test-all").Select(path => (JsonNode?)ScientificArtifactFiles.Describe(directory, path)).ToArray());
Check(artifacts.Count == 2 && artifacts[1]!["mediaType"]!.GetValue<string>() == "image/png", "fresh output records have correct media types");
Check(artifacts[0]!["bytes"]!.GetValue<long>() > 0 && artifacts[0]!["sha256"]!.GetValue<string>().Length == 64, "output size and SHA-256 recorded");
var current = (JsonObject)legacy.DeepClone(); current["artifacts"] = artifacts;
Check(ScientificArtifactFiles.ResolveRegistered(directory, Element(current), "sphere.vtp").EndsWith("sphere.vtp"), "registered mesh resolves for open/reveal");
var preview = ScientificArtifactFiles.ImagePreview(directory, Element(current), "render/vtk-offscreen.png");
Check(preview.MimeType == "image/png" && Convert.FromBase64String(preview.DataUrl.Split(',')[1]).SequenceEqual(png), "registered PNG reaches inline preview unchanged");
Reject(() => ScientificArtifactFiles.ImagePreview(directory, Element(current), "sphere.vtp"), "mesh cannot masquerade as PNG");
Reject(() => ScientificArtifactFiles.ResolveRegistered(directory, Element(current), "request.json"), "unregistered file rejected");
var escaped = (JsonObject)current.DeepClone(); escaped["artifacts"] = new JsonArray(new JsonObject { ["path"] = "../outside.png" });
Reject(() => ScientificArtifactFiles.ResolveRegistered(directory, Element(escaped), "../outside.png"), "registered path cannot escape run directory");
File.AppendAllText(Path.Combine(directory, "sphere.vtp"), "changed");
Reject(() => ScientificArtifactFiles.ResolveRegistered(directory, Element(current), "sphere.vtp"), "changed mesh rejected");
File.WriteAllText(Path.Combine(directory, "sphere.vtp"), "<VTKFile/>\n");
File.Move(Path.Combine(directory, "sphere.vtp"), Path.Combine(directory, "saved.vtp"));
Reject(() => ScientificArtifactFiles.ResolveRegistered(directory, Element(current), "sphere.vtp"), "missing output rejected");
File.Move(Path.Combine(directory, "saved.vtp"), Path.Combine(directory, "sphere.vtp"));
var recovered = ScientificArtifactFiles.RecoverLegacySmoke(directory, Element(legacy));
Check(recovered.GetProperty("artifacts").GetArrayLength() == 2 && recovered.GetProperty("artifacts")[0].GetProperty("recoveredFromLegacyRun").GetBoolean(), "legacy successful VTK outputs recovered and labelled");
Check(legacy["artifacts"]!.AsArray().Count == 0, "legacy result source remains unchanged");
foreach (var state in new[] { "failed", "cancelled", "timed-out" })
{
    var failed = (JsonObject)legacy.DeepClone(); failed["state"] = state;
    Check(ScientificArtifactFiles.RecoverLegacySmoke(directory, Element(failed)).GetProperty("artifacts").GetArrayLength() == 0, state + " run does not advertise output files");
    failed["artifacts"] = artifacts.DeepClone();
    Reject(() => ScientificArtifactFiles.ResolveRegistered(directory, Element(failed), "sphere.vtp"), state + " run cannot open successful output");
}
var noEvidence = (JsonObject)legacy.DeepClone(); noEvidence.Remove("artifact"); noEvidence.Remove("rendering");
Check(ScientificArtifactFiles.RecoverLegacySmoke(directory, Element(noEvidence)).GetProperty("artifacts").GetArrayLength() == 0, "files without legacy worker evidence not discovered");
request["outputArtifacts"] = new JsonArray(new JsonObject { ["path"] = "sphere.vtp" }); SaveRequest();
Check(ScientificArtifactFiles.RecoverLegacySmoke(directory, Element(legacy)).GetProperty("artifacts").GetArrayLength() == 0, "new request cannot acquire outputs through legacy fallback");
request["outputArtifacts"] = new JsonArray(); request["profileId"] = "other-profile"; SaveRequest();
Check(ScientificArtifactFiles.RecoverLegacySmoke(directory, Element(legacy)).GetProperty("artifacts").GetArrayLength() == 0, "mismatched legacy request not recovered");
File.WriteAllText(Path.Combine(directory, "render", "vtk-offscreen.png"), "not a PNG");
current["artifacts"] = new JsonArray(ScientificArtifactFiles.Describe(directory, "render/vtk-offscreen.png"));
Reject(() => ScientificArtifactFiles.ImagePreview(directory, Element(current), "render/vtk-offscreen.png"), "wrong PNG signature rejected even with matching hash");
using (var file = File.Create(Path.Combine(directory, "render", "vtk-offscreen.png"))) file.SetLength(WorkspaceFiles.MaxImageBytes + 1L);
current["artifacts"] = new JsonArray(ScientificArtifactFiles.Describe(directory, "render/vtk-offscreen.png"));
Reject(() => ScientificArtifactFiles.ImagePreview(directory, Element(current), "render/vtk-offscreen.png"), "oversized image rejected");
var dataRoot = Path.Combine(directory, "preparation");
var mathRoot = Path.Combine(directory, "Math3D");
var source = Path.Combine(mathRoot, "tests", "assets", "meshes", "basic", "02_cube.obj");
Directory.CreateDirectory(Path.GetDirectoryName(source)!);
File.WriteAllText(source, "cube source fixture");
var sourceHash = ScientificArtifactFiles.Hash(source);
var datasetId = ScientificMath3DPreparation.DatasetIds[1];
ScientificMath3DPreparation.ImportFixture(dataRoot, mathRoot, datasetId);
var manifestPath = Path.Combine(dataRoot, "datasets", "manifest.json");
var manifest = JsonNode.Parse(File.ReadAllText(manifestPath))!;
manifest["entries"]!.AsArray().Add(new JsonObject { ["id"] = "unrelated", ["path"] = "retained.obj" });
File.WriteAllText(manifestPath, manifest.ToJsonString());
ScientificMath3DPreparation.ImportFixture(dataRoot, mathRoot, datasetId);
manifest = JsonNode.Parse(File.ReadAllText(manifestPath))!;
Check(manifest["entries"]!.AsArray().Count == 2 && ScientificArtifactFiles.Hash(source) == sourceHash, "fixture preparation preserves unrelated datasets and source files");
var input = new JsonObject { ["datasetId"] = datasetId, ["path"] = Path.Combine(dataRoot, "datasets", datasetId), ["sha256"] = sourceHash };
var prefix = Path.Combine(directory, "dedicated-cgal");
Check(ScientificMath3DPreparation.FindBaseline(dataRoot, "laptop", prefix, input) == null, "missing validation baseline requires preparation");
var baselineFolder = Path.Combine(dataRoot, "runs", new string('b', 32));
Directory.CreateDirectory(baselineFolder);
File.WriteAllText(Path.Combine(baselineFolder, "validated.obj"), "validated fixture");
var baseline = new JsonObject { ["runId"] = new string('b', 32), ["profileId"] = "laptop", ["runtimeId"] = "cgal-win-conda", ["recipeId"] = "cgal.validate", ["state"] = "succeeded",
    ["diagnostics"] = new JsonArray(), ["inputArtifacts"] = new JsonArray(input.DeepClone()), ["artifacts"] = new JsonArray(ScientificArtifactFiles.Describe(baselineFolder, "validated.obj")),
    ["steps"] = new JsonArray(new JsonObject { ["stage"] = "configure", ["executable"] = Path.Combine(prefix, "Library", "bin", "cmake.exe") }) };
void SaveBaseline() => File.WriteAllText(Path.Combine(baselineFolder, "results.json"), baseline.ToJsonString());
SaveBaseline();
Check(ScientificMath3DPreparation.FindBaseline(dataRoot, "laptop", prefix, input) != null, "matching verified baseline reused");
Check(ScientificMath3DPreparation.FindBaseline(dataRoot, "other-profile", prefix, input) == null, "baseline from another profile not reused");
Check(ScientificMath3DPreparation.FindBaseline(dataRoot, "laptop", prefix + "-changed", input) == null, "baseline from another environment not reused");
var changedInput = (JsonObject)input.DeepClone(); changedInput["sha256"] = new string('0', 64);
Check(ScientificMath3DPreparation.FindBaseline(dataRoot, "laptop", prefix, changedInput) == null, "baseline for a changed input not reused");
File.AppendAllText(Path.Combine(baselineFolder, "validated.obj"), "tampered");
Check(ScientificMath3DPreparation.FindBaseline(dataRoot, "laptop", prefix, input) == null, "changed baseline output forces validation again");
baseline["state"] = "cancelled"; SaveBaseline();
Check(ScientificMath3DPreparation.FindBaseline(dataRoot, "laptop", prefix, input) == null, "cancelled preparation never supplies a baseline");
Reject(() => ScientificMath3DPreparation.ImportFixture(dataRoot, mathRoot, "../unsafe.obj"), "preparation accepts only the registered integration fixtures");
var booleanRequest = new JsonObject { ["inputAId"] = "cube-a.obj", ["inputBId"] = "cube-b.obj", ["operation"] = "difference", ["outputName"] = "result.m3dm", ["scaleB"] = 0.5,
    ["translateB"] = new JsonArray(0, 0, 0) };
Check(ScientificBooleanParameters.Parse(Element(booleanRequest)).ScaleB == 0.5, "Boolean parameters retain operation and placement");
foreach (var invalid in new[] { "../result.m3dm", "operand-a.m3dm", "result.obj", "C:/result.m3dm" })
{
    var invalidOutput = (JsonObject)booleanRequest.DeepClone(); invalidOutput["outputName"] = invalid;
    Reject(() => ScientificBooleanParameters.Parse(Element(invalidOutput)), "unsafe/reserved Boolean output rejected: " + invalid);
}
var invalidScale = (JsonObject)booleanRequest.DeepClone(); invalidScale["scaleB"] = -1;
Reject(() => ScientificBooleanParameters.Parse(Element(invalidScale)), "negative Boolean scale rejected");
var invalidTranslation = (JsonObject)booleanRequest.DeepClone(); invalidTranslation["translateB"] = new JsonArray(0, 0);
Reject(() => ScientificBooleanParameters.Parse(Element(invalidTranslation)), "incomplete Boolean placement rejected");
Console.WriteLine($"{count} checks passed. Fixtures retained at {directory}");
